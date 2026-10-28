#!/usr/bin/env python3
"""Espresso bundle builder v8 — hybrid GF(2) + brute-force approach."""
import struct, lz4.block, zlib

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/espresso_v8.bundle"
TARGET_CRC = 0xdc8b314f

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
    print("Espresso Bundle Builder v8 — Hybrid GF(2) + Brute-Force")
    
    with open(ORIGINAL_BUNDLE, 'rb') as f:
        buf = bytearray(f.read())
    
    original_size = len(buf)
    print(f"Original: {original_size:,} bytes (CRC=0x{zlib.crc32(bytes(buf)) & 0xFFFFFFFF:08x})")
    
    # Parse blocks and find uncompressed blocks
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
    
    pos = bs + blk_cs
    if flags & 0x200: pos = (pos + 15) & ~15
    
    uncomp_blocks = []
    for i, (bd, bc2, bf) in enumerate(blocks):
        if not (bf & 2):
            uncomp_blocks.append((i, pos, bd))
        pos += bc2 if (bf & 2) else bd
    
    print(f"Uncompressed blocks: {len(uncomp_blocks)}")
    
    # Find alignment padding location
    padding_offset = bs + blk_cs
    if flags & 0x200:
        padding_size = ((padding_offset + 15) & ~15) - padding_offset
    else:
        padding_size = 0
    
    print(f"Alignment padding: offset {padding_offset}, size {padding_size} bytes")
    
    # Build Espresso blob and inject into first uncompressed block
    espresso_blob = build_espresso_blob()
    inj_block = uncomp_blocks[0]
    patched = bytearray(buf)
    patched[inj_block[1]:inj_block[1]+len(espresso_blob)] = espresso_blob
    
    print(f"Injected {len(espresso_blob)}-byte blob into block {inj_block[0]}")
    
    # Compute CRC after injection
    current_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
    target_delta = current_crc ^ TARGET_CRC
    
    print(f"CRC after injection: 0x{current_crc:08x}")
    print(f"Target delta: 0x{target_delta:08x}")
    
    if target_delta == 0:
        print("✅ CRC already matches!")
    else:
        # Use last 3 padding bytes for brute-force search (16M combinations)
        # Fix first 6 bytes with GF(2), search last 3
        
        print(f"\nUsing last {min(3, padding_size)} padding bytes for brute-force...")
        
        if padding_size < 3:
            print("⚠️  Not enough padding bytes!")
        else:
            # Pre-compute CRC table and M matrix
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
            
            def byte_to_gf2(b):
                return [(b >> i) & 1 for i in range(8)] + [0] * 24
            
            # Compute CRC state before padding
            pre_crc_state = 0xFFFFFFFF
            for b in patched[:padding_offset]:
                pre_crc_state = (pre_crc_state >> 8) ^ crc_table[(pre_crc_state & 0xFF) ^ b]
            
            # For first 6 bytes, use GF(2) to get close
            # For last 3 bytes, brute-force search
            
            padding_values = [0] * padding_size
            
            print("Fixing first 6 bytes with GF(2)...")
            for i in range(min(6, padding_size)):
                pos_in_file = padding_offset + i
                bytes_after = original_size - pos_in_file - 1
                
                if bytes_after < 200:
                    Wi = mat_pow(M, bytes_after)
                else:
                    Wi = [[1 if j==k else 0 for k in range(32)] for j in range(32)]
                
                orig_val = patched[pos_in_file]
                best_d = 0
                best_reduction = -1
                
                # Target: reduce remaining delta most
                target_gf2 = [(target_delta >> j) & 1 for j in range(32)]
                
                for d in range(256):
                    gf2_d = byte_to_gf2(d)
                    contrib = mat_vec_mul(Wi, gf2_d)
                    
                    new_remaining = [target_gf2[j] ^ contrib[j] for j in range(32)]
                    reduction = sum(target_gf2[j] ^ new_remaining[j] for j in range(32))
                    
                    if reduction > best_reduction:
                        best_reduction = reduction
                        best_d = d
                
                patched[pos_in_file] = (orig_val + best_d) & 0xFF
                padding_values[i] = best_d
                
                # Update target delta (approximate)
                gf2_d = byte_to_gf2(best_d)
                contrib = mat_vec_mul(Wi, gf2_d)
                new_crc_state = pre_crc_state
                for j in range(32):
                    if contrib[j]:
                        new_crc_state ^= (1 << j)
                
                # Recompute target delta based on current state
                test_buf = bytearray(patched)
                for k, val in enumerate(padding_values):
                    test_buf[padding_offset + k] = val
                
                temp_crc = zlib.crc32(bytes(test_buf[:padding_offset])) & 0xFFFFFFFF
                for b in test_buf[padding_offset:padding_offset+i+1]:
                    temp_crc = (temp_crc >> 8) ^ crc_table[(temp_crc & 0xFF) ^ b]
                
                target_delta = (temp_crc ^ TARGET_CRC) & 0xFFFFFFFF
            
            # Now brute-force last 3 bytes (or remaining if < 6)
            start_idx = min(6, padding_size)
            end_idx = padding_size
            
            print(f"Brute-forcing bytes {start_idx} to {end_idx-1}...")
            
            import itertools
            found = False
            
            for combo in itertools.product(range(256), repeat=end_idx - start_idx):
                # Apply combination
                test_buf = bytearray(patched)
                for k, val in enumerate(combo):
                    test_buf[padding_offset + start_idx + k] = val
                
                final_crc = zlib.crc32(bytes(test_buf)) & 0xFFFFFFFF
                
                if final_crc == TARGET_CRC:
                    print(f"✅ Found! Combination: {[hex(v) for v in combo]}")
                    
                    # Apply to patched
                    for k, val in enumerate(combo):
                        patched[padding_offset + start_idx + k] = val
                    
                    found = True
                    break
                
                if len(combo) == end_idx - start_idx and not found:
                    pass  # Continue searching
            
            if not found:
                print("❌ Not found in brute-force search")
    
    # Final verification
    final_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
    
    print(f"\n{'='*60}")
    size_ok = "✅" if len(patched) == original_size else f"+{len(patched)-original_size:,}"
    crc_ok = "✅" if final_crc == TARGET_CRC else "❌"
    print(f"FINAL: size={len(patched):,} ({size_ok}), CRC=0x{final_crc:08x} {crc_ok}, target=0x{TARGET_CRC:08x}")
    
    with open(OUT_BUNDLE, 'wb') as f:
        f.write(bytes(patched))
    print(f"Output: {OUT_BUNDLE}")

if __name__ == '__main__':
    main()
