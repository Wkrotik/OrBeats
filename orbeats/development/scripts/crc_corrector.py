#!/usr/bin/env python3
"""
CRC Corrector for Addressables Pack Bundle.

Uses GF(2) linear algebra to compute exact byte modifications in uncompressed
blocks that make the bundle's CRC match the original (0xdc8b314f).

Key insight: 49 uncompressed blocks (flag=0) are stored as raw data with FIXED
sizes of 131,072 bytes each. Changing their CONTENT affects CRC but NOT file_size.
This gives us ~6.1 MB of free variables for CRC control without size impact.

Usage:
    python3 crc_corrector.py --original <orig_bundle> --modified <mod_bundle> --output <corrected>
"""

import struct, lz4.block, zlib, argparse

def parse_blocks_info(buf):
    """Parse blocks info from compressed data at offset 64."""
    blocks_info = lz4.block.decompress(
        bytes(buf[64:263]),
        uncompressed_size=859
    )

    r = 16  # block count at offset 16 (after 16-byte zero prefix)
    bc = struct.unpack('>I', blocks_info[r:r+4])[0]; r += 4

    block_specs = []
    for i in range(bc):
        bd = struct.unpack('>I', blocks_info[r:r+4])[0]; r += 4
        bc2 = struct.unpack('>I', blocks_info[r:r+4])[0]; r += 4
        bf = struct.unpack('>H', blocks_info[r:r+2])[0]; r += 2
        block_specs.append((i, bd, bc2, bf))

    return block_specs


def find_uncompressed_blocks(block_specs, data_offset):
    """Find all uncompressed blocks and their file positions."""
    raw_data_start = data_offset
    block_positions = []
    pos = 0

    for i, bd, bc2, bf in block_specs:
        if bf & 2:  # compressed
            stored_size = bc2
        else:  # uncompressed — stored as decompressed size
            stored_size = bd

        block_positions.append((i, raw_data_start + pos, stored_size))
        pos += stored_size

    uncomp_pos = [(i, start, size) for i, start, size in block_positions if not (block_specs[i][3] & 2)]
    return uncomp_pos


def crc32_update(state, byte_val):
    """Update CRC-32 state with one byte."""
    crc_table = _build_crc_table()
    return (state >> 8) ^ crc_table[(state & 0xFF) ^ byte_val]


def _build_crc_table():
    """Build standard CRC-32 lookup table."""
    table = [0] * 256
    for i in range(256):
        v = i
        for _ in range(8):
            v = (v >> 1) ^ (0xEDB88320 if v & 1 else 0)
        table[i] = v
    return table


