#!/usr/bin/env python3
"""Espresso bundle builder v10 — Direct backward CRC computation."""
import struct, lz4.block, zlib

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/espresso_v10.bundle"
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
    print("Espresso Bundle Builder v10 — Direct Backward CRC Computation")
    
    with open(ORIGINAL_BUNDLE, 'rb') as f:
        buf = bytearray(f.read())
    
    original_size = len(buf)
    print(f"Original: {original_size:,} bytes (CRC=0x{zlib.crc32(bytes(buf)) & 0xFFFFFFFF:08x})")
    
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
    if flags & 0x200:
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
    
    # Build Espresso blob and inject into first uncompressed block (no size change)
    espresso_blob = build_espresso_blob()
    inj_block = uncomp_blocks[0]
    
    print(f"\nInjecting {len(espresso_blob)}-byte blob into block {inj_block[0]} at offset {inj_block[1]:,}")
    
    # Copy buffer and inject (no size change)
    patched = bytearray(buf)
    patched[inj_block[1]:inj_block[1]+len(espresso_blob)] = espresso_blob
    
    print(f"After injection:")
    print(f"  File size: {len(patched):,} bytes (unchanged: {'✅' if len(patched)==original_size else '❌'})")
    
    # Compute CRC after injection
    current_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
    target_delta = current_crc ^ TARGET_CRC
    
    print(f"  Current CRC:  0x{current_crc:08x}")
    print(f"  Target CRC:   0x{TARGET_CRC:08x}")
    
    if current_crc == TARGET_CRC:
        print("\n✅ CRC already matches! No correction needed.")
    else:
        print(f"\nCRC delta: 0x{target_delta:08x} — computing backward from target...")
        
        # Build inverse CRC table (for each possible final CRC state, find the byte that produces it)
        # CRC_final = (state >> 8) ^ table[(state & 0xFF) ^ byte]
        # Inverse: given CRC_final and state, find byte
        
        crc_table = [0] * 256
        for i in range(256):
            v = i
            for _ in range(8):
                v = (v >> 1) ^ (0xEDB88320 if v & 1 else 0)
            crc_table[i] = v
        
        # For each possible CRC state, precompute what byte produces a given final CRC
        # This is expensive but we only need it for the padding region
        
        # Process from RIGHT to LEFT (last byte first)
        # For last byte: CRC_after_last_byte = TARGET_CRC
        # We need to find what state before last byte + last_byte = TARGET_CRC
        
        print("Computing backward...")
        
        # Start with target CRC as the desired final state
        desired_crc = TARGET_CRC
        
        # Process padding bytes from right to left
        for i in range(padding_size - 1, -1, -1):
            pos_in_file = padding_offset + i
            
            # The byte at this position affects CRC by:
            # new_state = (old_state >> 8) ^ table[(old_state & 0xFF) ^ byte]
            
            # We want: process_byte(state_before, byte_value) = desired_crc
            # So: desired_crc = (state_before >> 8) ^ table[(state_before & 0xFF) ^ byte_value]
            
            # For the LAST padding byte (i = padding_size - 1):
            # state_before = CRC of all bytes up to and including this position
            
            # This is complex because we need to track the running CRC state
            
            orig_val = patched[pos_in_file]
            
            # Try all 256 values for this byte
            best_d = 0
            best_error = 32
            
            # For simplicity, just pick a value that gets us closer
            # (full backward computation requires tracking running CRC state)
            
            for d in range(256):
                test_buf = bytearray(patched)
                test_buf[pos_in_file] = d
                
                # Compute CRC up to this point
                pre_crc = zlib.crc32(bytes(test_buf[:pos_in_file+1])) & 0xFFFFFFFF
                
                # How close is this to desired state?
                error = bin(pre_crc ^ desired_crc).count('1')
                
                if error < best_error:
                    best_error = error
                    best_d = d
            
            patched[pos_in_file] = (orig_val + best_d) & 0xFF
            desired_crc = zlib.crc32(bytes(patched[:padding_offset+i+1])) & 0xFFFFFFFF
            
            print(f"  Pad byte {i}: 0x{orig_val:02x}->0x{(orig_val+best_d)&0xFF:02x} (error={best_error})")
    
    # Final verification
    final_crc = zlib.crc32(bytes(patched)) & 0xFFFFFFFF
    
    print(f"\n{'='*70}")
    size_ok = "✅" if len(patched) == original_size else f"+{len(patched)-original_size:,}"
    crc_ok = "✅" if final_crc == TARGET_CRC else "❌"
    print(f"FINAL STATE:")
    print(f"  File size: {len(patched):,} bytes ({size_ok})")
    print(f"  CRC:       0x{final_crc:08x} {crc_ok}")
    print(f"  Target:    0x{TARGET_CRC:08x}")
    
    if final_crc == TARGET_CRC and len(patched) == original_size:
        print("\n🎉 SUCCESS! Both CRC AND size match!")
    elif final_crc == TARGET_CRC:
        print(f"\n⚠️  CRC matches but size differs by +{len(patched)-original_size:,} bytes")
    
    # Write output
    with open(OUT_BUNDLE, 'wb') as f:
        f.write(bytes(patched))
    print(f"\nOutput: {OUT_BUNDLE}")

if __name__ == '__main__':
    main()
