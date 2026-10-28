#!/usr/bin/env python3
"""
Build patched pack bundles that expose all 4 gameplay modes
(Standard / OneSaber / NoArrows / 90Degree) with 5 difficulties each.

This is the PRODUCTION implementation of the pack-patch approach proven on PS4
(Exp 179-182, 187): patch the `_previewDifficultyBeatmapSets` array of every
replaced BeatmapLevelSO in a pack bundle, rebuild the bundle (UnityFS + LZ4)
with a corrected object table, and regenerate the Addressables catalog entry
(m_Crc = zlib.crc32 of the DECOMPRESSED stream, m_BundleSize) for every patched
pack into a single merged catalog.

Patch identifiers (per-song pathID, blob offsets, album catalog bundle name/CRC/
size) come from `beat_saber_song_ids.json` — written once by
`development/scripts/scan_pack_patch_data.py`. This module only reads that file.

Usage (module API):
    results = build_pack_mode_bundles(song_ids_path, dump_dir, out_dir, packs=None)
    write_merged_catalog(dump_catalog_path, results, out_path)

CLI:
    python3 tools/build_pack_mode_bundles.py                 # dry-run summary
    python3 tools/build_pack_mode_bundles.py --packs therollingstones,billieeilish
    python3 tools/build_pack_mode_bundles.py --all --write
"""

import base64
import json
import os
import re
import struct
import sys
import zlib

import lz4.block

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONG_IDS_PATH = os.path.join(PROJECT_ROOT, "beat_saber_song_ids.json")

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
    """zlib.crc32 of the DECOMPRESSED UnityFS stream (== the catalog m_Crc)."""
    blk_cs = struct.unpack('>I', bundle_bytes[38:42])[0]
    blk_ds = struct.unpack('>I', bundle_bytes[42:46])[0]
    flags = struct.unpack('>I', bundle_bytes[46:50])[0]
    bs = (50 + 15) & ~15
    info = lz4.block.decompress(bytes(bundle_bytes[bs:bs + blk_cs]), uncompressed_size=blk_ds)
    r = 16
    bc = struct.unpack('>I', info[r:r + 4])[0]
    r += 4
    blocks = []
    for _ in range(bc):
        bd = struct.unpack('>I', info[r:r + 4])[0]
        r += 4
        bc2 = struct.unpack('>I', info[r:r + 4])[0]
        r += 4
        bf = struct.unpack('>H', info[r:r + 2])[0]
        r += 2
        blocks.append((bd, bc2, bf))
    ds = bs + blk_cs
    if flags & 0x200:
        ds = (ds + 15) & ~15
    dec = bytearray()
    for bd, bc2, bf in blocks:
        raw = bytes(bundle_bytes[ds:ds + bc2])
        dec.extend(lz4.block.decompress(raw, uncompressed_size=bd) if bf & 2 else raw)
        ds += bc2
    return zlib.crc32(bytes(dec)) & 0xFFFFFFFF


def get_cab_raw(path):
    """Decompress a UnityFS bundle; return (cab_serialized_bytes, blocks, flags, nodes, dec, buf)."""
    with open(path, 'rb') as f:
        buf = bytearray(f.read())
    blk_cs = struct.unpack('>I', buf[38:42])[0]
    blk_ds = struct.unpack('>I', buf[42:46])[0]
    flags = struct.unpack('>I', buf[46:50])[0]
    bs = (50 + 15) & ~15
    info = lz4.block.decompress(bytes(buf[bs:bs + blk_cs]), uncompressed_size=blk_ds)
    r = 16
    bc = struct.unpack('>I', info[r:r + 4])[0]
    r += 4
    blocks = []
    for _ in range(bc):
        bd = struct.unpack('>I', info[r:r + 4])[0]
        r += 4
        bc2 = struct.unpack('>I', info[r:r + 4])[0]
        r += 4
        bf = struct.unpack('>H', info[r:r + 2])[0]
        r += 2
        blocks.append((bd, bc2, bf))
    ds = bs + blk_cs
    if flags & 0x200:
        ds = (ds + 15) & ~15
    dec = bytearray()
    for bd, bc2, bf in blocks:
        raw = bytes(buf[ds:ds + bc2])
        dec.extend(lz4.block.decompress(raw, uncompressed_size=bd) if bf & 2 else raw)
        ds += bc2
    node_cnt = struct.unpack('>i', info[r:r + 4])[0]
    r += 4
    nodes = []
    for _ in range(node_cnt):
        off = struct.unpack('>q', info[r:r + 8])[0]
        r += 8
        sz = struct.unpack('>q', info[r:r + 8])[0]
        r += 8
        nf = struct.unpack('>i', info[r:r + 4])[0]
        r += 4
        pe = info.find(b'\x00', r)
        p = info[r:pe].decode()
        r = pe + 1
        nodes.append((p, off, sz, nf))
    return bytes(dec[:nodes[0][2]]), blocks, flags, nodes, dec, buf


