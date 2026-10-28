#!/usr/bin/env python3
"""
Build StartMeUp pack bundle with 4 preview mode sets (Standard, OneSaber, NoArrows, 90Degree).

Surgical approach: take the ORIGINAL StartMeUp BeatmapLevelSO blob (440 bytes) and
append OneSaber/NoArrows/90Degree preview sets (each 5 difficulties, data copied from
Standard). All identity fields (_levelID="StartMeUp", _songName, _previewAudioClip,
_coverImage, environment) are preserved byte-for-byte, so the levelID->BeatmapLevelsData
redirect for the per-song bundle still fires.

Unlike build_patched_pack_bundle.py, NO CRC forcing is applied: the bundle's actual
CRC and size are computed and printed, and a fresh catalog entry (m_Crc/m_BundleSize)
is generated so catalog.json can be redirected alongside the bundle.

Blob tail layout (verified from original):
  [0..235]      identity + env + colorSchemes(count=0)
  [236..239]    _previewDifficultyBeatmapSets count (1)
  [240..439]    set0: fileID(4)+pathID(8)+diffcount(4)+5*36 difficulties
  [436..439]    _contentRating = 1
New blob = [0..239] + count=4 + 4 sets + _contentRating
"""

import struct, lz4.block, zlib, json, base64, os


def crc_decompressed_stream(bundle_bytes):
    # Unity AssetBundleRequestOptions m_Crc = zlib.crc32 over the DECOMPRESSED stream.
    blk_cs = struct.unpack('>I', bundle_bytes[38:42])[0]
    blk_ds = struct.unpack('>I', bundle_bytes[42:46])[0]
    flags = struct.unpack('>I', bundle_bytes[46:50])[0]
    bs = (50 + 15) & ~15
    info = lz4.block.decompress(bytes(bundle_bytes[bs:bs + blk_cs]), uncompressed_size=blk_ds)
    r = 16; bc = struct.unpack('>I', info[r:r + 4])[0]; r += 4
    blocks = []
    for _ in range(bc):
        bd = struct.unpack('>I', info[r:r + 4])[0]; r += 4
        bc2 = struct.unpack('>I', info[r:r + 4])[0]; r += 4
        bf = struct.unpack('>H', info[r:r + 2])[0]; r += 2
        blocks.append((bd, bc2, bf))
    ds = bs + blk_cs
    if flags & 0x200: ds = (ds + 15) & ~15
    dec = bytearray()
    for bd, bc2, bf in blocks:
        raw = bytes(bundle_bytes[ds:ds + bc2])
        dec.extend(lz4.block.decompress(raw, uncompressed_size=bd) if bf & 2 else raw)
        ds += bc2
    return zlib.crc32(bytes(dec)) & 0xFFFFFFFF

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/startmeup_pack_modes.bundle"
OUT_CATALOG = "/workspace/beat_saber_deluxe/catalog_startmeup_modes.json"
ORIGINAL_CATALOG = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/catalog.json"
OBJECT_ID = 2287600824654271910

CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
}
SET_COUNT_OFF = 236
BLOB_TAIL_START = 240  # set0 header starts here
DIFF_BYTES = 5 * 36    # 180
CONTENT_RATING_OFF = 436  # in original blob: after set0

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


def build_modes_blob(orig_blob):
    """Take original 440B blob, append 3 extra preview sets. Returns new blob."""
    assert len(orig_blob) == 440, f"unexpected blob len {len(orig_blob)}"
    count = struct.unpack_from('<i', orig_blob, SET_COUNT_OFF)[0]
    assert count == 1, f"expected 1 set, got {count}"
    head = orig_blob[:SET_COUNT_OFF]                       # through _colorSchemes count
    std_set_header = orig_blob[BLOB_TAIL_START:BLOB_TAIL_START + 16]  # fileID+pathID+diffcount
    assert std_set_header[:4] == struct.pack('<i', 3), "set0 fileID != 3"
    assert std_set_header[4:12] == struct.pack('<q', CHAR_PATH_IDS["Standard"]), "set0 != Standard"
    assert std_set_header[12:16] == struct.pack('<i', 5), "diffcount != 5"
    std_diffs = orig_blob[BLOB_TAIL_START + 16:BLOB_TAIL_START + 16 + DIFF_BYTES]
    assert len(std_diffs) == DIFF_BYTES, f"diff data len {len(std_diffs)}"
    content_rating = orig_blob[CONTENT_RATING_OFF:CONTENT_RATING_OFF + 4]
    assert content_rating == struct.pack('<i', 1), f"contentRating {content_rating.hex()}"

    b = bytearray(head)
    b += struct.pack('<i', 4)                              # 4 preview sets
    for mode in ["Standard", "OneSaber", "NoArrows", "90Degree"]:
        b += struct.pack('<i', 3)                          # fileID (external CAB)
        b += struct.pack('<q', CHAR_PATH_IDS[mode])        # characteristic pathID
        b += struct.pack('<i', 5)                          # diff count
        b += std_diffs                                     # copy Standard's preview data
    b += content_rating
    return bytes(b)


