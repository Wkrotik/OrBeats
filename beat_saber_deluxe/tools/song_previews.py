#!/usr/bin/env python3
"""
Song preview patching for OrBeats pack bundles (M10).

When the player highlights a custom song in the song menu, the game plays the
pack bundle's preview AudioClip (BeatmapLevelSO._previewAudioClip →
SongPreviewPlayer.CrossfadeTo). Stock bundles carry the ORIGINAL song's 10s
preview there — confusing once the slot is replaced. This module swaps that
clip for a ~10s excerpt of the CUSTOM song's own deployed audio.

Design (plan: .agent/plans/song-previews.md; spike: Exp 269):
  - Source audio: the slot's own deployed per-song custom bundle
    (custom_songs/ etc.) — by construction in sync with gameplay.
  - Preview start: the mapper's Info.dat _previewStartTime when a matching
    local source dir exists; otherwise the busiest-bar heuristic computed from
    the deployed bundle's own beatmaps (always in sync).
  - Cut: 10.0 s @ 44.1 kHz stereo 16-bit, 8 ms fade-in, 250 ms fade-out.
  - Normalize: target -10.4 dBFS RMS (measured stock-preview fleet average),
    peak-limited to -1 dBFS, only when >3 dB off target.
  - Container: FSB5 PCM16 (mode 2) — the hardware-proven codec (full-song
    clips use the same). AudioClip fields mirror the proven values exactly
    (m_LoadType=1, m_CompressionFormat=1, m_LoadInBackground/m_Legacy3D true).
  - Bundle patch: new FSB5 blobs appended at the END of the pack bundle's
    inner .resource stream; the AudioClip's m_Resource.m_Offset/m_Size
    repointed IN PLACE (16 bytes, same blob length — zero object-table
    shifts). m_Offset is RELATIVE TO THE RESOURCE NODE START (Exp 269: the
    spike's absolute offsets made every clip read garbage).
  - BeatmapLevelSO floats are untouched: stock _previewStartTime=0.0 and
    _previewDuration=10.0 already play a pre-cut clip from its start.

Feature flag: enable_song_previews (features.json). The plugin gates the
pack redirect pair on it exactly like enable_beatmap_mode_mapping (Exp 222),
and the pipeline derives the bundle VARIANT (modes+previews vs modes-only)
from the current flag state at deploy time.
"""
import array
import bisect
import gzip
import io
import json
import math
import os
import struct
import wave

import UnityPy

PREVIEW_SECONDS = 10.0
PREVIEW_TARGET_DBFS = -10.4          # stock preview fleet average (Exp 269)
PREVIEW_TOLERANCE_DB = 3.0          # only normalize when further off than this
PREVIEW_PEAK_DBFS = -1.0            # peak limit
FADE_IN_MS = 8.0
FADE_OUT_MS = 250.0
SAMPLE_RATE = 44100


# ═══════════════════════════════════════════════════════════════════════════
# Preview audio extraction + selection
# ═══════════════════════════════════════════════════════════════════════════

def pcm_from_custom_bundle(bundle_path: str):
    """Full PCM (interleaved int16 array) from a custom song bundle's AudioClip."""
    env = UnityPy.load(bundle_path)
    for obj in env.objects:
        if obj.type.name == 'AudioClip':
            d = obj.read(check_read=False)
            for _k, wav in d.samples.items():
                w = wave.open(io.BytesIO(wav))
                data = array.array('h')
                data.frombytes(w.readframes(w.getnframes()))
                return data, w.getnframes() / float(SAMPLE_RATE)
    raise RuntimeError(f"no AudioClip in {bundle_path}")


