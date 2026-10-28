#!/usr/bin/env python3
"""
Build patched pack bundles with 4 preview mode sets (Standard, OneSaber, NoArrows, 90Degree).

Generalized version of build_startmeup_pack_modes.py: reads patch identifiers from
beat_saber_song_ids.json (written by scan_pack_patch_data.py) and patches EVERY
BeatmapLevelSO in a pack bundle so the song-select screen offers all 4 modes.

Approach per song blob:
  - Parse the existing _previewDifficultyBeatmapSets (any count, any characteristics).
  - Keep every existing set byte-for-byte, but extend any of the 4 target modes to
    exactly 5 difficulties (padding with the Standard set's preview data when needed).
  - Append any target mode that is missing, reusing the Standard set's fileID and diffs.
  - Identity fields (_levelID, _songName, _previewAudioClip, _coverImage, environment,
    colorSchemes) are preserved byte-for-byte.
After patching all blobs, the bundle is rebuilt (UnityFS + LZ4) with the object table
offsets/sizes fixed up, and a fresh catalog entry (m_Crc/m_BundleSize) is generated.

Usage:
  python3 development/scripts/build_all_pack_modes.py                  # dry run (summary)
  python3 development/scripts/build_all_pack_modes.py --pack therollingstones
  python3 development/scripts/build_all_pack_modes.py --all --write
"""

import struct, lz4.block, zlib, json, base64, os, sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SONG_IDS_PATH = os.path.join(PROJECT_ROOT, "beat_saber_song_ids.json")
OUT_DIR = os.path.join(PROJECT_ROOT, "pack_modes_bundles")

CHAR_PATH_IDS = {
    "Standard": -7286399427822119286,
    "OneSaber": -5623662769225589684,
    "NoArrows": -8583864861369561029,
    "90Degree": -5995858427784384822,
}
TARGET_MODES = ["Standard", "OneSaber", "NoArrows", "90Degree"]
TARGET_DIFFS = 5
DIFF_BYTES = 36


def crc_decompressed_stream(bundle_bytes):
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


def get_cab_raw(path):
    with open(path, 'rb') as f:
        buf = bytearray(f.read())
    blk_cs = struct.unpack('>I', buf[38:42])[0]
    blk_ds = struct.unpack('>I', buf[42:46])[0]
    flags = struct.unpack('>I', buf[46:50])[0]
    bs = (50 + 15) & ~15
    info = lz4.block.decompress(bytes(buf[bs:bs + blk_cs]), uncompressed_size=blk_ds)
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
        raw = bytes(buf[ds:ds + bc2])
        d = lz4.block.decompress(raw, uncompressed_size=bd) if bf & 2 else raw
        dec.extend(d); ds += bc2
    node_cnt = struct.unpack('>i', info[r:r + 4])[0]; r += 4
    nodes = []
    for _ in range(node_cnt):
        off = struct.unpack('>q', info[r:r + 8])[0]; r += 8
        sz = struct.unpack('>q', info[r:r + 8])[0]; r += 8
        nf = struct.unpack('>i', info[r:r + 4])[0]; r += 4
        pe = info.find(b'\x00', r); p = info[r:pe].decode(); r = pe + 1
        nodes.append((p, off, sz, nf))
    return bytes(dec[:nodes[0][2]]), blocks, flags, nodes, dec, buf