def main():
    print("StartMeUp Pack Modes Bundle Builder (Exp 179)")
    print("=" * 70)
    cab_raw, blocks, flags, nodes, dec, buf = get_cab_raw(ORIGINAL_BUNDLE)
    meta_sz = struct.unpack('>I', cab_raw[0x14:0x18])[0]
    data_off = (48 + meta_sz + 15) & ~15
    print(f"CAB: {len(cab_raw)}B, data_off={data_off}")

    from UnityPy import Environment
    env = Environment(ORIGINAL_BUNDLE)
    bf = list(env.files.values())[0]
    cab_key = next(k for k in bf.files if k.startswith('CAB-') and '.res' not in k)
    resS_key = cab_key + ".resS"; res_key = cab_key + ".resource"
    cab_obj = bf.files[cab_key]
    resS_raw = bytes(bf.files[resS_key].bytes)
    res_raw = bytes(bf.files[res_key].bytes)

    obj = cab_obj.objects[OBJECT_ID]
    blb_start = obj.byte_start
    blb_size = obj.byte_size
    orig_blob = bytes(cab_raw[blb_start:blb_start + blb_size])
    print(f"BeatmapLevelSO: offset={blb_start}, size={blb_size}")

    new_blob = build_modes_blob(orig_blob)
    delta = len(new_blob) - blb_size
    print(f"Blob: {blb_size} -> {len(new_blob)} (delta {delta:+d})")
    assert delta > 0

    patched = bytearray(cab_raw)
    patched[blb_start:blb_start + blb_size] = new_blob
    blob_end = blb_start + len(new_blob)

    # Update object table entries (objects after blob + blob's own size)
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
            continue
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

    # Update blob's own size in object table
    pat = struct.pack('<q', obj.path_id) + struct.pack('<Q', blb_start - data_off)
    pos = patched.find(pat, cab_header_sz, meta_region_end)
    if pos >= 0:
        patched[pos + 16:pos + 20] = struct.pack('<I', len(new_blob))
        print(f"Updated blob size: {blb_size} -> {len(new_blob)}")
    else:
        raise SystemExit("Could not find beatmap level SO entry in object table!")

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
    for bs_ in range(0, len(stream), BLOCK_SZ):
        chunk = bytes(stream[bs_:bs_ + BLOCK_SZ])
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
    info_comp = lz4.block.compress(bytes(info_buf), mode='high_compression', compression=9, store_size=False)

    tmp_buf = bytearray()
    def ba_write(b): tmp_buf.extend(b)
    def ba_tell(): return len(tmp_buf)
    ba_write(b'UnityFS\x00'); ba_write(struct.pack('>I', 8))
    ba_write(b'5.x.x\x00'); ba_write(b'2022.3.33f1\x00')
    ba_write(struct.pack('>Q', 0))
    ba_write(struct.pack('>I', len(info_comp)))
    ba_write(struct.pack('>I', len(info_buf)))
    ba_write(struct.pack('>I', flags))
    ba_write(b'\x00' * ((16 - ba_tell() % 16) % 16))
    ba_write(info_comp)
    if flags & 0x200:
        ba_write(b'\x00' * ((16 - ba_tell() % 16) % 16))
    ba_write(bytes(n_comp))
    fsz = ba_tell()
    tmp_buf[30:38] = struct.pack('>Q', fsz)

    with open(OUT_BUNDLE, 'wb') as f:
        f.write(bytes(tmp_buf))
    actual_crc = crc_decompressed_stream(bytes(tmp_buf))
    print(f"\n{OUT_BUNDLE.split('/')[-1]}: {fsz:,} bytes, dec-stream CRC=0x{actual_crc:08x}")

    # Verify with UnityPy (byte-level; typetree read_str may fail on patched object)
    try:
        env2 = Environment(OUT_BUNDLE)
        bf2 = list(env2.files.values())[0]
        for key in bf2.files:
            if key.startswith("CAB-") and '.res' not in key:
                c2 = bf2.files[key]
                o2 = c2.objects[OBJECT_ID]
                raw2 = bytes(o2.get_raw_data())
                print(f"  Patched blob len: {len(raw2)}")
                cnt = struct.unpack_from('<i', raw2, SET_COUNT_OFF)[0]
                print(f"  Preview sets count: {cnt} (expect 4)")
                for i in range(cnt):
                    o = SET_COUNT_OFF + 4 + i * (16 + DIFF_BYTES)
                    fid = struct.unpack_from('<i', raw2, o)[0]
                    pid = struct.unpack_from('<q', raw2, o + 4)[0]
                    dc = struct.unpack_from('<i', raw2, o + 12)[0]
                    print(f"    [{i}] fileID={fid} pathID={pid} diffs={dc}")
                break
    except Exception as e:
        print(f"  (UnityPy verify: {e})")

    # Generate fresh catalog with m_Crc/m_BundleSize updated
    cat = json.load(open(ORIGINAL_CATALOG))
    ed = bytearray(base64.b64decode(cat['m_ExtraDataString']))
    s = ed.decode('utf-16-le', 'replace')
    marker = '51dc790300eb3d900786837beb3ac335'  # rollingstones m_BundleName
    i = s.find(marker)
    if i < 0:
        raise SystemExit("BundleName marker not found in catalog extra data")
    # locate the JSON block start (last '{' before marker)
    j = s.rfind('{', 0, i)
    k = s.find('}', i)
    block = s[j:k + 1]
    old_crc = '3700109647'
    old_size = '7902803'
    assert old_crc in block and old_size in block, "expected original values"
    block_new = block.replace(f'"m_Crc":{old_crc}', f'"m_Crc":{actual_crc}')
    block_new = block_new.replace(f'"m_BundleSize":{old_size}', f'"m_BundleSize":{fsz}')
    s2 = s[:j] + block_new + s[k + 1:]
    ed2 = s2.encode('utf-16-le')
    cat['m_ExtraDataString'] = base64.b64encode(ed2).decode()
    with open(OUT_CATALOG, 'w') as f:
        json.dump(cat, f, indent=1)
    print(f"\nCatalog written: {OUT_CATALOG}")
    print(f"  old: m_Crc={old_crc}, m_BundleSize={old_size}")
    print(f"  new: m_Crc={actual_crc}, m_BundleSize={fsz}")


if __name__ == '__main__':
    main()