def preview_start_from_info(song_dir: str):
    """Mapper's chosen preview start from Info.dat (V2/V3 _previewStartTime,
    V4 audio.previewStartTime). None when absent/unreadable."""
    ip = os.path.join(song_dir, 'Info.dat')
    if not os.path.isfile(ip):
        return None
    try:
        with open(ip) as f:
            d = json.load(f)
        ps = d.get('_previewStartTime')
        if ps is None and isinstance(d.get('audio'), dict):
            ps = d['audio'].get('previewStartTime')
        return None if ps is None else float(ps)
    except Exception:
        return None


def preview_start_from_beatmaps(bundle_path: str, duration_s: float):
    """Busiest-bar heuristic from the bundle's own STANDARD beatmaps.

    Notes carry BEAT values (b/_time) — converted to seconds via the map's
    bpmEvents m field (the PS4-native format the pipeline writes). Mode clones
    (OneSaber/NoArrows/90Degree) duplicate density and are excluded; the
    winning window snaps back to a 4-beat bar for a musical entry. Returns
    seconds or None.
    """
    try:
        env = UnityPy.load(bundle_path)
        notes_b = []
        bpm = None
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
            if bpm is None:
                for e in (bt.get('bpmEvents') or []):
                    m = e.get('m')
                    if m and 40.0 <= float(m) <= 400.0:
                        bpm = float(m)
                        break
            notes = bt.get('_notes') or bt.get('colorNotes') or []
            for n in notes:
                t = n.get('_time', n.get('b'))
                if t is not None:
                    notes_b.append(float(t))
        if not notes_b or not bpm:
            return None
        secs = sorted(b * 60.0 / bpm for b in notes_b)
        last_s = secs[-1]
        if last_s <= PREVIEW_SECONDS + 2.0:
            return 0.0
        best = (0.0, -1)
        ws = max(2.0, last_s * 0.05)     # skip intros
        while ws < last_s - PREVIEW_SECONDS:
            lo = bisect.bisect_left(secs, ws)
            hi = bisect.bisect_right(secs, ws + PREVIEW_SECONDS)
            n = hi - lo
            if n > best[1]:
                best = (ws, n)
            ws += 1.0
        if best[1] < 0:
            return None
        bar = 4.0 * 60.0 / bpm
        return max(0.0, best[0] - (best[0] % bar))
    except Exception:
        return None


def _rms_db(data) -> float:
    if not len(data):
        return -96.0
    ssq = sum(x * x for x in data)
    return 20 * math.log10(max(1e-9, math.sqrt(ssq / len(data))) / 32768.0)


def cut_preview(pcm: array.array, start_s: float):
    """Cut [start, start+10)s; pad short sources; fade; normalize. int16 array."""
    ch = 2
    n_frames = len(pcm) // ch
    start_f = max(0, min(int(start_s * SAMPLE_RATE),
                         max(0, n_frames - int(PREVIEW_SECONDS * SAMPLE_RATE))))
    end_f = min(n_frames, start_f + int(PREVIEW_SECONDS * SAMPLE_RATE))
    seg = array.array('h', pcm[start_f * ch:end_f * ch])

    want = int(PREVIEW_SECONDS * SAMPLE_RATE) * ch
    if len(seg) < want:
        seg.extend(array.array('h', bytes(2 * (want - len(seg)))))

    # Normalize toward the stock-preview loudness (only when > tolerance off).
    cur_db = _rms_db(seg)
    if abs(cur_db - PREVIEW_TARGET_DBFS) > PREVIEW_TOLERANCE_DB:
        cur_rms = math.sqrt(sum(x * x for x in seg) / len(seg))
        gain = (10 ** (PREVIEW_TARGET_DBFS / 20.0) * 32768) / max(1e-9, cur_rms)
        seg = array.array('h', [max(-32768, min(32767, int(x * gain))) for x in seg])

    # Peak limit.
    peak = max((abs(x) for x in seg), default=0)
    peak_target = int(10 ** (PREVIEW_PEAK_DBFS / 20.0) * 32768)
    if peak > peak_target:
        lim = peak_target / peak
        seg = array.array('h', [int(x * lim) for x in seg])

    # Fades.
    fi = int(FADE_IN_MS / 1000 * SAMPLE_RATE) * ch
    fo = int(FADE_OUT_MS / 1000 * SAMPLE_RATE) * ch
    for i in range(min(fi, len(seg))):
        seg[i] = int(seg[i] * (i / fi))
    for i in range(min(fo, len(seg))):
        seg[len(seg) - 1 - i] = int(seg[len(seg) - 1 - i] * (i / fo))
    return seg


