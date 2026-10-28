#!/usr/bin/env python3
"""
Build Espresso pack bundle using UNCOMPRESSED BLOCKS for CRC control.

Key insight: 49 uncompressed blocks (flag=0) are stored as raw data with FIXED sizes.
- Block 16 at offset 1,488,727 (131,072 bytes): overlay BeatmapLevelSO blob here
- Remaining 48 blocks: use GF(2) linear algebra to fix CRC without changing file_size

Target CRC: 0xdc8b314f (from Addressables catalog)
Target size: 7,902,803 bytes (identical to original)
"""

import struct, lz4.block, zlib

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/espresso_pack_patched.bundle"
TARGET_CRC = 0xdc8b314f

# ── BeatmapLevelSO blob builder (Espresso with 5 modes) ────────────────
SCRIPT_PATHID_CORRECT = 2140275054477726686  # MonoScript, NOT BeatmapCharacteristicSO!
CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
    "360Degree":  1189643819550092755,
}

def encode_utf8_string(s):
    if not s:
        return b'\x00\x00'
    data = s.encode('utf-8')
    return struct.pack('<i', len(data)) + data + b'\x00'

def build_espresso_blob():
    """Build BeatmapLevelSO blob with 5 modes for Espresso."""
    b = bytearray()
    b += struct.pack('<i', 0)                                      # m_GameObject fileID
    b += struct.pack('<q', 0)                                      # m_GameObject pathID
    b += struct.pack('<I', 1)                                      # class/metadata
    b += struct.pack('<i', 1)                                      # m_Script fileID = 1
    b += struct.pack('<q', SCRIPT_PATHID_CORRECT)                  # MonoScript pathID
    
    b.extend(encode_utf8_string("EspressoCustomBeatmapLevel"))      # m_Name
    b.append(0x78); b.append(1); b.append(1)                       # _version
    
    b.extend(encode_utf8_string("custom/espresso"))                 # _levelID
    b.extend(encode_utf8_string("Espresso"))                        # _songName
    b.extend(b'\x00\x00')                                          # _songSubName
    b.extend(encode_utf8_string("Sabrina Carpenter"))               # _songAuthorName
    b.extend(encode_utf8_string("Sabrina Carpenter"))               # _levelAuthorName
    
    b += struct.pack('<i', 0) + struct.pack('<q', 0)               # _previewAudioClip (zeroed)
    for val in [126.5, -8.2, 0.0, 0.0, 0.0, 138.0, 10.0, 213.7]:
        b += struct.pack('<d', val)
    b += struct.pack('<i', 0) + struct.pack('<q', 0)               # _coverImage (zeroed)
    
    b.extend(encode_utf8_string(""))
    b.extend(encode_utf8_string(""))
    b += struct.pack('<i', 1)
    b.extend(encode_utf8_string("TheRollingStonesEnvironment"))
    b += struct.pack('<i', 0)
    
    # 5 modes: Standard, OneSaber, NoArrows, 90Degree, 360Degree
    b += struct.pack('<i', 5)
    for mode in ["Standard", "OneSaber", "NoArrows", "90Degree", "360Degree"]:
        b += struct.pack('<i', 3)                                   # fileID = 3 (external)
        b += struct.pack('<q', CHAR_PATH_IDS[mode])                 # pathID
        b += struct.pack('<i', 5)                                   # diff_count = 5
        b += b'\x00' * (5 * 36)                                    # zeroed diffs
    
    return bytes(b)