def walk_blob(blob):
    """Parse a MonoBehaviour BeatmapLevelSO blob; return dict of set info, or None."""
    try:
        o = 0
        o += 12  # m_GameObject PPtr
        o += 4   # m_Enabled u8 + align
        o += 12  # m_Script PPtr

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
        if not level_id:
            return None
        o += 12  # _previewAudioClip
        o += 32  # 8 floats
        o += 12  # _coverImage
        for _ in range(2):
            r, o = read_str(o)
            if r is None:
                return None
        cnt = struct.unpack_from('<i', blob, o)[0]
        o += 4
        if cnt < 0 or cnt > 20:
            return None
        for _ in range(cnt):
            r, o = read_str(o)
            if r is None:
                return None
        csc = struct.unpack_from('<i', blob, o)[0]
        o += 4
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


def build_modes_blob(orig_blob, info, enable_modes: list = None):
    """
    Return (new_blob, changed_bool). Preserves existing preview sets byte-for-byte,
    extends any target-mode set shipping with < TARGET_DIFFS difficulties to
    exactly 5 (padding with Standard's preview records), and appends missing
    target modes (cloned from Standard).

    If `enable_modes` is provided, only those modes (plus Standard) will be added.
    This allows partial pack deployments where only some songs get extra modes.
    """
    if enable_modes is None:
        enable_modes = TARGET_MODES  # default: all 4 modes

    sets_off = info['setsOff']
    head = orig_blob[:sets_off]
    content_rating = orig_blob[info['contentRatingOff']:info['contentRatingOff'] + 4]

    po = sets_off + 4
    existing = {}
    for s in info['sets']:
        fid = s['fileID']
        pid = s['pathID']
        dc = s['diffCount']
        existing[pid] = {
            'fileID': fid,
            'diffCount': dc,
            'diffs': orig_blob[po + 16:po + 16 + dc * DIFF_BYTES],
        }
        po += 16 + dc * DIFF_BYTES

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

    if len(template) < TARGET_DIFFS * DIFF_BYTES:
        template = template + template[:(TARGET_DIFFS * DIFF_BYTES - len(template))]
    template = template[:TARGET_DIFFS * DIFF_BYTES]

    final = []
    for pid, s in existing.items():
        diffs = s['diffs']
        dc = s['diffCount']
        if pid in CHAR_PATH_IDS.values() and dc < TARGET_DIFFS:
            existing_ranks = set()
            for d in range(dc):
                rank = struct.unpack_from('<i', diffs, d * DIFF_BYTES)[0]
                existing_ranks.add(rank)
            needed = TARGET_DIFFS - dc
            pad = bytearray()
            tpos = 0
            while len(pad) < needed * DIFF_BYTES and tpos + DIFF_BYTES <= len(template):
                rank = struct.unpack_from('<i', template, tpos)[0]
                if rank not in existing_ranks:
                    pad.extend(template[tpos:tpos + DIFF_BYTES])
                    existing_ranks.add(rank)
                tpos += DIFF_BYTES
            if len(pad) < needed * DIFF_BYTES:
                tpos = 0
                while len(pad) < needed * DIFF_BYTES and tpos + DIFF_BYTES <= len(template):
                    pad.extend(template[tpos:tpos + DIFF_BYTES])
                    tpos += DIFF_BYTES
            diffs = bytes(diffs) + bytes(pad[:needed * DIFF_BYTES])
            dc = TARGET_DIFFS
        final.append({'pathID': pid, 'fileID': s['fileID'], 'diffs': diffs, 'diffCount': dc})

    # Only add modes that are in enable_modes (plus Standard which is always included)
    for mode in TARGET_MODES:
        if mode == "Standard":
            continue
        if mode not in enable_modes:
            continue
        pid = CHAR_PATH_IDS[mode]
        if pid in existing:
            continue
        final.append({'pathID': pid, 'fileID': template_fid, 'diffs': template, 'diffCount': TARGET_DIFFS})

    b = bytearray(head)
    b += struct.pack('<i', len(final))
    for s in final:
        b += struct.pack('<i', s['fileID'])
        b += struct.pack('<q', s['pathID'])
        b += struct.pack('<i', s['diffCount'])
        b += s['diffs']
    b += content_rating
    return bytes(b), len(b) != len(orig_blob)