def build_preview_fsb5(pcm: array.array) -> bytes:
    """Wrap the 10s PCM in the exact FSB5 PCM16 container our proven clips use
    (mirror of hevag_encoder.build_pcm16_fsb5's layout)."""
    pcm_bytes = pcm.tobytes()
    total_frames = len(pcm) // 2
    shs = 65
    header = bytearray(128)
    header[0:4] = b'FSB5'
    struct.pack_into('<I', header, 4, 1)          # version
    struct.pack_into('<I', header, 8, 1)          # numSamples
    struct.pack_into('<I', header, 12, shs)       # sampleHeaderSize
    struct.pack_into('<I', header, 16, 0)
    struct.pack_into('<I', header, 20, len(pcm_bytes))
    struct.pack_into('<I', header, 24, 2)         # mode = PCM16
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


# ═══════════════════════════════════════════════════════════════════════════
# Pack bundle patching
# ═══════════════════════════════════════════════════════════════════════════

def parse_audioclip_blob(raw: bytes):
    """(tail_offset, m_Offset, m_Size, m_CompressionFormat) via the archive:/ anchor."""
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


def _so_preview_clip_pid(blob: bytes) -> int:
    """BeatmapLevelSO blob → its _previewAudioClip PPtr pathID (assumes local,
    m_FileID=0 — verified across all 5 replaced packs, Exp 268)."""
    o = 12 + 4 + 12                       # m_GameObject, m_Enabled+align, m_Script

    def _rs(o):
        n = struct.unpack_from('<i', blob, o)[0]
        if n < 0 or n > 200:
            raise ValueError('bad string len')
        o = o + 4 + max(0, n)
        o = (o + 3) & ~3
        return o

    o = _rs(o)                            # MonoBehaviour m_Name
    o += 4                                # _version
    for _ in range(5):                    # levelID..levelAuthorName
        o = _rs(o)
    fid = struct.unpack_from('<i', blob, o)[0]
    if fid != 0:
        raise ValueError(f'non-local _previewAudioClip (m_FileID={fid})')
    return struct.unpack_from('<q', blob, o + 4)[0]