def main():
    print("=" * 70)
    print("Espresso Pack Bundle Builder — Uncompressed Block CRC Control")
    print("=" * 70)
    
    with open(ORIGINAL_BUNDLE, 'rb') as f:
        buf = bytearray(f.read())
    
    original_size = len(buf)
    print(f"Original bundle: {original_size:,} bytes")
    
    # Parse blocks info to find uncompressed blocks
    blk_cs = struct.unpack('>I', buf[38:42])[0]
    blk_ds = struct.unpack('>I', buf[42:46])[0]
    flags = struct.unpack('>I', buf[46:50])[0]
    
    bs = (50 + 15) & ~15
    info = lz4.block.decompress(bytes(buf[bs:bs+blk_cs]), uncompressed_size=blk_ds)
    
    r = 16
    bc = struct.unpack('>I', info[r:r+4])[0]; r += 4
    
    blocks = []
    for _ in range(bc):
        bd = struct.unpack('>I', info[r:r+4])[0]; r += 4
        bc2 = struct.unpack('>I', info[r:r+4])[0]; r += 4
        bf = struct.unpack('>H', info[r:r+2])[0]; r += 2
        blocks.append((bd, bc2, bf))
    
    # Find uncompressed block positions
    pos = bs + blk_cs
    if flags & 0x200:
        pos = (pos + 15) & ~15
    
    uncomp_blocks = []
    for i, (bd, bc2, bf) in enumerate(blocks):
        if not (bf & 2):  # uncompressed
            uncomp_blocks.append((i, pos, bd))
        
        if bf & 2:
            pos += bc2
        else:
            pos += bd
    
    print(f"Found {len(uncomp_blocks)} uncompressed blocks ({sum(s for _,_,s in uncomp_blocks):,} bytes)")
    
    # Build Espresso blob
    espresso_blob = build_espresso_blob()
    print(f"\nEspresso BeatmapLevelSO blob: {len(espresso_blob)} bytes")
    
    # Overlay into first uncompressed block (block 16)
    injection_block = uncomp_blocks[0]
    inj_offset = injection_block[1]
    inj_size = injection_block[2]
    
    print(f"Injecting at offset {inj_offset:,} (block {injection_block[0]}, size {inj_size:,})")
    
    # Copy buffer to avoid modifying original
    patched = bytearray(buf)
    patched[inj_offset:inj_offset + len(espresso_blob)] = espresso_blob
    
    print(f"After injection:")
    print(f"  File size: {len(patched):,} bytes (unchanged: {'✅' if len(patched)==original_size else '❌'})")
    
    # Compute current CRC
    current_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
    print(f"  Current CRC:  0x{current_crc:08x}")
    print(f"  Target CRC:   0x{TARGET_CRC:08x}")
    
    if current_crc == TARGET_CRC:
        print("\n✅ CRC already matches! No correction needed.")
    else:
        delta = current_crc ^ TARGET_CRC
        print(f"  CRC delta:    0x{delta:08x} — applying GF(2) correction...")
        
        # Use remaining uncompressed blocks (skip injection block) for CRC control
        free_blocks = uncomp_blocks[1:]  # Skip first block (injection site)
        print(f"Using {len(free_blocks)} remaining uncompressed blocks for CRC correction")
        
        # Build CRC-32 table and M matrix over GF(2)
        crc_table = [0] * 256
        for i in range(256):
            v = i
            for _ in range(8):
                v = (v >> 1) ^ (0xEDB88320 if v & 1 else 0)
            crc_table[i] = v
        
        # M matrix: CRC state transformation for 1 zero byte
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
        
        # For each free block, compute weight matrix based on position
        # Weight depends on bytes_after = original_size - (block_start + offset_in_block) - 1
        
        print("\nComputing GF(2) corrections...")
        
        current_delta = delta
        corrections = {}
        
        # Process blocks from right to left (smallest L first for numerical stability)
        free_blocks_sorted = sorted(free_blocks, key=lambda x: original_size - x[1], reverse=True)
        
        for block in free_blocks_sorted:
            if current_delta == 0:
                break
            
            block_idx, start, size = block
            
            best_correction = None
            best_reduction = 0
            
            # Try a sample of byte positions (every 256 bytes for speed)
            for offset_in_block in range(0, size, 256):
                pos_in_file = start + offset_in_block
                bytes_after = original_size - pos_in_file - 1
                
                if bytes_after == 0:
                    Mk = [[1 if i==j else 0 for j in range(32)] for i in range(32)]
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
                    
                    reduction = bin(current_delta & contrib_int).count('1')
                    
                    if reduction > best_reduction:
                        best_reduction = reduction
                        best_correction = (offset_in_block, d)
            
            if best_reduction == 0:
                continue
            
            offset_in_block, delta_byte = best_correction
            pos_in_file = start + offset_in_block
            orig_val = patched[pos_in_file]
            new_val = orig_val ^ delta_byte
            
            corrections[(block_idx, offset_in_block)] = new_val
            
            # Apply correction immediately to track progress
            patched[pos_in_file] = new_val
            
            # Update current_delta (approximate)
            bytes_after = original_size - pos_in_file - 1
            if bytes_after == 0:
                Mk = [[1 if i==j else 0 for j in range(32)] for i in range(32)]
            elif bytes_after < 1000:
                Mk = mat_pow(M, bytes_after)
            else:
                Mk = [[1 if i==j else 0 for j in range(32)] for i in range(32)]
            
            gf2_d = [(delta_byte >> i) & 1 for i in range(8)] + [0] * 24
            contrib = mat_vec_mul(Mk, gf2_d)
            contrib_int = sum(contrib[i] << i for i in range(32))
            current_delta ^= contrib_int
            
            print(f"  Block {block_idx}, offset {offset_in_block}: 0x{orig_val:02x} -> 0x{new_val:02x} (reduced {best_reduction} bits)")
        
        # Verify final CRC
        final_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
        
        if final_crc == TARGET_CRC:
            print(f"\n✅ CRC MATCHES! 0x{final_crc:08x}")
        else:
            remaining_delta = final_crc ^ TARGET_CRC
            print(f"\n⚠️ CRC mismatch. Remaining delta: 0x{remaining_delta:08x}")
            
            # Try greedy single-byte search if needed
            print("Trying additional single-byte corrections...")
            for block in free_blocks_sorted:
                if zlib.crc32(bytes(patched)) & 0xFFFFFFFF == TARGET_CRC:
                    break
                
                block_idx, start, size = block
                
                for offset_in_block in range(0, size, 16):
                    pos_in_file = start + offset_in_block
                    
                    orig_val = patched[pos_in_file]
                    
                    found = False
                    for d in range(256):
                        test_buf = bytearray(patched)
                        test_buf[pos_in_file] = (orig_val + d) & 0xFF
                        
                        if zlib.crc32(bytes(test_buf)) & 0xFFFFFFFF == TARGET_CRC:
                            patched[pos_in_file] = (orig_val + d) & 0xFF
                            print(f"  Found! Block {block_idx}, offset {offset_in_block}: 0x{orig_val:02x} -> 0x{(orig_val+d)&0xFF:02x}")
                            found = True
                            break
                    
                    if found:
                        break
    
    # Verify final state
    final_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
    print(f"\n{'='*70}")
    print(f"FINAL STATE:")
    print(f"  File size: {len(patched):,} bytes (original: {original_size:,})")
    print(f"  Size diff: {'✅ ZERO' if len(patched)==original_size else f'+{len(patched)-original_size:,}'}")
    print(f"  CRC:       0x{final_crc:08x}")
    print(f"  Target:    0x{TARGET_CRC:08x}")
    print(f"  CRC match: {'✅ YES' if final_crc == TARGET_CRC else '❌ NO'}")
    
    # Write output
    with open(OUT_BUNDLE, 'wb') as f:
        f.write(bytes(patched))
    
    print(f"\n✅ Output: {OUT_BUNDLE}")
    print(f"   Size: {len(patched):,} bytes")
    print(f"   CRC: 0x{final_crc:08x}")

if __name__ == '__main__':
    main()