def walk_blob(blob):
    """Parse a BeatmapLevelSO blob; return sets info. None if not a BeatmapLevelSO."""
    try:
        o = 0
        o += 12  # m_GameObject
        o += 4   # m_Enabled + align
        o += 12  # m_Script
        def read_str(o):
            n = struct.unpack_from('<i', blob, o)[0]
            if n < 0 or n > 200:
                return None
            if n == 0:
                return '', o + 4
            data = blob[o + 4:o + 4 + n]
            o += 4 + n
            o = (o + 3) // 4 * 4
            return data.decode('utf-8', 'replace'), o
        r, o = read_str(o)
        if r is None:
            return None
        o += 4  # _version
        strings = []
        for _ in range(5):
            r, o = read_str(o)
            if r is None:
                return None
            strings.append(r)
        level_id = strings[0]
        o += 12  # _previewAudioClip
        o += 32  # 8 floats
        o += 12  # _coverImage
        for _ in range(2):
            r, o = read_str(o)
            if r is None:
                return None
        cnt = struct.unpack_from('<i', blob, o)[0]; o += 4
        if cnt < 0 or cnt > 20:
            return None
        for _ in range(cnt):
            r, o = read_str(o)
            if r is None:
                return None
        csc = struct.unpack_from('<i', blob, o)[0]; o += 4
        if csc < 0 or csc > 100:
            return None
        for _ in range(csc):
            r, o = read_str(o)
            if r is None:
                return None
            o += 4 + 28 * 4 + 4
        sets_off = o
        sc = struct.unpack_from('<i', blob, o)[0]
        if sc < 0 or sc > 8:
            return None
        sets = []
        po = o + 4
        for _ in range(sc):
            fid = struct.unpack_from('<i', blob, po)[0]
            pid = struct.unpack_from('<q', blob, po + 4)[0]
            dc = struct.unpack_from('<i', blob, po + 12)[0]
            if dc < 0 or dc > 20:
                return None
            sets.append({'fileID': fid, 'pathID': pid, 'diffCount': dc})
            po += 16 + dc * DIFF_BYTES
        return {
            'levelID': level_id,
            'setsOff': sets_off,
            'setCount': sc,
            'sets': sets,
            'contentRatingOff': po,
            'blobLen': len(blob),
        }
    except Exception:
        return None


def build_modes_blob(orig_blob, info):
    """Return (new_blob, changed_bool). Preserves existing sets, ensures target modes."""
    sets_off = info['setsOff']
    head = orig_blob[:sets_off]
    content_rating = orig_blob[info['contentRatingOff']:info['contentRatingOff'] + 4]

    po = sets_off + 4
    existing = {}  # pathID -> dict(fileID, diffCount, diffs_bytes)
    for s in info['sets']:
        fid = s['fileID']; pid = s['pathID']; dc = s['diffCount']
        existing[pid] = {
            'fileID': fid,
            'diffCount': dc,
            'diffs': orig_blob[po + 16:po + 16 + dc * DIFF_BYTES],
        }
        po += 16 + dc * DIFF_BYTES

    # template: Standard's diffs if present, else the largest existing set
    std_pid = CHAR_PATH_IDS["Standard"]
    if std_pid in existing:
        template = existing[std_pid]['diffs']
        template_fid = existing[std_pid]['fileID']
    elif existing:
        biggest = max(existing.values(), key=lambda v: v['diffCount'])
        template = biggest['diffs']
        template_fid = biggest['fileID']
    else:
        return orig_blob, False

    # pad template to exactly TARGET_DIFFS difficulties
    if len(template) < TARGET_DIFFS * DIFF_BYTES:
        template = template + template[:(TARGET_DIFFS * DIFF_BYTES - len(template))]
    template = template[:TARGET_DIFFS * DIFF_BYTES]

    # final set list: existing sets first (preserve), extending any target-mode
    # set that ships with < TARGET_DIFFS difficulties to exactly 5 (padding with
    # Standard's preview records), then missing target modes.
    final = []
    for pid, s in existing.items():
        diffs = s['diffs']
        dc = s['diffCount']
        if pid in CHAR_PATH_IDS.values() and dc < TARGET_DIFFS:
            diffs = (diffs + template)[:TARGET_DIFFS * DIFF_BYTES]
            dc = TARGET_DIFFS
        final.append({'pathID': pid, 'fileID': s['fileID'], 'diffs': diffs,
                      'diffCount': dc})
    for mode in TARGET_MODES:
        pid = CHAR_PATH_IDS[mode]
        if pid in existing:
            continue
        final.append({'pathID': pid, 'fileID': template_fid, 'diffs': template,
                      'diffCount': TARGET_DIFFS})

    b = bytearray(head)
    b += struct.pack('<i', len(final))
    for s in final:
        b += struct.pack('<i', s['fileID'])
        b += struct.pack('<q', s['pathID'])
        b += struct.pack('<i', s['diffCount'])
        b += s['diffs']
    b += content_rating
    return bytes(b), len(b) != len(orig_blob)


