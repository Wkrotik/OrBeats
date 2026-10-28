#!/usr/bin/env python3
"""
Final Espresso bundle builder using uncompressed blocks + GF(2) CRC correction.

Strategy:
1. Inject Espresso BeatmapLevelSO blob into first uncompressed block (no size change)
2. Use GF(2) linear algebra on 9 alignment padding bytes at offset 263 for CRC correction
3. File_size stays at exactly 7,902,803 bytes (matches catalog)

Target: CRC=0xdc8b314f, Size=7,902,803 bytes
"""

import struct, lz4.block, zlib

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/espresso_uncompressed_final.bundle"
TARGET_CRC = 0xdc8b314f
ORIGINAL_SIZE = 7902803

SCRIPT_PATHID_CORRECT = 2140275054477726686
CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
    "360Degree":  1189643819550092755,
}

def encode_utf8_string(s):
    if not s: return b'\x00\x00'
    data = s.encode('utf-8')
    return struct.pack('<i', len(data)) + data + b'\x00'

def build_espresso_blob():
    """Build BeatmapLevelSO blob with 5 modes for Espresso."""
    b = bytearray()
    b += struct.pack('<i', 0) + struct.pack('<q', 0) + struct.pack('<I', 1)
    b += struct.pack('<i', 1) + struct.pack('<q', SCRIPT_PATHID_CORRECT)
    b.extend(encode_utf8_string("EspressoCustomBeatmapLevel"))
    b.append(0x78); b.append(1); b.append(1)
    b.extend(encode_utf8_string("custom/espresso"))
    b.extend(encode_utf8_string("Espresso"))
    b.extend(b'\x00\x00')
    b.extend(encode_utf8_string("Sabrina Carpenter"))
    b.extend(encode_utf8_string("Sabrina Carpenter"))
    b += struct.pack('<i', 0) + struct.pack('<q', 0)
    for val in [126.5, -8.2, 0.0, 0.0, 0.0, 138.0, 10.0, 213.7]:
        b += struct.pack('<d', val)
    b += struct.pack('<i', 0) + struct.pack('<q', 0)
    b.extend(encode_utf8_string(""))
    b.extend(encode_utf8_string(""))
    b += struct.pack('<i', 1)
    b.extend(encode_utf8_string("TheRollingStonesEnvironment"))
    b += struct.pack('<i', 0)
    b += struct.pack('<i', 5)
    for mode in ["Standard", "OneSaber", "NoArrows", "90Degree", "360Degree"]:
        b += struct.pack('<i', 3) + struct.pack('<q', CHAR_PATH_IDS[mode])
        b += struct.pack('<i', 5) + b'\x00' * (5 * 36)
    return bytes(b)

