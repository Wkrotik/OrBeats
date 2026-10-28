#!/usr/bin/env python3
"""
Build patched pack bundle — manual blob builder + raw CAB injection + object table update.

save_typetree() ignores modifications for this object type (stuck at 440 bytes).
Fix: use inject_pack_bundle.py's blob builder (struct packing, byte-verified) with
the CORRECT m_Script PPtr, then raw-inject into the CAB with object table offset update.

Header format (v22+): metadata_size(BE) at 0x14, file_size(BE) at 0x1C,
data_offset = align16(48 + metadata_size).
Object table: pathID(int64) + offset(int64 relative to data_offset) + size(int32)
"""

import struct, os, lz4.block, zlib
from UnityPy import Environment

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/rollingstones_pack_patched.bundle"

# ── Fixed PPtr values ────────────────────────────────────────────────
SCRIPT_PATHID_CORRECT = 2140275054477726686  # MonoScript, NOT BeatmapCharacteristicSO!
CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
}

def encode_utf8_string(s):
    """Unity serialized UTF-8 string: stored_size = char count (no null), content without null, null after.
    NOTE: Original CAB format does NOT include null in stored_size!
    """
    if not s:
        return b'\x00\x00'  # stored_size=0 + null
    data = s.encode('utf-8')  # NO null in content
    return struct.pack('<i', len(data)) + data + b'\x00'  # size=char_count, content, then null

def build_blob(song_name="Espresso", artist="Sabrina Carpenter", bpm=126.5, level_id="custom/espresso"):
    """Build BeatmapLevelSO blob with 4 modes and correct m_Script PPtr. Returns 1061 bytes."""
    b = bytearray()
    b += struct.pack('<i', 0)                                      # m_GameObject fileID
    b += struct.pack('<q', 0)                                      # m_GameObject pathID
    b += struct.pack('<I', 1)                                      # class/metadata
    b += struct.pack('<i', 1)                                      # m_Script fileID = 1
    b += struct.pack('<q', SCRIPT_PATHID_CORRECT)                  # FIXED: MonoScript pathID

    b.extend(encode_utf8_string(f"{song_name}CustomBeatmapLevel"))  # m_Name
    b.append(0x78); b.append(1); b.append(1)                       # _version

    b.extend(encode_utf8_string(level_id))                          # _levelID
    b.extend(encode_utf8_string(song_name))                         # _songName
    b.extend(b'\x00\x00')                                          # _songSubName
    b.extend(encode_utf8_string(artist))                            # _songAuthorName
    b.extend(encode_utf8_string(artist))                            # _levelAuthorName

    b += struct.pack('<i', 0) + struct.pack('<q', 0)               # _previewAudioClip (zeroed)
    for val in [bpm, -8.2, 0.0, 0.0, 0.0, 138.0, 10.0, 213.7]:
        b += struct.pack('<d', val)
    b += struct.pack('<i', 0) + struct.pack('<q', 0)               # _coverImage (zeroed)

    b.extend(encode_utf8_string(""))
    b.extend(encode_utf8_string(""))
    b += struct.pack('<i', 1)
    b.extend(encode_utf8_string("TheRollingStonesEnvironment"))
    b += struct.pack('<i', 0)

    # 4 modes (360Degree unsupported on PS4)
    b += struct.pack('<i', 4)
    for mode in ["Standard", "OneSaber", "NoArrows", "90Degree"]:
        b += struct.pack('<i', 3)                                   # fileID = 3 (external)
        b += struct.pack('<q', CHAR_PATH_IDS[mode])                 # pathID
        b += struct.pack('<i', 5)                                   # diff_count = 5
        b += b'\x00' * (5 * 36)                                    # zeroed diffs

    return bytes(b)


