#!/usr/bin/env python3
"""
M10 Phase 1 spike — Song preview patcher for pack bundles (Exp 269).

Patches each custom song slot's preview AudioClip in a music-pack bundle so
the song menu plays the CUSTOM song's own ~10s preview instead of the stock
song's clip.

Approach (plan: .agent/plans/song-previews.md):
  1. SOURCE: the slot's own deployed per-song custom bundle (custom_songs/
     or mass_bundles/) — the exact FSB5 PCM16 audio gameplay plays.
  2. PREVIEW START: the mapper's Info.dat _previewStartTime when the source
     dir is available; otherwise the busiest-section heuristic computed from
     the beatmaps embedded in the custom bundle (note density peaks).
  3. CUT: 10.0 s @ 44.1 kHz stereo 16-bit, 8 ms fade-in / 250 ms fade-out.
  4. NORMALIZE: target -10.4 dBFS RMS (stock preview fleet average), peak
     limit -1.0 dBFS; applied only when the cut deviates > 3 dB.
  5. FORMAT: FSB5 PCM16 (mode 2) — our hardware-proven codec (Q1: mirror
     m_CompressionFormat=1 + m_LoadType=1 + m_LoadInBackground/legacy3D true,
     exactly like both our proven clips and stock).
  6. PATCH: append the FSB5 to the pack bundle's .resource stream; repoint the
     AudioClip's m_Resource.m_Offset/m_Size in place (16 bytes; same blob
     length → zero object-table shifts). SO floats untouched (stock
     _previewStartTime=0.0/_previewDuration=10.0 already play a pre-cut clip
     from 0.0).
  7. CRC + catalog via the existing build_pack_mode_bundles machinery.

This is the development-script proving ground; once hardware-validated it
moves into the production pipeline behind the enable_song_previews flag.
"""
import array
import io
import json
import math
import os
import struct
import sys
import wave

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, 'orbeats', 'tools'))
import UnityPy  # noqa: E402
import lz4.block  # noqa: E402

from build_pack_mode_bundles import (  # noqa: E402
    get_cab_raw, rebuild_bundle, rebuild_bundle_file, crc_decompressed_stream,
    patched_bundle_name, walk_blob,
)

PREVIEW_SECONDS = 10.0
PREVIEW_TARGET_DBFS = -10.4          # stock preview fleet average (Exp 269 measurement)
PREVIEW_TOLERANCE_DB = 3.0          # only normalize when further off than this
PREVIEW_PEAK_DBFS = -1.0            # peak limit
FADE_IN_MS = 8.0
FADE_OUT_MS = 250.0
SAMPLE_RATE = 44100


# ── Step 1: extract full PCM from the slot's custom bundle ──────────────────

def pcm_from_custom_bundle(bundle_path):
    """Return (pcm_int16_array_interleaved, sample_rate, channels, duration_s)."""
    env = UnityPy.load(bundle_path)
    for obj in env.objects:
        if obj.type.name == 'AudioClip':
            d = obj.read(check_read=False)
            for _k, wav in d.samples.items():
                w = wave.open(io.BytesIO(wav))
                assert w.getnchannels() == 2 and w.getframerate() == SAMPLE_RATE, \
                    f"unexpected audio shape in {bundle_path}"
                data = array.array('h')
                data.frombytes(w.readframes(w.getnframes()))
                return data, w.getframerate(), w.getnchannels(), w.getnframes() / float(SAMPLE_RATE)
    raise RuntimeError(f"no AudioClip in {bundle_path}")


# ── Step 2: preview start time ──────────────────────────────────────────────

def preview_start_from_info(song_dir):
    """Read the mapper's chosen preview start from Info.dat (V2/V3/V4). None if absent."""
    ip = os.path.join(song_dir, 'Info.dat')
    if not os.path.isfile(ip):
        return None
    try:
        d = json.load(open(ip))
        ps = d.get('_previewStartTime')
        if ps is None and isinstance(d.get('audio'), dict):
            ps = d['audio'].get('previewStartTime')
        if ps is None:
            return None
        return float(ps)
    except Exception:
        return None


