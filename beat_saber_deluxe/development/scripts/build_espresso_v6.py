#!/usr/bin/env python3
"""Espresso bundle builder v6 — rebuild with uncompressed injection + CRC correction."""
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

def decompress_bundle(buf):
    """Decompress bundle and extract raw data stream."""
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
    
    # Extract raw data stream (decompressed)
    pos = bs + blk_cs
    if flags & 0x200: pos = (pos + 15) & ~15
    
    stream = bytearray()
    for bd, bc2, bf in blocks:
        raw = bytes(buf[pos:pos+bc2])
        if bf & 2:  # compressed
            d = lz4.block.decompress(raw, uncompressed_size=bd)
        else:  # uncompressed
            d = raw
        stream.extend(d)
        pos += bc2
    
    return bytes(stream), blocks, flags

def rebuild_bundle(stream, original_blocks, original_flags):
    """Rebuild bundle from raw stream with LZ4HC compression."""
    BLOCK_SZ = 0x20000
    n_blocks = []
    n_comp = bytearray()
    
    for bs in range(0, len(stream), BLOCK_SZ):
        chunk = bytes(stream[bs:bs + BLOCK_SZ])
        comp = lz4.block.compress(chunk, mode='high_compression', compression=9, store_size=False)
        if len(comp) < len(chunk):
            n_blocks.append((len(chunk), len(comp), 3))
            n_comp.extend(comp)
        else:
            n_blocks.append((len(chunk), len(chunk), 0))
            n_comp.extend(chunk)
    
    # Build blocks info
    info_buf = b'\x00' * 16
    info_buf += struct.pack('>I', len(n_blocks))
    for bd, bc, bf in n_blocks:
        info_buf += struct.pack('>IIH', bd, bc, bf)
    
    # Add object table (empty for now - we'll add it later if needed)
    info_buf += struct.pack('>I', 0)  # 0 objects
    
    # Compress blocks info with LZ4HC
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
    ba_write(struct.pack('>I', original_flags))
    ba_write(b'\x00' * ((16 - ba_tell() % 16) % 16))
    ba_write(info_comp)
    
    if original_flags & 0x200:
        padding_start = ba_tell()
        padding_needed = (16 - padding_start % 16) % 16
        ba_write(b'\x00' * padding_needed)
        padding_size = padding_needed
    
    ba_write(bytes(n_comp))
    
    fsz = ba_tell()
    tmp_buf[30:38] = struct.pack('>Q', fsz)
    
    return bytes(tmp_buf), padding_size if original_flags & 0x200 else 0

