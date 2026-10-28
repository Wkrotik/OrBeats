#!/usr/bin/env python3
"""
Scan ALL Beat Saber PS4 pack bundles and extract the identifiers + binary layout
needed to patch each pack's BeatmapLevelSO objects (add OneSaber/NoArrows/90Degree
preview sets) and update the Addressables catalog entry for that pack.

Writes the results into beat_saber_song_ids.json (per-album catalog identifiers +
per-song patch identifiers) so the pipeline can rebuild patched pack bundles for any
custom-song slot without re-scanning the dump.

Output additions:
  album-level:
    catalogBundleName   m_BundleName hash from the catalog AssetBundleRequestOptions
    catalogCrc          original m_Crc (unsigned int32)
    catalogBundleSize   original m_BundleSize
    catalogDataIndex    byte offset into m_ExtraDataString where the JSON block starts
    packBundleSize      on-disk size of the pack bundle (should equal catalogBundleSize)
  song-level:
    patchPathID         object pathID of the BeatmapLevelSO in the pack CAB
    blobOffset          byte_start of the blob within the CAB serialized file
    blobSize            byte_size of the blob
    previewSetCount     current number of _previewDifficultyBeatmapSets

Usage:
    python3 development/scripts/scan_pack_patch_data.py [--write]
Without --write the scan results are validated and printed only.
"""

import sys, os, json, struct, base64, re
import lz4.block
from UnityPy import Environment

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DUMP = "/workspace/ps4_dump/CUSA12878-patch"
SONG_IDS_PATH = os.path.join(PROJECT_ROOT, "beat_saber_song_ids.json")
CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
    "360Degree": 4533580413116749821,
}


def get_cab_raw(path):
    """Decompress bundle and extract CAB raw bytes + metadata."""
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
    return bytes(dec[:nodes[0][2]]), buf


def walk_blob(blob):
    """Walk a serialized MonoBehaviour BeatmapLevelSO blob; return dict with offsets.

    Returns None if the blob does not look like a BeatmapLevelSO (e.g. no _levelID).
    """
    try:
        o = 0
        # m_GameObject PPtr (fileID i32 + pathID i64) = 12 bytes
        o += 12
        # m_Enabled u8 + align to 4
        o += 4
        # m_Script PPtr = 12 bytes
        o += 12
        # m_Name: aligned length-prefixed string (int32 len + data + pad to 4)
        def read_str(o):
            n = struct.unpack_from('<i', blob, o)[0]
            if n < 0 or n > 200:
                return None
            if n == 0:
                return '', o + 4  # empty string: just the length prefix
            data = blob[o + 4:o + 4 + n]
            o += 4 + n
            o = (o + 3) // 4 * 4  # pad to 4-byte alignment
            return data.decode('utf-8', 'replace'), o
        r, o = read_str(o)
        if r is None:
            return None
        # _version i32
        o += 4
        # 5 aligned strings: _levelID _songName _songSubName _songAuthorName _levelAuthorName
        strings = []
        for _ in range(5):
            r, o = read_str(o)
            if r is None:
                return None
            strings.append(r)
        level_id = strings[0]
        if not level_id:
            return None
        # _previewAudioClip PPtr = 12 bytes
        o += 12
        # 8 x float: bpm lufs timeOffset shuffle shufflePeriod previewStart previewDuration songDuration
        o += 32
        # _coverImage PPtr = 12 bytes
        o += 12
        # _environmentName, _allDirectionsEnvironmentName (each: _environmentName string)
        for _ in range(2):
            r, o = read_str(o)
            if r is None:
                return None
        # _environmentNames array
        cnt = struct.unpack_from('<i', blob, o)[0]; o += 4
        if cnt < 0 or cnt > 20:
            return None
        for _ in range(cnt):
            r, o = read_str(o)
            if r is None:
                return None
        # _colorSchemes array of ColorScheme structs
        csc = struct.unpack_from('<i', blob, o)[0]; o += 4
        if csc < 0 or csc > 100:
            return None
        for _ in range(csc):
            # ColorScheme: id string, _overrideNotes i32, 7x Color (4 floats each),
            # _overrideLights i32
            r, o = read_str(o)
            if r is None:
                return None
            o += 4 + 28 * 4 + 4  # overrideNotes + 7 colors + overrideLights
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
            po += 16 + dc * 36
        content_rating_off = po
        cr = struct.unpack_from('<i', blob, po)[0]
        return {
            'levelID': level_id,
            'songName': strings[1],
            'setsOff': sets_off,
            'setCount': sc,
            'sets': sets,
            'contentRatingOff': content_rating_off,
            'contentRating': cr,
            'blobLen': len(blob),
            'trailing': blob[po + 4:],
        }
    except Exception:
        return None