def preview_start_from_beatmaps(bundle_path, duration_s, bpm=None):
    """Fallback heuristic: the busiest 10s window of the bundle's own STANDARD
    beatmaps (in sync with the deployed audio by construction), beat-times
    converted to seconds via the map's bpmEvents m field, snapped back to a
    4-beat bar so the preview starts musically.

    Exp 269 lessons baked in:
      - m_Script decodes via surrogateescape (KB: surrogateescape-encoding)
      - notes carry beat values b/_time — must convert via BPM (m field of
        bpmEvents, the PS4-native format the pipeline writes)
      - mode clones (OneSaber/NoArrows/90Degree) duplicate density — excluded
      - lightshow/audio TextAssets excluded
    Returns seconds or None.
    """
    import bisect
    import gzip
    try:
        env = UnityPy.load(bundle_path)
        notes_b = []
        bpm_found = None
        for obj in env.objects:
            if obj.type.name != 'TextAsset':
                continue
            d = obj.read(check_read=False)
            name = d.m_Name or ''
            if 'lightshow' in name or 'audio' in name:
                continue
            if any(m in name for m in ('OneSaber', 'NoArrows', '90Degree')):
                continue
            try:
                raw = d.m_Script.encode('utf-8', 'surrogateescape')
                bt = json.loads(gzip.decompress(raw).decode('utf-8', 'replace'))
            except Exception:
                continue
            if bpm_found is None:
                for e in (bt.get('bpmEvents') or []):
                    m = e.get('m')
                    if m and 40.0 <= float(m) <= 400.0:
                        bpm_found = float(m)
                        break
            notes = bt.get('_notes') or bt.get('colorNotes') or []
            for n in notes:
                t = n.get('_time', n.get('b'))
                if t is not None:
                    notes_b.append(float(t))
        if not notes_b or not bpm_found:
            return None
        use_bpm = bpm or bpm_found
        secs = sorted(b * 60.0 / use_bpm for b in notes_b)
        last_s = secs[-1]
        best = (0.0, -1)
        ws = max(2.0, last_s * 0.05)     # skip intros (<5% or <2s)
        while ws < last_s - PREVIEW_SECONDS:
            lo = bisect.bisect_left(secs, ws)
            hi = bisect.bisect_right(secs, ws + PREVIEW_SECONDS)
            n = hi - lo
            if n > best[1]:
                best = (ws, n)
            ws += 1.0
        if best[1] < 0:
            return None
        # snap back to a 4-beat bar boundary (musical entry)
        bar = 4.0 * 60.0 / use_bpm
        start = best[0] - (best[0] % bar)
        return max(0.0, start)
    except Exception:
        return None


# ── Step 3+4: cut + fades + normalize ───────────────────────────────────────

def rms_db(data):
    if not data:
        return -96.0
    ssq = sum(x * x for x in data)
    return 20 * math.log10(max(1e-9, math.sqrt(ssq / len(data))) / 32768.0)


def cut_preview(pcm, start_s, duration_s):
    """Cut [start, start+10) seconds; apply fades; normalize. Returns int16 array."""
    sr = SAMPLE_RATE
    ch = 2
    n_frames = len(pcm) // ch
    start_f = max(0, min(int(start_s * sr), max(0, n_frames - int(PREVIEW_SECONDS * sr))))
    end_f = min(n_frames, start_f + int(PREVIEW_SECONDS * sr))
    seg = array.array('h', pcm[start_f * ch:end_f * ch])

    # pad to exactly 10s if the source ended early
    want = int(PREVIEW_SECONDS * sr) * ch
    if len(seg) < want:
        seg.extend(array.array('h', bytes(2 * (want - len(seg)))))

    # normalize (only if > tolerance off target)
    cur_db = rms_db(seg)
    if abs(cur_db - PREVIEW_TARGET_DBFS) > PREVIEW_TOLERANCE_DB:
        gain = (10 ** (PREVIEW_TARGET_DBFS / 20.0) * 32768) / max(1e-9, math.sqrt(sum(x*x for x in seg)/len(seg)))
        seg = array.array('h', [max(-32768, min(32767, int(x * gain))) for x in seg])

    # peak limit
    peak = max((abs(x) for x in seg), default=0)
    peak_target = int(10 ** (PREVIEW_PEAK_DBFS / 20.0) * 32768)
    if peak > peak_target:
        lim = peak_target / peak
        seg = array.array('h', [int(x * lim) for x in seg])

    # fades
    fi = int(FADE_IN_MS / 1000 * sr) * ch
    fo = int(FADE_OUT_MS / 1000 * sr) * ch
    for i in range(min(fi, len(seg))):
        seg[i] = int(seg[i] * (i / fi))
    for i in range(min(fo, len(seg))):
        j = len(seg) - 1 - i
        seg[j] = int(seg[j] * (i / fo))
    return seg


# ── Step 5: FSB5 PCM16 container (mirrors hevag_encoder.build_pcm16_fsb5) ───