def main():
    print("Espresso Bundle Builder v6 — Rebuild with Uncompressed Injection")
    
    with open(ORIGINAL_BUNDLE, 'rb') as f:
        orig_buf = bytearray(f.read())
    
    original_size = len(orig_buf)
    print(f"Original: {original_size:,} bytes (CRC=0x{zlib.crc32(bytes(orig_buf)) & 0xFFFFFFFF:08x})")
    
    # Decompress bundle to get raw stream
    stream, blocks, flags = decompress_bundle(orig_buf)
    print(f"Decompressed stream: {len(stream):,} bytes")
    
    # Find an uncompressed block in the stream and inject Espresso blob there
    pos = 0
    uncomp_block_idx = None
    
    for i, (bd, bc2, bf) in enumerate(blocks):
        if not (bf & 2):  # uncompressed
            if i == 16:  # Use block 16 (first uncompressed block)
                uncomp_block_idx = i
                break
        pos += bc2
    
    if uncomp_block_idx is None:
        print("❌ Could not find uncompressed block 16")
        return
    
    # Find the start of block 16 in the stream
    pos = 0
    for i, (bd, bc2, bf) in enumerate(blocks):
        if i == uncomp_block_idx:
            break
        if bf & 2:
            pos += bc2
        else:
            pos += bd
    
    print(f"Injecting into uncompressed block {uncomp_block_idx} at stream offset {pos:,}")
    
    # Build Espresso blob and inject
    espresso_blob = build_espresso_blob()
    patched_stream = bytearray(stream)
    patched_stream[pos:pos+len(espresso_blob)] = espresso_blob
    
    print(f"Injected {len(espresso_blob)}-byte blob")
    print(f"New stream size: {len(patched_stream):,} bytes (+{len(patched_stream)-len(stream):,})")
    
    # Rebuild bundle with LZ4HC compression
    print("\nRebuilding bundle with LZ4HC compression...")
    rebuilt_buf, padding_size = rebuild_bundle(patched_stream, blocks, flags)
    
    new_size = len(rebuilt_buf)
    size_diff = new_size - original_size
    
    print(f"Rebuilt bundle: {new_size:,} bytes (diff: {'✅ ZERO' if size_diff==0 else f'+{size_diff:,}'})")
    
    # Compute CRC and apply correction if needed
    current_crc = zlib.crc32(rebuilt_buf) & 0xFFFFFFFF
    print(f"Current CRC: 0x{current_crc:08x}")
    print(f"Target CRC: 0x{TARGET_CRC:08x}")
    
    if current_crc != TARGET_CRC and padding_size >= 4:
        print(f"\nApplying GF(2) CRC correction using {padding_size} padding bytes...")
        
        # Use the same algorithm as build_patched_pack_bundle.py (which worked)
        import numpy as np
        
        pre = bytes(rebuilt_buf[:padding_size])
        pos_end = padding_size
        suf = bytes(rebuilt_buf[pos_end:])
        suf_len = len(suf)
        
        crc_table = [0] * 256
        for i in range(256):
            v = i
            for _ in range(8):
                v = (v >> 1) ^ (0xEDB88320 if v & 1 else 0)
            crc_table[i] = v
        
        M = np.zeros((32, 32), dtype=np.uint8)
        for col in range(32):
            state = 1 << col
            state = (state >> 8) ^ crc_table[state & 0xFF]
            for row in range(32):
                if state & (1 << row):
                    M[row, col] = 1
        
        def mat_mul_np(A, B):
            return (A @ B) & 1
        
        def mat_pow_np(M, exp):
            result = np.eye(32, dtype=np.uint8)
            base = M.copy()
            while exp:
                if exp & 1:
                    result = (result @ base) & 1
                base = (base @ base) & 1
                exp >>= 1
            return result
        
        def mat_vec_mul_np(M, v):
            result = 0
            for col in range(32):
                if v & (1 << col):
                    col_val = 0
                    for row in range(32):
                        if M[row, col]:
                            col_val |= (1 << row)
                    result ^= col_val
            return result
        
        print(f"Computing M^{suf_len}...")
        M_pow_L = mat_pow_np(M, suf_len)
        
        # Compute CRC state before padding
        state = 0xFFFFFFFF
        for b in pre:
            state = (state >> 8) ^ crc_table[(state & 0xFF) ^ b]
        crc_before_padding = state
        
        # Solve for CRC_after_pad
        crc_suf_zlib_0 = zlib.crc32(suf, 0) & 0xFFFFFFFF
        rhs = TARGET_CRC ^ crc_suf_zlib_0
        
        # Invert M_pow_L via Gauss-Jordan
        aug = np.hstack([M_pow_L, np.eye(32, dtype=np.uint8)])
        for col in range(32):
            pivot = None
            for row in range(col, 32):
                if aug[row, col]:
                    pivot = row
                    break
            if pivot is None:
                raise ValueError("Matrix is singular!")
            if pivot != col:
                aug[[col, pivot]] = aug[[pivot, col]]
            for row in range(32):
                if row != col and aug[row, col]:
                    aug[row] ^= aug[col]
        
        M_pow_L_inv = aug[:, 32:]
        x = mat_vec_mul_np(M_pow_L_inv, rhs)
        crc_after_pad = x ^ 0xFFFFFFFF
        
        # Now solve for padding bytes
        target_vec = crc_after_pad ^ mat_vec_mul_np(mat_pow_np(M, padding_size), crc_before_padding)
        
        # Try all-zero padding first, then search for correction
        padding_values = [0] * padding_size
        
        n = padding_size
        fixed_contrib = 0
        for i in range(n - 1):
            phase = n - 1 - i
            if phase > 0 and phase < 17:
                fixed_contrib ^= mat_vec_mul_np(mat_pow_np(M, phase), crc_table[0])
        
        needed = target_vec ^ fixed_contrib
        
        if needed in {crc_table[i]: i for i in range(256)}:
            padding_values[n - 1] = next(k for k, v in {crc_table[i]: i for i in range(256)}.items() if v == needed)
            print(f"✅ Found exact correction: p{n-1} = 0x{padding_values[n-1]:02x}")
        else:
            # Search first 3 bytes
            precomp = {}
            for i in range(1, padding_size):
                for byte in range(256):
                    precomp[(i, byte)] = mat_vec_mul_np(mat_pow_np(M, i), crc_table[byte])
            
            w0 = n - 1; w1 = n - 2; w2 = n - 3
            total_try = 256**3
            print(f"Trying {total_try:,} combos...")
            found = False
            
            for p0 in range(256):
                contrib0 = precomp[(w0, p0)]
                for p1 in range(256):
                    contrib1 = precomp[(w1, p1)]
                    comb01 = contrib0 ^ contrib1
                    for p2 in range(256):
                        contrib2 = precomp[(w2, p2)]
                        needed3 = target_vec ^ fixed_contrib ^ comb01 ^ contrib2
                        if needed3 in {crc_table[i]: i for i in range(256)}:
                            padding_values[0] = p0
                            padding_values[1] = p1
                            padding_values[2] = p2
                            padding_values[n - 1] = next(k for k, v in {crc_table[i]: i for i in range(256)}.items() if v == needed3)
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            
            if found:
                print(f"✅ Found CRC correction")
        
        # Apply padding values
        for i in range(padding_size):
            rebuilt_buf = bytearray(rebuilt_buf)
            rebuilt_buf[padding_size + i] = padding_values[i]
        
        final_crc = zlib.crc32(bytes(rebuilt_buf)) & 0xFFFFFFFF
        
        if final_crc == TARGET_CRC:
            print(f"✅ CRC MATCHES! 0x{final_crc:08x}")
            rebuilt_buf_final = bytes(rebuilt_buf)
        else:
            print(f"⚠️ CRC mismatch. Final: 0x{final_crc:08x}")
            rebuilt_buf_final = rebuilt_buf
    else:
        rebuilt_buf_final = rebuilt_buf
    
    # Final verification
    final_crc = zlib.crc32(rebuilt_buf_final) & 0xFFFFFFFF
    
    print(f"\n{'='*60}")
    size_ok = "✅" if len(rebuilt_buf_final) == original_size else f"+{len(rebuilt_buf_final)-original_size:,}"
    crc_ok = "✅" if final_crc == TARGET_CRC else "❌"
    print(f"FINAL: size={len(rebuilt_buf_final):,} ({size_ok}), CRC=0x{final_crc:08x} {crc_ok}, target=0x{TARGET_CRC:08x}")
    
    with open(OUT_BUNDLE, 'wb') as f:
        f.write(rebuilt_buf_final)
    print(f"Output: {OUT_BUNDLE}")

if __name__ == '__main__':
    main()
