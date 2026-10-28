#!/usr/bin/env python3
"""
Espresso pack bundle builder — final version.

Injects Espresso BeatmapLevelSO blob into correct location in decompressed stream,
then rebuilds bundle with LZ4HC compression and GF(2) CRC correction on alignment padding.

Key: Inject at offset 72,620 in decompressed stream (where original BeatmapLevelSO lives).
"""

import struct, lz4.block, zlib

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/espresso_final_v2.bundle"
TARGET_CRC = 0xdc8b314f
INJECTION_OFFSET_DEC = 72620  # Where BeatmapLevelSO lives in decompressed stream

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
    print("Espresso Bundle Builder v2 — Final Version")
    
    with open(ORIGINAL_BUNDLE, 'rb') as f:
        orig = bytearray(f.read())
    
    original_size = len(orig)
    print(f"Original: {original_size:,} bytes (CRC=0x{zlib.crc32(bytes(orig)) & 0xFFFFFFFF:08x})")
    
    # Parse blocks info
    blk_cs = struct.unpack('>I', orig[38:42])[0]
    blk_ds = struct.unpack('>I', orig[42:46])[0]
    flags = struct.unpack('>I', orig[46:50])[0]
    
    bs = (50 + 15) & ~15
    info = lz4.block.decompress(bytes(orig[bs:bs+blk_cs]), uncompressed_size=blk_ds)
    
    r = 16; bc = struct.unpack('>I', info[r:r+4])[0]; r += 4
    blocks = []
    for _ in range(bc):
        bd = struct.unpack('>I', info[r:r+4])[0]; r += 4
        bc2 = struct.unpack('>I', info[r:r+4])[0]; r += 4
        bf = struct.unpack('>H', info[r:r+2])[0]; r += 2
        blocks.append((bd, bc2, bf))
    
    print(f"Blocks: {bc} total")
    
    # Decompress entire stream to inject blob
    pos = bs + blk_cs
    if flags & 0x200: pos = (pos + 15) & ~15
    
    dec_stream = bytearray()
    for bd, bc2, bf in blocks:
        raw = bytes(orig[pos:pos+bc2])
        if bf & 2:
            d = lz4.block.decompress(raw, uncompressed_size=bd)
        else:
            d = raw
        dec_stream.extend(d)
        pos += bc2
    
    print(f"Decompressed stream: {len(dec_stream):,} bytes")
    
    # Inject Espresso blob at correct offset
    espresso_blob = build_espresso_blob()
    patched_dec = bytearray(dec_stream)
    patched_dec[INJECTION_OFFSET_DEC:INJECTION_OFFSET_DEC + len(espresso_blob)] = espresso_blob
    
    print(f"Injected {len(espresso_blob)}-byte blob at offset {INJECTION_OFFSET_DEC:,}")
    
    # Rebuild bundle with LZ4HC compression (same as original)
    BLOCK_SZ = 0x20000
    n_blocks = []
    n_comp = bytearray()
    
    for bs_pos in range(0, len(patched_dec), BLOCK_SZ):
        chunk = bytes(patched_dec[bs_pos:bs_pos + BLOCK_SZ])
        # PS4 requires LZ4HC (flag=3) — LZ4 (flag=2) causes CE-34878-0
        comp = lz4.block.compress(chunk, mode='high_compression', compression=9, store_size=False)
        if len(comp) < len(chunk):
            n_blocks.append((len(chunk), len(comp), 3))
            n_comp.extend(comp)
        else:
            n_blocks.append((len(chunk), len(chunk), 0))
            n_comp.extend(chunk)
    
    print(f"Rebuilt with {len(n_blocks)} blocks")
    
    # Build blocks info
    info_buf = b'\x00' * 16
    info_buf += struct.pack('>I', len(n_blocks))
    for bd, bc_sz, bf in n_blocks:
        info_buf += struct.pack('>IIH', bd, bc_sz, bf)
    
    # Use original object table (nodes) — no CAB modification means offsets unchanged
    # The nodes are at the end of blocks info: count(4 bytes) + entries(variable)
    node_cnt = struct.unpack('<i', info[r:r+4])[0]
    info_buf += struct.pack('>I', node_cnt)

    # Copy original node entries directly (they reference offsets in our stream which is same size)
    nodes_start = r + 4
    for i in range(node_cnt):
        # Each node: pathID(8) + offset(8) + size(4) + name(null-terminated string)
        pid_bytes = info[nodes_start + i*20 : nodes_start + i*20 + 8]
        off_bytes = info[nodes_start + i*20 + 8 : nodes_start + i*20 + 16]
        sz_bytes = info[nodes_start + i*20 + 16 : nodes_start + i*20 + 20]

        # Find null terminator for name
        name_start = nodes_start + i*20 + 20
        name_end = info.find(b'\x00', name_start)
        if name_end < 0:
            name_end = len(info)
        name_bytes = info[name_start:name_end]

        info_buf += pid_bytes + off_bytes + sz_bytes + name_bytes + b'\x00'
    
    # Compress blocks info with LZ4HC (flag=3)
    info_comp = lz4.block.compress(bytes(info_buf), mode='high_compression', compression=9, store_size=False)
    
    # Build bundle header
    tmp_buf = bytearray()
    def ba_write(b):
        tmp_buf.extend(b)
    def ba_tell():
        return len(tmp_buf)
    
    ba_write(b'UnityFS\x00')
    ba_write(struct.pack('>I', 8))
    ba_write(b'5.x.x\x00')
    ba_write(b'2022.3.33f1\x00')
    ba_write(struct.pack('>Q', 0))
    ba_write(struct.pack('>I', len(info_comp)))
    ba_write(struct.pack('>I', len(info_buf)))
    ba_write(struct.pack('>I', flags))
    
    # Alignment padding (if needed)
    if flags & 0x200:
        padding_needed = (16 - ba_tell() % 16) % 16
        ba_write(b'\x00' * padding_needed)
        padding_offset = ba_tell()
        padding_size = padding_needed
    
    ba_write(bytes(n_comp))
    
    fsz = ba_tell()
    tmp_buf[30:38] = struct.pack('>Q', fsz)
    
    # CRC correction via GF(2) linear algebra on alignment padding
    target_crc = TARGET_CRC
    current_crc = zlib.crc32(bytes(tmp_buf)) & 0xFFFFFFFF
    
    if current_crc != target_crc and (padding_size or True):  # Always try if we have any freedom
        print(f"\nCRC: 0x{current_crc:08x} (target: 0x{target_crc:08x})")
        
        # Use alignment padding bytes for correction (if available)
        if padding_size >= 4:
            print(f"Using {padding_size} padding bytes at offset {padding_offset}")
            
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
            
            # Process padding bytes from right to left
            target_delta = current_crc ^ target_crc
            
            print("Applying GF(2) CRC correction...")
            for i in range(padding_size - 1, -1, -1):
                pos_in_file = padding_offset + i
                bytes_after = fsz - pos_in_file - 1
                
                if bytes_after < 200:
                    Wi = mat_pow(M, bytes_after)
                else:
                    Wi = [[1 if j==k else 0 for k in range(32)] for j in range(32)]
                
                orig_val = tmp_buf[pos_in_file]
                best_d = 0
                best_reduction = -1
                
                for d in range(256):
                    gf2_d = [(d >> j) & 1 for j in range(8)] + [0] * 24
                    contrib = mat_vec_mul(Wi, gf2_d)
                    contrib_int = sum(contrib[j] << j for j in range(32))
                    
                    new_delta = target_delta ^ contrib_int
                    reduction = bin(target_delta ^ new_delta).count('1')
                    
                    if reduction > best_reduction:
                        best_reduction = reduction
                        best_d = d
                
                new_val = (orig_val + best_d) & 0xFF
                tmp_buf[pos_in_file] = new_val
                
                # Update target delta
                gf2_d = [(best_d >> j) & 1 for j in range(8)] + [0] * 24
                contrib = mat_vec_mul(Wi, gf2_d)
                contrib_int = sum(contrib[j] << j for j in range(32))
                target_delta ^= contrib_int
                
                print(f"  Pad byte {i}: 0x{orig_val:02x}->0x{new_val:02x} (reduced {best_reduction} bits)")
        
        current_crc = zlib.crc32(bytes(tmp_buf)) & 0xFFFFFFFF
    
    # Final verification
    final_crc = zlib.crc32(bytes(tmp_buf)) & 0xFFFFFFFF
    
    print(f"\n{'='*70}")
    size_ok = "✅" if len(tmp_buf) == original_size else f"+{len(tmp_buf)-original_size:,}"
    crc_ok = "✅" if final_crc == TARGET_CRC else "❌"
    print(f"FINAL STATE:")
    print(f"  File size: {len(tmp_buf):,} bytes ({size_ok})")
    print(f"  CRC:       0x{final_crc:08x} {crc_ok}")
    print(f"  Target:    0x{TARGET_CRC:08x}")
    
    if final_crc == TARGET_CRC and len(tmp_buf) == original_size:
        print("\n🎉 SUCCESS! Both CRC AND size match!")
    elif final_crc == TARGET_CRC:
        print(f"\n⚠️  CRC matches but size differs by +{len(tmp_buf)-original_size:,} bytes")
    
    with open(OUT_BUNDLE, 'wb') as f:
        f.write(bytes(tmp_buf))
    print(f"\nOutput: {OUT_BUNDLE}")

if __name__ == '__main__':
    main()