def build_preview_fsb5(pcm):
    """Wrap 10s stereo PCM16 in the exact FSB5 our proven clips use."""
    pcm_bytes = pcm.tobytes()
    total_frames = len(pcm) // 2
    shs = 65
    header = bytearray(128)
    header[0:4] = b'FSB5'
    struct.pack_into('<I', header, 4, 1)          # version
    struct.pack_into('<I', header, 8, 1)          # numSamples
    struct.pack_into('<I', header, 12, shs)       # sampleHeaderSize
    struct.pack_into('<I', header, 16, 0)         # dataSize low? (see below)
    struct.pack_into('<I', header, 20, len(pcm_bytes))
    struct.pack_into('<I', header, 24, 2)          # mode = PCM16
    struct.pack_into('<I', header, 28, 1)
    struct.pack_into('<I', header, 32, 0)
    sd = (1 | (8 & 0xF) << 1 | (1 & 1) << 5 |
          (0 & 0xFFFFFFF) << 6 | (total_frames & 0x3FFFFFFF) << 34)
    struct.pack_into('<Q', header, 60, sd)
    struct.pack_into('<I', header, 68, 1 | (1 << 1) | (1 << 25))
    header[72] = 2
    struct.pack_into('<I', header, 73, 0 | (4 << 1) | (2 << 25))
    struct.pack_into('<I', header, 77, SAMPLE_RATE)

    result = bytearray()
    result.extend(header[:81])
    result.extend(b'\x00' * (60 + shs - 81))
    result.extend(pcm_bytes)
    return bytes(result)


# ── Step 6: pack bundle preview patch ────────────────────────────────────────

def parse_audioclip_blob(raw):
    """Return (tail_offset, m_Offset, m_Size, m_CompressionFormat) via archive: anchor."""
    a = raw.find(b'archive:/')
    if a < 0:
        raise RuntimeError('no archive:/ anchor in AudioClip blob')
    src_len_pos = a - 4
    src_len = struct.unpack('<I', raw[src_len_pos:src_len_pos + 4])[0]
    tail_at = src_len_pos + 4 + src_len
    if tail_at % 4:
        tail_at += 4 - (tail_at % 4)
    off, size = struct.unpack('<QQ', raw[tail_at:tail_at + 16])
    fmt = struct.unpack('<i', raw[tail_at + 16:tail_at + 20])[0]
    return tail_at, off, size, fmt