def patch_pack_previews(album: dict, preview_map: dict, bundle_path: str):
    """Append preview FSB5 blobs to a pack bundle's .resource and repoint the
    matching AudioClips in place. Returns a work dict for
    rebuild_bundle_with_previews(), or None when nothing to patch.

    bundle_path must be the MODES-patched bundle (previews ride on top of the
    mode-selector patch — one bundle carries both features).
    """
    from build_pack_mode_bundles import get_cab_raw, rebuild_bundle, walk_blob

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

    # songID -> preview clip PID (via the SO blob, same walk the modes patch uses)
    slot_clip_pid = {}
    for song in album['songs']:
        if 'patchPathID' not in song or song['songID'] not in preview_map:
            continue
        obj = cab_obj.objects.get(song['patchPathID'])
        if obj is None:
            continue
        blob = bytes(cab_raw[obj.byte_start:obj.byte_start + obj.byte_size])
        info = walk_blob(blob)
        if info is None or info['levelID'] != song['songID']:
            continue
        try:
            slot_clip_pid[song['songID']] = _so_preview_clip_pid(blob)
        except ValueError as e:
            raise RuntimeError(f"{song['songID']}: {e}") from e

    res_size = None
    for p, off, sz, nf in nodes:
        if p.endswith('.resource'):
            res_size = sz
    if res_size is None:
        return None

    patches = []
    layout = []                       # (clip_pid, relative_off, fsb5_bytes)
    cursor = res_size                 # RELATIVE to the resource node start
    for song in album['songs']:
        sid = song['songID']
        if sid not in preview_map or sid not in slot_clip_pid:
            continue
        clip_pid = slot_clip_pid[sid]
        cobj = cab_obj.objects.get(clip_pid)
        if cobj is None:
            continue
        craw = bytes(cab_raw[cobj.byte_start:cobj.byte_start + cobj.byte_size])
        tail_at, _old_off, _old_size, _fmt = parse_audioclip_blob(craw)
        fsb = preview_map[sid]
        new_craw = bytearray(craw)
        struct.pack_into('<QQ', new_craw, tail_at, cursor, len(fsb))
        patches.append((cobj.byte_start, cobj.byte_size, bytes(new_craw)))
        layout.append((clip_pid, cursor, fsb))
        cursor += len(fsb)

    if not patches:
        return None
    new_cab = rebuild_bundle(cab_raw, data_off, obj_table, patches)
    return {
        'new_cab': new_cab,
        'cab_raw': cab_raw,
        'blocks': blocks,
        'flags': flags,
        'nodes': nodes,
        'dec': bytes(dec),
        'buf': buf,
        'layout': layout,
        'res_size': res_size,
    }