def rebuild_bundle(cab_raw, data_off, patch_obj_table, patches):
    """
    Apply blob patches to the CAB serialized file and fix up the object table.

    patches = list of (blob_start, old_size, new_blob). The object table record
    layout (Unity 2022.3, serializedVersion >= 22) is:
        pathID(i64) byteStart(i64, RELATIVE to data_off) byteSize(u32) typeID(i32)
    Each object's stored byte offset shifts ONLY by the deltas of patches that
    START before it (a patched blob's own content stays in place — only its size
    field changes). Handles any number of patches with correct cumulative shifts.
    """
    patched = bytearray(cab_raw)
    meta_region_end = data_off
    patches = sorted(patches, key=lambda x: x[0])
    deltas = [(ps, len(nb) - osz) for ps, osz, nb in patches]

    records = {}
    for pid, bstart, bsize in patch_obj_table:
        stored = bstart - data_off
        pat = struct.pack('<qQ', pid, stored)
        pos = patched.find(pat, 48, meta_region_end)
        if pos < 0:
            raise RuntimeError(f"object table record not found: pid={pid} stored={stored}")
        records[pid] = pos

    cum = 0
    for blob_start, old_size, new_blob in patches:
        actual_start = blob_start + cum
        patched[actual_start:actual_start + old_size] = new_blob
        cum += len(new_blob) - old_size

    for pid, bstart, bsize in patch_obj_table:
        shift = sum(d for ps, d in deltas if ps < bstart)
        new_stored = (bstart - data_off) + shift
        pos = records[pid]
        patched[pos + 8:pos + 16] = struct.pack('<Q', new_stored)
        own = [len(nb) for ps, osz, nb in patches if ps == bstart]
        if own:
            patched[pos + 16:pos + 20] = struct.pack('<I', own[0])

    patched[0x1C:0x20] = struct.pack('>I', len(patched))
    return bytes(patched)


def rebuild_bundle_file(cab_raw, blocks, flags, nodes, dec, buf, new_cab):
    """Rebuild the full UnityFS bundle around the patched CAB serialized file."""
    cab_key = nodes[0][0]
    cab_orig_sz = nodes[0][2]
    resS_key = cab_key + ".resS"
    res_key = cab_key + ".resource"
    resS_raw = b''
    res_raw = b''
    for p, off, sz, nf in nodes:
        if p == resS_key:
            resS_raw = bytes(dec[off:off + sz])
        elif p == res_key:
            res_raw = bytes(dec[off:off + sz])

    new_cab_sz = len(new_cab)
    stream = bytearray(dec)
    stream[:cab_orig_sz] = new_cab
    new_nodes = [
        (cab_key, 0, new_cab_sz, 4),
        (resS_key, new_cab_sz, len(resS_raw), 0),
        (res_key, new_cab_sz + len(resS_raw), len(res_raw), 0),
    ]
    BLOCK_SZ = 0x20000
    n_blocks = []
    n_comp = bytearray()
    for bs_ in range(0, len(stream), BLOCK_SZ):
        chunk = bytes(stream[bs_:bs_ + BLOCK_SZ])
        comp = lz4.block.compress(chunk, mode='high_compression', compression=9, store_size=False)
        if len(comp) < len(chunk):
            n_blocks.append((len(chunk), len(comp), 3))
            n_comp.extend(comp)
        else:
            n_blocks.append((len(chunk), len(chunk), 0))
            n_comp.extend(chunk)
    info_buf = b'\x00' * 16
    info_buf += struct.pack('>I', len(n_blocks))
    for bd, bc, bf in n_blocks:
        info_buf += struct.pack('>IIH', bd, bc, bf)
    info_buf += struct.pack('>I', len(new_nodes))
    for p, o, s, nf in new_nodes:
        info_buf += struct.pack('>QQI', o, s, nf) + p.encode() + b'\x00'
    info_comp = lz4.block.compress(bytes(info_buf), mode='high_compression', compression=9, store_size=False)

    tmp_buf = bytearray()
    tmp_buf.extend(b'UnityFS\x00')
    tmp_buf.extend(struct.pack('>I', 8))
    tmp_buf.extend(b'5.x.x\x00')
    tmp_buf.extend(b'2022.3.33f1\x00')
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