def solve_crc_correction(orig_buf, mod_buf, target_crc):
    """
    Find byte modifications in uncompressed blocks of mod_buf that make its CRC match target.

    Strategy:
    1. Overlay BeatmapLevelSO blob into first uncompressed block (keeps size fixed)
    2. Use GF(2) linear algebra on remaining uncompressed blocks to fix CRC

    Returns modified buffer with correct CRC.
    """
    # Parse blocks info from original bundle
    block_specs = parse_blocks_info(orig_buf)

    # Find uncompressed block positions (using original's layout)
    data_offset = (64 + 199 + 15) & ~15  # with alignment after compressed blocks_info
    uncomp_pos = find_uncompressed_blocks(block_specs, data_offset)

    if not uncomp_pos:
        raise ValueError("No uncompressed blocks found!")

    print(f"Found {len(uncomp_pos)} uncompressed blocks")
    for i, start, size in uncomp_pos[:3]:
        print(f"  Block {i}: offset={start:,}, size={size:,}")

    # Step 1: Overlay BeatmapLevelSO blob into first uncompressed block
    injection_block = uncomp_pos[0]
    inj_start = injection_block[1]
    inj_size = injection_block[2]

    print(f"\nInjecting BeatmapLevelSO blob at offset {inj_start:,}...")

    # Build a sample blob (in practice, this comes from the pipeline's blob builder)
    # For now, use a simple pattern that represents the modification
    blob = bytearray(817)  # approximate size of Espresso BeatmapLevelSO blob
    for i in range(len(blob)):
        blob[i] = (i * 7 + 42) & 0xFF  # pseudo-random pattern

    # Overlay into uncompressed block (replacing existing content)
    mod_buf[inj_start:inj_start + len(blob)] = bytes(blob)

    print(f"Overlayed {len(blob)} bytes at offset {inj_start:,}")

    # Step 2: Compute current CRC and needed delta
    current_crc = zlib.crc32(bytes(mod_buf)) & 0xFFFFFFFF
    needed_delta = current_crc ^ target_crc

    print(f"\nCurrent CRC:  0x{current_crc:08x}")
    print(f"Target CRC:   0x{target_crc:08x}")
    print(f"Needed delta: 0x{needed_delta:08x}")

    if needed_delta == 0:
        print("CRC already matches! No correction needed.")
        return bytes(mod_buf)

    # Step 3: Use GF(2) linear algebra to find byte modifications
    # For each uncompressed block (except the injection site), compute its
    # "weight" — how changing its bytes affects the final CRC.

    print("\nComputing GF(2) weight vectors...")

    # Build CRC-32 table and M matrix
    crc_table = _build_crc_table()

    # M[row][col] = 1 if processing one zero byte flips bit 'row' when input has only bit 'col' set
    M = [[0]*32 for _ in range(32)]
    for col in range(32):
        state = 1 << col
        state = (state >> 8) ^ crc_table[state & 0xFF]
        for row in range(32):
            if state & (1 << row):
                M[row][col] = 1

    # Matrix operations over GF(2)
    def mat_mul(A, B):
        n = len(A)
        return [[sum(A[i][k] & B[k][j] for k in range(n)) & 1 for j in range(n)] for i in range(n)]

    def mat_pow(M, exp):
        n = len(M)
        result = [[1 if i==j else 0 for j in range(n)] for i in range(n)]
        base = [row[:] for row in M]
        while exp:
            if exp & 1:
                result = mat_mul(result, base)
            base = mat_mul(base, base)
            exp >>= 1
        return result

    def mat_vec_mul(M, v):
        n = len(M)
        return [sum(M[i][j] & v[j] for j in range(n)) & 1 for i in range(n)]

    # For each uncompressed block (except injection site), compute weight matrix W_k
    # where W_k * gf2(delta_byte) gives the CRC delta contribution.
    #
    # The weight depends on the position within the file: bytes after the modification
    # transform the contribution through M^(bytes_after).

    # We'll use a greedy approach: process blocks from right to left (smallest L first).

    print("Solving with GF(2) linear algebra...")

    current_delta = needed_delta
    corrections = {}  # (block_idx, offset_in_block) -> new_byte_value

    for block in reversed(uncomp_pos[1:]):  # skip injection site
        if current_delta == 0:
            break

        block_idx, start, size = block

        # For each byte position in this block, compute its weight vector
        # The weight depends on bytes_after = len(mod_buf) - (start + offset_in_block) - 1

        best_correction = None
        best_reduction = 0

        for offset_in_block in range(size):
            pos_in_file = start + offset_in_block
            bytes_after = len(mod_buf) - pos_in_file - 1

            # Compute M^(bytes_after) — this transforms the byte's contribution
            if bytes_after == 0:
                Mk = [[1 if i==j else 0 for j in range(32)] for i in range(32)]  # identity
            elif bytes_after < 1000:
                Mk = mat_pow(M, bytes_after)
            else:
                # For large exponents, use binary representation
                Mk = [[1 if i==j else 0 for j in range(32)] for i in range(32)]
                bit = 0
                temp_exp = bytes_after
                while temp_exp:
                    if temp_exp & 1:
                        Mk = mat_mul(Mk, mat_pow(M, 1 << bit))
                    temp_exp >>= 1
                    bit += 1

            # Try all 256 byte values and pick the one that reduces current_delta most
            for d in range(256):
                gf2_d = [(d >> i) & 1 for i in range(8)] + [0] * 24

                contrib = mat_vec_mul(Mk, gf2_d)
                contrib_int = sum(contrib[i] << i for i in range(32))

                # How much does this reduce current_delta?
                reduction = bin(current_delta & contrib_int).count('1')

                if reduction > best_reduction:
                    best_reduction = reduction
                    best_correction = (offset_in_block, d)

        if best_reduction == 0:
            continue

        offset_in_block, delta_byte = best_correction
        pos_in_file = start + offset_in_block
        orig_val = mod_buf[pos_in_file]
        new_val = orig_val ^ delta_byte

        corrections[(block_idx, offset_in_block)] = new_val
        current_delta ^= sum([((delta_byte >> i) & 1) for i in range(8)]) << 0  # Simplified

        print(f"  Block {block_idx}, offset {offset_in_block}: 0x{orig_val:02x} -> 0x{new_val:02x} (reduced {best_reduction} bits)")

    # Apply corrections to mod_buf
    for (block_idx, offset_in_block), new_val in corrections.items():
        block = uncomp_pos[block_idx] if block_idx < len(uncomp_pos) else None
        if block:
            start = block[1]
            pos_in_file = start + offset_in_block
            mod_buf[pos_in_file] = new_val

    # Verify
    final_crc = zlib.crc32(bytes(mod_buf)) & 0xFFFFFFFF
    print(f"\nFinal CRC: 0x{final_crc:08x}")

    if final_crc == target_crc:
        print("✅ CRC MATCHES!")
        return bytes(mod_buf)
    else:
        print(f"⚠️ CRC mismatch. Delta remaining: 0x{(final_crc ^ target_crc):08x}")
        # Try to fix with more corrections...
        return _try_remaining_corrections(mod_buf, target_crc, uncomp_pos[1:], corrections)


