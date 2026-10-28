#!/usr/bin/env python3
"""Espresso bundle builder v4 — use end-of-block positions for CRC correction."""
import struct, lz4.block, zlib

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/espresso_pack_patched.bundle"
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
    print("Espresso Bundle Builder v4 — End-of-Block CRC Correction")
    
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
        # Use end-of-block positions from remaining uncompressed blocks (5-10 bytes before end)
        free_blocks = uncomp_blocks[1:]
        
        # Pick correction positions: last 16 bytes of each of the last 8 blocks
        correction_positions = []
        for block in reversed(free_blocks[:8]):
            block_idx, start, size = block
            # Use positions near end (bytes_after < 20)
            for offset_in_block in range(size - 16, size):
                if offset_in_block >= 0:
                    correction_positions.append((block_idx, start + offset_in_block))
        
        print(f"\nUsing {len(correction_positions)} correction positions (last 16 bytes of last 8 blocks)...")
        
        # Greedy search with CRC verification
        current_delta = target_delta
        
        for block_idx, pos_in_file in correction_positions:
            if current_delta == 0:
                break
            
            orig_val = patched[pos_in_file]
            
            # Try all 256 byte values and pick the one that reduces delta most
            best_d = 0
            best_reduction = -1
            best_new_crc = None
            
            for d in range(256):
                test_buf = bytearray(patched)
                test_buf[pos_in_file] = (orig_val + d) & 0xFF
                
                test_crc = zlib.crc32(bytes(test_buf)) & 0xFFFFFFFF
                new_delta = test_crc ^ TARGET_CRC
                
                # Count bits reduced in delta
                reduction = bin(current_delta ^ new_delta).count('1')
                
                if reduction > best_reduction:
                    best_reduction = reduction
                    best_d = d
                    best_new_crc = test_crc
            
            # Apply correction
            patched[pos_in_file] = (orig_val + best_d) & 0xFF
            current_delta = best_new_crc ^ TARGET_CRC
            
            print(f"  Pos {pos_in_file:,}: reduced {best_reduction} bits, remaining=0x{current_delta:08x}")
    
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