def update_catalog_entry(catalog_json, bundle_name_marker, new_crc, new_size):
    """
    Return a copy of the catalog dict with the m_Crc/m_BundleSize of the
    AssetBundleRequestOptions block containing `bundle_name_marker` updated.

    m_ExtraDataString is a BINARY concatenation of per-entry blocks (type byte,
    1-byte-length assembly name, class name, 4-byte JS length, UTF-16-LE JSON).
    We walk it byte-wise (like scan_pack_patch_data.decode_catalog_index) so we
    only ever touch the JSON of the matching block and never rely on whole-string
    UTF-16 alignment (which misaligns for some blocks and hides the marker).

    CRITICAL (Exp 188 fix): m_EntryDataString is a binary array of 28-byte entry
    records whose 5th int32 is a byte offset (dataIndex) into m_ExtraDataString,
    pointing at the start (type byte) of each block. When a block's JSON grows or
    shrinks (e.g. lizzo's m_Crc went 7 digits -> 10 digits, +6 bytes), every later
    block shifts — so ALL entry dataIndexes pointing past the patched block must
    be shifted by the same delta, or the game reads garbage and crashes right
    after loading the catalog (v0.5319 PS4 crash at OPEN #74).
    """
    marker_json = f'"m_BundleName":"{bundle_name_marker}"'
    ed = bytearray(base64.b64decode(catalog_json['m_ExtraDataString']))
    n = len(ed)
    found = False
    i = 0
    while i < n:
        if ed[i] != 7:
            i += 1
            continue
        try:
            ln = ed[i + 1]
            po = i + 2 + ln
            ln = ed[po]
            po = po + 1 + ln
            jslen = struct.unpack_from('<I', ed, po)[0]
            po += 4
        except Exception:
            i += 1
            continue
        if jslen <= 0 or jslen > 400000 or po + jslen > n:
            i = po + jslen if (jslen > 0 and po + jslen <= n) else i + 1
            continue
        js = ed[po:po + jslen]
        s = js.decode('utf-16-le', 'replace')
        if marker_json not in s:
            i = po + jslen
            continue
        block, old_crc, old_size = _parse_catalog_block(s, bundle_name_marker)
        if old_crc is None or old_size is None:
            raise ValueError(f"Could not parse catalog block for {bundle_name_marker!r}")
        block_new = block.replace(f'"m_Crc":{old_crc}', f'"m_Crc":{new_crc}')
        block_new = block_new.replace(f'"m_BundleSize":{old_size}', f'"m_BundleSize":{new_size}')
        s2 = s.replace(block, block_new)
        new_js = s2.encode('utf-16-le')
        ed[po - 4:po - 4 + 4] = struct.pack('<I', len(new_js))
        ed[po:po + jslen] = new_js
        delta = len(new_js) - jslen
        if delta != 0 and 'm_EntryDataString' in catalog_json:
            # Shift every entry dataIndex that points past this block's start.
            edi = bytearray(base64.b64decode(catalog_json['m_EntryDataString']))
            cnt = struct.unpack_from('<I', edi, 0)[0]
            off = 4
            for _ in range(cnt):
                rec = list(struct.unpack_from('<7i', edi, off))
                if rec[4] > i:
                    rec[4] += delta
                edi[off:off + 28] = struct.pack('<7i', *rec)
                off += 28
            catalog_json['m_EntryDataString'] = base64.b64encode(bytes(edi)).decode()
        found = True
        break
    if not found:
        raise ValueError(f"BundleName marker {bundle_name_marker!r} not found in catalog")
    cat2 = dict(catalog_json)
    cat2['m_ExtraDataString'] = base64.b64encode(bytes(ed)).decode()
    return cat2