def scan_pack_bundle(path, pack_name):
    """Return per-slot patch data for a pack bundle."""
    cab_raw, _ = get_cab_raw(path)
    env = Environment(path)
    bf = list(env.files.values())[0]
    cab_key = next(k for k in bf.files if k.startswith('CAB-') and '.res' not in k)
    cab_obj = bf.files[cab_key]
    data_off = struct.unpack('>I', cab_raw[0x14:0x18])[0]
    data_off = (48 + data_off + 15) & ~15
    slots = []
    for pid, o in cab_obj.objects.items():
        if o.type.name != 'MonoBehaviour':
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        if not tt.get('_levelID'):
            continue
        blob = cab_raw[o.byte_start:o.byte_start + o.byte_size]
        info = walk_blob(blob)
        if info is None:
            print(f"  !! {pack_name}: blob walk failed for {tt.get('_levelID')} (pathID {pid})")
            continue
        if info['levelID'] != tt.get('_levelID'):
            print(f"  !! {pack_name}: levelID mismatch walker={info['levelID']} typetree={tt.get('_levelID')}")
            continue
        slots.append({
            'songID': info['levelID'],
            'patchPathID': pid,
            'blobOffset': o.byte_start,
            'blobSize': o.byte_size,
            'previewSetCount': info['setCount'],
        })
    return slots, data_off


def load_catalog():
    cat_path = os.path.join(DUMP, "Media/StreamingAssets/aa/catalog.json")
    with open(cat_path) as f:
        return json.load(f)


def decode_catalog_index(cat):
    """Decode bucket/key/entry/extra data to map bundle filename -> (m_BundleName, dataIndex)."""
    def read_str1(b, o):
        ln = b[o]; o += 1
        return b[o:o + ln].decode('utf-8', 'replace'), o + ln
    def read_str4(b, o):
        ln = struct.unpack_from('<I', b, o)[0]; o += 4
        return b[o:o + ln].decode('utf-8', 'replace'), o + ln
    def read_str4u(b, o):
        ln = struct.unpack_from('<I', b, o)[0]; o += 4
        return b[o:o + ln].decode('utf-16-le', 'replace'), o + ln

    buck = base64.b64decode(cat['m_BucketDataString'])
    bc = struct.unpack_from('<I', buck, 0)[0]
    o = 4; buckets = []
    for i in range(bc):
        off = struct.unpack_from('<I', buck, o)[0]; o += 4
        ec = struct.unpack_from('<I', buck, o)[0]; o += 4
        entries = list(struct.unpack_from('<%dI' % ec, buck, o)); o += 4 * ec
        buckets.append((off, entries))

    kd = base64.b64decode(cat['m_KeyDataString'])
    kc = struct.unpack_from('<I', kd, 0)[0]
    keys = []
    for i, (off, _en) in enumerate(buckets[:kc]):
        po = off; t = kd[po]; po += 1
        if t == 0: s, po = read_str4(kd, po)
        elif t == 1: s, po = read_str4u(kd, po)
        elif t == 5: s, po = read_str1(kd, po)
        else: s = f'<t{t}>'
        keys.append(s)

    ed = base64.b64decode(cat['m_EntryDataString'])
    ec2 = struct.unpack_from('<I', ed, 0)[0]
    o = 4; entries = []
    for i in range(ec2):
        rec = struct.unpack_from('<7i', ed, o); o += 28
        entries.append(rec)

    ex = base64.b64decode(cat['m_ExtraDataString'])
    mapping = {}
    for i, key in enumerate(keys):
        if not key.endswith('.bundle'):
            continue
        for loc in buckets[i][1]:
            e = entries[loc]
            di = e[4]
            if di < 0:
                continue
            t = ex[di]
            if t != 7:
                continue
            ln = ex[di + 1]; asm = ex[di + 2:di + 2 + ln].decode('utf-8', 'replace')
            po = di + 2 + ln
            ln = ex[po]; cls = ex[po + 1:po + 1 + ln].decode('utf-8', 'replace')
            po = po + 1 + ln
            jslen = struct.unpack_from('<I', ex, po)[0]; po += 4
            js = ex[po:po + jslen].decode('utf-16-le', 'replace')
            bn = re.search(r'\"m_BundleName\":\"([^\"]+)\"', js)
            sz = re.search(r'\"m_BundleSize\":(\d+)', js)
            crc = re.search(r'\"m_Crc\":(\d+)', js)
            if bn:
                mapping.setdefault(key, {
                    'm_BundleName': bn.group(1),
                    'm_BundleSize': int(sz.group(1)) if sz else None,
                    'm_Crc': int(crc.group(1)) if crc else None,
                    'dataIndex': di,
                })
    return mapping