def rebuild_bundle(cab_raw, blocks, flags, nodes, dec, buf, patches):
    """Apply patches to CAB raw, rebuild bundle. patches = list of (blob_start, old_size, new_blob)."""
    patched = bytearray(cab_raw)
    data_off = struct.unpack('>I', cab_raw[0x14:0x18])[0]
    data_off = (48 + data_off + 15) & ~15
    meta_region_end = data_off
    patches = sorted(patches, key=lambda x: x[0])
    deltas = [(ps, len(nb) - osz) for ps, osz, nb in patches]

    # Locate every object-table record ONCE, before any mutation. Record layout
    # (Unity 2022.3, serializedVersion >= 22): pid(i64) byteStart(i64, relative
    # to data_off) byteSize(u32) typeID(i32), each record 8-byte aligned.
    records = {}
    for pid, bstart, bsize in patch_obj_table:
        stored = bstart - data_off
        pat = struct.pack('<qQ', pid, stored)
        pos = patched.find(pat, 48, meta_region_end)
        if pos < 0:
            raise RuntimeError(f"object table record not found: pid={pid} stored={stored}")
        records[pid] = pos

    # 1. Apply blob replacements, honoring cumulative shifts between blobs.
    cum = 0
    for blob_start, old_size, new_blob in patches:
        actual_start = blob_start + cum
        patched[actual_start:actual_start + old_size] = new_blob
        cum += len(new_blob) - old_size

    # 2. Update the object table in a single pass. Each object's stored byte
    #    offset shifts ONLY by the sum of deltas of patches that START before it
    #    (a patched blob's own content stays in place; its size field alone is
    #    updated). Blobs between two patches therefore shift correctly.
    for pid, bstart, bsize in patch_obj_table:
        shift = sum(d for ps, d in deltas if ps < bstart)
        new_stored = (bstart - data_off) + shift
        pos = records[pid]
        patched[pos + 8:pos + 16] = struct.pack('<Q', new_stored)
        own_new_size = [len(nb) for ps, osz, nb in patches if ps == bstart]
        if own_new_size:
            patched[pos + 16:pos + 20] = struct.pack('<I', own_new_size[0])

    new_cab_sz = len(patched)
    patched[0x1C:0x20] = struct.pack('>I', new_cab_sz)

    cab_key = nodes[0][0]
    cab_orig_sz = nodes[0][2]
    # find res nodes (they follow the CAB node)
    resS_key = cab_key + ".resS"; res_key = cab_key + ".resource"
    resS_raw = b''
    res_raw = b''
    for p, off, sz, nf in nodes:
        if p == resS_key:
            resS_raw = bytes(dec[off:off + sz])
        elif p == res_key:
            res_raw = bytes(dec[off:off + sz])

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
    tmp_buf.extend(b'UnityFS\x00'); tmp_buf.extend(struct.pack('>I', 8))
    tmp_buf.extend(b'5.x.x\x00'); tmp_buf.extend(b'2022.3.33f1\x00')
    tmp_buf.extend(struct.pack('>Q', 0))
    tmp_buf.extend(struct.pack('>I', len(info_comp)))
    tmp_buf.extend(struct.pack('>I', len(info_buf)))
    tmp_buf.extend(struct.pack('>I', flags))
    tmp_buf.extend(b'\x00' * ((16 - len(tmp_buf) % 16) % 16))
    tmp_buf.extend(info_comp)
    if flags & 0x200:
        tmp_buf.extend(b'\x00' * ((16 - len(tmp_buf) % 16) % 16))
    tmp_buf.extend(bytes(n_comp))
    fsz = len(tmp_buf)
    tmp_buf[30:38] = struct.pack('>Q', fsz)
    return bytes(tmp_buf)


def update_catalog(cat, bundle_name, new_crc, new_size):
    """Return catalog copy with the bundle's m_Crc/m_BundleSize updated."""
    ed = bytearray(base64.b64decode(cat['m_ExtraDataString']))
    s = ed.decode('utf-16-le', 'replace')
    i = s.find(bundle_name)
    if i < 0:
        raise SystemExit(f"BundleName marker {bundle_name} not found in catalog")
    j = s.rfind('{', 0, i)
    k = s.find('}', i)
    block = s[j:k + 1]
    old_crc = None; old_size = None
    for token in block.split(','):
        if 'm_Crc' in token:
            old_crc = token.split(':')[-1].strip()
        if 'm_BundleSize' in token:
            old_size = token.split(':')[-1].strip()
    if old_crc is None or old_size is None:
        raise SystemExit(f"Could not parse catalog block for {bundle_name}")
    block_new = block.replace(f'"m_Crc":{old_crc}', f'"m_Crc":{new_crc}')
    block_new = block_new.replace(f'"m_BundleSize":{old_size}', f'"m_BundleSize":{new_size}')
    s2 = s[:j] + block_new + s[k + 1:]
    ed2 = s2.encode('utf-16-le')
    cat2 = dict(cat)
    cat2['m_ExtraDataString'] = base64.b64encode(ed2).decode()
    return cat2