def patch_pack_previews(album, preview_map, dump_dir, out_dir,
                        enable_modes=None, in_bundle_path=None):
    """Patch previews (and modes, when requested) into a pack bundle.

    preview_map: {slot_songID: fsb5_bytes}
    Returns result dict like patch_pack_bundle's, or None.
    """
    original_name = album['packBundle']
    bundle_path = in_bundle_path or os.path.join(
        dump_dir, 'Media/StreamingAssets/aa/PS4', original_name)
    if not os.path.isfile(bundle_path):
        return None

    cab_raw, blocks, flags, nodes, dec, buf = get_cab_raw(bundle_path)
    data_off = struct.unpack('>I', cab_raw[0x14:0x18])[0]
    data_off = (48 + data_off + 15) & ~15

    from UnityPy import Environment
    env = Environment(bundle_path)
    bf = list(env.files.values())[0]
    cab_key = next(k for k in bf.files if k.startswith('CAB-') and '.res' not in k)
    cab_obj = bf.files[cab_key]
    obj_table = sorted(
        [(pid, o.byte_start, o.byte_size) for pid, o in cab_obj.objects.items()],
        key=lambda x: x[1])

    # Map songID -> (so_pid, preview_clip_pid) for slots we're patching
    slot_to_pid = {}
    clip_pid_by_name = {}
    for pid, o in cab_obj.objects.items():
        if o.class_id == 83:  # AudioClip
            clip_pid_by_name[pid] = None  # filled below
    # identify each SO's preview clip pid
    for song in album['songs']:
        if 'patchPathID' not in song:
            continue
        so_pid = song['patchPathID']
        obj = cab_obj.objects.get(so_pid)
        if obj is None:
            continue
        blob = bytes(cab_raw[obj.byte_start:obj.byte_start + obj.byte_size])
        info = walk_blob(blob)
        if info is None or info['levelID'] != song['songID']:
            continue
        # _previewAudioClip PPtr sits after the 5 strings + version (see walk_blob):
        # strings[0]=levelID... offset math: replicate walk_blob's walk
        o = 12 + 4 + 12
        def _rs(o):
            n = struct.unpack_from('<i', blob, o)[0]
            data = blob[o+4:o+4+n] if n > 0 else b''
            o = o + 4 + n
            o = (o + 3) & ~3
            return data.decode('utf-8', 'replace'), o
        _, o = _rs(o)     # m_Name (MonoBehaviour header string)
        o += 4            # _version
        for _ in range(5):
            _, o = _rs(o)
        fid = struct.unpack_from('<i', blob, o)[0]
        clip_pid = struct.unpack_from('<q', blob, o + 4)[0]
        assert fid == 0, f"non-local preview PPtr for {song['songID']}"
        slot_to_pid[song['songID']] = (so_pid, clip_pid)

    # Build CAB patches:
    #   AudioClip blob patch: repoint m_Offset/m_Size (in place, same length).
    #   New blobs are appended sequentially at the END of the .resource —
    #   running offset so each clip gets a distinct, non-overlapping slice.
    res_off = res_size = None
    for p, off, sz, nf in nodes:
        if p.endswith('.resource'):
            res_off, res_size = off, sz
    assert res_off is not None, 'no .resource node'

    patches = []
    patched = 0
    # m_Offset is RELATIVE TO THE RESOURCE NODE START (stock: first clip = 0 while
    # the node sits at absolute stream offset 2,013,244). Appended blobs start at
    # the old resource SIZE — everything after the stock content.
    append_cursor = res_size
    layout = []          # (clip_pid, new_off, new_fsb)
    for song in album['songs']:
        sid = song['songID']
        if sid not in preview_map or sid not in slot_to_pid:
            continue
        so_pid, clip_pid = slot_to_pid[sid]
        cobj = cab_obj.objects.get(clip_pid)
        if cobj is None:
            continue
        craw = bytes(cab_raw[cobj.byte_start:cobj.byte_start + cobj.byte_size])
        tail_at, old_off, old_size, fmt = parse_audioclip_blob(craw)
        new_fsb = preview_map[sid]

        new_craw = bytearray(craw)
        struct.pack_into('<QQ', new_craw, tail_at, append_cursor, len(new_fsb))
        patches.append((cobj.byte_start, cobj.byte_size, bytes(new_craw)))
        layout.append((clip_pid, append_cursor, new_fsb))
        append_cursor += len(new_fsb)
        patched += 1

    if not patches:
        return None

    new_cab = rebuild_bundle(cab_raw, data_off, obj_table, patches)
    return {
        'patched': patched,
        'new_cab': new_cab,
        'dec': bytes(dec),
        'nodes': nodes,
        'blocks': blocks,
        'flags': flags,
        'buf': buf,
        'cab_raw': cab_raw,
        'layout': layout,
        'res_off': res_off,
        'res_size': res_size,
    }