def main():
    print("Espresso Bundle Builder — Uncompressed Block Injection")
    print("=" * 70)
    
    with open(ORIGINAL_BUNDLE, 'rb') as f:
        buf = bytearray(f.read())
    
    print(f"Original bundle: {len(buf):,} bytes (CRC=0x{zlib.crc32(bytes(buf)) & 0xFFFFFFFF:08x})")
    
    # Parse blocks info to find uncompressed blocks and alignment padding
    blk_cs = struct.unpack('>I', buf[38:42])[0]
    blk_ds = struct.unpack('>I', buf[42:46])[0]
    flags = struct.unpack('>I', buf[46:50])[0]
    
    bs = (50 + 15) & ~15
    info = lz4.block.decompress(bytes(buf[bs:bs+blk_cs]), uncompressed_size=blk_ds)
    
    r = 16; bc = struct.unpack('>I', info[r:r+4])[0]; r += 4
    blocks = []
    for _ in range(bc):
        bd = struct.unpack('>I', info[r:r+4])[0]; r += 4
        bc2 = struct.unpack('>I', info[r:r+4])[0]; r += 4
        bf = struct.unpack('>H', info[r:r+2])[0]; r += 2
        blocks.append((bd, bc2, bf))
    
    # Find uncompressed block positions in file
    pos = bs + blk_cs
    if flags & 0x200:  # BlockInfoNeedPaddingAtStart
        pos = (pos + 15) & ~15
    
    uncomp_blocks = []
    for i, (bd, bc2, bf) in enumerate(blocks):
        if not (bf & 2):  # uncompressed
            uncomp_blocks.append((i, pos, bd))
        
        # Move to next block
        if bf & 2:
            pos += bc2
        else:
            pos += bd
    
    print(f"Found {len(uncomp_blocks)} uncompressed blocks")
    
    # Find alignment padding location
    raw_data_start = bs + blk_cs
    if flags & 0x200:
        raw_data_start = (raw_data_start + 15) & ~15
    
    padding_offset = bs + blk_cs
    padding_size = raw_data_start - padding_offset
    print(f"Alignment padding: offset {padding_offset}, size {padding_size} bytes")
    
    # Build Espresso blob and inject into first uncompressed block
    espresso_blob = build_espresso_blob()
    inj_block = uncomp_blocks[0]
    
    print(f"\nInjecting {len(espresso_blob)}-byte blob into block {inj_block[0]} at offset {inj_block[1]:,}")
    
    # Copy buffer and inject (no size change)
    patched = bytearray(buf)
    patched[inj_block[1]:inj_block[1]+len(espresso_blob)] = espresso_blob
    
    print(f"After injection:")
    print(f"  File size: {len(patched):,} bytes (unchanged: {'✅' if len(patched)==ORIGINAL_SIZE else '❌'})")
    
    # Compute CRC after injection
    current_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
    target_delta = current_crc ^ TARGET_CRC
    
    print(f"  Current CRC:  0x{current_crc:08x}")
    print(f"  Target CRC:   0x{TARGET_CRC:08x}")
    
    if current_crc == TARGET_CRC:
        print("\n✅ CRC already matches! No correction needed.")
    else:
        print(f"\nCRC delta: 0x{target_delta:08x} — applying GF(2) linear algebra correction...")
        
        # Build CRC table and M matrix over GF(2)
        crc_table = [0] * 256
        for i in range(256):
            v = i
            for _ in range(8):
                v = (v >> 1) ^ (0xEDB88320 if v & 1 else 0)
            crc_table[i] = v
        
        M = [[0]*32 for _ in range(32)]
        for col in range(32):
            state = 1 << col
            state = (state >> 8) ^ crc_table[state & 0xFF]
            for row in range(32):
                if state & (1 << row):
                    M[row][col] = 1
        
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
        
        # Compute CRC state before padding (state after processing all bytes up to padding_start)
        pre_crc_state = 0xFFFFFFFF
        for b in patched[:padding_offset]:
            pre_crc_state = (pre_crc_state >> 8) ^ crc_table[(pre_crc_state & 0xFF) ^ b]
        
        # For each padding byte at position (padding_offset + i):
        # contribution = M^(bytes_after_i) * table[byte_i] (over GF(2))
        # where bytes_after_i = ORIGINAL_SIZE - (padding_offset + i) - 1
        
        print("Computing GF(2) weight matrices...")
        
        target_gf2 = [(target_delta >> j) & 1 for j in range(32)]
        padding_values = [0] * padding_size
        
        # Process from right to left (smallest L first for stability)
        current_remaining = target_gf2[:]
        
        for i in range(padding_size - 1, -1, -1):
            if all(b == 0 for b in current_remaining):
                break
            
            pos_in_file = padding_offset + i
            bytes_after = ORIGINAL_SIZE - pos_in_file - 1
            
            # Compute weight matrix W_i = M^bytes_after
            if bytes_after < 200:
                Wi = mat_pow(M, bytes_after)
            else:
                # For large exponents, use binary representation
                Wi = [[1 if j==k else 0 for k in range(32)] for j in range(32)]
                bit = 0
                temp_exp = bytes_after
                while temp_exp:
                    if temp_exp & 1:
                        Wi = mat_mul(Wi, mat_pow(M, 1 << bit))
                    temp_exp >>= 1
                    bit += 1
            
            # Try all 256 byte values and pick the one that reduces current_remaining most
            best_d = 0
            best_reduction = -1
            
            for d in range(256):
                gf2_d = [(d >> j) & 1 for j in range(8)] + [0] * 24
                contrib = mat_vec_mul(Wi, gf2_d)
                
                new_remaining = [current_remaining[j] ^ contrib[j] for j in range(32)]
                reduction = sum(current_remaining[j] ^ new_remaining[j] for j in range(32))
                
                if reduction > best_reduction:
                    best_reduction = reduction
                    best_d = d
            
            padding_values[i] = best_d
            
            # Update remaining (approximate)
            gf2_d = [(best_d >> j) & 1 for j in range(8)] + [0] * 24
            contrib = mat_vec_mul(Wi, gf2_d)
            current_remaining = [current_remaining[j] ^ contrib[j] for j in range(32)]
            
            if (padding_size - i) % 3 == 0:
                print(f"  Progress: {padding_size - i}/{padding_size} bytes solved")
        
        # Apply padding values
        for i, val in enumerate(padding_values):
            patched[padding_offset + i] = val
        
        print("Padding values applied.")
    
    # Final verification
    final_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
    
    print(f"\n{'='*70}")
    size_ok = "✅" if len(patched) == ORIGINAL_SIZE else f"+{len(patched)-ORIGINAL_SIZE:,}"
    crc_ok = "✅" if final_crc == TARGET_CRC else "❌"
    print(f"FINAL STATE:")
    print(f"  File size: {len(patched):,} bytes ({size_ok})")
    print(f"  CRC:       0x{final_crc:08x} {crc_ok}")
    print(f"  Target:    0x{TARGET_CRC:08x}")
    
    if final_crc == TARGET_CRC and len(patched) == ORIGINAL_SIZE:
        print("\n🎉 SUCCESS! Both CRC AND size match!")
    elif final_crc == TARGET_CRC:
        print(f"\n⚠️  CRC matches but size differs by +{len(patched)-ORIGINAL_SIZE:,} bytes")
    
    # Write output
    with open(OUT_BUNDLE, 'wb') as f:
        f.write(bytes(patched))
    print(f"\nOutput: {OUT_BUNDLE}")

if __name__ == '__main__':
    main()