def _parse_catalog_block(s, bundle_name_marker):
    """Extract (exact JSON block text, m_Crc, m_BundleSize) from a single block string."""
    i = s.find(bundle_name_marker)
    j = s.rfind('{', 0, i)
    k = s.find('}', i)
    block = s[j:k + 1]
    crc_m = re.search(r'"m_Crc":\s*(\d+)', block)
    size_m = re.search(r'"m_BundleSize":\s*(\d+)', block)
    old_crc = crc_m.group(1) if crc_m else None
    old_size = size_m.group(1) if size_m else None
    return block, old_crc, old_size


def validate_catalog_dataindexes(catalog_json):
    """
    Validate a catalog's m_EntryDataString against its m_ExtraDataString.

    Every entry record's 5th int32 is a byte offset (dataIndex) into
    m_ExtraDataString pointing at the type byte (7) of a block. Returns
    (total, nonzero, bad) where bad counts dataIndexes that are >= 0 but do
    NOT point at a type-7 block start. A nonzero `bad` is the signature of
    the v0.5319 PS4 crash (game reads garbage right after loading the catalog).
    """
    edi = base64.b64decode(catalog_json['m_EntryDataString'])
    ex = base64.b64decode(catalog_json['m_ExtraDataString'])
    cnt = struct.unpack_from('<I', edi, 0)[0]
    o = 4
    bad = 0
    nonzero = 0
    for _ in range(cnt):
        rec = struct.unpack_from('<7i', edi, o)
        o += 28
        di = rec[4]
        if di != 0:
            nonzero += 1
        if di >= 0 and (di >= len(ex) or ex[di] != 7):
            bad += 1
    return cnt, nonzero, bad


def find_catalog_entry_js(catalog_json, bundle_name_marker):
    """
    Return the UTF-16 JSON text of the catalog block whose m_BundleName equals
    `bundle_name_marker`, or None. Byte-wise walk (type-7 blocks) — does NOT rely
    on whole-string UTF-16 alignment (which misaligns for some blocks).
    """
    marker_json = f'"m_BundleName":"{bundle_name_marker}"'
    ed = base64.b64decode(catalog_json['m_ExtraDataString'])
    n = len(ed)
    i = 0
    while i < n:
        if ed[i] != 7:
            i += 1
            continue
        try:
            ln = ed[i + 1]
            po = i + 2 + ln
            ln = ed[po]
            po = po + 1 + ln
            jslen = struct.unpack_from('<I', ed, po)[0]
            po += 4
        except Exception:
            i += 1
            continue
        if jslen <= 0 or jslen > 400000 or po + jslen > n:
            i += 1
            continue
        s = ed[po:po + jslen].decode('utf-16-le', 'replace')
        if marker_json in s:
            return s
        i = po + jslen
    return None


def validate_catalog_entries(catalog_json, entries):
    """
    Validate that every entry's catalog block carries the expected m_Crc and
    m_BundleSize (i.e. the merged catalog was actually regenerated from these
    patched bundles, not left stale). `entries` is a list of (bundleNameMarker,
    expected_crc, expected_size). Returns (missing, mismatched) lists.
    """
    missing, mismatched = [], []
    for marker, crc, size in entries:
        s = find_catalog_entry_js(catalog_json, marker)
        if s is None:
            missing.append(marker)
            continue
        if f'"m_Crc":{crc}' not in s or f'"m_BundleSize":{size}' not in s:
            mismatched.append(marker)
    return missing, mismatched


def patched_bundle_name(original_bundle_name):
    """Derive the patched pack bundle filename from the original one."""
    return os.path.basename(original_bundle_name).replace('_assets_all_', '_modes_assets_all_')