def rebuild_with_previews(result, out_path):
    """Extend the decompressed stream with the new preview blobs and rebuild the bundle.

    `dec` layout: [ CAB | resS | resource ] per the node offsets. We append
    the new FSB5 blobs after the resource (the CAB's m_Offset fields already
    point at these absolute positions), then rebuild via the standard
    rebuild_bundle_file machinery (blocks re-derived with LZ4HC flag 3).
    """
    dec = bytearray(result['dec'])
    for clip_pid, off, fsb in result['layout']:
        # layout offsets are resource-relative; the append position in the
        # stream is res_off + relative offset
        assert result['res_off'] + off == len(dec), \
            f"layout offset {off} != stream end {len(dec)} — append order broken"
        dec.extend(fsb)

    cab_key = result['nodes'][0][0]
    resS_key = cab_key + '.resS'
    res_key = cab_key + '.resource'

    # Rebuild bundle with the extended stream. rebuild_bundle_file derives
    # resS/resource raws from `dec` at the OLD node offsets/sizes; the new
    # resource node must span to the end of `dec`.
    new_resource_size = len(dec) - (result['res_off'] + result['res_size']) + result['res_size']
    nodes = []
    for p, o, s, nf in result['nodes']:
        if p == res_key:
            s = new_resource_size
        nodes.append((p, o, s, nf))

    new_bundle = rebuild_bundle_file(
        result['cab_raw'], result['blocks'], result['flags'], nodes, bytes(dec),
        result['buf'], result['new_cab'])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(new_bundle)
    return new_bundle


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Spike: patch song previews into a pack bundle')
    ap.add_argument('--pack', required=True, help='pack id, e.g. lizzo')
    ap.add_argument('--preview-seconds', type=float, default=PREVIEW_SECONDS)
    ap.add_argument('--out-dir', default=os.path.join(REPO, 'orbeats', 'development', 'preview_bundles'))
    args = ap.parse_args()

    ids = json.load(open(os.path.join(REPO, 'orbeats', 'beat_saber_song_ids.json')))
    album = [a for a in ids['albums'] if a['pack'] == args.pack][0]
    dump_dir = os.path.join(REPO, 'ps4_dump', 'CUSA12878-patch')

    meta = json.load(open(os.path.join(REPO, 'orbeats', 'song_metadata.json')))["song_names"]
    # local song sources (Info.dat) — best effort; bundle fallback otherwise
    repo_songs = os.path.join(REPO, 'beat-saber-ps4-custom-songs', 'songs_repo')
    title_idx = {}
    if os.path.isdir(repo_songs):
        for h in os.listdir(repo_songs):
            ip = os.path.join(repo_songs, h, 'Info.dat')
            if os.path.isfile(ip):
                try:
                    d = json.load(open(ip))
                    n = (d.get('_songName') or d.get('song', {}).get('title') or '').strip()
                    if n:
                        title_idx.setdefault(n.lower(), os.path.join(repo_songs, h))
                except Exception:
                    pass

    custom_dir = os.path.join(REPO, 'orbeats', 'custom_songs')
    preview_map = {}
    for song in album['songs']:
        sid = song['songID']
        stock = song['songName']
        if stock not in meta:
            continue  # slot not custom — keep its stock preview untouched
        # find the local custom bundle for this slot
        cpath = None
        for cand in (os.path.join(custom_dir, f'{sid}_custom.bundle'),
                     os.path.join(custom_dir, f'{sid}_v3.bundle')):
            if os.path.isfile(cand):
                cpath = cand
                break
        if cpath is None:
            print(f"  ⚠️  {sid}: no local custom bundle — preview SKIPPED (stock preview stays)")
            continue

        pcm, sr, ch, dur = pcm_from_custom_bundle(cpath)
        # PREVIEW START — two paths, both in the DEPLOYED bundle's own timebase:
        #   1. the mapper's Info.dat _previewStartTime when a LOCAL SOURCE DIR
        #      exists (it matches the deployed map version when the local dir
        #      was the build source)
        #   2. the busiest-bar heuristic computed from the DEPLOYED bundle's own
        #      beatmaps — always in sync with what gameplay plays (Exp 269:
        #      repo-dir starts proved WRONG for freshly-downloaded deploys;
        #      e.g. deployed 2BeLoved audio = a different map version whose
        #      content sits 0.5s later than the repo copy's timing)
        start = None
        disp = meta[stock]
        name_part = disp.split(' / ')[0].strip().lower()
        src_dir = title_idx.get(name_part)
        if src_dir:
            start = preview_start_from_info(src_dir)
        if start is None:
            start = preview_start_from_beatmaps(cpath, dur)
        if start is None:
            start = 0.0
        start = max(0.0, min(start, max(0.0, dur - args.preview_seconds)))

        seg = cut_preview(pcm, start, dur)
        fsb = build_preview_fsb5(seg)
        preview_map[sid] = fsb
        print(f"  ✂️  {sid:<18} start={start:7.1f}s  dur={dur:6.1f}s  fsb5={len(fsb):,} B  "
              f"(rms {rms_db(seg):.1f} dBFS)")

    if not preview_map:
        print("nothing to patch")
        return 1

    # Modes + previews in ONE bundle: patch previews ON TOP of the existing
    # modes-patched bundle (the deployed one), so the mode buttons stay.
    modes_bundle = os.path.join(REPO, 'orbeats', 'pack_modes_bundles',
                                os.path.basename(album['packBundle']).replace(
                                    '_pack_assets_all_', '_pack_modes_assets_all_'))
    src_bundle = modes_bundle if os.path.isfile(modes_bundle) else None
    if src_bundle is None:
        print(f"  ⚠️  modes bundle not found at {modes_bundle} — patching from dump original")
        src_bundle = os.path.join(dump_dir, 'Media/StreamingAssets/aa/PS4', album['packBundle'])

    result = patch_pack_previews(album, preview_map, dump_dir, args.out_dir,
                                  in_bundle_path=src_bundle)
    if result is None:
        print("no patches produced")
        return 1

    # variant name: modes + previews
    base = os.path.basename(src_bundle)
    out_name = base.replace('_pack_modes_assets_all_', '_pack_modes_previews_assets_all_')
    if out_name == base:
        out_name = base.replace('_pack_assets_all_', '_pack_modes_previews_assets_all_')
    out_path = os.path.join(args.out_dir, out_name)
    new_bundle = rebuild_with_previews(result, out_path)

    crc = crc_decompressed_stream(new_bundle)
    print(f"\n  📦 {out_name}")
    print(f"     size {len(new_bundle):,} B  crc {crc}  previews {result['patched']}")
    return 0


if __name__ == '__main__':
    main()