def main():
    write = '--write' in sys.argv
    data = json.load(open(SONG_IDS_PATH))
    cat = load_catalog()
    cat_index = decode_catalog_index(cat)
    print(f"Catalog index: {len(cat_index)} bundles mapped")
    all_ok = True
    updated_albums = 0
    updated_songs = 0

    for album in data['albums']:
        pack = album['pack']
        bundle_name = album.get('packBundle', '')
        bundle_path = os.path.join(DUMP, "Media/StreamingAssets/aa/PS4", bundle_name)
        if not os.path.isfile(bundle_path) or os.path.getsize(bundle_path) == 0:
            print(f"  !! {pack}: bundle missing/empty: {bundle_name}")
            all_ok = False
            continue
        cat_info = cat_index.get(bundle_name)
        if not cat_info:
            print(f"  !! {pack}: no catalog entry for {bundle_name}")
            all_ok = False
            continue

        slots, data_off = scan_pack_bundle(bundle_path, pack)
        slot_map = {s['songID']: s for s in slots}
        missing = [s['songID'] for s in album['songs'] if s['songID'] not in slot_map]
        if missing:
            print(f"  !! {pack}: songs missing BeatmapLevelSO: {missing}")
            all_ok = False

        album['catalogBundleName'] = cat_info['m_BundleName']
        album['catalogCrc'] = cat_info['m_Crc']
        album['catalogBundleSize'] = cat_info['m_BundleSize']
        album['catalogDataIndex'] = cat_info['dataIndex']
        album['packBundleSize'] = os.path.getsize(bundle_path)
        album['patchDataOffset'] = data_off
        updated_albums += 1

        for song in album['songs']:
            s = slot_map.get(song['songID'])
            if not s:
                continue
            song['patchPathID'] = s['patchPathID']
            song['blobOffset'] = s['blobOffset']
            song['blobSize'] = s['blobSize']
            song['previewSetCount'] = s['previewSetCount']
            updated_songs += 1

        print(f"  OK {pack:20s} bundle={bundle_name[:45]:45s} size={album['packBundleSize']:>9,} "
              f"cat={cat_info['m_BundleName'][:16]}... dataIndex={cat_info['dataIndex']:6d} slots={len(slots)}")

    print(f"\nAlbums updated: {updated_albums}/{len(data['albums'])}")
    print(f"Songs updated: {updated_songs}")
    if not all_ok:
        print("SCAN ISSUES FOUND — not writing")
        sys.exit(1)
    if write:
        with open(SONG_IDS_PATH, 'w') as f:
            json.dump(data, f, indent=2)
            f.write('\n')
        print(f"Wrote {SONG_IDS_PATH}")
    else:
        print("Dry run OK — rerun with --write to persist.")


if __name__ == '__main__':
    main()