def patch_pack_bundle(song_ids_data, album, dump_dir, out_dir, enable_modes: list = None,
                      target_slots: list = None):
    """
    Patch one pack album. Returns a result dict or None.
    result keys: pack, packBundle (original name), patchedBundle (name),
                 local_path, size, crc, catalogBundleName, patched_slots.

    If `enable_modes` is provided, only those modes (plus Standard) will be
    enabled in the pack bundle. This is used for partial pack deployments
    where only some songs in the pack are custom and should show extra modes.

    If `target_slots` is provided, only patch BeatmapLevelSOs for those specific
    song slots. This allows surgical patching of only custom songs in the pack.
    """
    pack = album['pack']
    if 'packBundle' not in album or 'catalogBundleName' not in album:
        return None
    original_name = album['packBundle']
    bundle_path = os.path.join(dump_dir, "Media/StreamingAssets/aa/PS4", original_name)
    if not os.path.isfile(bundle_path) or os.path.getsize(bundle_path) == 0:
        return None

    from UnityPy import Environment
    cab_raw, blocks, flags, nodes, dec, buf = get_cab_raw(bundle_path)
    data_off = struct.unpack('>I', cab_raw[0x14:0x18])[0]
    data_off = (48 + data_off + 15) & ~15

    env = Environment(bundle_path)
    bf = list(env.files.values())[0]
    cab_key = next(k for k in bf.files if k.startswith('CAB-') and '.res' not in k)
    cab_obj = bf.files[cab_key]
    obj_table = sorted(
        [(pid, o.byte_start, o.byte_size) for pid, o in cab_obj.objects.items()],
        key=lambda x: x[1]
    )

    patches = []
    patched_slots = 0
    # Case-insensitive target slot matching (PS4 redirects may carry different
    # casing than song_ids.json, e.g. "Crystallized" vs "crystallized")
    target_slots_lower = {s.lower() for s in target_slots} if target_slots is not None else None
    for song in album['songs']:
        if 'patchPathID' not in song:
            continue
        # If target_slots is provided, only patch those specific slots
        if target_slots_lower is not None and song['songID'].lower() not in target_slots_lower:
            continue
        obj = cab_obj.objects.get(song['patchPathID'])
        if obj is None:
            continue
        blob = bytes(cab_raw[obj.byte_start:obj.byte_start + obj.byte_size])
        info = walk_blob(blob)
        if info is None or info['levelID'] != song['songID']:
            continue
        new_blob, changed = build_modes_blob(blob, info, enable_modes=enable_modes)
        if not changed:
            continue
        patches.append((obj.byte_start, obj.byte_size, new_blob))
        patched_slots += 1

    if not patches:
        return None

    new_cab = rebuild_bundle(cab_raw, data_off, obj_table, patches)
    new_bundle = rebuild_bundle_file(cab_raw, blocks, flags, nodes, dec, buf, new_cab)
    actual_crc = crc_decompressed_stream(new_bundle)

    out_name = patched_bundle_name(original_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, out_name)
    with open(out_path, 'wb') as f:
        f.write(new_bundle)

    return {
        'pack': pack,
        'packBundle': original_name,
        'patchedBundle': out_name,
        'local_path': out_path,
        'size': len(new_bundle),
        'crc': actual_crc,
        'catalogBundleName': album['catalogBundleName'],
        'patched_slots': patched_slots,
    }


def _manifest_path(out_dir):
    return os.path.join(out_dir, 'manifest.json')


def load_manifest(out_dir):
    """Load build results recorded in <out_dir>/manifest.json. [] if none."""
    p = _manifest_path(out_dir)
    if os.path.isfile(p):
        try:
            with open(p) as f:
                data = json.load(f)
                return [e for e in data.get('entries', [])
                        if isinstance(e, dict) and e.get('pack')]
        except Exception:
            return []
    return []