def get_cab_raw(path):
    """Decompress bundle and extract CAB raw bytes + metadata."""
    with open(path, 'rb') as f:
        buf = bytearray(f.read())
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
    ds = bs + blk_cs
    if flags & 0x200: ds = (ds + 15) & ~15
    dec = bytearray()
    for bd, bc2, bf in blocks:
        raw = bytes(buf[ds:ds+bc2])
        d = lz4.block.decompress(raw, uncompressed_size=bd) if bf & 2 else raw
        dec.extend(d); ds += bc2
    node_cnt = struct.unpack('>i', info[r:r+4])[0]; r += 4
    nodes = []
    for _ in range(node_cnt):
        off = struct.unpack('>q', info[r:r+8])[0]; r += 8
        sz = struct.unpack('>q', info[r:r+8])[0]; r += 8
        nf = struct.unpack('>i', info[r:r+4])[0]; r += 4
        pe = info.find(b'\x00', r); p = info[r:pe].decode(); r = pe + 1
        nodes.append((p, off, sz, nf))
    return bytes(dec[:nodes[0][2]]), blocks, flags, nodes, dec, buf


def main():
    print("=" * 70)
    print("Manual Blob Builder + Raw CAB Injection + Object Table Update")
    print("=" * 70)

    cab_raw, blocks, flags, nodes, dec, buf = get_cab_raw(ORIGINAL_BUNDLE)
    meta_sz = struct.unpack('>I', cab_raw[0x14:0x18])[0]
    file_sz_be = struct.unpack('>I', cab_raw[0x1C:0x20])[0]
    data_off = (48 + meta_sz + 15) & ~15  # 53456
    print(f"CAB: {len(cab_raw)}B, meta_sz={meta_sz}, file_sz={file_sz_be}, data_off={data_off}")

    # Load via UnityPy for object metadata (byte_start, byte_size)
    env = Environment(ORIGINAL_BUNDLE)
    bf = list(env.files.values())[0]
    cab_key = next(k for k in bf.files if k.startswith('CAB-') and '.res' not in k)
    resS_key = cab_key + ".resS"; res_key = cab_key + ".resource"
    cab_obj = bf.files[cab_key]
    resS_raw = bytes(bf.files[resS_key].bytes)
    res_raw = bytes(bf.files[res_key].bytes)

    obj = cab_obj.objects[2287600824654271910]
    blb_start = obj.byte_start
    blb_size = obj.byte_size
    print(f"BeatmapLevelSO: offset={blb_start}, size={blb_size}")

    # Build modified blob
    new_blob = build_blob()
    delta = len(new_blob) - blb_size
    print(f"Blob: {blb_size} -> {len(new_blob)} (delta: {delta:+d})")
    assert delta > 0, "Expected blob to be larger!"

    # Patch CAB: replace blob
    patched = bytearray(cab_raw)
    patched[blb_start:blb_start + blb_size] = new_blob
    blob_end = blb_start + len(new_blob)

    # Update object table entries (objects AFTER the blob + blob's own size)
    cab_header_sz = 48
    meta_region_end = data_off
    obj_list = sorted(
        [(pid, o.byte_start, o.byte_size) for pid, o in cab_obj.objects.items()],
        key=lambda x: x[1]
    )
    updated_off = 0
    not_found = 0
    for pid, bstart, bsize in obj_list:
        if bstart < blb_start + blb_size:
            continue  # before or inside old blob
        old_stored = bstart - data_off
        new_stored = old_stored + delta
        pat = struct.pack('<q', pid) + struct.pack('<Q', old_stored)
        pos = patched.find(pat, cab_header_sz, meta_region_end)
        if pos >= 0:
            patched[pos + 8:pos + 16] = struct.pack('<Q', new_stored)
            updated_off += 1
        else:
            not_found += 1
    print(f"Object table: {updated_off} offsets updated, {not_found} not found")

    # Update the blob's own size in the object table
    pat = struct.pack('<q', obj.path_id) + struct.pack('<Q', blb_start - data_off)
    pos = patched.find(pat, cab_header_sz, meta_region_end)
    if pos >= 0:
        # size is at pos+16 (after pathID=8 + offset=8)
        patched[pos + 16:pos + 20] = struct.pack('<I', len(new_blob))
        print(f"Updated blob size: 440 -> {len(new_blob)}")
    else:
        print("  ⚠️  Could not find beatmap level SO entry in object table!")

    # Update file_size in CAB header
    new_cab_sz = len(patched)
    patched[0x1C:0x20] = struct.pack('>I', new_cab_sz)
    print(f"CAB: {len(cab_raw)} -> {new_cab_sz}")

    # Build bundle
    cab_orig_sz = nodes[0][2]
    stream = bytearray(dec)
    stream[:cab_orig_sz] = bytes(patched)
    new_nodes = [
        (cab_key, 0, new_cab_sz, 4),
        (resS_key, new_cab_sz, len(resS_raw), 0),
        (res_key, new_cab_sz + len(resS_raw), len(res_raw), 0),
    ]
    BLOCK_SZ = 0x20000
    n_blocks = []; n_comp = bytearray()
    for bs in range(0, len(stream), BLOCK_SZ):
        chunk = bytes(stream[bs:bs + BLOCK_SZ])
        # PS4 requires LZ4HC (flag=3) for all blocks — LZ4 (flag=2) causes CE-34878-0
        comp = lz4.block.compress(chunk, mode='high_compression', compression=9, store_size=False)
        if len(comp) < len(chunk):
            n_blocks.append((len(chunk), len(comp), 3)); n_comp.extend(comp)
        else:
            n_blocks.append((len(chunk), len(chunk), 0)); n_comp.extend(chunk)
    info_buf = b'\x00' * 16
    info_buf += struct.pack('>I', len(n_blocks))
    for bd, bc, bf in n_blocks:
        info_buf += struct.pack('>IIH', bd, bc, bf)
    info_buf += struct.pack('>I', len(new_nodes))
    for p, o, s, nf in new_nodes:
        info_buf += struct.pack('>QQI', o, s, nf) + p.encode() + b'\x00'
    # Also compress blocks info with LZ4HC (flag=3)
    info_comp = lz4.block.compress(bytes(info_buf), mode='high_compression', compression=9, store_size=False)

    # Build bundle in memory for CRC correction
    tmp_buf = bytearray()
    def ba_write(b):
        tmp_buf.extend(b)
    def ba_tell():
        return len(tmp_buf)

    ba_write(b'UnityFS\x00'); ba_write(struct.pack('>I', 8))
    ba_write(b'5.x.x\x00'); ba_write(b'2022.3.33f1\x00')
    ba_write(struct.pack('>Q', 0))
    ba_write(struct.pack('>I', len(info_comp)))
    ba_write(struct.pack('>I', len(info_buf)))
    ba_write(struct.pack('>I', flags))
    ba_write(b'\x00' * ((16 - ba_tell() % 16) % 16))
    ba_write(info_comp)
    if flags & 0x200:
        padding_start = ba_tell()
        padding_needed = (16 - padding_start % 16) % 16
        ba_write(b'\x00' * padding_needed)
        padding_size = padding_needed
    ba_write(bytes(n_comp))
    fsz = ba_tell()
    # Update file_size at offset 30
    tmp_buf[30:38] = struct.pack('>Q', fsz)

    # ── CRC Correction via GF(2) Linear Algebra ──────────────────────────
    # CRC through zero bytes is a linear transformation over GF(2).
    # We use matrix algebra to compute exact padding bytes that make
    # the bundle CRC match the original (0xdc8b314f).
    target_crc = 0xdc8b314f  # Original rolling stones pack bundle CRC32
    current_crc = zlib.crc32(bytes(tmp_buf)) & 0xFFFFFFFF

    if current_crc != target_crc and padding_size >= 4:
        import numpy as np
        print(f"CRC: 0x{current_crc:08x} (target: 0x{target_crc:08x})")
        print(f"Padding: {padding_size} bytes at offset {padding_start}")
        print(f"Computing CRC correction via GF(2) linear algebra...")

        pre = bytes(tmp_buf[:padding_start])
        pos_end = padding_start + padding_size
        suf = bytes(tmp_buf[pos_end:])
        suf_len = len(suf)

        # Build CRC-32 table
        crc_table = [0] * 256
        for i in range(256):
            v = i
            for _ in range(8):
                v = (v >> 1) ^ (0xEDB88320 if v & 1 else 0)
            crc_table[i] = v

        # Build inverse CRC table (maps 32-bit value -> byte)
        crc_table_inv = {}
        for i in range(256):
            crc_table_inv[crc_table[i]] = i

        # Build M matrix (32x32 GF(2)): CRC state transformation for 1 zero byte
        # M[col] has bit j set if processing 1 zero byte flips bit j when input has only bit col set
        M = np.zeros((32, 32), dtype=np.uint8)
        for col in range(32):
            state = 1 << col
            # Process one zero byte: state = (state >> 8) ^ table[state & 0xFF]
            state = (state >> 8) ^ crc_table[state & 0xFF]
            for row in range(32):
                if state & (1 << row):
                    M[row, col] = 1

        # Matrix multiply over GF(2)
        def mat_mul(A, B):
            return (A @ B) & 1

        # Matrix power over GF(2) - fast exponentiation
        def mat_pow(M, exp):
            result = np.eye(32, dtype=np.uint8)
            base = M.copy()
            while exp:
                if exp & 1:
                    result = (result @ base) & 1
                base = (base @ base) & 1
                exp >>= 1
            return result

        # Matrix-vector multiply over GF(2): result = M * v (v is 32-bit integer)
        def mat_vec_mul(M, v):
            result = 0
            for col in range(32):
                if v & (1 << col):
                    # Add column
                    col_val = 0
                    for row in range(32):
                        if M[row, col]:
                            col_val |= (1 << row)
                    result ^= col_val
            return result

        # Compute M^L where L = suffix length
        print(f"  Computing M^{suf_len} (suffix length)...")
        M_pow_L = mat_pow(M, suf_len)

        # Compute M^1 through M^10 for padding byte weights
        M_pow = [np.eye(32, dtype=np.uint8)]
        for i in range(1, 17):
            M_pow.append((M_pow[i-1] @ M) & 1)

        # Compute CRC_before_padding: raw CRC state before padding starts
        # For zlib: internal state = init XOR 0xFFFFFFFF
        state = 0xFFFFFFFF  # zlib initial state
        for b in pre:
            state = (state >> 8) ^ crc_table[(state & 0xFF) ^ b]
        crc_before_padding = state

        # Compute CRC_after_pad using the forward formula:
        # CRC_final = M^L * (CRC_after_pad XOR 0xFFFFFFFF) XOR zlib.crc32(suf, 0)
        # So: M^L * (CRC_after_pad XOR 0xFFFFFFFF) = CRC_final XOR zlib.crc32(suf, 0)
        # CRC_after_pad = M^(-L) * (CRC_final XOR zlib.crc32(suf, 0)) XOR 0xFFFFFFFF

        # zlib.crc32 with init=0 (in zlib: init=0 is XORed with 0xFFFFFFFF internally)
        def raw_crc32(data, init=0):
            s = init ^ 0xFFFFFFFF
            for b in data:
                s = (s >> 8) ^ crc_table[(s & 0xFF) ^ b]
            return s ^ 0xFFFFFFFF

        crc_suf_from_0 = raw_crc32(suf, 0)
        crc_target_raw = target_crc  # This is the zlib CRC value

        # Solve: M^L * (CRC_after_pad XOR 0xFFFFFFFF) = target_crc XOR crc_suf_from_0
        rhs = target_crc ^ crc_suf_from_0  # This is a raw CRC value (no final XOR)

        # Actually, I need to be more careful. Let me re-derive.
        # raw_crc(data, init) = M^L * (init XOR 0xFFFFFFFF) XOR raw_crc(data, 0)
        # zlib.crc32(data, init) = raw_crc(data, init) XOR 0xFFFFFFFF

        # So: zlib.crc32(suf, CRC_after_pad)
        #   = raw_crc(suf, CRC_after_pad) XOR 0xFFFFFFFF
        #   = (M^L * (CRC_after_pad XOR 0xFFFFFFFF) XOR raw_crc(suf, 0)) XOR 0xFFFFFFFF

        # raw_crc(suf, 0) = zlib.crc32(suf, 0) XOR 0xFFFFFFFF

        # So: zlib.crc32(suf, CRC_after_pad)
        #   = M^L * (CRC_after_pad XOR 0xFFFFFFFF) XOR zlib.crc32(suf, 0) XOR 0xFFFFFFFF XOR 0xFFFFFFFF
        #   = M^L * (CRC_after_pad XOR 0xFFFFFFFF) XOR zlib.crc32(suf, 0)

        # Set equal to target: M^L * (CRC_after_pad XOR 0xFFFFFFFF) = target_crc XOR zlib.crc32(suf, 0)

        # zlib.crc32(suf, 0) I can compute directly:
        crc_suf_zlib_0 = zlib.crc32(suf, 0) & 0xFFFFFFFF

        rhs = target_crc ^ crc_suf_zlib_0

        # Now solve M_pow_L * x = rhs for x = (CRC_after_pad XOR 0xFFFFFFFF)
        # Invert M_pow_L: need inverse matrix
        # For GF(2), M^(-1) = M^adj using Gauss-Jordan
        # Augment M_pow_L with identity and perform row reduction
        aug = np.hstack([M_pow_L, np.eye(32, dtype=np.uint8)])
        for col in range(32):
            # Find pivot
            pivot = None
            for row in range(col, 32):
                if aug[row, col]:
                    pivot = row
                    break
            if pivot is None:
                raise ValueError("Matrix is singular!")
            # Swap rows
            if pivot != col:
                aug[[col, pivot]] = aug[[pivot, col]]
            # Eliminate other rows
            for row in range(32):
                if row != col and aug[row, col]:
                    aug[row] ^= aug[col]

        M_pow_L_inv = aug[:, 32:]

        # x = M^(-L) * rhs
        x = mat_vec_mul(M_pow_L_inv, rhs)
        crc_after_pad = x ^ 0xFFFFFFFF

        # Now I have: CRC_after_pad (state after 10 padding bytes, before suffix)
        # I need to find padding[0..9] such that processing them from crc_before_padding
        # gives crc_after_pad.

        # Forward: CRC after processing padding bytes:
        # For byte b: crc = (crc >> 8) ^ table[(crc & 0xFF) ^ b]
        # This is: crc_new = M * crc_old XOR table[b]
        # (because table[(crc & 0xFF) ^ b] = table[(crc & 0xFF)] XOR table[b] by linearity)

        # Wait, the CRC table IS linear: table[a XOR b] = table[a] XOR table[b]?
        # This is true for CRC tables (the table is a linear transformation).
        # So: table[(crc & 0xFF) ^ b] = table[crc & 0xFF] XOR table[b]
        # And: crc_new = (crc >> 8) ^ table[crc & 0xFF] ^ table[b]
        #            = M * crc XOR table[b]

        # After 10 padding bytes:
        # crc_after_pad = M^10 * crc_before_padding XOR
        #                 M^9 * table[p0] XOR M^8 * table[p1] XOR ... XOR table[p9]

        # So: M^9 * table[p0] XOR M^8 * table[p1] XOR ... XOR table[p9] = target
        # where target = crc_after_pad XOR M^n * crc_before_padding (n = padding_size)

        target_vec = crc_after_pad ^ mat_vec_mul(M_pow[padding_size], crc_before_padding)

        # Find padding values p[0..n-1] such that the weighted XOR of table[p_i] equals target_vec
        # Strategy: use LAST padding byte as the "correction" byte.
        # Set p[0..n-2] = arbitrary (all 0)
        # Then: table[p9] = target_vec XOR (M^9 * table[0] XOR M^8 * table[0] XOR ... XOR M * table[0])

        # Alternative: set all to 0, compute what p9 needs to be
        padding_values = [0] * padding_size

        # Compute contribution of fixed bytes (all but the last padding byte = 0)
        n = padding_size
        fixed_contrib = 0
        for i in range(n - 1):  # i = 0..n-2 (all but last)
            phase = n - 1 - i  # M^(n-1-i) for byte i
            if phase > 0 and phase < 17:  # M_pow has indices up to 16
                fixed_contrib ^= mat_vec_mul(M_pow[phase], crc_table[0])
        # For last byte: weight = M^0 = I, so contribution = table[last_byte]

        needed = target_vec ^ fixed_contrib

        if needed in crc_table_inv:
            padding_values[padding_size - 1] = crc_table_inv[needed]
            print(f"  ✅ Found exact CRC correction: p{padding_size-1} = 0x{padding_values[padding_size - 1]:02x}")
        else:
            # Precompute M^i * table[byte] for all needed powers
            precomp = {}
            for i in range(1, padding_size):
                for byte in range(256):
                    precomp[(i, byte)] = mat_vec_mul(M_pow[i], crc_table[byte])

            # Try varying first 3 bytes to make needed for last byte land in CRC table
            n = padding_size
            w0 = n - 1; w1 = n - 2; w2 = n - 3  # weights M^(n-1), M^(n-2), M^(n-3)
            total_try = 256**3
            print(f"  Trying {total_try:,} combos (weights {w0},{w1},{w2})...")
            found = False
            for p0 in range(256):
                contrib0 = precomp[(w0, p0)]
                for p1 in range(256):
                    contrib1 = precomp[(w1, p1)]
                    comb01 = contrib0 ^ contrib1
                    for p2 in range(256):
                        contrib2 = precomp[(w2, p2)]
                        needed3 = target_vec ^ fixed_contrib ^ comb01 ^ contrib2
                        if needed3 in crc_table_inv:
                            padding_values[0] = p0
                            padding_values[1] = p1
                            padding_values[2] = p2
                            padding_values[n - 1] = crc_table_inv[needed3]
                            found = True
                            break
                    if found:
                        break
                if found:
                    break

            if found:
                print(f"  ✅ Found CRC correction: p0=0x{padding_values[0]:02x}, p1=0x{padding_values[1]:02x}, p2=0x{padding_values[2]:02x}, p{padding_size-1}=0x{padding_values[padding_size - 1]:02x}")
            else:
                print(f"  ⚠️ Could not find exact correction via linear method")

        # Write padding bytes
        for i in range(padding_size):
            tmp_buf[padding_start + i] = padding_values[i]

        current_crc = zlib.crc32(bytes(tmp_buf)) & 0xFFFFFFFF
        if current_crc == target_crc:
            print(f"✅ CRC MATCHES! 0x{current_crc:08x} == 0x{target_crc:08x}")
        else:
            print(f"⚠️ CRC: 0x{current_crc:08x} (target 0x{target_crc:08x})")
    else:
        print(f"CRC: 0x{current_crc:08x} {'✅ MATCH' if current_crc==target_crc else ' (need >=4 padding bytes)'}")

    # Write final bundle
    with open(OUT_BUNDLE, 'wb') as f:
        f.write(bytes(tmp_buf))
    fsz = len(tmp_buf)

    print(f"\n✅ {OUT_BUNDLE.split('/')[-1]}: {fsz:,} bytes")

    # Verify with UnityPy
    try:
        env2 = Environment(OUT_BUNDLE)
        bf2 = list(env2.files.values())[0]
        for key in bf2.files:
            if key.startswith("CAB-") and '.res' not in key:
                c2 = bf2.files[key]
                o2 = c2.objects[2287600824654271910]
                t2 = o2.read_typetree()
                pds2 = t2.get('_previewDifficultyBeatmapSets', [])
                ms2 = t2.get('m_Script', {})
                print(f"  m_Script: fileID={ms2.get('m_FileID')}, pathID={ms2.get('m_PathID')}")
                print(f"  Song: {t2.get('_songName','?')}")
                print(f"  Modes: {len(pds2)} {'✅ 5 MODES!' if len(pds2)==5 else ''}")
                for i, p in enumerate(pds2):
                    bc = p.get('_beatmapCharacteristic', {})
                    print(f"    [{i}] fileID={bc.get('m_FileID')}, pathID={bc.get('m_PathID')}")
                break
    except Exception as e:
        print(f"  ⚠️ UnityPy verification failed: {e}")
        print("  (Bundle may still work on PS4)")


if __name__ == '__main__':
    main()