def rebuild_bundle_with_previews(work: dict, out_path: str) -> bytes:
    """Extend the decompressed stream with the preview blobs and rebuild the
    full UnityFS bundle (LZ4HC blocks re-derived — PS4 requirement)."""
    from build_pack_mode_bundles import rebuild_bundle_file

    dec = bytearray(work['dec'])
    # The resource node is the LAST node; appended blobs continue the stream.
    res_off = None
    for p, off, sz, nf in work['nodes']:
        if p.endswith('.resource'):
            res_off = off
    if res_off is None:
        raise RuntimeError('no .resource node')
    for clip_pid, rel_off, fsb in work['layout']:
        assert res_off + rel_off == len(dec), \
            f"layout offset {rel_off} != stream end {len(dec)} — append order broken"
        dec.extend(fsb)

    cab_key = work['nodes'][0][0]
    new_resource_size = work['res_size'] + sum(len(f) for _p, _o, f in work['layout'])
    nodes = []
    for p, o, s, nf in work['nodes']:
        if p == cab_key + '.resource':
            s = new_resource_size
        nodes.append((p, o, s, nf))

    new_bundle = rebuild_bundle_file(
        work['cab_raw'], work['blocks'], work['flags'], nodes, bytes(dec),
        work['buf'], work['new_cab'])
    d = os.path.dirname(out_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(new_bundle)
    return new_bundle


def previews_bundle_name(modes_bundle_name: str) -> str:
    """Derive the modes+previews variant filename from the modes one."""
    base = os.path.basename(modes_bundle_name)
    return base.replace('_pack_modes_assets_all_', '_pack_modes_previews_assets_all_')


# ═══════════════════════════════════════════════════════════════════════════
# Fleet resolution: slot -> preview FSB5 bytes
# ═══════════════════════════════════════════════════════════════════════════

def find_custom_bundle_for_slot(slot: str, config: dict, log=None):
    """Locate the local deployed-bundle for a slot. Search order:
    paths.output_dir (custom_songs/) <slot>_custom.bundle, then
    <slot>_v3.bundle; then mass_deploy.bundle_dir. Returns path or None."""
    paths = config.get('paths', {}) or {}
    out_dir = paths.get('output_dir') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'custom_songs')
    md = config.get('mass_deploy', {}) or {}
    md_dir = md.get('bundle_dir')
    candidates = [
        os.path.join(out_dir, f'{slot}_custom.bundle'),
        os.path.join(out_dir, f'{slot}_v3.bundle'),
    ]
    if md_dir:
        candidates += [
            os.path.join(md_dir, f'{slot}_v3.bundle'),
            os.path.join(md_dir, f'{slot}_custom.bundle'),
        ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _display_title(disp: str) -> str:
    """The custom song's TITLE from its 'Title / Artist' display string.

    Splits on the LAST ' / ' — titles rarely contain the separator, but
    ARTISTS sometimes do ('Queencard ( / G)I-DLE': the map's own title is
    literally 'Queencard (' with artist '(G)I-DLE' — BeatSaver metadata is
    occasionally malformed). Splitting on the FIRST separator truncated the
    title and the repo-source lookup failed → the busiest-bar heuristic
    silently took over with a different (stable but mapper-intent-free)
    start (Exp 269c)."""
    if ' / ' in disp:
        return disp.rsplit(' / ', 1)[0].strip().lower()
    return disp.strip().lower()


def _resolve_source_dir(disp: str) -> str | None:
    """Best-effort local source dir for the slot's custom song.

    Ladder (Exp 269c): exact extracted title → title with trailing
    punctuation/whitespace stripped (catches 'Queencard (' → 'queencard')
    → title with ALL parens/brackets content dropped → None (heuristic path).
    """
    title = _display_title(disp)
    idx = _repo_title_index()
    if title in idx:
        return idx[title]
    stripped = title.rstrip(' ([-_')
    if stripped != title and stripped in idx:
        return idx[stripped]
    noparen = title.split('(')[0].strip().rstrip(' -_')
    if noparen and noparen in idx:
        return idx[noparen]
    return None


def build_preview_map(album: dict, config: dict, log=print, want_inputs=False):
    """For every CUSTOM slot in the album (present in song_metadata.json),
    build the preview FSB5. Returns {slot_songID: fsb5_bytes}; slots without
    a local custom bundle are skipped with a warning (stock preview stays).

    want_inputs=True also returns a per-slot INPUT FINGERPRINT dict:
        {slot: [bundle_md5, start_seconds]}
    — everything that determines the preview bytes. Stored in the variant's
    manifest row, it lets future deploys skip slots (and whole packs) whose
    inputs are unchanged (Exp 269c dirty-checking)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    meta_path = os.path.join(root, 'song_metadata.json')
    meta = {}
    if os.path.isfile(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f).get('song_names', {})
        except Exception:
            meta = {}

    # Local BeatSaver source dirs (Info.dat preview starts) — best effort.
    repo = os.path.join(os.path.dirname(root), 'beat-saber-ps4-custom-songs', 'songs_repo')
    title_idx = {}
    if os.path.isdir(repo):
        for h in os.listdir(repo):
            ip = os.path.join(repo, h, 'Info.dat')
            if os.path.isfile(ip):
                try:
                    with open(ip) as f:
                        d = json.load(f)
                    n = (d.get('_songName') or d.get('song', {}).get('title') or '').strip()
                    if n:
                        title_idx.setdefault(n.lower(), os.path.join(repo, h))
                except Exception:
                    pass

    import hashlib
    preview_map = {}
    inputs = {}
    for song in album['songs']:
        sid = song['songID']
        stock = song.get('songName', '')
        if stock not in meta:
            continue                       # not a custom slot
        cpath = find_custom_bundle_for_slot(sid, config)
        if cpath is None:
            log(f"  ⚠️  {sid}: no local custom bundle — preview SKIPPED (stock preview stays)")
            continue
        try:
            pcm, dur = pcm_from_custom_bundle(cpath)
        except Exception as e:
            log(f"  ⚠️  {sid}: audio read failed ({e}) — preview SKIPPED")
            continue

        start = None
        disp = meta[stock]
        src_dir = _resolve_source_dir(disp)
        if src_dir:
            start = preview_start_from_info(src_dir)
        if start is None:
            start = preview_start_from_beatmaps(cpath, dur)
        if start is None:
            start = 0.0
        start = max(0.0, min(start, max(0.0, dur - PREVIEW_SECONDS)))

        seg = cut_preview(pcm, start)
        fsb = build_preview_fsb5(seg)
        preview_map[sid] = fsb
        if want_inputs:
            with open(cpath, 'rb') as f:
                bundle_md5 = hashlib.md5(f.read()).hexdigest()
            inputs[sid] = [bundle_md5, _info_dat_md5_for(disp, root)]
        log(f"  ✂️  {sid:<18} start={start:7.1f}s  dur={dur:6.1f}s  "
            f"fsb5={len(fsb):,} B  rms {_rms_db(seg):.1f} dBFS")
    if want_inputs:
        return preview_map, inputs
    return preview_map


_REPO_TITLE_INDEX_CACHE = None


def _repo_title_index() -> dict:
    """{lowercase song title: repo dir} for the local BeatSaver sources.

    Cached for the process lifetime — the repo rarely changes mid-run, and
    without the cache the dirty-check re-parsed ~100 Info.dat files PER SLOT
    (46 slots × 100 files = 42 s of pure waste; profiling caught it)."""
    global _REPO_TITLE_INDEX_CACHE
    if _REPO_TITLE_INDEX_CACHE is not None:
        return _REPO_TITLE_INDEX_CACHE
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo = os.path.join(os.path.dirname(root), 'beat-saber-ps4-custom-songs', 'songs_repo')
    title_idx = {}
    if os.path.isdir(repo):
        for h in os.listdir(repo):
            ip = os.path.join(repo, h, 'Info.dat')
            if os.path.isfile(ip):
                try:
                    with open(ip) as f:
                        d = json.load(f)
                    n = (d.get('_songName') or d.get('song', {}).get('title') or '').strip()
                    if n:
                        title_idx.setdefault(n.lower(), os.path.join(repo, h))
                except Exception:
                    pass
    _REPO_TITLE_INDEX_CACHE = title_idx
    return title_idx


def _info_dat_md5_for(disp: str, root: str) -> str | None:
    """md5 of the local source dir's Info.dat that would supply this slot's
    preview START (None when no source dir matches → heuristic path, whose
    output is a pure function of the bundle bytes the md5 already covers)."""
    import hashlib
    if not disp:
        return None
    src_dir = _resolve_source_dir(disp)
    if not src_dir:
        return None
    ip = os.path.join(src_dir, 'Info.dat')
    if not os.path.isfile(ip):
        return None
    with open(ip, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def slot_input_fingerprint(sid: str, config: dict, album: dict) -> list | None:
    """Cheap per-slot dirty-check input WITHOUT building the preview.

    Shape: [bundle_md5, info_dat_md5_or_None].
      - bundle_md5: the deployed custom bundle's exact bytes — the audio AND
        the embedded beatmaps that drive the heuristic start are both inside
        it, so any content change flips the md5.
      - info_dat_md5: the local source dir's Info.dat (the mapper's preview
        start). None = no source dir → the start is the in-bundle heuristic,
        fully covered by bundle_md5.
    NO UnityPy parsing on this path — a clean 47-slot fleet checks in
    seconds (pure file reads; ~0.4 s per large bundle for the md5).
    None = no bundle → slot cannot preview (dirty-check treats as skip)."""
    import hashlib
    cpath = find_custom_bundle_for_slot(sid, config)
    if cpath is None:
        return None
    with open(cpath, 'rb') as f:
        bundle_md5 = hashlib.md5(f.read()).hexdigest()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    meta_path = os.path.join(root, 'song_metadata.json')
    disp = ''
    if os.path.isfile(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f).get('song_names', {})
            stock = next((s.get('songName', '') for s in album.get('songs', [])
                          if s.get('songID') == sid), '')
            disp = meta.get(stock, '')
        except Exception:
            disp = ''
    return [bundle_md5, _info_dat_md5_for(disp, root)]