def patch_pack(album, write=False, orig_catalog=None):
    """Patch all songs in one pack. Returns summary dict."""
    pack = album['pack']
    if 'packBundle' not in album or 'catalogBundleName' not in album:
        return {'pack': pack, 'status': 'skip-no-data'}
    from scan_pack_patch_data import DUMP
    bundle_path = os.path.join(DUMP, "Media/StreamingAssets/aa/PS4", album['packBundle'])
    if not os.path.isfile(bundle_path) or os.path.getsize(bundle_path) == 0:
        return {'pack': pack, 'status': 'skip-missing-bundle'}

    cab_raw, blocks, flags, nodes, dec, buf = get_cab_raw(bundle_path)
    data_off = struct.unpack('>I', cab_raw[0x14:0x18])[0]
    data_off = (48 + data_off + 15) & ~15

    from UnityPy import Environment
    env = Environment(bundle_path)
    bf = list(env.files.values())[0]
    cab_key = next(k for k in bf.files if k.startswith('CAB-') and '.res' not in k)
    cab_obj = bf.files[cab_key]

    global patch_obj_table
    patch_obj_table = sorted(
        [(pid, o.byte_start, o.byte_size) for pid, o in cab_obj.objects.items()],
        key=lambda x: x[1]
    )

    patches = []
    changed = 0
    for song in album['songs']:
        if 'patchPathID' not in song:
            continue
        obj = cab_obj.objects.get(song['patchPathID'])
        if obj is None:
            print(f"  !! {pack}: object {song['patchPathID']} not found in CAB")
            continue
        blob = bytes(cab_raw[obj.byte_start:obj.byte_start + obj.byte_size])
        info = walk_blob(blob)
        if info is None:
            print(f"  !! {pack}: walk failed for {song['songID']}")
            continue
        if info['levelID'] != song['songID']:
            print(f"  !! {pack}: levelID mismatch {info['levelID']} vs {song['songID']}")
            continue
        new_blob, is_changed = build_modes_blob(blob, info)
        if not is_changed:
            continue
        patches.append((obj.byte_start, obj.byte_size, new_blob))
        changed += 1
        print(f"  . {pack:18s} {song['songID']:22s} blob {obj.byte_size:4d}->{len(new_blob):4d} sets {info['setCount']}->{info['setCount'] + sum(1 for m in TARGET_MODES if CHAR_PATH_IDS[m] not in {s['pathID'] for s in info['sets']})}")

    if not patches:
        return {'pack': pack, 'status': 'no-change', 'slots': len(album['songs'])}

    new_bundle = rebuild_bundle(cab_raw, blocks, flags, nodes, dec, buf, patches)
    actual_crc = crc_decompressed_stream(new_bundle)

    out_name = os.path.basename(bundle_path).replace('_assets_all_', '_modes_assets_all_')
    out_path = os.path.join(OUT_DIR, out_name)
    with open(out_path, 'wb') as f:
        f.write(new_bundle)

    result = {'pack': pack, 'status': 'patched', 'slots': len(album['songs']),
              'patched': changed, 'out': out_path,
              'size': len(new_bundle), 'crc': actual_crc}
    print(f"  OK {pack:18s} {out_name} {len(new_bundle):>9,}B crc={actual_crc} patched={changed}")
    return result


def main():
    args = sys.argv[1:]
    write = '--write' in args
    data = json.load(open(SONG_IDS_PATH))

    target_packs = None
    if '--pack' in args:
        target_packs = [args[args.index('--pack') + 1]]

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    cat = None
    if write:
        cat_path = os.path.join(os.path.dirname(SONG_IDS_PATH), "catalog_origin.json")
        if not os.path.isfile(cat_path):
            # locate the dump catalog
            from scan_pack_patch_data import DUMP
            cat_path = os.path.join(DUMP, "Media/StreamingAssets/aa/catalog.json")
        cat = json.load(open(cat_path))

    results = []
    for album in data['albums']:
        if target_packs and album['pack'] not in target_packs:
            continue
        r = patch_pack(album, write, cat)
        results.append(r)

    print("\nSummary:")
    patched = [r for r in results if r['status'] == 'patched']
    for r in patched:
        print(f"  {r['pack']}: {r['patched']} songs patched -> {os.path.basename(r['out'])}")
    print(f"  packs patched: {len(patched)}, no-change: {len([r for r in results if r['status']=='no-change'])}")


if __name__ == '__main__':
    main()