def _save_manifest(out_dir, results):
    """Merge the latest MODES build results into the manifest (per-pack, keyed
    by pack) — WITHOUT dropping previews-VARIANT rows.

    Exp 269c: a pack has up to TWO manifest rows sharing its pack key — the
    modes row (this builder's) and the modes+previews variant row (the
    previews pipeline's, carries 'previews'). Keying the merge purely by pack
    made every modes rebuild CLOBBER the variant rows; the post-deploy check
    then compared the (stale) modes CRCs against the deployed catalog (which
    correctly carries the variant's) and failed validation on all 5 packs —
    twice, in two different shapes. Variant rows are preserved here; only the
    variant builder (_record_previews_manifest) ever replaces them, by
    patchedBundle name. Duplicate variant rows (same patchedBundle) dedupe
    to the newest previewsAt."""
    modes_rows = {}
    variant_rows = {}
    for r in load_manifest(out_dir):
        if 'previews' in r:
            key = r.get('patchedBundle') or r.get('bundle') or r['pack']
            old = variant_rows.get(key)
            if old is None or r.get('previewsAt', 0) >= old.get('previewsAt', 0):
                variant_rows[key] = r
        else:
            modes_rows[r['pack']] = r
    for r in results:
        modes_rows[r['pack']] = r
    entries = sorted(list(modes_rows.values()) + list(variant_rows.values()),
                     key=lambda r: r['pack'])
    with open(_manifest_path(out_dir), 'w') as f:
        json.dump({'entries': entries}, f, indent=2)


def build_pack_mode_bundles(song_ids_path=SONG_IDS_PATH, dump_dir=None, out_dir=None,
                            packs=None, enable_modes: list = None, target_slots: list = None):
    """
    Build patched pack bundles for the selected packs. Returns list of result dicts.

    packs=None -> all albums in song_ids.json that have patch data.
    out_dir=None -> <project_root>/pack_modes_bundles.
    dump_dir=None -> <project_root>/ps4_dump/CUSA12878-patch.
    enable_modes=None -> all 4 modes (Standard, OneSaber, NoArrows, 90Degree).
    target_slots=None -> patch all songs in the pack (for partial deploy, specify only custom song slots).
    """
    if out_dir is None:
        out_dir = os.path.join(PROJECT_ROOT, "pack_modes_bundles")
    if dump_dir is None:
        dump_dir = os.path.join(PROJECT_ROOT, "ps4_dump", "CUSA12878-patch")
    with open(song_ids_path) as f:
        data = json.load(f)
    results = []
    for album in data['albums']:
        if packs and album['pack'] not in packs:
            continue
        result = patch_pack_bundle(data, album, dump_dir, out_dir, enable_modes=enable_modes, target_slots=target_slots)
        if result:
            results.append(result)
    _save_manifest(out_dir, results)
    return results


def write_merged_catalog(dump_catalog_path, results, out_path):
    """
    Write a copy of the game catalog with m_Crc/m_BundleSize updated for every
    patched pack in `results`. Returns the number of entries updated.
    """
    with open(dump_catalog_path) as f:
        cat = json.load(f)
    updated = 0
    for r in results:
        cat = update_catalog_entry(cat, r['catalogBundleName'], r['crc'], r['size'])
        updated += 1
    d = os.path.dirname(out_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(cat, f)
        f.write('\n')
    return updated


def main():
    args = sys.argv[1:]
    write = '--write' in args
    packs = None
    dump_dir = None
    enable_modes = None
    if '--packs' in args:
        packs = [p.strip() for p in args[args.index('--packs') + 1].split(',')]
    if '--dump-dir' in args:
        dump_dir = args[args.index('--dump-dir') + 1]
    if '--enable-modes' in args:
        enable_modes = [m.strip() for m in args[args.index('--enable-modes') + 1].split(',')]

    results = build_pack_mode_bundles(packs=packs, dump_dir=dump_dir, enable_modes=enable_modes)
    print(f"Packs patched: {len(results)}")
    for r in results:
        print(f"  {r['pack']:20s} {r['patchedBundle']} ({r['size']:,} B, crc={r['crc']}) "
              f"slots={r['patched_slots']}")
    if write:
        cat_out = os.path.join(PROJECT_ROOT, "catalog_pack_modes.json")
        cat_path = os.path.join(PROJECT_ROOT, "ps4_dump", "CUSA12878-patch",
                                "Media/StreamingAssets/aa/catalog.json")
        if dump_dir:
            cat_path = os.path.join(dump_dir, "Media/StreamingAssets/aa/catalog.json")
        n = write_merged_catalog(cat_path, results, cat_out)
        print(f"Wrote {cat_out} ({n} catalog entries updated)")
    else:
        print("Dry run (bundles written; catalog written only with --write).")


if __name__ == '__main__':
    main()