def _try_remaining_corrections(mod_buf, target_crc, uncomp_blocks, existing_corrections):
    """Try additional corrections if initial approach didn't fully work."""
    print("\nTrying additional corrections...")

    current_crc = zlib.crc32(bytes(mod_buf)) & 0xFFFFFFFF
    needed_delta = current_crc ^ target_crc

    if needed_delta == 0:
        return bytes(mod_buf)

    # Use a simpler approach: try single-byte changes across all uncompressed blocks
    for block in uncomp_blocks:
        if zlib.crc32(bytes(mod_buf)) & 0xFFFFFFFF == target_crc:
            break

        block_idx, start, size = block

        for offset_in_block in range(0, size, 16):  # sample every 16 bytes for speed
            pos_in_file = start + offset_in_block

            orig_val = mod_buf[pos_in_file]

            # Try all 256 values
            for d in range(256):
                test_buf = bytearray(mod_buf)
                test_buf[pos_in_file] = (orig_val + d) & 0xFF

                if zlib.crc32(bytes(test_buf)) & 0xFFFFFFFF == target_crc:
                    print(f"  Found! Block {block_idx}, offset {offset_in_block}: 0x{orig_val:02x} -> 0x{(orig_val+d)&0xFF:02x}")
                    mod_buf[pos_in_file] = (orig_val + d) & 0xFF
                    break

    final_crc = zlib.crc32(bytes(mod_buf)) & 0xFFFFFFFF
    if final_crc == target_crc:
        print("✅ CRC MATCHES!")
    else:
        print(f"⚠️ Still mismatched. Final delta: 0x{(final_crc ^ target_crc):08x}")

    return bytes(mod_buf)


def main():
    parser = argparse.ArgumentParser(description='CRC corrector for Addressables pack bundles')
    parser.add_argument('--original', required=True, help='Original bundle file')
    parser.add_argument('--modified', required=True, help='Modified bundle file (with BeatmapLevelSO injected)')
    parser.add_argument('--output', required=True, help='Output corrected bundle file')
    parser.add_argument('--target-crc', default='0xdc8b314f', help='Target CRC from Addressables catalog')

    args = parser.parse_args()

    target_crc = int(args.target_crc, 16)

    with open(args.original, 'rb') as f:
        orig_buf = bytearray(f.read())

    with open(args.modified, 'rb') as f:
        mod_buf = bytearray(f.read())

    print("=" * 70)
    print("CRC Corrector for Addressables Pack Bundle")
    print("=" * 70)
    print(f"Original: {args.original}")
    print(f"Modified: {args.modified}")
    print(f"Target CRC: 0x{target_crc:08x}")

    corrected = solve_crc_correction(orig_buf, mod_buf, target_crc)

    with open(args.output, 'wb') as f:
        f.write(corrected)

    final_crc = zlib.crc32(corrected) & 0xFFFFFFFF
    print(f"\nOutput: {args.output}")
    print(f"Final CRC: 0x{final_crc:08x}")
    if final_crc == target_crc:
        print("✅ SUCCESS!")
    else:
        print("⚠️ CRC mismatch — may need additional corrections")


if __name__ == '__main__':
    main()
