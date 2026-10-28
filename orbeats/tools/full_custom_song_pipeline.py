#!/usr/bin/env python3
"""
Full Custom Song Pipeline for PS4 Beat Saber
=============================================
Takes a community custom song (WAV + beatmap .dat files) and produces a
drop-in AssetBundle replacement for a target song (e.g., startmeup).

Usage:
    python3 full_custom_song_pipeline.py \\
        --song-dir ./my_custom_song \\
        --target startmeup \\
        [--deploy]

Example:
    python3 full_custom_song_pipeline.py \\
        --song-dir /workspace/beat-saber-ps4-custom-songs/songs_repo/249ed7fe4b66b339af8322d6e054567bcf7c1b07 \\
        --target startmeup \\
        --deploy

Pipeline Steps:
    1. Load the target song's original AssetBundle (template)
    2. Convert custom WAV audio to HEVAG -> FSB5 (with 12MB padding)
    3. Replace .resource data in the bundle with new FSB5
    4. Update AudioClip metadata (m_Length, m_Resource.m_Size)
    5. Update audio.gz metadata (songSampleCount, bpmData)
    6. Replace all 5 difficulty beatmaps (.dat -> gzip -> TextAsset)
    7. Save the modified bundle with LZ4 compression
    8. Deploy to PS4 via FTP (optional)
"""

import argparse
import copy
import gzip
import hashlib
import json
import logging
import os
import shutil
import struct
import sys
import tempfile

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TOOLS_DIR)
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'ps4_config.json')
sys.path.insert(0, TOOLS_DIR)

# Session upload ledger (Exp 264): remote filenames this process uploaded.
# verify_ps4_deployment's size check hard-fails ONLY for these — the check's
# purpose is "did MY upload land intact?". An out-of-scope redirect target
# whose stale LOCAL artifact differs from the live PS4 file (e.g. a leftover
# bundle built by a different pipeline version) is reported as an
# informational note, not a deploy-blocking error — the deployed copy is
# what the game boots, and the deploy never touched that song.
_SESSION_UPLOADED_BUNDLES: set[str] = set()


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_config(config_path: str) -> dict:
    """
    Load PS4 configuration from a JSON file.
    Falls back to a sensible default if file is missing.

    Exp 270a: every default that pointed at a devcontainer-absolute path
    (/workspace/…) is now PROJECT_ROOT-RELATIVE — the release zip works from
    any extraction directory without hand-localizing the config (the Exp 234
    "post-merge finding #1" finally fixed). Users who localized their config
    keep their explicit values; only the DEFAULTS changed. The game dump
    default is '<extraction>/ps4_dump/CUSA12878-patch' — matching the README's
    documented dump location relative to wherever the user extracted.
    """
    dump_rel = os.path.join(PROJECT_ROOT, 'ps4_dump', 'CUSA12878-patch')
    default_config = {
        "ps4": {"ip": "192.168.100.117", "ftp_port": 2121,
                "ftp_user": "anonymous", "ftp_password": ""},
        "title": {"id": "CUSA12878", "patch_suffix": "-patch"},
        "paths": {
            "afr_base": "/data/GoldHEN/AFR",
            "afr_target_suffix": "_v3.bundle",
            "game_dump_dir": dump_rel,
            # M12 (Exp 280): local cache the in-console extractor's output is
            # pulled into — mirrors the dump layout exactly, so it is a
            # drop-in for game_dump_dir. Users need NO PC-side dump.
            "game_data_dir": os.path.join(PROJECT_ROOT, 'game_data'),
            "template_dir": "Media/StreamingAssets/BeatmapLevelsData",
            "output_dir": os.path.join(PROJECT_ROOT, 'custom_songs')
        },
        "pipeline": {"default_target": "startmeup", "sample_rate": 44100},
        # Generalized pack patch (Exp 188+): ALL configured DLC packs get 4 preview
        # mode sets (Standard/OneSaber/NoArrows/90Degree) × 5 difficulties. Built by
        # tools/build_pack_mode_bundles.py from beat_saber_song_ids.json + the dump;
        # every patched pack bundle is served via a redirect and a SINGLE merged
        # catalog (aa/catalog.json -> catalog_pack_modes.json) carries the updated
        # m_Crc/m_BundleSize for exactly the packs being patched. The merged catalog
        # is regenerated from the ORIGIN catalog on every build so entries for packs
        # NOT patched remain byte-identical (never point a redirect at a patched
        # bundle without its matching catalog entry, and never update a catalog entry
        # for a bundle that is served unpatched — both crash at boot, Exp 180).
        "pack_modes": {
            # NO hardcoded pack list (Exp 224 user directive): the pipeline has
            # ZERO expectations about which music packs are modified — that is
            # entirely up to what the user deploys. An empty list means
            # AUTO-DISCOVER: every pack with a patched bundle built locally
            # (in build_dir) is in scope, so validation/deployment match
            # reality. Users may still set an explicit list in ps4_config.json
            # to pin behavior.
            "packs": [],
            "build_dir": os.path.join(PROJECT_ROOT, 'pack_modes_bundles'),
            "song_ids_path": os.path.join(PROJECT_ROOT, 'beat_saber_song_ids.json'),
            "dump_dir": dump_rel,
            "catalog_key": "aa/catalog.json",
            "patched_catalog": "catalog_pack_modes.json",
            "patched_catalog_local": os.path.join(PROJECT_ROOT, 'catalog_pack_modes.json'),
        },
        # Mass deploy (deploy_all38.sh replacement): list of all custom song slots
        # deployed as <slot>_v3.bundle into the AFR dir. bundle_dir is a STABLE
        # committed location (not /tmp) so a fresh container can reproduce the
        # exact loadout: build_deploy_all38.py writes builds here, then
        # --deploy-mass-bundles uploads them.
        "mass_deploy": {
            "bundle_dir": os.path.join(PROJECT_ROOT, 'mass_bundles'),
            "slots": [
                "startmeup", "angry", "bitemyheadoff", "cantyouhearmeknocking",
                "deadmanwalking", "gimmeshelter", "icantgetnosatisfaction",
                "livebythesword", "messitup", "paintitblack", "sugarsoaker",
                "sympathyforthedevil", "wholewideworld",
                "Oxytocin", "AllTheGoodGirlsGoToHell", "YouShouldSeeMeInACrown",
                "Bellyache", "BuryAFriend", "IDidntChangeMyNumber",
                "HappierThanEver", "BadGuy", "NDA", "ThereforeIAm",
                "2BeLoved", "AboutDamnTime", "CuzILoveYou", "EverybodysGay",
                "GoodAsHell", "Juice", "Tempo", "TruthHurts", "Worship",
                "crystallized", "cyclehit", "exitthisearthsatomosphere",
                "ghost", "lightitup", "whatthecat",
            ],
        },
    }
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                user_config = json.load(f)
            # Deep-merge user config over defaults
            def deep_merge(base, override):
                result = base.copy()
                for k, v in override.items():
                    if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                        result[k] = deep_merge(result[k], v)
                    else:
                        result[k] = v
                return result
            # Exp 270a: RELATIVE PATHS in the user's config resolve against
            # PROJECT_ROOT (the release/checkout root) — ps4_config.example.json
            # ships './ps4_dump/...' and './custom_songs', which must work from
            # any extraction directory (absolute devcontainer paths in the
            # shipped example were the Exp 234 release finding #1).
            def localize_paths(node, prefix):
                for k, v in list(node.items()):
                    if isinstance(v, dict):
                        localize_paths(v, prefix)
                    elif (isinstance(v, str) and v.startswith('./')
                          and (k.endswith('_dir') or k.endswith('_path')
                               or k.endswith('_local'))):
                        node[k] = os.path.normpath(os.path.join(prefix, v))
                return node
            localize_paths(user_config, PROJECT_ROOT)
            merged = deep_merge(default_config, user_config)
            # Exp 281d: pack_modes.dump_dir follows paths.game_dump_dir unless
            # the user PINNED it — the pack-modes builder reads the same
            # game-data root as the per-song templates (pack bundles + origin
            # catalog), so the game_data cache is a drop-in for both. Without
            # this, switching game_dump_dir to the cache left pack-modes at the
            # old dump path and deploys skipped the pack patch ("Dump dir
            # missing" — the user's live report).
            user_pm = user_config.get('pack_modes') or {}
            if 'dump_dir' not in user_pm:
                merged['pack_modes']['dump_dir'] = merged['paths']['game_dump_dir']
            log.info(f"Loaded config from {config_path}")
            return merged
        except Exception as e:
            log.warning(f"Failed to load config {config_path}: {e}")
            return default_config
    return default_config

# ---------------------------------------------------------------------------
# Imports from our toolchain
# ---------------------------------------------------------------------------
import build_pack_mode_bundles as pack_modes_builder
import song_previews
import soundfile as sf
import UnityPy
from UnityPy.streams import EndianBinaryReader

try:
    from hevag_encoder import build_fsb5, build_pcm16_fsb5, build_vorbis_fsb5, fast_pcm_to_hevag
except ImportError:
    # Fallback: try to import directly
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'tools'))
    from hevag_encoder import build_fsb5, build_pcm16_fsb5, build_vorbis_fsb5, fast_pcm_to_hevag

try:
    from lapped_audio import detect_lapped, lap_audio
except ImportError:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'tools'))
    from lapped_audio import detect_lapped, lap_audio

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ORIGINAL_RESOURCE_SIZE = 12305632   # size of original startmeup .resource (12MB)
SAMPLE_RATE = 44100
CHANNELS = 2

# Default audio + beatmap behaviors (v0.5314+):
#   - PCM16 FSB5 (lossless) is the DEFAULT codec. Oppose with --hevag / --vorbis.
#   - NO padding (full song audio) is the DEFAULT. Oppose with --pad-fsb5.
#   - Beatmap mode mapping + generation is ON by DEFAULT. Oppose with
#     --disable-beatmap-mode-mapping / --skip-mode-generation.
#   - V2 -> V3.2.0 conversion is ON by DEFAULT. Oppose with --no-convert-to-v3.
DEFAULT_AUDIO_CODEC = 'pcm16'
DEFAULT_PAD_TO_SIZE = 0
DEFAULT_MODE_MAPPING = True
DEFAULT_CONVERT_TO_V3 = True


def resolve_audio_codec(hevag: bool = False, vorbis: bool = False) -> str:
    """Resolve the FSB5 audio codec. Default: PCM16 (lossless)."""
    if hevag:
        return 'hevag'
    if vorbis:
        return 'vorbis'
    return DEFAULT_AUDIO_CODEC


def resolve_pad_to_size(pad_fsb5: bool = False) -> int:
    """Resolve FSB5 pad target. Default: no padding (full song audio)."""
    return ORIGINAL_RESOURCE_SIZE if pad_fsb5 else DEFAULT_PAD_TO_SIZE


def resolve_mode_mapping(disable_beatmap_mode_mapping: bool = False) -> bool:
    """Resolve beatmap mode mapping default. Default: ON."""
    return DEFAULT_MODE_MAPPING and not disable_beatmap_mode_mapping


def resolve_convert_to_v3(no_convert_to_v3: bool = False) -> bool:
    """Resolve V2->V3 conversion default. Default: ON (V3 beatmaps untouched)."""
    return DEFAULT_CONVERT_TO_V3 and not no_convert_to_v3

# Beatmap difficulty names expected in the template
DIFFICULTIES = ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('pipeline')


# ============================================================================
# Step 0: Audio -> PCM -> HEVAG -> FSB5 (with padding)
# Supports .wav AND .ogg via soundfile
# ============================================================================

def audio_to_fsb5(audio_path: str, pad_to_size: int = ORIGINAL_RESOURCE_SIZE) -> bytes:
    """
    Convert an audio file (.wav or .ogg) to a PS4-compatible FSB5 file.

    1. Read audio via soundfile (handles WAV, OGG, FLAC, etc.)
    2. Encode PCM to HEVAG frames
    3. Build FSB5 container
    4. Pad to match original .resource size (required by PS4 decoder)

    Returns:
        Complete FSB5 bytes (padded to pad_to_size if smaller)
    """
    log.info(f"Reading audio: {audio_path}")

    # soundfile returns numpy array, convert to list of ints (normalized)
    from hevag_encoder import read_audio_normalized
    data, framerate = read_audio_normalized(audio_path)
    if data.ndim == 1:
        # Mono -> convert to interleaved for encoder
        pcm_data = data.tobytes()
        nchannels = 1
    else:
        nchannels = data.shape[1]
        pcm_data = data.tobytes()

    duration = len(data) / framerate

    log.info(f"  Frames: {len(data)}, Rate: {framerate}Hz, "
             f"Channels: {nchannels}, Duration: {duration:.1f}s")

    # Encode to HEVAG (using fast encoder for speed)
    log.info("Encoding PCM -> HEVAG (fast mode)...")
    hevag_data = fast_pcm_to_hevag(pcm_data, channels=nchannels)
    log.info(f"  HEVAG frames: {len(hevag_data)} bytes")

    # Build FSB5
    log.info("Building FSB5 container...")
    fsb5_bytes = build_fsb5(hevag_data, framerate, nchannels,
                            pcm_frames=len(data))
    log.info(f"  FSB5 size: {len(fsb5_bytes)} bytes")

    # Pad to match original resource size (CRITICAL for PS4)
    if len(fsb5_bytes) < pad_to_size:
        padding = bytes(pad_to_size - len(fsb5_bytes))
        fsb5_bytes = fsb5_bytes + padding
        log.info(f"  Padded to {len(fsb5_bytes)} bytes (+{len(padding)} bytes)")

    return fsb5_bytes


# ============================================================================
# Step 1: Load template bundle
# ============================================================================

def load_target_bundle(template_path: str):
    """
    Load the target song's AssetBundle and return the BundleFile + CAB.
    """
    log.info(f"Loading target bundle: {template_path}")
    env = UnityPy.load(template_path)
    bundles = list(env.files.values())
    if not bundles:
        raise RuntimeError(f"No bundles found in {template_path}")

    bf = bundles[0]

    # Auto-detect CAB name from bundle files
    cab_key = None
    for key in bf.files:
        if key.startswith("CAB-") and not key.endswith(".resource"):
            cab_key = key
            break
    if cab_key is None:
        raise RuntimeError("No CAB file found in bundle")

    resource_key = f"{cab_key}.resource"
    if resource_key not in bf.files:
        raise RuntimeError(f"Resource file '{resource_key}' not found in bundle")

    cab = bf.files[cab_key]

    log.info(f"  Bundle loaded: CAB={cab_key} ({len(cab.objects)} objects), "
             f"Resource={resource_key} ({bf.files[resource_key].Length} bytes)")

    return bf, cab, cab_key, resource_key


# ============================================================================
# Step 2: Replace .resource data
# ============================================================================

def replace_resource(bf, fsb5_bytes: bytes, resource_key: str):
    new_res = EndianBinaryReader(fsb5_bytes)
    new_res.flags = 0
    new_res.BaseOffset = 0
    bf.files[resource_key] = new_res
    log.info(f"  .resource replaced ({len(fsb5_bytes)} bytes)")


# ============================================================================
# Step 3: Update AudioClip
# ============================================================================

def update_audioclip(cab, fsb5_bytes: bytes, duration: float, sample_rate: int = SAMPLE_RATE):
    """
    Update the AudioClip's metadata (m_Length, m_Frequency, m_Resource.m_Size).
    """

    for pid, reader in cab.objects.items():
        if reader.class_id == 83:
            tt = reader.read_typetree()
            tt['m_Resource']['m_Size'] = len(fsb5_bytes)
            tt['m_Length'] = duration
            tt['m_Frequency'] = sample_rate
            reader.save_typetree(tt)
            log.info(f"  AudioClip updated: length={duration:.1f}s, "
                     f"frequency={sample_rate}Hz, resource_size={len(fsb5_bytes)}")
            return

    raise RuntimeError("No AudioClip (class_id=83) found in bundle!")


# ============================================================================
# Step 4: Update audio.gz metadata
# ============================================================================

def _scan_beatmap_max_beat(song_dir: str) -> float:
    """Scan all beatmap .dat files and return the highest _time/b value found."""
    import glob as _glob
    max_beat = 0.0
    bm_files = _glob.glob(os.path.join(song_dir, "*.dat"))
    for bm_path in bm_files:
        fname = os.path.basename(bm_path).lower()
        if fname in ('info.dat', 'bpminfo.dat'):
            continue
        try:
            with open(bm_path) as f:
                data = json.load(f)
            notes = data.get('_notes', data.get('colorNotes', []))
            for note in notes:
                t = note.get('_time', note.get('b', 0))
                if isinstance(t, (int, float)) and t > max_beat:
                    max_beat = t
        except Exception:
            pass
    return max_beat


def _read_info_bpm(song_dir: str) -> float | None:
    """Read _beatsPerMinute from Info.dat/info.dat, or None if unavailable.

    Format-aware (Exp 228): V4 maps carry BPM in audio.bpm instead of
    _beatsPerMinute — fall back to it so v4 sources sync correctly."""
    for fname in ("Info.dat", "info.dat"):
        info_path = os.path.join(song_dir, fname)
        if os.path.exists(info_path):
            try:
                with open(info_path) as f:
                    info = json.load(f)
                bpm = float(info.get("_beatsPerMinute", info.get("beatsPerMinute", 0)) or 0)
                if bpm > 0:
                    return bpm
                bpm = _read_info_bpm_from_dict(info)
                if bpm:
                    return bpm
            except Exception:
                pass
    return None


def load_bpm_regions(song_dir: str, sample_count: int) -> list:
    """
    Load BPM region data from BPMInfo.dat (preferred) or compute from Info.dat BPM.

    The bpmData maps sample ranges to beat ranges. This is CRITICAL for sync:
    the game converts beatmap 'b' values (in beats) to time positions using
    these regions. If eb is in seconds instead of beats, the tempo is halved
    at 120 BPM, causing progressive desync.

    The mapper's beat grid IS Info.dat's _beatsPerMinute — notes are placed on
    that grid by the editor, so beat B of the map falls at B*60/bpm seconds in
    the audio regardless of how much trailing silence the audio has (Exp 218:
    the old `max_beat*60/audio_duration` heuristic undershot BPM by the
    trailing-silence fraction of every map with an outro — 'Roni 112.1 vs the
    real 117 → notes 9s late by song end, "BPM wayyy too slow").

    The beatmap max-beat scan is kept ONLY as a guard: if a map's last note
    lands beyond the Info.dat grid (mapper used a different BPM than declared,
    or BPMInfo.dat's regions end early), extend eb to cover it so high beats
    still resolve inside the audio.

    Returns list of {"si": startSampleIndex, "ei": endSampleIndex,
                     "sb": startBeat, "eb": endBeat} dicts.
    """
    bpm_path = os.path.join(song_dir, "BPMInfo.dat")
    if os.path.exists(bpm_path):
        with open(bpm_path) as f:
            bpm_data = json.load(f)
        regions = bpm_data.get("_regions", [])
        if regions:
            # Still scan beatmaps to check if BPMInfo.dat's eb is too small
            max_beat = _scan_beatmap_max_beat(song_dir)
            if max_beat > regions[-1]["_endBeat"]:
                log.info(f"  Beatmap max beat ({max_beat:.1f}) > BPMInfo.dat eb ({regions[-1]['_endBeat']:.1f}) — using beatmap value")
                regions[-1]["_endBeat"] = max_beat
            return [
                {"si": r["_startSampleIndex"], "ei": r["_endSampleIndex"],
                 "sb": r["_startBeat"], "eb": r["_endBeat"]}
                for r in regions
            ]

    duration = sample_count / SAMPLE_RATE

    # Authoritative grid: Info.dat _beatsPerMinute (the mapper's editor grid).
    info_bpm = _read_info_bpm(song_dir)

    # Guard: cover any notes placed beyond the declared grid.
    max_beat = _scan_beatmap_max_beat(song_dir)

    if info_bpm:
        total_beats = duration * info_bpm / 60.0
        if max_beat > total_beats:
            # Notes exist beyond the Info.dat grid — the mapper's real tempo is
            # faster than declared. Scale to cover the last note exactly.
            log.info(f"  Note beyond Info.dat grid (last beat {max_beat:.1f} > "
                     f"grid {total_beats:.1f}) — extending eb to cover it")
            total_beats = max_beat
        log.info(f"  Info.dat BPM grid: {info_bpm} (total_beats={total_beats:.1f}, audio={duration:.1f}s)")
    elif max_beat > 0:
        # No Info.dat BPM available — fall back to the beatmap-derived estimate.
        eff_bpm = max_beat * 60.0 / duration
        total_beats = duration * eff_bpm / 60.0
        log.info(f"  Beatmap-based BPM fallback: {eff_bpm:.1f} (from last beat={max_beat:.1f}, audio={duration:.1f}s)")
    else:
        # Absolute fallback: assume 120 BPM
        total_beats = duration * 2.0
        log.info(f"  No BPM data — assuming 120 BPM (total_beats={total_beats:.1f})")

    return [{"si": 0, "ei": sample_count, "sb": 0.0, "eb": total_beats}]


def update_audio_gz(cab, duration: float, sample_rate: int = SAMPLE_RATE,
                    bpm_regions: list = None):
    """
    Update the audio.gz TextAsset to reflect new audio duration/sample count.
    """
    sample_count = int(duration * sample_rate)

    if bpm_regions is None:
        bpm_regions = [{"si": 0, "ei": sample_count, "sb": 0.0,
                         "eb": duration * 2.0}]  # fallback: assume 120 BPM

    meta = {
        "version": "4.0.0",
        "songChecksum": "custom",
        "songSampleCount": sample_count,
        "songFrequency": sample_rate,
        "bpmData": bpm_regions
    }

    meta_json = json.dumps(meta, separators=(',', ':'))
    compressed = gzip.compress(meta_json.encode('utf-8'))

    for pid, reader in cab.objects.items():
        n = reader.peek_name() or ''
        if reader.class_id == 49 and 'audio.gz' in n:
            tt = reader.read_typetree()
            tt['m_Script'] = compressed.decode('utf-8', 'surrogateescape')
            reader.save_typetree(tt)
            log.info(f"  audio.gz updated: {sample_count} samples, "
                     f"{duration:.1f}s")
            return

    raise RuntimeError("No audio.gz TextAsset found in bundle!")


# ============================================================================
# V2 → V3/V4 beatmap converter
# ============================================================================

def is_v2_beatmap(data: dict) -> bool:
    """Check if a beatmap dict is in V2 format (needs conversion)."""
    ver = data.get("version") or data.get("_version") or ""
    if ver.startswith("2"):
        return True
    if "_notes" in data and "colorNotes" not in data:
        return True
    return False


def is_v4_beatmap(data: dict) -> bool:
    """
    Check if a beatmap dict is in V4 format (BeatSaver v4.0.x columnar layout).

    V4 splits every object list into an index-bearing event array plus a
    columnar data array: colorNotes[{b, i?}] + colorNotesData[{x,y,c,d,a}],
    bombNotes/bombNotesData, obstacles/obstaclesData, arcs/arcsData,
    chains/chainsData, basicBeatmapEvents/basicBeatmapEventsData,
    njsEvents/njsEventsData. The *Data suffix is the reliable marker —
    a V3 beatmap never carries it.
    """
    if str(data.get("version", "")).startswith("4"):
        return True
    return any(k in data for k in (
        "colorNotesData", "bombNotesData", "obstaclesData",
        "arcsData", "chainsData", "basicBeatmapEventsData",
    ))


# V4 columnar pairs: (event array name, data array name, V3 target key).
# Events carry timing/index ({b, i?}); data rows carry geometry
# ({x, y, c, d, a} for notes, {x, y, d, w, h} for obstacles, etc.).
_V4_COLUMNAR_PAIRS = (
    ("colorNotes", "colorNotesData", "colorNotes"),
    ("bombNotes", "bombNotesData", "bombNotes"),
    ("obstacles", "obstaclesData", "obstacles"),
    ("arcs", "arcsData", "arcs"),
    ("chains", "chainsData", "chains"),
    ("basicBeatmapEvents", "basicBeatmapEventsData", "basicBeatmapEvents"),
    ("colorBoostBeatmapEvents", "colorBoostBeatmapEventsData", "colorBoostBeatmapEvents"),
)


def convert_v4_to_v3(v4_data: dict) -> dict:
    """
    Convert a V4 (v4.0.x) columnar beatmap to the denormalized V3.2.0
    layout the PS4 deserializer expects.

    V4 stores objects split-by-concern: the event array holds timing plus an
    optional row index ('i', defaulting to the event's own position), and
    the paired *Data array holds the per-row geometry/attributes. V3 wants
    one flat object per note. Denormalize by merging event[n] with
    data[i] and dropping the v4-only keys.

    Exp 228: without this, v4 sources (BeatSaver 4dea2/443f3) passed through
    'is_v2_beatmap' untouched and shipped notes with ONLY {b, i} — the game
    read default x=0/y=0 and every note stacked in the bottom-left cell.
    """
    if not is_v4_beatmap(v4_data):
        return v4_data

    out = dict(v4_data)  # keep unknown keys (harmless); overwrite below
    out["version"] = "3.2.0"

    for events_key, data_key, v3_key in _V4_COLUMNAR_PAIRS:
        events = v4_data.get(events_key) or []
        rows = v4_data.get(data_key) or []
        merged = []
        for n, ev in enumerate(events):
            if not isinstance(ev, dict):
                continue
            idx = ev.get("i", n)
            row = rows[idx] if isinstance(idx, int) and 0 <= idx < len(rows) else {}
            obj = dict(ev)
            obj.pop("i", None)
            obj.update(row)
            merged.append(obj)
        out[v3_key] = merged
        out.pop(data_key, None)

    # V4-only event kinds without V3 equivalents: drop (PS4 ignores njs anyway)
    for k in ("njsEvents", "njsEventsData"):
        out.pop(k, None)

    return out


# Complete V3.2.0 schema as emitted by the game's own files and by
# convert_v2_to_v3(). Beatmaps entering a bundle MUST carry every array the PS4
# deserializer expects — minimal-schema maps (e.g. V4→V3-reconstructed Chromeo
# sources with only 8 keys, Exp 200) crash the game at gameplay load with
# CE-34878-0.
_V3_REQUIRED_ARRAYS = (
    "colorNotes",
    "bombNotes",
    "obstacles",
    "sliders",
    "burstSliders",
    "basicBeatmapEvents",
    "colorBoostBeatmapEvents",
    "bpmEvents",
    "rotationEvents",
    "waypoints",
    "lightColorEventBoxGroups",
    "lightRotationEventBoxGroups",
    "lightTranslationEventBoxGroups",
    "arcs",
    "chains",
)

_V3_REQUIRED_SCALARS = {
    "useNormalEventsAsCompatibleEvents": True,
    "customData": {},
}


def normalize_v3_schema(data: dict) -> dict:
    """Fill missing V3 arrays/fields with empty defaults (idempotent).

    Mutates and returns `data` in place — callers report what changed if they
    care (Exp 230: the `changed` flag was a dead store, never read).
    """
    for key in _V3_REQUIRED_ARRAYS:
        if key not in data or data[key] is None:
            data[key] = []
    for key, default in _V3_REQUIRED_SCALARS.items():
        if key not in data:
            data[key] = default if not isinstance(default, dict) else dict(default)
    # basicEventTypesWithKeywords must exist and be a dict with 'd' list
    if not isinstance(data.get("basicEventTypesWithKeywords"), dict):
        types = sorted({int(e.get("et", 0)) for e in data.get("basicBeatmapEvents", [])
                        if isinstance(e, dict)})
        data["basicEventTypesWithKeywords"] = {
            "d": [{"e": t, "n": f"EventType{t}"} for t in types]
        }
    elif "d" not in data["basicEventTypesWithKeywords"]:
        data["basicEventTypesWithKeywords"]["d"] = []

    # --- Repair colorNotes: if all entries have c=0, d=0, restore structure ---
    color_notes = data.get("colorNotes", [])
    if color_notes:
        all_zero = all(cn.get("c") == 0 and cn.get("d") == 0 for cn in color_notes)
        if all_zero and len(color_notes) > 0:
            # Restore color/direction: c defaults to 0 (Standard), d based on note index
            for i, cn in enumerate(color_notes):
                cn["c"] = 0 if i % 2 == 0 else 1
                cn["d"] = i % 8
            data["colorNotes"] = color_notes
    # --- Repair bpmEvents: if all have b=0, ensure m (BPM) is set ---
    bpm_events = data.get("bpmEvents", [])
    if bpm_events:
        all_zero_b = all(ev.get("b") == 0 for ev in bpm_events)
        if all_zero_b:
            # Ensure BPM value m is preserved; set to 120 as default if None
            for ev in bpm_events:
                if ev.get("m") is None:
                    ev["m"] = 120.0
                # Ensure b offset is explicitly set
                ev["b"] = 0.0
    return data


def beatmap_is_empty(data: dict) -> bool:
    """True when a V3 beatmap has no playable content (no notes/bombs/obstacles)."""
    return not (data.get("colorNotes") or data.get("bombNotes") or data.get("obstacles"))


# V2 rotation event (types 14/15) _value enumeration -> signed degrees.
# Negative = counter-clockwise (left), positive = clockwise (right). These are
# RELATIVE deltas the game accumulates onto the current spawn rotation.
_V2_ROTATION_VALUE_TO_DEGREES = {
    0: -60, 1: -45, 2: -30, 3: -15,
    4: 15, 5: 30, 6: 45, 7: 60,
}


def convert_v2_to_v3(v2_data: dict, default_bpm: float = 120.0) -> dict:
    """
    Convert a V2 beatmap dict to V3.2.0 format.

    V2 beatmaps store notes as _notes[] with _time/_lineIndex/_lineLayer/
    _type/_cutDirection.  V3 uses colorNotes[] plus bombNotes[] with
    b/x/y/a/d fields.  Obstacles, events, and sliders are converted
    similarly, and the result is a minimal V3 structure the PS4 game
    can parse without crashing on unknown keys.

    default_bpm: BPM to use for bpmEvents (from Info.dat, not beatmap file).
    """
    # Pass through if already V3/V4
    if not is_v2_beatmap(v2_data):
        return v2_data

    # -- notes -----------------------------------------------------------------
    color_notes = []
    bomb_notes = []
    for note in v2_data.get("_notes", []):
        nt = int(note.get("_type", 0))
        base = {
            "b": float(note["_time"]),
            "x": int(note.get("_lineIndex", 0)),
            "y": int(note.get("_lineLayer", 0)),
        }
        if nt == 3:
            base["d"] = int(note.get("_cutDirection", 0))
            bomb_notes.append(base)
        else:
            base["a"] = nt
            base["c"] = nt  # PS4 game uses 'c' for color (V3.3.0+), not 'a'
            base["d"] = int(note.get("_cutDirection", 0))
            color_notes.append(base)

    # -- obstacles -------------------------------------------------------------
    obstacles = []
    for obs in v2_data.get("_obstacles", []):
        ot = int(obs.get("_type", 0))
        obstacles.append({
            "b": float(obs["_time"]),
            "x": int(obs.get("_lineIndex", 0)),
            "y": 0,
            "d": float(obs.get("_duration", 0)),
            "w": int(obs.get("_width", 1)),
            "h": 3 if ot == 0 else 1,
        })

    # -- events: basicBeatmapEvents + rotationEvents ----------------------------
    # V2 event types 14 (early) / 15 (late) are spawn-rotation events (BSMG wiki,
    # Extended Mapping). Their _value is an enumeration of RELATIVE rotation that
    # the game accumulates:
    #   0=-60, 1=-45, 2=-30, 3=-15, 4=+15, 5=+30, 6=+45, 7=+60 degrees
    # (negative = counter-clockwise / left, positive = clockwise / right).
    # Everything else — including laser-speed events 12/13 — stays a basic event.
    # V3 basicBeatmapEvents use `et` (event type), `i`, `f` (game's
    # BeatmapSaveDataVersion3.BasicEventData), so `_type` maps to `et`.
    basic_events = []
    rotation_events = []
    for ev in v2_data.get("_events", []):
        etype = int(ev.get("_type", 0))
        b = float(ev["_time"])
        if etype in (14, 15):
            rotation_events.append({
                "b": b,
                "e": 0 if etype == 14 else 1,
                "r": _V2_ROTATION_VALUE_TO_DEGREES.get(int(ev.get("_value", 0)), 0),
            })
        else:
            basic_events.append({
                "b": b,
                "et": etype,
                "i": int(ev.get("_value", 0)),
            })

    event_types = sorted(set(e["et"] for e in basic_events))

    # -- build V3 structure ----------------------------------------------------
    v3 = {
        "version": "3.2.0",
        "colorNotes": color_notes,
        "bombNotes": bomb_notes,
        "obstacles": obstacles,
        "sliders": [],
        "burstSliders": [],
        "basicBeatmapEvents": basic_events,
        "colorBoostBeatmapEvents": [],
        "bpmEvents": [{"b": 0, "m": default_bpm}],
        "rotationEvents": rotation_events,
        "basicEventTypesWithKeywords": {
            "d": [{"e": t, "n": f"EventType{t}"} for t in event_types]
        },
        "useNormalEventsAsCompatibleEvents": True,
        "customData": {},
    }
    return v3


# ============================================================================
# Step 5: Replace beatmaps
# ============================================================================

def _select_beatmap_file(diff: str, beatmap_files: list, ignore_non_standard: bool = False) -> str | None:
    """
    Select the best beatmap file for a given difficulty using a priority fallback chain.

    Priority order (highest to lowest):
      1. Standard mode:  <Diff>Standard.dat    (e.g. ExpertPlusStandard.dat)
      2. Bare difficulty: <Diff>.dat            (e.g. ExpertPlus.dat)
      3. Beatmap-dot:    <Diff>.beatmap.dat     (e.g. ExpertPlus.beatmap.dat)
      4. Other modes:    <Diff>90Degree.dat, <Diff>OneSaber.dat, <Diff>NoArrows.dat, etc.
                         (limited gameplay but functional on PS4)

    360Degree files are always excluded — the PS4 camera cannot track the
    single-camera 90-degree arc that 360Degree gameplay requires, so notes
    behind the player are unplayable.

    The ignore_non_standard flag suppresses tier 4 (alternate modes).
    Bare files (tier 2) are always included — they have no mode suffix.
    """
    # Tiers: 1=Standard, 2=bare, 3=.beatmap.dat, 4=other modes
    tier1, tier2, tier3, tier4 = [], [], [], []

    for f in beatmap_files:
        base = f
        if 'Info' in base or 'Lightshow' in base or 'AudioData' in base:
            continue
        if not base.endswith(('.dat', '.json')):
            continue
        # Must contain the difficulty name
        if diff not in base:
            continue
        # ExpertPlus guard: when matching "Expert" never pick an "ExpertPlus" file
        if diff == 'Expert' and 'ExpertPlus' in base:
            continue

        stem = base  # e.g. "ExpertPlusStandard.dat" or "ExpertPlus.dat"

        if f'{diff}Standard' in stem:
            tier1.append(f)
        elif stem == f'{diff}.dat' or stem == f'{diff}.json':
            tier2.append(f)
        elif f'{diff}.beatmap' in stem:
            tier3.append(f)
        elif '360Degree' in stem:
            # 360Degree is unsupported on PS4 (camera cannot track full rotation)
            continue
        else:
            # 90Degree, OneSaber, NoArrows, Legacy, etc.
            if not ignore_non_standard:
                tier4.append(f)

    for tier in (tier1, tier2, tier3, tier4):
        if tier:
            return tier[0]
    return None


def _find_populated_beatmap(beatmap_dir: str, empty_file: str):
    """Find a Standard beatmap file in beatmap_dir that has playable content.

    Used as a donor for empty difficulties (Exp 200: Chromeo V4→V3 reconstruction
    produced zero-note Easy maps). Preference order: Normal, Hard, Expert,
    ExpertPlus, Easy — the closest full-fidelity neighbors of an empty slot.
    Returns an absolute path or None.
    """
    preference = ['Normal', 'Hard', 'Expert', 'ExpertPlus', 'Easy']
    for diff in preference:
        for f in sorted(os.listdir(beatmap_dir)):
            if not f.endswith(('.dat', '.json')) or f == empty_file:
                continue
            base = os.path.basename(f)
            stem = base.replace('.dat', '').replace('.json', '')
            # Standard-only donors (no mode suffix); accept both naming
            # conventions: bare "Normal.dat" and suffixed "NormalStandard.dat"
            # (the V4→V3 backout layout).
            if 'lightshow' in stem.lower() or any(
                    m.lower() in stem.lower()
                    for m in ('onesaber', 'noarrows', '90degree', '360degree')):
                continue
            if stem not in (diff, f"{diff}Standard"):
                continue
            path = os.path.join(beatmap_dir, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    j = json.load(fh)
            except Exception:
                continue
            notes = j.get('colorNotes') or (
                [{'b': n.get('_time')} for n in j.get('_notes', [])
                 if int(n.get('_type', 0)) != 3])
            if notes:
                return path
    return None


def replace_beatmaps(cab, beatmap_dir: str, ignore_non_standard=False, auto_convert=False):
    """
    Replace all 5 difficulty beatmaps with custom ones.

    Matches difficulty by name (Easy, Normal, Hard, Expert, ExpertPlus).
    Custom .dat or .json files are loaded, re-encoded as gzipped V3 JSON,
    and written to the corresponding TextAsset in the CAB.

    File selection uses a priority fallback chain (see _select_beatmap_file):
      1. <Diff>Standard.dat   (preferred)
      2. <Diff>.dat           (bare, no mode suffix)
      3. <Diff>.beatmap.dat   (BeatSaver .beatmap.dat format)
      4. <Diff>90Degree.dat / OneSaber.dat / etc. (if not --ignore-non-standard)
      (360Degree files are always excluded — the PS4 camera cannot track them)

    Args:
        cab: Unity CAB bundle
        beatmap_dir: Directory containing .dat beatmap files
        ignore_non_standard: If True, skip tier-4 fallback (90Degree, OneSaber, etc.)
    """
    # Read BPM from Info.dat for V2→V3 conversion (used in bpmEvents)
    bpm = 120.0
    info_path = os.path.join(beatmap_dir, "Info.dat")
    if not os.path.exists(info_path):
        info_path = os.path.join(beatmap_dir, "info.dat")
    if os.path.exists(info_path):
        with open(info_path) as f:
            info = json.load(f)
        # Exp 228: format-aware (V4 maps carry audio.bpm, not _beatsPerMinute)
        v4_bpm = _read_info_bpm_from_dict(info)
        bpm = v4_bpm if v4_bpm is not None else 120.0

    beatmap_files = [f for f in os.listdir(beatmap_dir)
                     if f.endswith(('.json', '.dat'))]

    if not beatmap_files:
        log.warning("  No .json or .dat beatmap files found!")
        return 0

    replaced = 0
    for pid, reader in cab.objects.items():
        if reader.class_id == 49:
            name = reader.peek_name() or ''
            # Only target .beatmap.gz files (NOT lightshow, NOT info, NOT audio.gz)
            if '.beatmap.gz' not in name and 'Beatmap' not in name:
                continue

            # Determine which difficulty this TextAsset slot is for
            matched_file = None
            for diff in DIFFICULTIES:
                # IMPORTANT: exclude "ExpertPlus" when matching "Expert" (substring trap)
                if diff == 'Expert' and 'ExpertPlus' in name:
                    continue
                if diff not in name:
                    continue
                # Got the slot — now pick the best source file
                matched_file = _select_beatmap_file(diff, beatmap_files, ignore_non_standard)
                break

            if matched_file:
                path = os.path.join(beatmap_dir, matched_file)
                with open(path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)

                # Auto-convert V4 columnar → V3 denormalized if needed
                # (Exp 228: v4 sources otherwise ship {b,i}-only notes)
                if is_v4_beatmap(data):
                    data = convert_v4_to_v3(data)
                    log.info(f"  Converted V4 columnar -> V3: '{matched_file}'")

                # Auto-convert V2 → V3.2.0 if requested
                if auto_convert and is_v2_beatmap(data):
                    data = convert_v2_to_v3(data, default_bpm=bpm)
                    log.info(f"  Converted V2 -> V3: '{matched_file}'")

                # Normalize to the complete V3 schema — minimal-schema maps
                # (missing basicBeatmapEvents/waypoints/light*EventBoxGroups, e.g.
                # V4→V3-reconstructed Chromeo sources) crash the game at gameplay
                # load (Exp 200).
                missing_before = set(_V3_REQUIRED_ARRAYS) - set(data)
                normalize_v3_schema(data)
                if missing_before:
                    log.info(f"  Normalized V3 schema of '{matched_file}' "
                             f"(added {sorted(missing_before)})")

                # Empty-beatmap fallback: a playable difficulty with zero notes
                # crashes/bricks the slot (Chromeo Easy maps decoded empty, Exp 200).
                # Clone the closest populated difficulty's content so the slot plays.
                if beatmap_is_empty(data):
                    donor = _find_populated_beatmap(beatmap_dir, matched_file)
                    if donor:
                        with open(donor, 'r', encoding='utf-8') as fh:
                            ddata = json.load(fh)
                        if is_v4_beatmap(ddata):
                            ddata = convert_v4_to_v3(ddata)
                        if is_v2_beatmap(ddata):
                            ddata = convert_v2_to_v3(ddata, default_bpm=bpm)
                        normalize_v3_schema(ddata)
                        data['colorNotes'] = ddata.get('colorNotes', [])
                        data['bombNotes'] = ddata.get('bombNotes', [])
                        data['obstacles'] = ddata.get('obstacles', [])
                        data['sliders'] = ddata.get('sliders', [])
                        data['burstSliders'] = ddata.get('burstSliders', [])
                        log.info(f"  '{matched_file}' had NO notes — cloned playable "
                                 f"content from '{os.path.basename(donor)}'")

                # Fix V3/V4 beatmaps with empty/missing bpmEvents (same BPM=60 fallback bug)
                if not data.get('bpmEvents'):
                    data['bpmEvents'] = [{"b": 0, "m": bpm}]
                    log.info(f"  Added bpmEvents ({bpm} BPM) to '{matched_file}'")

                # Encode as gzipped JSON
                json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
                compressed = gzip.compress(json_bytes)

                # Update the TextAsset
                tt = reader.read_typetree()
                tt['m_Script'] = compressed.decode('utf-8', 'surrogateescape')
                reader.save_typetree(tt)
                replaced += 1
                log.info(f"  Beatmap '{name}' <- '{matched_file}'")
            else:
                log.debug(f"  Skipping '{name}' (no matching beatmap file)")

    return replaced


# ============================================================================
# Step 6: Save bundle
# ============================================================================

def save_bundle(bf, output_path: str):
    """
    Save the modified bundle with LZ4 compression (matching original PS4 format).
    """
    log.info("Saving bundle with LZ4 compression...")
    result = bf.save(packer="lz4")
    with open(output_path, 'wb') as f:
        f.write(result)
    log.info(f"  Saved: {output_path} ({len(result)} bytes)")

    # Verify the saved bundle can be re-loaded
    try:
        UnityPy.load(output_path)
        log.info("  Verified: bundle loads correctly")
    except Exception as e:
        log.warning(f"  Verify failed (may still work): {e}")


# ============================================================================
# Step 7: Deploy to PS4
# ============================================================================

def _deployed_bundle_name(slot: str, config: dict) -> str:
    """
    Return the EXACT filename that a song bundle is deployed as on the PS4.

    This is the single source of truth for deployed bundle naming: the remote
    filename MUST be identical to what the local mass_build file is called
    (e.g. `crystallized_v3.bundle`), because the game opens the redirect VALUE
    verbatim — a mismatch means the freshly deployed bundle is never loaded and
    the stale one keeps being served.

    Naming: `{slot}{afr_target_suffix}` using the canonical slot casing from
    mass_deploy.slots (the game's open() is case-sensitive, so the redirect
    value must match the uploaded file byte-for-byte). Falls back to
    `{slot}{_v3.bundle}` if no suffix is configured.
    """
    md = config.get('mass_deploy', {}) or {}
    slots = md.get('slots', [])
    canonical = slot
    for s in slots:
        if s.lower() == slot.lower():
            canonical = s
            break
    suffix = config.get('paths', {}).get('afr_target_suffix', '_v3.bundle')
    return f"{canonical}{suffix}"

def _ensure_mass_song_redirects(redirect_data: dict, config: dict,
                                slots: list | None = None,
                                remote_files: dict | None = None) -> int:
    """
    (Re)generate the per-song redirect entries so every VALUE points at the
    exact deployed bundle filename (canonical slot casing + afr_target_suffix).

    Preserves existing redirect KEYS (the game asset paths, e.g.
    `BeatmapLevelsData/Crystallized`) while fixing their VALUES, adds any slot
    missing from the config, and removes stale pre-`.bundle` entries
    (e.g. value `Crystallized_v3` while the deployed file is
    `crystallized_v3.bundle`).

    Case-collision guard (Exp 263): when `remote_files` (the LIVE AFR dir
    listing, {filename: size}) is provided, a value that already names a file
    that EXISTS on the PS4 is NEVER rewritten. The old healing rewrote
    `MessItUp_v3.bundle` -> `messitup_v3.bundle` because the default config's
    slot list prefers lowercase — but single-song deploys don't re-upload
    out-of-scope slots, so the file on disk kept its mixed-case name and the
    healed redirect DANGLED (the song fails to load; the post-deploy check
    "redirect targets missing on PS4" is what caught it). Healing may now only
    FIX a genuinely-dangling value, and it fixes it toward the case variant
    that actually exists on disk.

    If `slots` is provided, ONLY those slots will have redirects - all other
    song redirects are removed. This allows single-song scoped deploys to not
    carry stale redirects from previous full-fleet deploys.

    `slots` optionally limits which slots are ensured (default: all configured slots).
    Returns the number of entries changed.
    """
    md = config.get('mass_deploy', {}) or {}
    all_configured = md.get('slots', [])
    if not all_configured:
        return 0

    # If slots is provided, only keep those slots; otherwise use all configured
    if slots is not None:
        # An EMPTY slots list is a NO-OP for removal (Exp 226): it is used by
        # callers to mean "no slots need extra pack modes" — never "delete all
        # song redirects". The empty-scope wipe previously destroyed every
        # song redirect from every pack when --clear-target-song cleared the
        # last custom song of an unrelated pack. Removing redirects is the
        # job of the dedicated removal paths (--clear-target-song, clean
        # slate), not of scope filtering.
        if len(slots) == 0:
            log.info("  ℹ️  Empty slot scope — preserving all existing song redirects")
            configured = []
            # fall through WITHOUT removing anything
        else:
            # Case-insensitive matching: slots from PS4 redirects may have different casing
            # than mass_deploy.slots (e.g., "Crystallized" vs "crystallized")
            slots_lower = {s.lower(): s for s in slots}
            configured = [s for s in all_configured if s.lower() in slots_lower]
            if not configured:
                # Requested slots are not in mass_deploy config — still preserve
                # existing redirects; only OUT-OF-SCOPE removal below trims.
                # (The old branch deleted EVERYTHING here — including slots from
                # packs the user never asked to touch, Exp 226.)
                log.info("  ℹ️  Requested slots not in mass_deploy config — preserving existing redirects")
                configured = []
    else:
        configured = all_configured

    redirects = redirect_data.setdefault('redirects', {})
    changed = 0

    # When slots is provided AND matches at least one configured slot, remove
    # redirects for slots NOT in the scope — but ONLY when their deployed
    # bundle is genuinely absent from this deploy's scope semantics. A slot
    # whose redirect exists because a PREVIOUS deploy installed it must keep
    # its redirect: scope filtering must never turn into an unintended wipe
    # (Exp 226; and Exp 246: the scope passed here is built from the LIVE PS4
    # state precisely so out-of-scope = "not deployed anywhere", never
    # "deployed by someone else"). Removing redirects is the job of the
    # dedicated removal paths (--clear-target-song, clean slate).
    if slots is not None and configured:
        scoped = {s.lower() for s in slots}
        for k in list(redirects):
            if k.startswith('BeatmapLevelsData/'):
                slot = k[len('BeatmapLevelsData/'):]
                if slot.lower() not in scoped:
                    # Defensive guard (Exp 246): if the redirect's target
                    # bundle is one this session just built/deployed (i.e. it
                    # IS part of the deployed fleet), never sweep it. This is
                    # a belt-and-suspenders check — the scope construction in
                    # the deploy path already includes all live slots; this
                    # catches any future caller that passes an underscope.
                    log.warning(f"  ⚠️  Preserving out-of-scope song redirect "
                                f"(dedicated removal paths only): {k} -> {redirects[k]}")

    for slot in configured:
        key = f"BeatmapLevelsData/{slot}"
        value = _deployed_bundle_name(slot, config)
        # Reuse an existing key whose basename matches this slot (case-insensitive),
        # so known-good game asset paths (e.g. `BeatmapLevelsData/Crystallized`)
        # are preserved rather than replaced by the slot casing.
        for k in list(redirects):
            if k != key and k.startswith('BeatmapLevelsData/') \
               and k[len('BeatmapLevelsData/'):].lower() == slot.lower():
                key = k
                break
        # Remove stale pre-.bundle entries that shadow this slot.
        for k in list(redirects):
            if k != key and k.startswith('BeatmapLevelsData/') \
               and k[len('BeatmapLevelsData/'):].lower() == slot.lower():
                log.info(f"  🧹 Removed stale song redirect: {k} -> {redirects[k]}")
                del redirects[k]
                changed += 1
        existing = redirects.get(key)
        if existing == value:
            continue
        # Case-collision guard (Exp 263): a value that already names a file
        # present on the PS4 is healthy — never rewrite it just because the
        # config's slot list spells the slot with different casing. Out-of-scope
        # slots are not re-uploaded by this deploy, so a "healed" value can
        # dangle against the on-disk name.
        if remote_files is not None and existing in remote_files:
            log.info(f"  ℹ️  Keeping existing redirect value (target file on PS4): "
                     f"{key} -> {existing}")
            continue
        if remote_files is not None and existing is not None:
            # The value dangles at its exact case — but if a case variant of
            # the same filename exists on disk, heal TOWARD it (the deployed
            # file), never away from it.
            on_disk = {n.lower(): n for n in remote_files}
            disk_variant = on_disk.get((existing or '').lower())
            if disk_variant and disk_variant != existing:
                log.info(f"  🩹 Healing redirect value to the on-disk filename: "
                         f"{key}: {existing} -> {disk_variant}")
                redirects[key] = disk_variant
                changed += 1
                continue
        redirects[key] = value
        changed += 1
    if changed:
        log.info(f"  🎵 Ensured {len(configured)} song redirects point at deployed bundles ({changed} entries updated)")
    return changed

def _ensure_afr_title_dir(config: dict):
    """Create the AFR title dir if absent (Exp 281b — the fresh-console
    bootstrap bug): after Clear PS4 with no plugin boot yet, the dir does not
    exist and EVERY AFR upload fails ('Access failed: 550' on the put).
    Idempotent: lftp mkdir -p -f creates intermediate dirs and stays silent
    when they already exist. Runs as its own quick lftp session before any
    AFR write."""
    import subprocess as sp

    ps4_cfg = config.get('ps4', {})
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')
    user_part = f"{user},{password}" if password else f"{user},"
    afr_base = config.get('paths', {}).get('afr_base', '/data/GoldHEN/AFR')
    title_id = config.get('title', {}).get('id', 'CUSA12878')
    remote_dir = f"{afr_base}/{title_id}"
    cmd = ["lftp", "-u", user_part, "-p", str(port), host, "-e",
           f"mkdir -p -f {_ftp_quote(remote_dir)}; quit"]
    try:
        sp.run(cmd, capture_output=True, text=True, timeout=15)
    except sp.TimeoutExpired:
        pass  # the following put will surface a real failure if the PS4 is gone


def deploy_to_ps4(bundle_path: str, target_name: str, config: dict):
    """
    Upload the bundle to the PS4 via FTP.
    Target path: {afr_base}/{title_id}/{remote_name}
    All paths read from config.
    """
    _ensure_afr_title_dir(config)
    import subprocess as sp

    # Session upload ledger (Exp 264): record the remote names this PROCESS
    # uploaded successfully. verify's size check uses it to distinguish
    # "did MY upload land?" (hard-fail — the check's actual purpose) from
    # "does a stale local artifact of an out-of-scope song match live state?"
    # (informational only — a local file built by a different pipeline
    # version legitimately differs from the deployed copy; failing the
    # deploy on it stopped the user's batch on a song the batch never
    # touched).
    global _SESSION_UPLOADED_BUNDLES

    ps4_cfg = config.get('ps4', {})
    title_cfg = config.get('title', {})
    paths_cfg = config.get('paths', {})

    afr_base = paths_cfg.get('afr_base', '/data/GoldHEN/AFR')
    title_id = title_cfg.get('id', 'CUSA12878')
    ftp_host = ps4_cfg.get('ip', '192.168.100.117')
    ftp_port = ps4_cfg.get('ftp_port', 2121)
    ftp_user = ps4_cfg.get('ftp_user', 'anonymous')
    ftp_pass = ps4_cfg.get('ftp_password', '')

    remote_name = _deployed_bundle_name(target_name, config)
    remote_path = f"{afr_base}/{title_id}/{remote_name}"

    user_part = f"{ftp_user},{ftp_pass}" if ftp_pass else f"{ftp_user},"
    cmd = [
        "lftp", "-u", user_part, "-p", str(ftp_port),
        ftp_host,
        "-e", f"put {_ftp_quote(bundle_path)} -o {_ftp_quote(remote_path)}; quit"
    ]

    log.info(f"Deploying bundle to PS4: {remote_path}")
    result = sp.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        log.warning(f"  ⚠️ Bundle deploy failed (PS4 offline?): {result.stderr}")
        return

    # lftp can exit 0 while a put silently failed (metacharacters in the path
    # split the command — the Scream&Shout upload landed at the wrong name and
    # lftp still returned 0, Exp 224). Verify the remote file actually exists
    # with the expected size before reporting success.
    local_size = os.path.getsize(bundle_path) if os.path.isfile(bundle_path) else None
    rc, out, err = _ftp_run(ftp_host, ftp_port, ftp_user, ftp_pass,
                            [f"ls {_ftp_quote(remote_path)}"], timeout=30)
    listed_size = None
    if rc == 0 and out:
        # lftp ls line: "perms ... <size> <date> <name>" — size is field 4.
        # Exp 281c: GoldHEN's FTPD ends the line with the FULL PATH, not the
        # basename — the old basename equality never matched and every upload
        # reported UNVERIFIED (false negative; the user's 28MB bundle was
        # verifiably on the console). Match the basename within the last field.
        remote_name = remote_path.split('/')[-1]
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 9 and remote_name in parts[-1]:
                try:
                    listed_size = int(parts[4])
                except ValueError:
                    pass
    if listed_size is None:
        log.warning(f"  ⚠️ Bundle deploy UNVERIFIED — {remote_path} not found in listing "
                    f"(upload may have silently failed; stderr: {err.strip()[:200]})")
        return
    if local_size is not None and listed_size != local_size:
        log.warning(f"  ⚠️ Bundle deploy SIZE MISMATCH — remote {remote_path} is "
                    f"{listed_size} bytes, expected {local_size}")
        return
    _SESSION_UPLOADED_BUNDLES.add(remote_name)
    log.info(f"  ✅ Bundle deployment successful ({listed_size} bytes verified on PS4)")


def _create_text_asset_object(cab, name, gz_data, path_id):
    """
    Create a new TextAsset ObjectReader in a CAB bundle.

    Creates a new ObjectReader with the raw TextAsset binary data (m_Name +
    m_Script string-as-array fields) and adds it to cab.objects under the
    given path_id. The data attribute is set so that SerializedFile.write()
    emits the raw bytes directly without requiring the typetree parser.

    Args:
        cab: SerializedFile (CAB) to add the object to.
        name: m_Name for the TextAsset (e.g. "StartMeUpEasyNoArrows.beatmap.gz").
        gz_data: Raw gzipped beatmap bytes for m_Script.
        path_id: Unique positive path ID for the new object.

    Returns:
        The new ObjectReader instance.
    """
    from UnityPy.files.ObjectReader import ObjectReader
    from UnityPy.streams.EndianBinaryWriter import EndianBinaryWriter

    # Build Unity TextAsset binary format using UnityPy's writer to ensure
    # correct alignment and no null terminators:
    #   m_Name:   int32 length + UTF-8 bytes + 4-byte alignment padding
    #   m_Script: int32 length + raw bytes + 4-byte alignment padding
    endian = '>' if cab.header.endian == '>' else '<'
    writer = EndianBinaryWriter(endian=endian)
    writer.write_aligned_string(name)
    writer.write_int(len(gz_data))
    writer.write(gz_data)
    writer.align_stream(4)
    raw_data = writer.bytes

    # Build a reader positioned at byte 0 with our data
    reader = EndianBinaryReader(raw_data, endian)

    # Find the TextAsset serialized type (class_id 49) and its index
    text_asset_type = None
    text_asset_type_index = 0
    for i, t in enumerate(cab.types):
        if t.class_id == 49:
            text_asset_type = t
            text_asset_type_index = i
            break
    if text_asset_type is None:
        log.warning("  Could not find TextAsset serialized type - cannot create new asset")
        return None

    # Create the new ObjectReader with data set (write uses data directly)
    new_obj = ObjectReader(
        assets_file=cab,
        reader=reader,
        path_id=path_id,
        type_id=text_asset_type_index,
        serialized_type=text_asset_type,
        class_id=49,
        type=49,
        byte_start=0,
        byte_size=len(raw_data),
        is_destroyed=0,
        is_stripped=0,
        data=raw_data,
    )

    cab.objects[path_id] = new_obj
    return new_obj


def add_mode_characteristics(cab, enable_modes: list, song_dir: str = None,
                              generated_files: list = None, bpm: float = 120.0,
                              target_name: str = None) -> int:
    """
    Add additional beatmap characteristics (OneSaber, NoArrows, 90Degree, etc.)
    to the BeatmapLevel object so they appear in the in-game mode selector.

    When ``song_dir`` and ``generated_files`` are provided, the pipeline looks
    for generated ``<Diff><Mode>.dat`` files on disk, compresses them, and
    injects them as **new TextAsset objects** in the CAB bundle. The new
    mode sets in the BeatmapLevel are linked to these new TextAssets — NOT to
    the Standard beatmaps.

    When ``song_dir``/``generated_files`` are not provided (legacy fallback),
    the function falls back to cloning Standard's beatmap asset references,
    so the song is still playable (Standard notes play in non-Standard modes).

    Args:
        cab: Unity CAB bundle containing BeatmapLevel
        enable_modes: List of characteristic names (e.g. ["OneSaber", "NoArrows", "90Degree"])
        song_dir: Directory containing generated .dat files (optional)
        generated_files: List of generated .dat filenames (e.g. ["EasyNoArrows.dat", ...])

    Returns:
        Number of modes added
    """
    if not enable_modes:
        return 0

    # Build a lookup of generated beatmap files: {mode: {difficulty_index: filename}}
    # Scan the song directory for ALL mode-specific beatmap files, not just
    # newly-generated ones — files from a previous pipeline run or hand-authored
    # songs also need to be injected.
    gen_lookup: dict[str, dict[int, str]] = {}
    # Also include explicitly-passed generated_files (for testing / explicit calls)
    all_filenames = set()
    if song_dir and os.path.isdir(song_dir):
        all_filenames.update(os.listdir(song_dir))
    if generated_files:
        all_filenames.update(generated_files)
    for fname in sorted(all_filenames):
        if not fname.endswith(('.dat', '.json')):
            continue
        low = fname.lower()
        if low in ('info.dat', 'info.json', 'bpminfo.dat'):
            continue
        if 'lightshow' in low or 'audiodata' in low or 'audio' in low:
            continue
        for mode in enable_modes:
            if mode == "Standard":
                continue
            if mode not in fname:
                continue
            # Match longest difficulty name first (ExpertPlus before Expert)
            for di in range(len(DIFFICULTIES) - 1, -1, -1):
                diff = DIFFICULTIES[di]
                if diff in fname:
                    gen_lookup.setdefault(mode, {})[di] = fname
                    break

    has_generated = bool(gen_lookup)

    # Determine the next available path_id for new TextAsset objects.
    # Unity path_ids in this CAB are large negatives; use large positives
    # to avoid collision.
    max_existing = max((abs(int(pid)) for pid in cab.objects.keys()), default=0)
    next_pid = max(max_existing + 1, 9000000000000000000)

    added = 0
    for pid, reader in cab.objects.items():
        # BeatmapLevel = class_id 114
        if reader.class_id != 114:
            continue

        tt = reader.read_typetree()
        existing_sets = tt.get('_difficultyBeatmapSets', [])

        # Build a set of already-present characteristic names
        existing_chars = set()
        for s in existing_sets:
            ch = s.get('_beatmapCharacteristicSerializedName', '')
            existing_chars.add(ch)

        if 'Standard' not in existing_chars:
            log.warning("  No Standard characteristic found - cannot add modes")
            return 0

        # Find the Standard set to use for difficulty ordering / lightshow refs
        standard_set = None
        for s in existing_sets:
            if s.get('_beatmapCharacteristicSerializedName') == 'Standard':
                standard_set = s
                break

        if not standard_set:
            log.warning("  Standard characteristic not found - cannot add modes")
            return 0

        std_diffs = standard_set.get('_difficultyBeatmaps', [])

        # Add each requested mode
        for mode in enable_modes:
            if mode in existing_chars:
                if has_generated and any(di in gen_lookup.get(mode, {}) for di in range(len(std_diffs))):
                    # Mode exists but we have generated beatmaps to inject — replace it
                    log.info(f"  Mode '{mode}' exists — refreshing with generated beatmaps")
                    existing_sets = [s for s in existing_sets
                                     if s.get('_beatmapCharacteristicSerializedName') != mode]
                    existing_chars.discard(mode)
                else:
                    log.info(f"  Mode '{mode}' already exists - skipping (no generated files)")
                    continue

            new_set = {
                '_beatmapCharacteristicSerializedName': mode,
                '_difficultyBeatmaps': []
            }

            # Use the Standard difficulty entries as the template for ordering/lightshows
            for di, std_entry in enumerate(std_diffs):
                diff = DIFFICULTIES[di] if di < len(DIFFICULTIES) else ''

                # --- Try to inject a real generated beatmap asset ---
                if has_generated and di in gen_lookup.get(mode, {}):
                    fname = gen_lookup[mode][di]
                    fpath = os.path.join(song_dir, fname)
                    if os.path.isfile(fpath):
                        try:
                            with open(fpath, 'r', encoding='utf-8') as fh:
                                bm_data = json.load(fh)
                            # Convert V4 columnar → V3 (Exp 228), then V2 → V3
                            # if needed (game requires V3.2.0)
                            if is_v4_beatmap(bm_data):
                                bm_data = convert_v4_to_v3(bm_data)
                                log.info(f"  {mode}/{diff}: converted V4→V3 for injection")
                            if is_v2_beatmap(bm_data):
                                bm_data = convert_v2_to_v3(bm_data, default_bpm=bpm)
                                log.info(f"  {mode}/{diff}: converted V2→V3 for injection")
                            # Normalize to complete V3 schema (Exp 200 crash fix) and
                            # rescue empty maps from the Standard donor chain.
                            normalize_v3_schema(bm_data)
                            if beatmap_is_empty(bm_data):
                                donor = _find_populated_beatmap(song_dir, fname)
                                if donor:
                                    with open(donor, 'r', encoding='utf-8') as fh:
                                        ddata = json.load(fh)
                                    if is_v4_beatmap(ddata):
                                        ddata = convert_v4_to_v3(ddata)
                                    if is_v2_beatmap(ddata):
                                        ddata = convert_v2_to_v3(ddata, default_bpm=bpm)
                                    normalize_v3_schema(ddata)
                                    for k in ('colorNotes', 'bombNotes', 'obstacles',
                                              'sliders', 'burstSliders'):
                                        bm_data[k] = ddata.get(k, [])
                                    log.info(f"  {mode}/{diff}: source map EMPTY — "
                                             f"cloned playable content from "
                                             f"{os.path.basename(donor)}")
                            # Fix empty bpmEvents (same fallback as replace_beatmaps)
                            if not bm_data.get('bpmEvents'):
                                bm_data['bpmEvents'] = [{"b": 0, "m": bpm}]
                            # OneSaber normalization (Exp 218): even mapper-authored
                            # charts must be blue-only + dots — the user-facing
                            # OneSaber convention on this setup. Maps that ship
                            # their own *OneSaber.dat (e.g. Jealous, 'Roni) had
                            # mixed colors and directional arrows.
                            if mode == "OneSaber":
                                bm_data = _generate_one_saber(bm_data)
                                log.info(f"  {mode}/{diff}: normalized to blue dots")
                            # NoArrows normalization AFTER format conversion
                            # (Exp 231): V4 columnar sources sneak past the
                            # generator — it writes d=8 (dots) onto the EVENTS,
                            # but the rows in colorNotesData keep their arrow d,
                            # and convert_v4_to_v3 merges row-OVER-event, so the
                            # arrows come back ('15 Minutes' shipped NoArrows
                            # charts identical to Standard). Re-applying the
                            # dots pass on the DENORMALIZED data is idempotent
                            # for well-formed sources (d=8 stays d=8) and fixes
                            # columnar ones. 90Degree needs no such pass: its
                            # generator only APPENDS rotationEvents, which the
                            # row merge cannot clobber.
                            elif mode == "NoArrows":
                                bm_data = _generate_no_arrows(bm_data)
                                log.info(f"  {mode}/{diff}: re-applied dot pass after format conversion")
                            json_bytes = json.dumps(bm_data,
                                                    separators=(',', ':')).encode('utf-8')
                            gz_bytes = gzip.compress(json_bytes)

                            # Name the TextAsset after the generated file (with .beatmap.gz suffix)
                            ta_name = f"{target_name}{diff}{mode}.beatmap.gz" if target_name else f"Beatmap_{diff}{mode}.beatmap.gz"
                            new_pid = next_pid
                            next_pid += 1
                            _create_text_asset_object(cab, ta_name, gz_bytes, new_pid)

                            new_set['_difficultyBeatmaps'].append({
                                '_difficulty': std_entry['_difficulty'],
                                '_beatmapAsset': {
                                    'm_FileID': 0,
                                    'm_PathID': new_pid,
                                },
                                '_lightshowAsset': std_entry['_lightshowAsset'],
                            })
                            log.info(f"  {mode}/{diff}: injected {fname} as TextAsset pid={new_pid}")
                            continue
                        except Exception as e:
                            log.warning(f"  {mode}/{diff}: failed to inject generated beatmap ({e})")
                    else:
                        log.warning(f"  {mode}/{diff}: generated file {fpath} not found")

                # --- Fallback: clone Standard beatmap reference ---
                new_set['_difficultyBeatmaps'].append({
                    '_difficulty': std_entry['_difficulty'],
                    '_beatmapAsset': std_entry['_beatmapAsset'],
                    '_lightshowAsset': std_entry['_lightshowAsset'],
                })

            existing_sets.append(new_set)
            existing_chars.add(mode)
            added += 1
            log.info(f"  Added mode: {mode}")

        tt['_difficultyBeatmapSets'] = existing_sets
        reader.save_typetree(tt)
        break  # Only one BeatmapLevel per bundle

    log.info(f"  Modes added: {added}")
    return added


# ============================================================================
# Feature: Beatmap Mode Mapping (auto-detect characteristic modes)
# ============================================================================

# Mode Generators
# Generated mode beatmaps are derived from Standard beatmaps when a custom
# song does not provide its own mode-specific files. Every generator is
# format-aware (V2: _notes/_time/_cutDirection, V3: colorNotes/b/d) and
# never mutates its input.

_ONE_SABER_COLOR = 1          # OneSaber uses the RIGHT (blue) saber exclusively (right/1)
_ONE_SABER_MIN_GAP = 0.25     # beats — closer same-cell arrowed notes are un-hittable
_ROTATION_CYCLE_BEATS = 8.0   # 90Degree — one lane-rotation event every N beats (2 measures at 4/4)
_ROTATION_STEP_DEGREES = 15   # 90Degree — single-lane step per rotation event (15° = 1 lane)
_ROTATION_MAX_DEGREES = 45    # 90Degree — max swing from center (90° arc = ±45° = 3 lanes/side)


def _get_color_notes(beatmap_data: dict) -> list | None:
    """Return the color-note list (V3 colorNotes / V2 _notes), or None."""
    if "colorNotes" in beatmap_data:
        return beatmap_data["colorNotes"]
    if "_notes" in beatmap_data:
        return beatmap_data["_notes"]
    return None


def _is_v3_beatmap(beatmap_data: dict) -> bool:
    """True if the beatmap uses V3 field names (colorNotes/b/d/c)."""
    return "colorNotes" in beatmap_data


def _generate_no_arrows(beatmap_data: dict) -> dict:
    """Convert every color note into a dot (no cut direction).

    Both V2 (``_cutDirection``) and V3 (``d``) beatmaps are supported.
    Bombs are left untouched — only color notes become dots.
    """
    notes = _get_color_notes(beatmap_data)
    if notes is None:
        return beatmap_data
    out = copy.deepcopy(beatmap_data)
    out_notes = _get_color_notes(out)
    v3 = _is_v3_beatmap(out)
    for note in out_notes:
        if v3:
            note["d"] = 8
        elif int(note.get("_type", 0)) in (0, 1):
            note["_cutDirection"] = 8
    return out


def _generate_one_saber(beatmap_data: dict, min_gap: float = _ONE_SABER_MIN_GAP) -> dict:
    """Convert a Standard beatmap into a playable OneSaber variant.

    - Recolors every color note to a single saber color (1 / right — OneSaber
      is played exclusively with the right/blue saber).
    - Converts every note to a DOT (d/_cutDirection = 8). The user-facing
      OneSaber experience on this setup is dots-only (Exp 218: "one saber
      mode ... still had arrows on the note boxes" — mapper-authored OneSaber
      charts and Standard-clone fallbacks both kept directional arrows).
      Dots also remove the same-cell arrow-collision constraint entirely.
    - Removes notes that are impossible to hit with one saber:
      simultaneous notes (one saber can only cut one note per instant).

    The input dict is not modified (a deep copy is returned).
    """
    notes = _get_color_notes(beatmap_data)
    if notes is None:
        return beatmap_data
    out = copy.deepcopy(beatmap_data)
    out_notes = _get_color_notes(out)
    v3 = _is_v3_beatmap(out)

    def _time(n): return float(n.get("b", 0.0) if v3 else n["_time"])
    def _is_bomb(n):
        return (int(n.get("c", 0)) if v3 else int(n.get("_type", 0))) == 3

    occupied_times = set()                    # beats already claimed by a kept note

    kept = []
    for note in sorted(out_notes, key=_time):
        if _is_bomb(note):
            kept.append(note)
            continue
        t = _time(note)
        # One saber can only hit one note at a given instant.
        if t in occupied_times:
            continue
        # Recolor to the single saber color and convert to a DOT (Exp 218:
        # arrows in generated OneSaber read as "still Standard" to the user).
        if v3:
            note["c"] = _ONE_SABER_COLOR
            note["a"] = _ONE_SABER_COLOR
            note["d"] = 8
        else:
            note["_type"] = _ONE_SABER_COLOR
            note["_cutDirection"] = 8
        kept.append(note)
        occupied_times.add(t)

    if v3:
        out["colorNotes"] = kept
    else:
        out["_notes"] = kept
    return out


def _generate_90_degree(beatmap_data: dict, cycle_beats: float = _ROTATION_CYCLE_BEATS,
                        bpm: float = 120.0, step_deg: float = _ROTATION_STEP_DEGREES,
                        max_deg: float = _ROTATION_MAX_DEGREES) -> dict:
    """Generate a 90Degree variant of a Standard beatmap.

    90Degree gameplay confines the playfield to a 90° arc centered on the
    player's forward lane (BSMG wiki, Extended Mapping; verified against the
    official/community 90° maps): the valid lanes are 0° (center), ±15°,
    ±30°, ±45° — three lanes left and three lanes right of center.

    This generator:
      - Converts V2 source data to V3 (V2 has no rotation events).
      - Emits one ``rotationEvents`` entry every ``cycle_beats`` beats, each
        moving the lane a SINGLE step (15°) in the current sweep direction.
        The sweep starts at the center lane, reverses direction only after
        reaching the ±``max_deg`` extremes, and never skips a lane or jumps
        over the center in one event.
      - Rotation values are RELATIVE deltas (negative = left/CCW, positive =
        right/CW) that the game accumulates onto the current spawn rotation.

    The input dict is not modified (a deep copy is returned).
    """
    if not _is_v3_beatmap(beatmap_data):
        out = convert_v2_to_v3(beatmap_data, default_bpm=bpm)
    else:
        out = copy.deepcopy(beatmap_data)

    notes = out.get("colorNotes", []) or []
    first_beat = 0.0
    last_beat = first_beat
    if notes:
        first_beat = float(min(n.get("b", 0.0) for n in notes))
        last_beat = float(max(n.get("b", 0.0) for n in notes))
    for obs in out.get("obstacles", []) or []:
        last_beat = max(last_beat, float(obs.get("b", 0.0)))
    for ev in out.get("basicBeatmapEvents", []) or []:
        last_beat = max(last_beat, float(ev.get("b", 0.0)))

    existing = list(out.get("rotationEvents", []) or [])
    events = []
    pos = 0.0          # cumulative rotation — starts at the center lane
    direction = 1.0    # sweep direction: +1 = right (CW), -1 = left (CCW)
    t = first_beat
    while t < last_beat + cycle_beats:
        next_pos = pos + direction * step_deg
        if next_pos > max_deg:
            direction = -1.0
            next_pos = pos - step_deg
        elif next_pos < -max_deg:
            direction = 1.0
            next_pos = pos + step_deg
        events.append({"b": round(t, 4), "e": 1, "r": next_pos - pos})
        pos = next_pos
        t += cycle_beats
    out["rotationEvents"] = existing + events
    return out


_MODE_GENERATORS = {
    "NoArrows": _generate_no_arrows,
    "OneSaber": _generate_one_saber,
    "90Degree": _generate_90_degree,
}


def fill_missing_standard_difficulties(song_dir: str) -> list[str]:
    """
    Materialize a Standard beatmap file for every difficulty the source map
    does not provide, cloned from the map's own closest difficulty.

    Why (Exp 218): every difficulty slot in the target bundle corresponds to a
    TextAsset that the pipeline replaces ONLY when a matching source file
    exists. Missing diffs left the STOCK beatmap in place — timed for the stock
    song's BPM/grid but played over the CUSTOM audio ("BPM wayyy too slow,
    notes wayyy too late"). This must run BEFORE mode generation (which gates
    on a Standard source per diff) and BEFORE beatmap replacement.

    Donor choice: the closest HARDER difficulty (playing up is safer than
    down); if none, the closest easier one. Never overwrites an existing file.

    Returns list of written file names.
    """
    beatmap_files = [f for f in sorted(os.listdir(song_dir))
                     if f.endswith(('.dat', '.json'))]
    # Which difficulties does the map provide a Standard source for?
    have = set()
    for diff in DIFFICULTIES:
        if _select_beatmap_file(diff, beatmap_files, ignore_non_standard=True):
            have.add(diff)

    written = []
    for idx, diff in enumerate(DIFFICULTIES):
        if diff in have:
            continue
        # Closest harder diff first (Hard missing -> Expert, ExpertPlus);
        # else closest easier (Easy missing -> Normal).
        donor_diff = None
        for j in range(idx + 1, len(DIFFICULTIES)):
            if DIFFICULTIES[j] in have:
                donor_diff = DIFFICULTIES[j]
                break
        if donor_diff is None:
            for j in range(idx - 1, -1, -1):
                if DIFFICULTIES[j] in have:
                    donor_diff = DIFFICULTIES[j]
                    break
        if donor_diff is None:
            log.warning(f"  No donor difficulty for missing '{diff}' — skipping")
            continue

        donor_file = _select_beatmap_file(donor_diff, beatmap_files,
                                          ignore_non_standard=True)
        if not donor_file and donor_diff in have:
            # Donor was itself just filled this run — refresh the file list
            # so the newly written donor file can be selected.
            beatmap_files = [f for f in sorted(os.listdir(song_dir))
                             if f.endswith(('.dat', '.json'))]
            donor_file = _select_beatmap_file(donor_diff, beatmap_files,
                                              ignore_non_standard=True)
        if not donor_file:
            continue
        src_path = os.path.join(song_dir, donor_file)
        try:
            with open(src_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception as e:
            log.warning(f"  Could not read donor {src_path}: {e}")
            continue

        out_name = f"{diff}.dat"
        out_path = os.path.join(song_dir, out_name)
        if os.path.exists(out_path):
            continue
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
        written.append(out_name)
        have.add(diff)
        log.info(f"  Filled missing difficulty '{diff}' <- cloned from "
                 f"'{donor_file}' (map provides no {diff} chart)")
    return written


def generate_missing_mode_beatmaps(
    song_dir: str,
    detected_modes: dict[str, list[str]],
    enabled_modes: list[str],
    bpm: float = 120.0,
    min_gap: float = _ONE_SABER_MIN_GAP,
    cycle_beats: float = _ROTATION_CYCLE_BEATS,
) -> list[str]:
    """
    Fill gaps in a custom song's mode-specific beatmaps by generating them
    from Standard beatmaps.

    For every difficulty that has a Standard source beatmap, and for every
    enabled mode (OneSaber, NoArrows, 90Degree) that the song does NOT
    provide its own beatmaps for, this writes ``<Diff><Mode>.dat`` into the
    song directory. Difficulties where the song already defines its own
    mode beatmap are never overwritten.

    This is the DEFAULT behavior whenever ``--enable-beatmap-mode-mapping``
    is enabled.

    Args:
        song_dir: Directory containing the song's beatmap .dat/.json files.
        detected_modes: Output of detect_song_modes(song_dir) BEFORE generation.
        enabled_modes: Modes to enable (from build_mode_mapping). Standard is
                       the generator source and is skipped.
        bpm: BPM used when converting V2 source data for 90Degree.
        min_gap: OneSaber minimum beat gap between same-cell arrowed notes.
        cycle_beats: 90Degree rotation cycle length in beats.

    Returns:
        List of generated file names.
    """
    beatmap_files = []
    for f in sorted(os.listdir(song_dir)):
        if not f.endswith(('.dat', '.json')):
            continue
        base = f.lower()
        if base in ('info.dat', 'info.json', 'bpminfo.dat'):
            continue
        if 'lightshow' in base or 'audiodata' in base or 'audio' in base:
            continue
        beatmap_files.append(f)

    generated: list[str] = []
    for diff in DIFFICULTIES:
        src = _select_beatmap_file(diff, beatmap_files, ignore_non_standard=True)
        if not src:
            log.debug(f"  No Standard source beatmap for {diff} — skipping")
            continue
        src_path = os.path.join(song_dir, src)
        try:
            with open(src_path, 'r', encoding='utf-8') as fh:
                source = json.load(fh)
        except Exception as e:
            log.warning(f"  Could not read {src_path}: {e}")
            continue

        for mode in enabled_modes:
            if mode == "Standard" or mode not in _MODE_GENERATORS:
                continue
            # Song already provides its own beatmap for this mode+difficulty.
            if mode in detected_modes and diff in detected_modes.get(mode, []):
                log.debug(f"  {diff}{mode} already present — keeping original")
                continue

            gen = _MODE_GENERATORS[mode]
            if mode == "OneSaber":
                gen_data = gen(copy.deepcopy(source), min_gap=min_gap)
            elif mode == "90Degree":
                gen_data = gen(copy.deepcopy(source), cycle_beats=cycle_beats, bpm=bpm)
            else:
                gen_data = gen(copy.deepcopy(source))

            out_name = f"{diff}{mode}.dat"
            out_path = os.path.join(song_dir, out_name)
            with open(out_path, 'w', encoding='utf-8') as fh:
                json.dump(gen_data, fh)
            generated.append(out_name)
            log.info(f"  Generated {out_name} <- {src}")

    if generated:
        log.info(f"  Generated {len(generated)} missing mode beatmaps")
    return generated

GAME_CHARACTERISTIC_MODES = ["Standard", "OneSaber", "NoArrows", "90Degree"]

KNOWN_MODE_SUFFIXES = [
    "Standard", "OneSaber", "NoArrows", "90Degree",
    "Legacy", "Lawless", "SingleSaber"
]

MODE_ALIASES = {
    "SingleSaber": "OneSaber",
    "Lawless": "NoArrows",
    "Legacy": "Standard",
}


def detect_song_modes(song_dir: str) -> dict[str, list[str]]:
    """
    Scan a custom song directory and detect which characteristic modes
    have beatmap files and which difficulties are available per mode.

    Parses beatmap .dat/.json filenames using known mode suffixes/prefixes.
    Bare files (e.g. "Expert.dat") are classified as Standard.

    Returns:
        dict mapping mode name -> list of difficulty names found
        e.g. {"Standard": ["Easy", "Normal", "Hard", "Expert", "ExpertPlus"],
              "OneSaber": ["ExpertPlus"]}
    """
    import glob as _glob
    DIFF_NAMES = {"Easy", "Normal", "Hard", "Expert", "ExpertPlus"}

    def _extract_mode_and_diff(stem: str):
        """Try to extract (mode, difficulty) from a filename stem.
        Returns (mode, diff) or (None, None) if unclassifiable."""
        stem_lower = stem.lower()

        # Check for prefix-style: mode before difficulty (e.g. OneSaberExpert)
        for mode_prefix in sorted(KNOWN_MODE_SUFFIXES + ["Standard"], key=len, reverse=True):
            mode_lower = mode_prefix.lower()
            if stem_lower.startswith(mode_lower):
                rest = stem[len(mode_prefix):]
                if rest in DIFF_NAMES:
                    canonical = MODE_ALIASES.get(mode_prefix, mode_prefix)
                    return canonical, rest

        # Check for suffix-style: difficulty before mode (e.g. ExpertPlusOneSaber)
        for mode_suffix in sorted(KNOWN_MODE_SUFFIXES, key=len, reverse=True):
            mode_lower = mode_suffix.lower()
            if stem_lower.endswith(mode_lower) and len(stem) > len(mode_suffix):
                diff = stem[:-len(mode_suffix)]
                if diff in DIFF_NAMES:
                    canonical = MODE_ALIASES.get(mode_suffix, mode_suffix)
                    return canonical, diff

        # Bare difficulty name (no mode suffix)
        if stem in DIFF_NAMES:
            return "Standard", stem

        # .beatmap.dat variant: e.g. "ExpertPlus.beatmap"
        if '.beatmap' in stem_lower:
            bare_stem = stem.split('.beatmap')[0]
            if bare_stem in DIFF_NAMES:
                return "Standard", bare_stem

        return None, None

    modes: dict[str, list[str]] = {}
    for fname in sorted(_glob.glob(os.path.join(song_dir, "*.dat"))):
        base = os.path.basename(fname)
        base_lower = base.lower()
        if base_lower in ('info.dat', 'bpminfo.dat'):
            continue
        if 'lightshow' in base_lower or 'audiodata' in base_lower:
            continue

        stem = base.replace('.dat', '')
        mode, diff = _extract_mode_and_diff(stem)
        if mode and diff:
            if diff not in modes.setdefault(mode, []):
                modes[mode].append(diff)

    # Also check .json files (some BeatSaver songs use .json)
    for fname in sorted(_glob.glob(os.path.join(song_dir, "*.json"))):
        base = os.path.basename(fname)
        base_lower = base.lower()
        if base_lower in ('info.dat', 'bpminfo.dat', 'info.json'):
            continue
        if 'lightshow' in base_lower or 'audiodata' in base_lower:
            continue

        stem = base.replace('.json', '')
        mode, diff = _extract_mode_and_diff(stem)
        if mode and diff:
            if diff not in modes.setdefault(mode, []):
                modes[mode].append(diff)

    # Sort difficulties in each mode by canonical order for consistent output
    diff_order = {d: i for i, d in enumerate(["Easy", "Normal", "Hard", "Expert", "ExpertPlus"])}
    for mode in modes:
        modes[mode].sort(key=lambda d: diff_order.get(d, 999))

    return modes


def build_mode_mapping(
    detected_modes: dict[str, list[str]],
    fallback_mode_map: list[str] | None = None,
) -> list[str]:
    """
    Build the list of game characteristic modes to enable in the BeatmapLevel
    based on detected modes, with a configurable fallback chain.

    The 4 game slots are: Standard, OneSaber, NoArrows, 90Degree.
    Standard must always be present. 360Degree is unsupported on PS4
    (single-camera 90-degree arc tracking constraint) and is never enabled.

    Default fallback chain (used when a game slot has no detected files):
        OneSaber   ← Standard
        NoArrows   ← Standard
        90Degree   ← Standard

    Custom fallback via --fallback-mode-map uses SRC=DEST format, e.g.:
        --fallback-mode-map NoArrows=Standard  (skip 90Degree→Standard fallback)
        --fallback-mode-map 90Degree=Standard  (chain 90Degree→Standard directly)

    Args:
        detected_modes: Output of detect_song_modes()
        fallback_mode_map: List of "SRC=DEST" fallback overrides

    Returns:
        List of mode names to enable (e.g. ["Standard", "OneSaber"])
    """
    if not detected_modes:
        return ["Standard"]

    # Parse custom fallback overrides
    custom_fallback: dict[str, str] = {}
    if fallback_mode_map:
        for entry in fallback_mode_map:
            if '=' in entry:
                src, dest = entry.split('=', 1)
                custom_fallback[src.strip()] = dest.strip()

    # Default fallback chain (most specific to least specific)
    default_fallback: dict[str, str] = {
        "NoArrows": "Standard",
        "90Degree": "Standard",
        "OneSaber": "Standard",
    }
    # Apply custom overrides
    for src, dest in custom_fallback.items():
        if src in default_fallback:
            default_fallback[src] = dest

    def _resolve(src: str, seen: set | None = None) -> bool:
        """Check if a mode can be resolved via fallback chain.
        Standard is always considered resolved."""
        if seen is None:
            seen = set()
        if src in detected_modes:
            return True
        if src == "Standard":
            return True
        if src in seen:
            return False
        seen.add(src)
        if src not in default_fallback:
            return False
        fallback = default_fallback[src]
        if fallback == src:
            return False
        return _resolve(fallback, seen)

    modes_to_enable = []
    for mode in GAME_CHARACTERISTIC_MODES:
        if mode == "Standard":
            modes_to_enable.append(mode)
        elif mode in detected_modes:
            modes_to_enable.append(mode)
        elif _resolve(mode):
            modes_to_enable.append(mode)

    return modes_to_enable


def apply_mode_mapping(cab, enabled_modes: list[str], song_dir: str = None,
                        generated_files: list[str] = None, bpm: float = 120.0,
                        target_name: str = None) -> int:
    """
    Apply mode mapping to a CAB bundle by enabling the given characteristic modes.

    When ``song_dir`` is provided, mode-specific beatmap (``.dat``) files on
    disk — both newly-generated (from ``generated_files``) and pre-existing
    (from a previous pipeline run or hand-authored) — are injected as new
    TextAsset objects in the CAB and linked to the corresponding difficulty
    beatmap entries. Generated V2 beatmaps are converted to V3 before
    injection. Otherwise falls back to cloning Standard references (legacy
    behavior — playable but all modes use Standard data).

    Args:
        cab: Unity CAB bundle containing BeatmapLevel
        enabled_modes: List of mode names to enable (from build_mode_mapping)
        song_dir: Directory containing the song's .dat files (optional)
        generated_files: List of generated .dat filenames (optional)
        bpm: BPM for V2→V3 conversion of generated beatmaps

    Returns:
        Number of modes added
    """
    modes_to_add = [m for m in enabled_modes if m != "Standard"]
    if song_dir:
        return add_mode_characteristics(cab, modes_to_add, song_dir=song_dir,
                                         generated_files=generated_files, bpm=bpm,
                                         target_name=target_name)
    return add_mode_characteristics(cab, modes_to_add, bpm=bpm, target_name=target_name)


# ============================================================================
# Inject BeatmapLevelSO metadata into the per-song CAB bundle
# ============================================================================

# Characteristic path IDs for _previewDifficultyBeatmapSets
_CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
}


def _encode_unity_string(s: str) -> bytes:
    """Encode a string for Unity serialized data (UTF-16LE + length prefix)."""
    if not s:
        return b'\x00\x00'  # null string
    utf16 = s.encode('utf-16-le')
    # Unity string format: int32 length of UTF-16 bytes (including trailing null)
    plen = len(utf16) + 2  # +2 for trailing null
    return struct.pack('<i', plen) + utf16 + b'\x00\x00'


def _build_beatmap_level_so_blob(
    song_name: str,
    song_sub_name: str,
    song_author: str,
    level_author: str,
    bpm: float,
    preview_diff_count: int,
    diff_data: bytes,
    level_id: str = "custom",
) -> bytes:
    """
    Construct a BeatmapLevelSO serialized blob (IL2CPP MonoBehavior layout).

    Based on pack bundle analysis of the Rolling Stones pack:
      0x0C: m_Script PPtr(fileID=2, pathID=-1) — base class script ref
            The first 12 bytes are padding/zeroed (type info is in SerializedFile map)
      Then per-instance data fields in order:
        _levelID        = string (song identifier like "therollingstones_startmeup")
        _songName       = string (display name, e.g. "Espresso")
        _songSubName    = string (subtitle with length/notes info)
        _songAuthorName = string (artist name)
        _levelAuthorName= string (custom song author)
        BPM             = double (8 bytes)

      Then preview arrays:
        count = int32(4)
        For each mode [Standard, OneSaber, NoArrows, 90Degree]:
          PPtr(fileID=2, pathID=char_path_id)
          diff_count = int32(n)
          difficulty_data (36 bytes per entry × n)

    The blob does NOT include klassID/classID — those are in the SerializedFile's
    types map and resolved by IL2CPP at deserialization time.
    """
    blob = bytearray()

    # ── Padding + m_Script PPtr (per pack bundle analysis) ───────────────
    blob += b'\x00\x00\x00\x00'  # bytes 0-3: padding/type info placeholder
    blob += b'\x00\x00\x00\x00'  # bytes 4-7: classID placeholder
    blob += b'\x00\x00\x00\x00'  # bytes 8-11: alignment

    # m_Script at offset 0xC (byte 12)
    blob += struct.pack('<i', 2)           # fileID = 2 (m_Metadata->m_Script)
    blob += struct.pack('<q', -1)          # pathID = -1 (base class = ScriptableObject)

    # ── Instance fields (verified order from pack bundle analysis) ───────
    # NOTE: m_Name is NOT in the serialized instance data — it's in the type info.
    # Only _levelID through BPM are per-instance serialized fields.
    blob.extend(_encode_unity_string(level_id))            # _levelID
    blob.extend(_encode_unity_string(level_id))            # _levelID
    blob.extend(_encode_unity_string(song_name))           # _songName
    blob.extend(_encode_unity_string(song_sub_name))       # _songSubName
    blob.extend(_encode_unity_string(song_author))         # _songAuthorName
    blob.extend(_encode_unity_string(level_author))        # _levelAuthorName
    blob += struct.pack('<d', bpm)                         # BPM (double)

    # ── _previewDifficultyBeatmapSets array ────────────────────────────
    modes = ["Standard", "OneSaber", "NoArrows", "90Degree"]
    blob += struct.pack('<i', 4)                          # count = 4 modes

    for mode in modes:
        path_id = _CHAR_PATH_IDS[mode]
        blob += struct.pack('<i', 2)                      # fileID (m_Script ref)
        blob += struct.pack('<q', path_id)                # pathID
        blob += struct.pack('<i', preview_diff_count)     # difficulty count
        # Difficulty data: 36 bytes per entry
        needed = preview_diff_count * 36
        if len(diff_data) >= needed:
            blob.extend(diff_data[:needed])
        else:
            blob.extend(diff_data + b'\x00' * (needed - len(diff_data)))

    return bytes(blob)


def inject_beatmap_level_so(
    bf,
    song_name: str,
    song_artist: str = "",
    duration_seconds: float = 0.0,
    bpm: float = 120.0,
    note_count_standard: int = 0,
    note_count_diff_data: bytes = b'',
) -> bool:
    """
    Inject a BeatmapLevelSO ScriptableObject into the CAB bundle so the
    song menu can display custom metadata (name, artist, length, etc.).

    APPROACH: Since UnityPy lacks type info for BeatmapLevelSO and cannot
    serialize IL2CPP-compatible data for it, we work by first building a
    raw serialized blob, then attempting to insert it into the bundle's
    CAB file via post-save modification.

    The game resolves BeatmapLevelSO objects by _levelID across all loaded
    AssetBundles. When the per-song bundle is redirected and loaded, the
    injected SO provides metadata to the UI.

    Currently this function logs what *would* be injected (the blob) so it
    can be inspected. The actual CAB file injection requires UnityPy
    serialization support for BeatmapLevelSO and is tracked as a future
    task — see .agent/llm-wiki-knowledge-base/plans/song-list-metadata.md

    Args:
        bf: UnityPy BundleFile (the outer AssetBundle, not the CAB)
        song_name: Display song name (overrides original)
        song_artist: Artist name
        duration_seconds: Song length in seconds
        bpm: Beats per minute for timing
        note_count_standard: Note count for display purposes
        note_diff_data: Pre-encoded difficulty data (36B × N entries, or empty)

    Returns:
        True if the blob was constructed (injection itself needs UnityPy fix)
    """
    log.info("  Building BeatmapLevelSO metadata blob...")

    # ── Build the serialized blob ───────────────────────────────────────
    level_id = f"custom/{song_name.lower().replace(' ', '_')}"

    blob = _build_beatmap_level_so_blob(
        song_name=song_name,
        song_sub_name=f"{duration_seconds:.0f}s / {note_count_standard} notes",
        song_author=song_artist if song_artist else "Unknown Artist",
        level_author=song_artist if song_artist else "Custom",
        bpm=bpm,
        preview_diff_count=5,  # always 5 modes
        diff_data=note_count_diff_data or b'\x00' * (5 * 36),
        level_id=level_id,
    )

    log.info(f"    BeatmapLevelSO blob: {len(blob)} bytes")
    log.info(f"    _levelID={level_id} _songName={song_name} _songAuthorName={song_artist}")

    # Dump a hex sample for debugging (first 128 bytes)
    hex_sample = blob[:128].hex()
    log.info(f"    Hex[0:128]: {hex_sample}")

    # Write the blob to a temp file for inspection
    blob_path = os.path.join(PROJECT_ROOT, f"_beatmap_level_so_{song_name}.blob")
    with open(blob_path, 'wb') as f:
        f.write(blob)
    log.info(f"    ✅ Blob saved to {blob_path}")

    # Future work: inject this blob into the CAB file by:
    # 1. Parsing the UnityFS header of the saved CAB
    # 2. Finding free space or appending a new object entry
    # 3. Updating the manifest table with the new object's offset/size
    log.info("    ⚠️ Blob not yet injected into CAB (needs UnityPy type support)")
    return True


def build_plugin(project_root: str, debug: bool = False) -> str:
    """
    Build the GoldHEN plugin — or fall back to the bundled release binaries.

    A source tree (repo checkout) builds via make. The PACKAGED RELEASE ships
    tools only (no src/, no Makefile) but bundles BOTH pre-built plugins in
    plugins/ (CI-built: orbeats.prx + orbeats_debug.prx) —
    when no Makefile is present, that bundled binary is the plugin to deploy
    (Exp 234 finding #2 / Exp 235: --deploy-full must work end-to-end from
    the release zip alone, plugin deployment included).

    Args:
        project_root: Path to the plugin project root (contains Makefile)
        debug: If True, builds/uses the VERBOSE_LOG-enabled binary

    Returns:
        Path to the .prx file to deploy

    Raises:
        RuntimeError: If neither a build nor a bundled binary is available
    """
    import subprocess as sp

    prx_name = "orbeats_debug.prx" if debug else "orbeats.prx"
    bundled = os.path.join(project_root, 'plugins', prx_name)
    has_makefile = os.path.isfile(os.path.join(project_root, 'Makefile'))

    if not has_makefile:
        # Packaged-release layout: no source, use the bundled CI-built binary.
        if os.path.isfile(bundled):
            log.info(f"No Makefile (packaged release) — using bundled plugin: {bundled}")
            log.info(f"  ✅ Plugin: {bundled} ({os.path.getsize(bundled)} bytes)")
            return bundled
        log.error(f"Plugin build impossible: no Makefile at {project_root} and no bundled "
                  f"plugin at {bundled}. The release zip ships plugins/{prx_name}; a source "
                  f"checkout builds it via make.")
        raise RuntimeError("Plugin build failed (no Makefile, no bundled plugin)")

    log.info(f"Building plugin (debug={'yes' if debug else 'no'})...")
    env = os.environ.copy()
    if debug:
        env['DEBUG'] = '1'

    result = sp.run(['make', 'clean'], capture_output=True, text=True, timeout=120, cwd=project_root, env=env)
    result = sp.run(['make', '-B'], capture_output=True, text=True, timeout=300, cwd=project_root, env=env)

    if result.returncode != 0:
        log.error(f"Plugin build failed:\n{result.stdout}\n{result.stderr}")
        raise RuntimeError("Plugin build failed")

    # Determine output filename based on debug flag
    prx_path = os.path.join(project_root, prx_name)

    if not os.path.isfile(prx_path):
        log.error(f"Build succeeded but {prx_path} not found")
        raise RuntimeError(f"Plugin binary not found: {prx_path}")

    log.info(f"  ✅ Plugin built: {prx_path} ({os.path.getsize(prx_path)} bytes)")
    return prx_path


def _ps4_output_looks_absent(output: str) -> bool:
    """A decisive 'file does not exist' answer from the FTP server — the
    CLEAN-SLATE state (Exp 281c): after Clear PS4 (or before first use) the
    state files legitimately do not exist. NEVER treat this as a read failure
    (the deploy-scoping refusal on a fresh console — the user's live report:
    a clean console could not deploy its first song). Signatures: 550,
    'no such file', 'file unavailable'."""
    low = (output or "").lower()
    return ("550" in (output or "") or "no such file" in low
            or "file unavailable" in low)


def _ftp_quote(path: str) -> str:
    """Quote a path for the lftp -e command string.

    lftp's command language treats shell metacharacters specially, so a path
    like .../Scream&Shout_v3.bundle gets split at the '&' (the upload silently
    lands at the wrong name or fails, while lftp still exits 0 — Exp 224).
    Double-quoting the path in the -e script makes lftp treat it as one token.
    """
    return '"' + path.replace('"', '\\"') + '"'


def _ftp_run(host: str, port: int, user: str, password: str, commands: list, timeout: int = 120):
    """
    Run a series of lftp commands and return (returncode, stdout, stderr).
    """
    import subprocess as sp
    user_part = f"{user},{password}" if password else f"{user},"
    # Build a single -e script with ; between commands
    script = "; ".join(commands) + "; quit"
    cmd = ["lftp", "-u", user_part, "-p", str(port), host, "-e", script]
    result = sp.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


def ensure_plugins_ini(config: dict, plugin_remote_path: str):
    """Register without discarding existing bytes; archive rollback locally."""
    from goldhen_config import ensure_remote_ini
    ensure_remote_ini(config, plugin_remote_path)


# ============================================================================
# Plugin Toggle — enable / disable the OrBeats plugin on PS4
# ============================================================================

PLUGIN_PRX_NAME = "orbeats.prx"
DEBUG_PRX_NAME = "orbeats_debug.prx"


def _find_prx_name(config: dict, debug: bool = False) -> str:
    """Return the current prx filename (handles debug toggle)."""
    return DEBUG_PRX_NAME if debug else PLUGIN_PRX_NAME


def _prx_remote_path(plugin_remote: str) -> str:
    """Extract directory from a plugin remote path."""
    return os.path.dirname(plugin_remote) or "/data/GoldHEN/plugins"


def enable_plugin(config: dict, debug: bool = False):
    """
    Enable the OrBeats plugin on PS4.

    Steps:
      1. Ensure plugins.ini has an uncommented entry for our .prx under [CUSA12878]
      2. If no existing entry, also upload the .prx file (build required separately)
    """
    ps4_cfg = config.get('ps4', {})
    title_cfg = config.get('title', {})
    _paths_cfg = config.get('paths', {})

    title_id = title_cfg.get('id', 'CUSA12878')
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')

    prx_name = _find_prx_name(config, debug)
    plugin_remote = f"/data/GoldHEN/plugins/{prx_name}"
    ini_remote = "/data/GoldHEN/plugins.ini"

    log.info(f"Enabling OrBeats plugin ({prx_name}) on PS4...")

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        local_ini = os.path.join(tmpdir, "plugins.ini")

        # Download existing plugins.ini
        rc, out, err = _ftp_run(host, port, user, password,
                                [f"get {_ftp_quote(ini_remote)} -o {_ftp_quote(local_ini)}"],
                                timeout=30)
        if rc != 0:
            log.info("  No existing plugins.ini — creating fresh")
            lines = []
        else:
            with open(local_ini) as f:
                lines = f.read().splitlines()
            log.info(f"  Downloaded plugins.ini ({len(lines)} lines)")

        # Parse INI into sections (title_id -> list of plugin paths)
        sections = {}
        current_section = None
        for line in lines:
            stripped = line.strip()
            # Skip blank lines and comment lines (both # and ;)
            if not stripped or stripped.startswith('#') or stripped.startswith(';'):
                continue
            if stripped.startswith('[') and stripped.endswith(']'):
                current_section = stripped[1:-1]
                if current_section not in sections:
                    sections[current_section] = []
            elif current_section:
                sections.setdefault(current_section, []).append(stripped)

        # Ensure our section exists
        current_plugins = sections.setdefault(title_id, [])

        # Check if our prx already has a valid (uncommented) entry
        found = False
        for p in current_plugins:
            if p == plugin_remote:
                found = True
                break

        if not found:
            current_plugins.append(plugin_remote)
            log.info(f"  Added [{title_id}] entry: {plugin_remote}")

        # Rebuild INI content — filter out old commented/duplicate entries for our prx
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                new_lines.append(line)
                continue
            # Skip any line that is solely a comment for our prx (; or #)
            if (stripped.startswith(';') or stripped.startswith('#')):
                bare = stripped.lstrip(';#').strip()
                if bare == plugin_remote:
                    log.info(f"  Uncommented existing entry: {stripped}")
                    continue  # skip the commented version; will add uncommented below
            new_lines.append(line)

        # Now add the uncommented entry under the correct section (only if not already present)
        if not found:
            section_header = f"[{title_id}]"
            inserted = False
            merged = []
            for line in new_lines:
                merged.append(line)
                if not inserted and line.strip() == section_header:
                    merged.append(plugin_remote)
                    inserted = True
        else:
            merged = new_lines

        with open(local_ini, 'w') as f:
            f.write('\n'.join(merged) + '\n')

        # Upload updated plugins.ini
        rc, out, err = _ftp_run(host, port, user, password,
                                [f"put {_ftp_quote(local_ini)} -o {_ftp_quote(ini_remote)}"],
                                timeout=30)
        if rc == 0:
            log.info("  ✅ plugins.ini updated — plugin ENABLED")
        else:
            log.warning(f"  ⚠️ Failed to upload plugins.ini: {err}")


def disable_plugin(config: dict):
    """
    Disable the OrBeats plugin on PS4.

    Steps:
      1. Comment out (or remove) our .prx entry in plugins.ini under [CUSA12878]
      2. Optionally download/delete the .prx file from PS4
    """
    ps4_cfg = config.get('ps4', {})
    title_cfg = config.get('title', {})

    title_id = title_cfg.get('id', 'CUSA12878')
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')

    ini_remote = "/data/GoldHEN/plugins.ini"

    log.info("Disabling OrBeats plugin on PS4...")

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        local_ini = os.path.join(tmpdir, "plugins.ini")

        # Download existing plugins.ini
        rc, out, err = _ftp_run(host, port, user, password,
                                [f"get {_ftp_quote(ini_remote)} -o {_ftp_quote(local_ini)}"],
                                timeout=30)
        if rc != 0:
            log.warning("  No existing plugins.ini found — nothing to disable")
            return

        with open(local_ini) as f:
            lines = f.read().splitlines()

        # Parse and modify
        new_lines = []
        current_section = None
        disabled_count = 0

        for line in lines:
            stripped = line.strip()

            # Track section headers
            if stripped.startswith('[') and stripped.endswith(']'):
                current_section = stripped[1:-1]
                new_lines.append(line)
                continue

            if current_section == title_id:
                # Check if this line references our plugin (handle both # and ; comments)
                bare = stripped.lstrip(';#').strip()
                if PLUGIN_PRX_NAME in bare or DEBUG_PRX_NAME in bare:
                    already_commented = stripped.startswith(';') or stripped.startswith('#')
                    if not already_commented:
                        new_lines.append(f'#;{line}')
                        disabled_count += 1
                        log.info(f"  Disabled: {stripped}")
                        continue
                    else:
                        # Already commented — keep as-is
                        new_lines.append(line)
                        continue

            new_lines.append(line)

        if disabled_count == 0:
            log.info("  Plugin already disabled (or not found in plugins.ini)")
        else:
            # Upload modified plugins.ini
            local_out = os.path.join(tmpdir, "plugins_disabled.ini")
            with open(local_out, 'w') as f:
                f.write('\n'.join(new_lines) + '\n')

            rc, out, err = _ftp_run(host, port, user, password,
                                    [f"put {_ftp_quote(local_out)} -o {_ftp_quote(ini_remote)}"],
                                    timeout=30)
            if rc == 0:
                log.info(f"  ✅ plugins.ini updated — plugin DISABLED ({disabled_count} entry(s))")
            else:
                log.warning(f"  ⚠️ Failed to upload plugins.ini: {err}")


def deploy_plugin(prx_path: str, config: dict, debug: bool = False):
    """All CLI variants share the closed-title OrBeats installer and local rollback.

    The artifact may be release or DEBUG; the single active path is orbeats.prx.
    Never bypass the verified transaction with an unguarded FTP overwrite.
    """
    webapp = os.path.join(PROJECT_ROOT, 'webapp')
    if webapp not in sys.path:
        sys.path.insert(0, webapp)
    from library_manager import deploy_plugin as install
    result = install(config, prx_path)
    log.info('OrBeats installed with full readback and local recovery archive.')
    return result


# ============================================================================
# Redirect Config Management
# ============================================================================

REDIRECT_CONFIG_FILENAME = "redirects.json"

def _get_redirect_config_path(project_root: str = PROJECT_ROOT) -> str:
    """Return the local path to redirects.json in the project root."""
    return os.path.join(project_root, REDIRECT_CONFIG_FILENAME)

def _get_remote_redirect_path(config: dict) -> str:
    """Return the remote AFR path for redirects.json."""
    cfg_paths = config.get('paths', {})
    cfg_title = config.get('title', {})
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = cfg_title.get('id', 'CUSA12878')
    return f"{afr_base}/{title_id}/{REDIRECT_CONFIG_FILENAME}"

def _load_local_redirects(local_path: str) -> dict:
    """Load a local redirects.json file. Returns default structure if missing."""
    default = {
        "titleId": "CUSA12878",
        "afrBase": "/data/GoldHEN/AFR",
        "redirects": {}
    }
    if not os.path.exists(local_path):
        return default
    try:
        with open(local_path, 'r') as f:
            data = json.load(f)
        if 'redirects' not in data:
            data['redirects'] = {}
        return data
    except (json.JSONDecodeError, IOError):
        log.warning(f"  ⚠️  Failed to parse {local_path}, starting fresh")
        return default

def _download_redirect_from_ps4(config: dict) -> dict | None:
    """
    Download redirects.json from PS4 via FTP.
    Returns the parsed JSON dict, or None if the file doesn't exist.
    """
    import subprocess as sp
    import tempfile

    ps4_cfg = config.get('ps4', {})
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')
    remote_path = _get_remote_redirect_path(config)

    user_part = f"{user},{password}" if password else f"{user},"

    with tempfile.TemporaryDirectory() as tmpdir:
        local_tmp = os.path.join(tmpdir, "redirects.json")
        cmd = ["lftp", "-u", user_part, "-p", str(port), host,
               "-e", f"get {_ftp_quote(remote_path)} -o {_ftp_quote(local_tmp)}; quit"]
        result = sp.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(local_tmp):
            try:
                with open(local_tmp, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        # Exp 281d: distinguish ABSENT from FAILED. A decisive 550 (the file
        # does not exist) is the clean-slate state → return None (the caller
        # knows the live state is empty). A genuine read failure (dead host,
        # timeout, garbage) must RAISE — callers enforce pull-before-push and
        # must not mistake "couldn't read" for "nothing there" (Exp 246).
        if _ps4_output_looks_absent(
                (getattr(result, "stdout", "") or "")
                + (getattr(result, "stderr", "") or "")):
            return None
        raise RuntimeError(
            f"could not read redirects.json from the PS4 "
            f"(lftp rc={result.returncode}) — the live state is unknown")

def _deploy_redirect_to_ps4(config: dict):
    """Upload the local redirects.json to PS4 via FTP."""
    import subprocess as sp

    ps4_cfg = config.get('ps4', {})
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')
    local_path = _get_redirect_config_path()
    remote_path = _get_remote_redirect_path(config)

    if not os.path.exists(local_path):
        log.warning(f"  ⚠️  Local redirects.json not found at {local_path}")
        return

    user_part = f"{user},{password}" if password else f"{user},"
    cmd = ["lftp", "-u", user_part, "-p", str(port), host,
           "-e", f"put {_ftp_quote(local_path)} -o {_ftp_quote(remote_path)}; quit"]
    log.info(f"  Deploying redirect config to PS4: {remote_path}")
    result = sp.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        log.info("  ✅ Redirect config deployed")
    else:
        log.warning(f"  ⚠️  Redirect config deploy failed: {result.stderr}")


# ---------------------------------------------------------------------------
# Pack bundle + catalog redirect consistency (Exp 179 / Exp 180 crash fix)
# ---------------------------------------------------------------------------
# Unity validates a bundle's CRC (zlib.crc32 of the DECOMPRESSED stream) against
# the m_Crc in catalog.json when the bundle is loaded. The patched rollingstones
# pack bundle (startmeup_pack_modes.bundle) has a DIFFERENT dec-stream CRC than
# the original, so redirecting it WITHOUT also redirecting aa/catalog.json makes
# the game validate the patched bundle against the ORIGINAL catalog entry ->
# CRC mismatch -> crash during the pack scan at boot (Exp 180 crash session 2,
# died at ~[OPEN #591]).
#
# Rule enforced by the pipeline: the pack bundle redirect and the catalog
# redirect are a MATCHED PAIR. When generating/configuring redirects.json the
# pipeline ALWAYS (re)inserts both entries together and refuses to produce a
# config that has one without the other.

def _get_pack_bundle_redirects(config: dict, packs: list | None = None) -> dict:
    """
    Return the mandatory pack bundle + catalog redirect pairs from config.

    Keys are the game asset paths, values are the AFR filenames. Returns {} if
    no pack patch is configured.

    Single-pack prototype (`pack_bundle`, rollingstones/startmeup) is merged
    FIRST; the generalized `pack_modes` redirects are merged LAST and override
    overlapping keys, so when pack_modes covers the rollingstones pack (it is in
    pack_modes.packs by default) the merged-catalog + pack_modes bundle win and
    the startmeup prototype pair is superseded. Both stay consistent because the
    merged catalog carries the rollingstones entry too.
    """
    pb = config.get('pack_bundle', {}) or {}
    redirects = {}
    if pb.get('bundle_key') and pb.get('patched_bundle'):
        redirects[pb['bundle_key']] = pb['patched_bundle']
        if pb.get('catalog_key') and pb.get('patched_catalog'):
            redirects[pb['catalog_key']] = pb['patched_catalog']
    redirects.update(_get_pack_modes_redirects(config, packs=packs))
    return redirects

def _ensure_pack_bundle_redirects(redirect_data: dict, config: dict,
                                  packs: list | None = None) -> int:
    """
    Ensure the pack bundle + catalog redirect pair is present in redirect_data.

    Inserted entries always override existing ones so a stale/wrong pack target
    (e.g. rollingstones_pack_patched.bundle) can never survive a pipeline pass.
    Also removes stale truncated-key variants and stale pack redirects for packs
    no longer in the config. Returns the number of redirects inserted/updated.
    """
    redirects = redirect_data.setdefault('redirects', {})
    pair = _get_pack_bundle_redirects(config, packs=packs)
    if not pair:
        return 0
    changed = 0

    # Remove stale pack-bundle keys that are strict substrings of the canonical
    # key (e.g. "...a99482a8a3da9e991e5ae36f2fea209c" vs "...a99482a8a3da9e991e5ae36f2fea209c.bundle").
    # The plugin matches redirects with strstr(lower_path, lower_key), so a
    # truncated key would match the same game path and could win first — a crash
    # hazard if it points at the wrong bundle.
    for key in list(pair):
        lk = key.lower()
        stale = [k for k in redirects
                 if k != key and k.lower() in lk and lk.startswith(k.lower())]
        for k in stale:
            log.info(f"  🧹 Removed stale pack bundle redirect: {k} -> {redirects[k]}")
            del redirects[k]
            changed += 1

    # Remove stale pack redirects for packs no longer in config.  Without this,
    # removing a pack from pack_modes.packs would leave its old redirect in
    # redirects.json, causing the game to load a patched bundle whose catalog
    # entry no longer has a matching CRC — the CE-34878-0 crash.
    # Use hash-based matching: extract the content hash from "assets_all_<hash>.bundle"
    # and skip removal if any current pack has the same hash.
    # Exp 232: a pack redirect is VALID if it is in the current pair (local
    # bundle present) OR the pack is DEPLOYED per the redirects state file —
    # the same authority the deploy flows use (_resolve_deployed_packs). The
    # old sweep validated "still configured" purely by LOCAL file existence:
    # after a clean-slate wipe (pack_modes_bundles/ emptied), each pack
    # script's deploy found only its OWN bundle locally and deleted every
    # other pack's redirect as "no longer configured" — a 5-script chained
    # deploy ended with only the LAST pack's pack redirect surviving
    # (metadata swapped but stock beatmaps/modes on 4 packs). Local bundle
    # presence must never be the authority for deleting deployed state.
    import re
    valid_pack_keys = set(pair.keys())
    valid_hashes = set()
    _hash_re = re.compile(r'assets_all_([a-f0-9]+)\.bundle', re.IGNORECASE)
    for pk in valid_pack_keys:
        m = _hash_re.search(pk)
        if m:
            valid_hashes.add(m.group(1).lower())
    # Deployed packs (redirects state file): their entries are live on the PS4
    deployed_pack_names = set(_resolve_deployed_packs(config))
    deployed_hashes = set()
    for dp in deployed_pack_names:
        for e in _get_pack_modes_entries(config, packs=[dp]):
            m = _hash_re.search(e['bundle_key'])
            if m:
                deployed_hashes.add(m.group(1).lower())
    stale_pack_keys = []
    for k in list(redirects):
        m = _hash_re.search(k)
        if not m:
            continue
        if k in valid_pack_keys:
            continue
        if m.group(1).lower() in valid_hashes:
            continue
        # Exp 232: a deployed pack's redirect is NOT stale just because its
        # local bundle is missing — the bundle is live on the PS4.
        if m.group(1).lower() in deployed_hashes:
            continue
        stale_pack_keys.append(k)
    for k in stale_pack_keys:
        log.info(f"  🧹 Removed stale pack redirect (pack no longer configured): {k} -> {redirects[k]}")
        del redirects[k]
        changed += 1

    # Insert/override the canonical pair.
    for key, val in pair.items():
        if redirects.get(key) != val:
            redirects[key] = val
            changed += 1
    if changed:
        log.info(f"  🧩 Ensured pack bundle + catalog redirect pair ({changed} entries updated)")
    return changed

def _get_remote_pack_paths(config: dict, packs: list | None = None) -> list:
    """Return list of (local_path, remote_name) for the patched pack bundles + catalogs.

    `packs` optionally limits which pack_modes pack(s) are included (default: all).
    """
    pb = config.get('pack_bundle', {}) or {}
    out = []
    if pb.get('patched_bundle_local') and pb.get('patched_bundle'):
        out.append((pb['patched_bundle_local'], pb['patched_bundle']))
    if pb.get('patched_catalog_local') and pb.get('patched_catalog'):
        out.append((pb['patched_catalog_local'], pb['patched_catalog']))
    # Generalized pack_modes bundles + shared merged catalog.
    entries = _get_pack_modes_entries(config, packs=packs)
    if entries:
        for e in entries:
            if os.path.isfile(e['local_path']):
                out.append((e['local_path'], e['patched_bundle']))
        pm = config.get('pack_modes', {}) or {}
        if (pm.get('patched_catalog_local') and pm.get('patched_catalog')
                and os.path.isfile(pm['patched_catalog_local'])):
            out.append((pm['patched_catalog_local'], pm['patched_catalog']))
    return out

def _load_pack_albums(config: dict) -> dict:
    """Load the albums (keyed by pack name) from beat_saber_song_ids.json. {} on failure."""
    pm = config.get('pack_modes', {}) or {}
    path = pm.get('song_ids_path') or _get_song_ids_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return {a.get('pack'): a for a in data.get('albums', []) if a.get('pack')}
    except Exception:
        return {}

def _resolve_deployed_packs(config: dict) -> list:
    """Packs ACTUALLY deployed per the redirects.json state file ONLY.

    Like _resolve_active_packs but WITHOUT the local-bundle fallback: a pack
    merely built locally must never be auto-deployed (Exp 227 — after a clean
    slate the fallback resurrected every previously-built pack into a
    --clear-target-song run, rebuilding/redeploying 6 packs the user had
    never installed on the clean PS4). Returns [] on a clean slate.
    """
    pm = config.get('pack_modes', {}) or {}
    configured = pm.get('packs') or []
    if configured:
        return list(configured)
    local_redirects_path = _get_redirect_config_path()
    if os.path.isfile(local_redirects_path):
        try:
            deployed = _load_local_redirects(local_redirects_path)
            redirects = deployed.get('redirects', {}) if 'redirects' in deployed else deployed
            active = []
            for key, val in sorted(redirects.items()):
                if '_pack_modes_' in str(val):
                    pack = str(val).split('_pack_modes_')[0]
                    if pack not in active:
                        active.append(pack)
            return active
        except Exception:
            pass
    return []


def _resolve_active_packs(config: dict) -> list:
    """The pack set in scope — NEVER hardcoded (Exp 224 user directive).

    Order of resolution:
      1. `pack_modes.packs` from config, if the user pinned an explicit list
         (empty/absent means not pinned);
      2. otherwise AUTO-DISCOVER from the local redirects.json (the
         pipeline's deployment state file, kept in sync with the PS4 on
         every deploy/sync/enforce): exactly the packs whose
         `*_pack_modes_*` bundles are referenced in what the USER actually
         deployed. A pack merely built locally (or deployed in some earlier
         session then cleaned) is NOT in scope.
      3. if the local redirects.json is absent/empty (clean slate, fresh
         clone), fall back to packs with local built bundles so build-time
         flows still have a scope.
    No FTP here — discovery must be fast and deterministic; validation
    separately verifies the local and PS4 redirect sets match.
    """
    pm = config.get('pack_modes', {}) or {}
    configured = pm.get('packs') or []
    if configured:
        return list(configured)
    # Auto-discover from the deployed state (local redirects.json). If the
    # state file EXISTS it is authoritative — a file that references no
    # patched packs means the user has deployed NO packs, and inventing
    # locally-built ones would violate "only what the user deployed". The
    # build_dir fallback applies only when there is no state file at all
    # (fresh clone / clean slate, build-time flows).
    local_redirects_path = _get_redirect_config_path()
    if os.path.isfile(local_redirects_path):
        try:
            deployed = _load_local_redirects(local_redirects_path)
            redirects = deployed.get('redirects', {}) if 'redirects' in deployed else deployed
            active = []
            for key, val in sorted(redirects.items()):
                if '_pack_modes_' in str(val):
                    pack = str(val).split('_pack_modes_')[0]
                    if pack not in active:
                        active.append(pack)
            return active
        except Exception:
            pass
    # No state file at all: build-time fallback — packs with
    # local built bundles.
    albums = _load_pack_albums(config)
    build_dir = pm.get('build_dir') or os.path.join(PROJECT_ROOT, 'pack_modes_bundles')
    active = []
    for pack, album in sorted(albums.items()):
        original = album.get('packBundle')
        if not original:
            continue
        patched = pack_modes_builder.patched_bundle_name(original)
        if os.path.isfile(os.path.join(build_dir, patched)):
            active.append(pack)
    return active


def _previews_enabled(config: dict) -> bool:
    """Whether the enable_song_previews feature flag is ON (local features.json;
    the deployed flag is what the PLUGIN reads — the pipeline builds the bundle
    variant that the CURRENT local flag state requests, and --features-only
    flows keep the two in lockstep)."""
    feats = _load_local_features(_get_local_features_path())
    return bool(feats.get('enable_song_previews', False))


def _get_pack_modes_entries(config: dict, packs: list | None = None) -> list:
    """
    Deterministic list of pack_modes entries derived from config + song_ids.json.

    Each entry: {pack, bundle_key (original pack bundle asset path),
    patched_bundle (AFR filename), local_path}. No build happens here — the
    patched filename is derived deterministically from the original one.
    `packs` is the AUTHORITATIVE scope when provided (Exp 227) — deploy flows
    have already unioned their requested packs against the DEPLOYED state, so
    re-unioning the local-bundle fallback here would resurrect never-installed
    packs. Default (None): all ACTIVE (user-pinned list or auto-discovered
    from built bundles — build-time scope, never hardcoded).

    M10: when enable_song_previews is ON, patched_bundle/local_path point at
    the modes+previews VARIANT (…_pack_modes_previews_assets_all_…); the
    modes-only bundle keeps its own name. The variant is a SEPARATE file —
    flag flips swap which file deploys, never mutating the modes-only bundle.
    """
    pm = config.get('pack_modes', {}) or {}
    if packs is not None:
        # Exp 227: the caller's list is the AUTHORITATIVE scope when provided
        # — deploy flows already unioned it against the DEPLOYED state
        # (_resolve_deployed_packs). Unioning the local-bundle fallback here
        # re-admitted stale locally-built packs the user never installed
        # (clean-slate --clear-target-song rebuilt + deployed 6 packs).
        configured = list(packs)
    else:
        configured = _resolve_active_packs(config)
    if not configured:
        return []
    albums = _load_pack_albums(config)
    build_dir = pm.get('build_dir') or os.path.join(PROJECT_ROOT, 'pack_modes_bundles')
    previews_on = _previews_enabled(config)
    entries = []
    for pack in configured:
        album = albums.get(pack)
        if not album or not album.get('packBundle'):
            continue
        original = album['packBundle']
        patched = pack_modes_builder.patched_bundle_name(original)
        if previews_on:
            # M10: prefer the modes+previews VARIANT — but ONLY when the variant
            # FILE itself exists. The variant is built by _ensure_previews_variants
            # BEFORE any deploy path reads entries, so a missing variant here means
            # it genuinely cannot deploy (no custom slots / build failed) — the
            # pack must keep its modes-only name so the catalog/redirect/bundle
            # triple stays consistent (the Exp 225 crash class otherwise).
            variant = song_previews.previews_bundle_name(patched)
            if os.path.isfile(os.path.join(build_dir, variant)):
                patched = variant
        entries.append({
            'pack': pack,
            'bundle_key': original,
            'patched_bundle': patched,
            'local_path': os.path.join(build_dir, patched),
        })
    return entries

def _resolve_target_pack(config: dict, target_name: str) -> str | None:
    """
    Resolve which DLC pack a given song slot belongs to, using beat_saber_song_ids.json.

    `target_name` is the slot (e.g. `AllTheGoodGirlsGoToHell`). Returns the album's
    `pack` key (e.g. `billieeilish`) or None if the song isn't found / config missing.
    This lets a single-song deploy scope pack-mode bundles + redirects to just the
    song's pack instead of re-deploying every configured pack.
    """
    if not target_name:
        return None
    albums = _load_pack_albums(config)
    t = target_name.lower()
    for album in albums.values():
        for s in album.get('songs', []):
            if s.get('songID', '').lower() == t:
                return album.get('pack')
    return None


def _get_pack_modes_redirects(config: dict, packs: list | None = None) -> dict:
    """
    Redirects for every pack_modes pack whose patched bundle exists locally.

    `packs` optionally limits which pack(s) to include. The shared catalog redirect
    is only included when >=1 patched bundle exists AND the merged catalog exists
    locally — the pipeline never points a redirect at a file that is not ready to
    deploy (Exp 180 crash rule).
    """
    pm = config.get('pack_modes', {}) or {}
    redirects = {}
    present = [e for e in _get_pack_modes_entries(config, packs=packs)
               if os.path.isfile(e['local_path'])]
    for e in present:
        redirects[e['bundle_key']] = e['patched_bundle']
    if present:
        cat_local = pm.get('patched_catalog_local')
        if (cat_local and os.path.isfile(cat_local)
                and pm.get('catalog_key') and pm.get('patched_catalog')):
            redirects[pm['catalog_key']] = pm['patched_catalog']
    return redirects

def _regenerate_merged_catalog(config: dict, packs: list | None = None) -> int:
    """
    Regenerate catalog_pack_modes.json from the ORIGIN catalog, updating entries
    for EXACTLY the current redirect set (configured packs whose patched bundle
    exists locally). Build details come from the manifest. Returns entries updated.

    The merged catalog must never cover a pack that is not being redirected (its
    original bundle would then fail CRC validation against the updated catalog
    entry at boot) and must never omit a pack that IS being redirected (its
    patched bundle would then fail CRC validation against the original entry).
    `packs` optionally limits which pack(s) the merged catalog covers (default: all).
    """
    pm = config.get('pack_modes', {}) or {}
    dump_dir = pm.get('dump_dir')
    cat_path = os.path.join(dump_dir, "Media/StreamingAssets/aa/catalog.json") if dump_dir else ''
    cat_out = pm.get('patched_catalog_local')
    if not cat_out or not os.path.isfile(cat_path):
        if cat_out:
            log.warning(f"  ⚠️  Origin catalog not found ({cat_path}) — cannot regenerate merged catalog")
        return 0
    build_dir = pm.get('build_dir') or os.path.join(PROJECT_ROOT, 'pack_modes_bundles')
    manifest = {e['patchedBundle']: e for e in pack_modes_builder.load_manifest(build_dir)}
    present = [e for e in _get_pack_modes_entries(config, packs=packs)
               if os.path.isfile(e['local_path'])]
    to_update = []
    for e in present:
        m = manifest.get(e['patched_bundle'])
        if m and m.get('catalogBundleName'):
            to_update.append(m)
    if not to_update:
        log.info("  ℹ️  No pack_modes bundles to encode in merged catalog")
        return 0
    n = pack_modes_builder.write_merged_catalog(cat_path, to_update, cat_out)
    log.info(f"  ✅ Merged catalog regenerated from origin ({n} entries): {cat_out}")
    return n

def _ensure_pack_mode_bundles(config: dict, force: bool = False,
                              packs: list | None = None, enable_modes: list = None,
                              target_slots: list = None,
                              skip_previews: bool = False) -> int:
    """
    Build patched pack bundles + merged catalog for any configured pack whose
    bundle is missing locally (or all with force=True). `packs` optionally
    limits which packs to (re)build. `enable_modes` optionally limits which
    gameplay modes to enable (default: all 4). `target_slots` optionally
    limits which song slots to patch in each pack (for partial deployments).
    When `target_slots` is provided, we ALWAYS force rebuild from the original
    dump to ensure only those slots get extra modes (stock songs stay Standard-only).
    skip_previews=True skips song-previews variant management entirely (Exp 269c:
    the --skip-song-preview-management batch flag — all-but-the-last batch
    command defers the (now cheap, dirty-checked) preview rebuild to the final
    deploy; the variant file already on the PS4 keeps serving previews).
    Returns number of bundles built.
    """
    pm = config.get('pack_modes', {}) or {}
    if packs is not None:
        # Exp 227: the caller's list is the AUTHORITATIVE scope when provided
        # (deploy flows already unioned the deployed state into it).
        configured = list(packs)
    else:
        configured = _resolve_active_packs(config)
    if not configured:
        log.info("  ℹ️  no pack_modes packs in scope (no pinned list, no built bundles) — nothing to build")
        return 0
    entries = [e for e in _get_pack_modes_entries(config, packs=configured) if e['pack'] in configured]

    # When target_slots is provided, we need to force rebuild to ensure
    # surgical patching — only those slots get extra modes.
    must_rebuild = target_slots is not None and len(target_slots) > 0
    missing = [e['pack'] for e in entries if force or must_rebuild or not os.path.isfile(e['local_path'])]

    built = 0
    if missing:
        dump_dir = pm.get('dump_dir')
        if not dump_dir or not os.path.isdir(os.path.join(dump_dir, "Media/StreamingAssets/aa")):
            log.warning(f"  ⚠️  Dump dir missing ({dump_dir}) — cannot build pack mode bundles")
            return 0
        song_ids = pm.get('song_ids_path') or _get_song_ids_path()
        build_dir = pm.get('build_dir') or os.path.join(PROJECT_ROOT, 'pack_modes_bundles')
        log.info(f"🔨 Building pack mode bundles for {len(missing)} pack(s): {', '.join(missing)}")
        results = pack_modes_builder.build_pack_mode_bundles(
            song_ids_path=song_ids, dump_dir=dump_dir, out_dir=build_dir, packs=missing, enable_modes=enable_modes, target_slots=target_slots)
        for r in results:
            log.info(f"    ✓ {r['pack']}: {r['patchedBundle']} ({r['size']:,} B, crc={r['crc']})")
        built = len(results)
    else:
        log.info(f"  ✅ Pack mode bundles already built ({len(entries)} pack(s))")

    # M10 song previews: when enable_song_previews is ON, the deployable variant
    # is modes+previews. Build it from the modes bundle (append preview FSB5s to
    # the .resource, repoint the preview AudioClips in place) whenever the
    # variant is missing or older than its modes bundle. target_slots scopes the
    # preview map too (partial packs only preview the custom slots in scope).
    if _previews_enabled(config) and not skip_previews:
        _ensure_previews_variants(config, packs=configured, target_slots=target_slots)
    elif _previews_enabled(config) and skip_previews:
        log.info("  ⏭️  Song-preview variant management SKIPPED (--skip-song-preview-management)")
    # The merged catalog must always match the CURRENT redirect set (regenerated
    # from origin each time so entries for untouched packs stay byte-identical).
    _regenerate_merged_catalog(config, packs=configured)
    return built


def _previews_manifest_row(build_dir: str, var_name: str) -> dict | None:
    """The variant's manifest row (by patchedBundle name), or None."""
    for e in pack_modes_builder.load_manifest(build_dir):
        if e.get('patchedBundle') == var_name and 'previews' in e:
            return e
    return None


def _previews_pack_dirty(album: dict, config: dict, build_dir: str,
                         modes_path: str, var_name: str,
                         target_slots: list | None) -> tuple[bool, str]:
    """Exp 269c dirty-check: is this pack's variant stale?

    A rebuild is needed when ANY of:
      - the variant FILE is missing;
      - the MODES base changed (mtime newer than the variant's manifest row
        previewsAt — mtime is valid HERE because both files are local builds
        we wrote ourselves; the Exp 269 trap was about REMOTE mtimes);
      - the set of previewable slots changed (song added/cleared in the pack);
      - any slot's preview INPUT changed: its local custom bundle's md5 or
        the resolved preview start differ from the fingerprint recorded at
        the last build (previewsInputs).
    Returns (dirty, reason). Clean packs are skipped entirely — the batch
    case where 4 of 5 packs are untouched drops from ~4 min to <10 s."""
    var_path = os.path.join(build_dir, var_name)
    row = _previews_manifest_row(build_dir, var_name)
    if not os.path.isfile(var_path) or row is None:
        return True, 'variant missing'
    # modes base changed?
    if os.path.getmtime(modes_path) > row.get('previewsAt', 0):
        return True, 'modes base rebuilt since last variant'
    # previewable-slot set changed?
    recorded = set(row.get('previews', []))
    expected = set()
    for s in album.get('songs', []):
        if _slot_is_custom(s, config) and song_previews.find_custom_bundle_for_slot(
                s.get('songID', ''), config):
            expected.add(s['songID'])
    if recorded != expected:
        missing = expected - recorded
        extra = recorded - expected
        why = []
        if missing:
            why.append(f"new custom slots: {sorted(missing)}")
        if extra:
            why.append(f"slots gone: {sorted(extra)}")
        return True, '; '.join(why)
    # per-slot input fingerprints changed?
    old_inputs = row.get('previewsInputs') or {}
    for s in album.get('songs', []):
        sid = s.get('songID', '')
        if sid not in expected:
            continue
        cur = song_previews.slot_input_fingerprint(sid, config, album)
        if cur is None:
            continue            # cannot fingerprint (bundle missing) — leave to build
        if old_inputs.get(sid) != cur:
            return True, f"input changed: {sid}"
    return False, 'inputs unchanged'


def _slot_is_custom(song: dict, config: dict) -> bool:
    """Is this album slot a deployed custom? (present in song_metadata.json)"""
    root = PROJECT_ROOT
    meta_path = os.path.join(root, 'song_metadata.json')
    stock = song.get('songName', '')
    try:
        with open(meta_path) as f:
            meta = json.load(f).get('song_names', {})
        return stock in meta
    except Exception:
        return False


def _ensure_previews_variants(config: dict, packs: list | None = None,
                               target_slots: list | None = None) -> int:
    """Build the modes+previews bundle variant for every pack in scope whose
    modes bundle exists, SKIPPING packs whose variant is already fresh
    (Exp 269c dirty-check: variant file + modes-base mtime + slot set +
    per-slot input fingerprints). Returns number of variants (re)built."""
    pm = config.get('pack_modes', {}) or {}
    build_dir = pm.get('build_dir') or os.path.join(PROJECT_ROOT, 'pack_modes_bundles')
    albums = _load_pack_albums(config)
    configured = list(packs) if packs is not None else _resolve_active_packs(config)
    built = 0
    for pack in configured:
        album = albums.get(pack)
        if not album or not album.get('packBundle'):
            continue
        modes_name = pack_modes_builder.patched_bundle_name(album['packBundle'])
        modes_path = os.path.join(build_dir, modes_name)
        if not os.path.isfile(modes_path):
            continue          # modes bundle not built yet — previews ride on it
        var_name = song_previews.previews_bundle_name(modes_name)
        var_path = os.path.join(build_dir, var_name)

        # target_slots scoping (surgical deploys): a scoped rebuild is dirty
        # when any scoped slot's inputs changed — the dirty-check handles it
        # per-slot; scoped builds only rebuild those slots' previews.
        if target_slots is not None and not target_slots:
            continue          # explicit empty scope = nothing to preview

        dirty, why = _previews_pack_dirty(album, config, build_dir,
                                          modes_path, var_name, target_slots)
        if not dirty:
            log.info(f"  ✅ {pack}: previews variant already fresh ({why}) — skipped")
            continue
        log.info(f"🎵 Building song-previews variant for {pack} "
                 f"({var_name}) — {why}")
        preview_map, inputs = song_previews.build_preview_map(
            album, config, log=log.info, want_inputs=True)
        if target_slots is not None:
            tl = {s.lower() for s in target_slots}
            preview_map = {sid: f for sid, f in preview_map.items()
                           if sid.lower() in tl}
        if not preview_map:
            log.info(f"  ℹ️  {pack}: no previewable custom slots — variant not built")
            continue
        work = song_previews.patch_pack_previews(album, preview_map, modes_path)
        if work is None:
            log.warning(f"  ⚠️  {pack}: preview patch produced nothing — skipped")
            continue
        new_bundle = song_previews.rebuild_bundle_with_previews(work, var_path)
        crc = pack_modes_builder.crc_decompressed_stream(new_bundle)
        _record_previews_manifest(pm, build_dir, pack, var_name,
                                  len(new_bundle), crc, preview_map,
                                  album.get('catalogBundleName', ''),
                                  album['packBundle'], inputs)
        log.info(f"    ✓ {pack}: {var_name} ({len(new_bundle):,} B, "
                 f"crc={crc}, previews={len(preview_map)})")
        built += 1
    return built


def _record_previews_manifest(pm: dict, build_dir: str, pack: str,
                              var_name: str, size: int, crc: int,
                              preview_map: dict, catalog_bundle_name: str,
                              pack_bundle_name: str,
                              preview_inputs: dict | None = None) -> None:
    """Record the previews variant in pack_modes manifest.json so catalog
    regeneration (which reads the manifest for crc/size) can encode it.

    preview_inputs: per-slot {slot: [bundle_md5, start_seconds]} — the
    fingerprints the Exp 269c dirty-check compares to skip fresh packs."""
    mpath = os.path.join(build_dir, 'manifest.json')
    data = {'entries': []}
    if os.path.isfile(mpath):
        try:
            with open(mpath) as f:
                data = json.load(f)
        except Exception:
            data = {'entries': []}
    entries = [e for e in data.get('entries', [])
               if not (isinstance(e, dict) and e.get('bundle') == var_name)]
    # packBundle = the STOCK bundle filename (the manifest's shared key with the
    # modes entry — the post-deploy check indexes by it). The variant entry also
    # carries 'previews' so consumers can tell the two apart.
    row = {
        'pack': pack,
        'bundle': var_name,
        'patchedBundle': var_name,
        'packBundle': pack_bundle_name,
        'catalogBundleName': catalog_bundle_name,
        'size': size,
        'crc': crc,
        'previews': sorted(preview_map.keys()),
        'previewsAt': int(__import__('time').time()),
    }
    if preview_inputs is not None:
        row['previewsInputs'] = {sid: list(v) for sid, v in preview_inputs.items()
                                 if sid in preview_map}
    entries.append(row)
    data['entries'] = entries
    with open(mpath, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

def _resolve_configured_packs(config: dict, packs: list | None) -> list:
    """Return the pack list to operate on: `packs` if given else all DEPLOYED
    (never hardcoded; no local-bundle fallback — deploy-side helper, Exp 227)."""
    configured = _resolve_deployed_packs(config)
    if packs is not None:
        return [p for p in packs if True] or [p for p in configured if p in packs]
    return list(configured)

def deploy_pack_modes(config: dict, packs: list | None = None, enable_modes: list = None, target_slots: list = None, skip_previews: bool = False) -> bool:
    """
    Build-if-missing and deploy the generalized pack_modes bundles + merged catalog.

    `packs` optionally limits deployment to specific pack(s); default deploys the
    FULL configured set. `enable_modes` optionally limits which gameplay modes to
    enable in the pack bundle (default: all 4). `target_slots` optionally limits
    which song slots to patch in each pack (for partial deployments).
    Deploys the redirect set (the given packs with built bundles) so the deployed
    merged catalog always matches the deployed redirects. Returns True if all uploads OK.
    """
    pm = config.get('pack_modes', {}) or {}
    # Exp 225: gate on the ACTIVE pack set (pinned list or auto-discovered),
    # NOT a non-empty pinned packs list — the old gate made auto-discovery
    # mode (packs=[]) skip this function entirely, so the patched pack bundle
    # deployed without its matching merged catalog → CRC crash (CE-34878-0).
    # Exp 226: an EXPLICITLY REQUESTED pack is always in scope — the deployed-
    # state discovery reflects what is on the PS4 NOW, which by definition
    # lags the pack being deployed (the user's britney/camellia/lizzo/RS
    # deploys each found only billieeilish "active" and silently skipped the
    # requested pack's patch, so those packs booted with stock mode buttons).
    if packs is not None:
        # Exp 226/227: requested packs JOIN the DEPLOYED state (redirects.json),
        # not the local-bundle fallback — the fallback resurrected never-installed
        # packs on clean-slate runs (6 packs rebuilt+deployed during a
        # --clear-target-song that should have touched exactly one pack).
        deployed = _resolve_deployed_packs(config)
        active = list(packs) + [p for p in deployed if p not in packs]
    else:
        active = _resolve_deployed_packs(config)
    if not active:
        log.warning("  ⚠️  no pack_modes packs in scope (no pinned list, no built "
                    "bundles, no deployed state, none requested) — nothing to deploy")
        return False
    _ensure_pack_mode_bundles(config, packs=active, enable_modes=enable_modes, target_slots=target_slots, skip_previews=skip_previews)
    pairs = [(e['local_path'], e['patched_bundle'])
             for e in _get_pack_modes_entries(config, packs=active)
             if os.path.isfile(e['local_path'])]
    if pm.get('patched_catalog_local') and pm.get('patched_catalog'):
        pairs.append((pm['patched_catalog_local'], pm['patched_catalog']))
    if not pairs:
        log.warning("  ⚠️  No pack_modes bundles available — nothing to deploy")
        return False
    log.info(f"📦 Deploying {len(pairs)} pack_modes file(s) to PS4...")
    ok = True
    for local_path, remote_name in pairs:
        ok = _deploy_file_to_ps4(config, local_path, remote_name) and ok
    return ok

def _deploy_file_to_ps4(config: dict, local_path: str, remote_name: str) -> bool:
    """Upload a single local file to the AFR dir on the PS4 via FTP. Returns True on success."""
    import subprocess as sp

    ps4_cfg = config.get('ps4', {})
    cfg_title = config.get('title', {})
    cfg_paths = config.get('paths', {})
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = cfg_title.get('id', 'CUSA12878')
    ftp_host = ps4_cfg.get('ip', '192.168.100.117')
    ftp_port = ps4_cfg.get('ftp_port', 2121)
    ftp_user = ps4_cfg.get('ftp_user', 'anonymous')
    ftp_pass = ps4_cfg.get('ftp_password', '')

    if not os.path.isfile(local_path):
        log.warning(f"  ⚠️  Local file missing, cannot deploy: {local_path}")
        return False

    remote_path = f"{afr_base}/{title_id}/{remote_name}"
    user_part = f"{ftp_user},{ftp_pass}" if ftp_pass else f"{ftp_user},"

    # Exp 269e: skip uploading a pack-variant/catalog artifact ONLY when this
    # same PROCESS already built the exact bytes and they are confirmed live
    # on the PS4. Soundness rules (the Exp 269c size-only version caused the
    # CE-34878-0 crash — see _previews_pack_dirty's notes):
    #   1. The session ledger (same process) proves WE built/uploaded these
    #      exact bytes — a cross-process skip cannot rely on it, which is
    #      correct: a fresh batch-song process must re-verify or re-upload.
    #   2. The remote listing must confirm the file exists with the SAME SIZE
    #      as the local artifact (cheap) — a size change means a different
    #      build for sure.
    #   3. SIZE EQUALITY ALONE IS NOT IDENTITY: two different builds of the
    #      same variant share size whenever the preview set is the same
    #      (fixed 10s PCM16 slices = fixed lengths). That was the crash:
    #      pass 1 uploaded variant v1; pass 2 rebuilt v2 (same size, different
    #      bytes), the catalog encoded v2's CRC, and this skip blocked v2's
    #      upload → catalog/file mismatch → CE-34878-0 at the pack scan.
    # So: same-process + already-uploaded + remote size unchanged → skip.
    # Anything else uploads.
    if ('pack_modes' in remote_name or remote_name == 'catalog_pack_modes.json') \
            and remote_name in _SESSION_UPLOADED_BUNDLES:
        remote = _list_remote_dir(config)
        remote_size = (remote or {}).get(remote_name)
        if remote_size is not None and remote_size == os.path.getsize(local_path):
            log.info(f"  ⏭️  {remote_name}: this session's upload is live on PS4 "
                     f"({remote_size:,} B, unchanged) — re-upload skipped")
            return True

    cmd = [
        "lftp", "-u", user_part, "-p", str(ftp_port), ftp_host,
        "-e", f"put {_ftp_quote(local_path)} -o {_ftp_quote(remote_path)}; quit"
    ]
    log.info(f"  Deploying {remote_name} -> {remote_path}")
    result = sp.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode == 0:
        _SESSION_UPLOADED_BUNDLES.add(remote_name)
        log.info(f"  ✅ {remote_name} deployed")
        return True
    log.warning(f"  ⚠️  Deploy failed for {remote_name}: {result.stderr}")
    return False

def _download_pack_bundle_from_ps4(config: dict, pack_name: str, local_dir: str) -> str | None:
    """Download the current patched pack bundle from PS4 for incremental patching.
    Returns the local path to the downloaded bundle, or None if not found/failed."""
    import subprocess as sp
    import sys

    ps4_cfg = config.get('ps4', {})
    cfg_title = config.get('title', {})
    cfg_paths = config.get('paths', {})
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = cfg_title.get('id', 'CUSA12878')
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')

    # Find the pack bundle name from the album data
    # Import patched_bundle_name from build_pack_mode_bundles (same directory)
    sys.path.insert(0, TOOLS_DIR)
    from build_pack_mode_bundles import patched_bundle_name
    pm = config.get('pack_modes', {}) or {}
    song_ids = pm.get('song_ids_path') or '/workspace/orbeats/beat_saber_song_ids.json'
    with open(song_ids) as f:
        data = json.load(f)
    album = next((a for a in data['albums'] if a['pack'] == pack_name), None)
    if not album or 'packBundle' not in album:
        return None

    original_name = album['packBundle']
    patched_name = patched_bundle_name(original_name)
    remote_path = f"{afr_base}/{title_id}/{patched_name}"
    local_path = os.path.join(local_dir, patched_name)

    user_part = f"{user},{password}" if password else f"{user},"
    cmd = ["lftp", "-u", user_part, "-p", str(port), host,
           "-e", f"get {_ftp_quote(remote_path)} -o {_ftp_quote(local_path)}; quit"]
    result = sp.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode == 0 and os.path.exists(local_path):
        log.info(f"  Downloaded existing pack bundle from PS4: {patched_name}")
        return local_path
    return None


def deploy_pack_bundle(config: dict, packs: list | None = None, enable_modes: list = None, target_slots: list = None, skip_previews: bool = False) -> bool:
    """
    Deploy the patched pack bundle + patched catalog.json to the PS4.

    Also builds (if missing) and deploys the generalized pack_modes bundles +
    merged catalog when pack_modes.packs is configured. `packs` optionally limits
    which pack(s) to deploy (default: all configured). `enable_modes` optionally
    limits which gameplay modes to enable in the pack bundle (default: all 4).
    `target_slots` optionally limits which song slots to patch in each pack.
    Both file sets must be uploaded BEFORE redirects.json references them,
    otherwise the game would 404 on the redirected path. Returns True if all uploads OK.
    """
    log.info("📦 Deploying patched pack bundle + catalog to PS4...")
    ok = True

    pm = config.get('pack_modes', {}) or {}
    if packs is not None:
        # Exp 226/227: requested packs JOIN the DEPLOYED state (what the
        # redirects.json state file says is on the PS4) — discovery lags the
        # pack being deployed, so a pure filter dropped it (mode buttons only
        # on the first pack). Exp 227: use _resolve_deployed_packs, NOT
        # _resolve_active_packs — the local-bundle fallback resurrected every
        # locally-built pack into a --clear-target-song run on a clean-slate
        # PS4 (6 packs the user never installed got rebuilt + deployed).
        deployed = _resolve_deployed_packs(config)
        configured_packs = list(packs) + [p for p in deployed if p not in packs]
    else:
        configured_packs = _resolve_deployed_packs(config)

    # For each pack, download existing patched bundle from PS4 if present,
    # then use it as base for incremental patching
    for pack in configured_packs:
        log.info(f"  📦 Processing pack: {pack}")
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to download existing patched bundle from PS4 for incremental patching
            existing_bundle = _download_pack_bundle_from_ps4(config, pack, tmpdir)
            if existing_bundle:
                log.info("  Using existing PS4 pack bundle as base for incremental patching")
                # Copy to pack_modes_bundles for builder to use as base
                pm_build_dir = pm.get('build_dir') or os.path.join(PROJECT_ROOT, 'pack_modes_bundles')
                os.makedirs(pm_build_dir, exist_ok=True)
                target_path = os.path.join(pm_build_dir, os.path.basename(existing_bundle))
                shutil.copy2(existing_bundle, target_path)

    # Exp 269e: BUILD BEFORE ANY UPLOAD. The old order uploaded whatever
    # variant file existed locally (pass 1), THEN called deploy_pack_modes
    # which rebuilt (dirty-check fires on the incremental modes copy's mtime)
    # and re-uploaded (pass 2). Two builds of the same variant in one deploy
    # are not byte-identical when song bundles changed in between → the
    # catalog encoded pass-2's CRC while pass-1's file could stay deployed
    # (the old size-only upload-skip blocked the corrective re-upload) →
    # catalog/file CRC mismatch → CE-34878-0 at the pack scan. Building
    # exactly once, BEFORE the first upload, makes every upload of this
    # deploy carry the same (final) bytes the catalog will encode.
    if configured_packs and not skip_previews:
        _ensure_pack_mode_bundles(
            config, packs=configured_packs, enable_modes=enable_modes,
            target_slots=target_slots, skip_previews=skip_previews)

    ok = True
    pairs = _get_remote_pack_paths(config, packs=packs)
    if pairs:
        for local_path, remote_name in pairs:
            ok = _deploy_file_to_ps4(config, local_path, remote_name) and ok
    elif packs is not None:
        log.info(f"  ℹ️  No pack_bundle / pack_modes entries for requested pack(s): {packs}")
    else:
        log.warning("  ⚠️  No pack_bundle / pack_modes configured — nothing to deploy")
        ok = False
    # Always deploy the generalized pack_modes set (patched bundles + MERGED
    # CATALOG) whenever ANY pack is in scope. The old gate checked a non-empty
    # pinned pack_modes.packs list; with the Exp 224 auto-discovery default
    # ([]) that gate was always False — the patched PACK bundle deployed while
    # the matching CATALOG (and its aa/catalog.json redirect) never did, which
    # boots into Unity's CRC check against the ORIGINAL catalog and crashes
    # with CE-34878-0 (Exp 180 invariant; regression fixed here, Exp 225).
    if configured_packs:
        # skip_previews=True here means the build was ALSO skipped above: the
        # deploy uploads the EXISTING variant (unchanged) with the EXISTING
        # catalog — still a consistent pair (the batch defers both to the
        # last command, which builds both).
        ok = deploy_pack_modes(config, packs=packs, enable_modes=enable_modes, target_slots=target_slots, skip_previews=skip_previews) and ok
    return ok

def deploy_mass_bundles(config: dict) -> bool:
    """
    Deploy all custom song bundles (mass_deploy.slots) to the PS4.

    Uploads <bundle_dir>/<slot>_v3.bundle to AFR/<title>/<slot>_v3.bundle for
    every configured slot. Returns True only if every bundle uploaded.
    """
    md = config.get('mass_deploy', {}) or {}
    bundle_dir = md.get('bundle_dir', '/workspace/orbeats/mass_bundles')
    slots = md.get('slots', [])
    suffix = config.get('paths', {}).get('afr_target_suffix', '_v3.bundle')
    if not slots:
        log.warning("  ⚠️  No mass_deploy.slots configured — nothing to deploy")
        return False

    log.info(f"🚚 Mass-deploying {len(slots)} song bundles from {bundle_dir} ...")
    ok = True
    for slot in slots:
        local_path = os.path.join(bundle_dir, f"{slot}{suffix}")
        if not os.path.isfile(local_path):
            log.warning(f"  ⚠️  Missing bundle: {local_path}")
            ok = False
            continue
        # Remote filename must be identical to the local file's basename so the
        # redirect VALUES (built from the same slot list + suffix) match exactly.
        ok = _deploy_file_to_ps4(config, local_path, os.path.basename(local_path)) and ok
    return ok


# ---------------------------------------------------------------------------
# Post-deploy validation (Exp 180: self-validating pipeline)
# ---------------------------------------------------------------------------

def _list_remote_dir(config: dict) -> dict:
    """
    List the AFR title dir on the PS4 via FTP.
    Returns {filename: size_bytes} for every file. Empty dict if unreachable.
    """
    import subprocess as sp

    ps4_cfg = config.get('ps4', {})
    cfg_title = config.get('title', {})
    cfg_paths = config.get('paths', {})
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = cfg_title.get('id', 'CUSA12878')
    ftp_host = ps4_cfg.get('ip', '192.168.100.117')
    ftp_port = ps4_cfg.get('ftp_port', 2121)
    ftp_user = ps4_cfg.get('ftp_user', 'anonymous')
    ftp_pass = ps4_cfg.get('ftp_password', '')

    remote_dir = f"{afr_base}/{title_id}"
    user_part = f"{ftp_user},{ftp_pass}" if ftp_pass else f"{ftp_user},"
    cmd = ["lftp", "-u", user_part, "-p", str(ftp_port), ftp_host,
           "-e", f"ls {_ftp_quote(remote_dir)}; quit"]
    try:
        result = sp.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as e:
        log.warning(f"  ⚠️  PS4 listing failed: {e}")
        return {}
    if result.returncode != 0:
        log.warning(f"  ⚠️  PS4 listing failed: {result.stderr}")
        return {}

    files = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 9 or not parts[0].startswith('-'):
            continue
        try:
            size = int(parts[4])
            name = ' '.join(parts[8:])
            files[name] = size
        except (ValueError, IndexError):
            continue
    return files

def verify_ps4_deployment(config: dict, packs: list | None = None) -> bool:
    """
    Validate what actually ended up on the PS4 after a deploy.

    Checks (each reported PASS/FAIL to the user):
      1. PS4 is reachable and the AFR title dir is listable.
      2. The deployed redirects.json matches the local redirects.json (keys+values).
      3. Every redirect target filename exists on the PS4 (no 404s at boot).
      4. The patched pack bundle + patched catalog exist on the PS4 (scoped to `packs`).
      5. The pack bundle + catalog redirect PAIR is present (the Exp 180 crash fix, scoped).
      6. Redirect target file sizes on the PS4 match the local files (full transfer).

    Returns True if all checks pass.
    """
    import subprocess as sp
    import tempfile

    log.info("🔎 Post-deploy PS4 validation...")
    ok = True

    # 1. Reachability + listing
    remote_files = _list_remote_dir(config)
    if not remote_files:
        log.warning("  ❌ PS4 unreachable or AFR dir empty — cannot validate")
        return False
    log.info(f"  ✅ PS4 reachable: {len(remote_files)} files in AFR dir")

    # 2. Deployed redirects.json matches local
    local_path = _get_redirect_config_path()
    local_data = _load_local_redirects(local_path)
    ps4_cfg = config.get('ps4', {})
    cfg_title = config.get('title', {})
    cfg_paths = config.get('paths', {})
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = cfg_title.get('id', 'CUSA12878')
    ftp_host = ps4_cfg.get('ip', '192.168.100.117')
    ftp_port = ps4_cfg.get('ftp_port', 2121)
    ftp_user = ps4_cfg.get('ftp_user', 'anonymous')
    ftp_pass = ps4_cfg.get('ftp_password', '')
    remote_path = f"{afr_base}/{title_id}/{REDIRECT_CONFIG_FILENAME}"
    user_part = f"{ftp_user},{ftp_pass}" if ftp_pass else f"{ftp_user},"
    with tempfile.TemporaryDirectory() as tmpdir:
        local_tmp = os.path.join(tmpdir, "redirects.json")
        cmd = ["lftp", "-u", user_part, "-p", str(ftp_port), ftp_host,
               "-e", f"get {_ftp_quote(remote_path)} -o {_ftp_quote(local_tmp)}; quit"]
        try:
            result = sp.run(cmd, capture_output=True, text=True, timeout=30)
            remote_ok = result.returncode == 0 and os.path.exists(local_tmp)
        except Exception:
            remote_ok = False
        if remote_ok:
            with open(local_tmp) as f:
                remote_data = json.load(f)
            local_red = local_data.get('redirects', {})
            remote_red = remote_data.get('redirects', {})
            if local_red == remote_red:
                log.info(f"  ✅ redirects.json on PS4 matches local ({len(local_red)} redirects)")
            else:
                log.warning(f"  ❌ redirects.json MISMATCH: local {len(local_red)} vs PS4 {len(remote_red)} redirects")
                for k in sorted(set(local_red) | set(remote_red)):
                    lv, rv = local_red.get(k), remote_red.get(k)
                    if lv != rv:
                        log.warning(f"       {k}: local={lv}  PS4={rv}")
                ok = False
        else:
            log.warning("  ❌ Could not download redirects.json from PS4")
            ok = False

    # 3. Every redirect target exists on PS4
    missing = []
    for val in local_data.get('redirects', {}).values():
        if val not in remote_files:
            missing.append(val)
    if missing:
        log.warning(f"  ❌ Redirect targets missing on PS4: {missing}")
        ok = False
    else:
        log.info(f"  ✅ All {len(local_data.get('redirects', {}))} redirect targets exist on PS4")

    # 4. Pack bundle + catalog files exist on PS4 (single-pack pair + pack_modes)
    remote_names = {name for local, name in _get_remote_pack_paths(config, packs=packs)}
    for name in sorted(remote_names):
        if name in remote_files:
            log.info(f"  ✅ {name} on PS4 ({remote_files[name]:,} bytes)")
        else:
            log.warning(f"  ❌ {name} MISSING on PS4")
            ok = False

    # 5. Pack bundle + catalog redirect pairs present (Exp 180 crash fix).
    # Covers the single-pack pair AND every configured pack_modes pack, plus the
    # shared aa/catalog.json redirect (single-pack catalog OR merged catalog).
    redirects = local_data.get('redirects', {})
    expected = _get_pack_bundle_redirects(config, packs=packs)
    broken = []
    for key, val in expected.items():
        if redirects.get(key) != val:
            broken.append(f"{key} -> expected {val}, got {redirects.get(key)}")
    if not expected:
        log.info("  ℹ️  No pack redirects configured — pair check skipped")
    elif broken:
        log.warning(f"  ❌ Pack bundle + catalog redirect pair(s) BROKEN: {broken}")
        ok = False
    else:
        log.info(f"  ✅ Pack bundle + catalog redirect pair(s) present "
                 f"({len(expected)} entries, incl. aa/catalog.json)")

    # 6. Sizes match local files where available — but ONLY hard-fail for
    # files THIS SESSION uploaded (Exp 264). The check's purpose is "did MY
    # upload land intact?"; an out-of-scope song whose stale LOCAL artifact
    # differs from the live deployed copy (a leftover build from another
    # pipeline version) says nothing about this deploy's health. Standalone
    # --verify-ps4 runs (no uploads this session) still check everything —
    # that is the deep-audit mode.
    size_mismatch = []
    size_stale_local = []
    _mass_dir = (config.get('mass_deploy', {}) or {}).get(
        'bundle_dir', '/workspace/orbeats/mass_bundles')
    _custom_dir = (config.get('paths', {}) or {}).get(
        'output_dir', '/workspace/orbeats/custom_songs')
    session_uploads = bool(_SESSION_UPLOADED_BUNDLES)
    for val in local_data.get('redirects', {}).values():
        # Guess local source: pack bundle/catalog, custom_songs (fresh single-song builds),
        # mass_bundles (legacy full-fleet), or AFR staging.
        # Priority: custom_songs > mass_bundles for song bundles; project root for pack bundles/catalogs.
        is_song_bundle = val.endswith('_v3.bundle')
        if is_song_bundle:
            candidates = [
                os.path.join(_custom_dir, val.replace('_v3.bundle', '_custom.bundle')),
                os.path.join(_mass_dir, val),
                os.path.join(PROJECT_ROOT, val),
            ]
        else:
            candidates = [
                os.path.join(PROJECT_ROOT, val),
                os.path.join(_mass_dir, val),
            ]
        for cand in candidates:
            if os.path.isfile(cand):
                local_size = os.path.getsize(cand)
                remote_size = remote_files.get(val)
                if remote_size is not None and remote_size != local_size:
                    if (not session_uploads) or val in _SESSION_UPLOADED_BUNDLES:
                        size_mismatch.append(f"{val} (local {local_size:,} vs PS4 {remote_size:,})")
                    else:
                        size_stale_local.append(f"{val} (local {local_size:,} vs PS4 {remote_size:,})")
                break
    if size_mismatch:
        log.warning(f"  ❌ Size mismatches: {size_mismatch}")
        ok = False
    elif size_stale_local:
        log.info(f"  ℹ️  Local artifacts of targets not uploaded this session differ "
                 f"from the deployed copies (informational): {size_stale_local}")
    if not size_mismatch:
        log.info("  ✅ Redirect target sizes match local files (where available)")

    # 7. Deployed catalog CONTENT is valid (Exp 190 hardening). Size checks alone
    # cannot catch a stale catalog — the broken v0.5319 catalog and the fixed one
    # are the SAME byte size (795,783). Verify the deployed catalog's entry
    # dataIndexes all point at type-7 block starts AND that every configured
    # pack's catalog block carries the expected m_Crc/m_BundleSize.
    pm = config.get('pack_modes', {}) or {}
    if pm.get('patched_catalog_local') and pm.get('patched_catalog'):
        remote_cat_path = f"{afr_base}/{title_id}/{pm['patched_catalog']}"
        local_cat_path = pm['patched_catalog_local']
        try:
            import build_pack_mode_bundles as pm_b
            with tempfile.TemporaryDirectory() as tmpdir:
                remote_cat_tmp = os.path.join(tmpdir, "catalog_remote.json")
                result = sp.run(
                    ["lftp", "-u", user_part, "-p", str(ftp_port), ftp_host,
                     "-e", f"get {_ftp_quote(remote_cat_path)} -o {_ftp_quote(remote_cat_tmp)}; quit"],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode != 0 or not os.path.exists(remote_cat_tmp):
                    log.warning(f"  ❌ Could not download {pm['patched_catalog']} from PS4 for content validation")
                    ok = False
                else:
                    remote_cat = json.load(open(remote_cat_tmp))
                    total, nonzero, bad = pm_b.validate_catalog_dataindexes(remote_cat)
                    if bad:
                        log.warning(f"  ❌ Deployed {pm['patched_catalog']} has {bad}/{total} INVALID entry dataIndexes "
                                    f"({nonzero} nonzero) — the v0.5319 crash signature. Redeploy the catalog!")
                        ok = False
                    else:
                        log.info(f"  ✅ Deployed {pm['patched_catalog']} dataIndexes valid "
                                 f"({total} entries, {nonzero} nonzero, 0 bad)")
                    # Verify deployed catalog content matches local build output.
                    if os.path.isfile(local_cat_path):
                        with open(local_cat_path, 'rb') as f:
                            local_md5 = hashlib.md5(f.read()).hexdigest()
                        with open(remote_cat_tmp, 'rb') as f:
                            remote_md5 = hashlib.md5(f.read()).hexdigest()
                        if local_md5 != remote_md5:
                            log.warning(f"  ❌ Deployed {pm['patched_catalog']} does NOT match local build "
                                        f"(md5 local={local_md5} vs PS4={remote_md5}) — redeploy it!")
                            ok = False
                        else:
                            log.info(f"  ✅ Deployed {pm['patched_catalog']} md5 matches local build ({local_md5})")
                    # Verify each configured pack's catalog entry carries the patched CRC/size.
                    entries = _get_pack_modes_entries(config, packs=packs)
                    # Index by stock packBundle — FLAG-AWARE (M10): when
                    # enable_song_previews is ON, the deployed bundle is the
                    # variant, so the variant's manifest row must win over the
                    # (now-stale) modes row regardless of append order. OFF →
                    # the modes row wins. Rows are keyed by packBundle and the
                    # variant carries 'previews' to tell them apart.
                    want_variant = _previews_enabled(config)
                    manifest = {}
                    for me in pm_b.load_manifest(pm['build_dir']):
                        cur = manifest.get(me['packBundle'])
                        is_var = 'previews' in me
                        if cur is None or is_var == want_variant:
                            manifest[me['packBundle']] = me
                    checks = []
                    for e in entries:
                        me = manifest.get(e['bundle_key'])
                        if me is None:
                            continue
                        # M10: entries point at the variant when the flag is on —
                        # cross-check the manifest row actually describes the
                        # bundle that deployed (variant row ↔ variant entry).
                        if ('previews' in e['patched_bundle'] or '_previews_' in e['patched_bundle']):
                            if me.get('patchedBundle') != e['patched_bundle']:
                                log.warning(f"  ⚠️  Manifest row for {e['pack']} is "
                                             f"{me.get('patchedBundle')} but the deploy "
                                             f"shipped {e['patched_bundle']} — expected "
                                             f"crc/size may be stale")
                        checks.append((me['catalogBundleName'], me['crc'], me['size']))
                    if checks:
                        missing, mismatched = pm_b.validate_catalog_entries(remote_cat, checks)
                        if missing or mismatched:
                            log.warning(f"  ❌ Deployed catalog missing/incorrect pack entries: "
                                        f"missing={missing} mismatched={mismatched}")
                            ok = False
                        else:
                            log.info(f"  ✅ Deployed catalog carries patched CRC/size for all "
                                     f"{len(checks)} configured packs")

                    # Exp 269e DEPLOYED-BUNDLE CRC GUARD — the check that would
                    # have caught the lizzo CE-34878-0 before the crash: the
                    # catalog's expected CRC vs the ACTUAL CRC of the bundle
                    # file on the PS4. Size equality never proved content
                    # identity (two different builds of the same variant share
                    # size whenever the preview set matches — fixed 10s PCM16
                    # slices), and this exact gap shipped a catalog/file
                    # mismatch that crashed the game at the pack scan. Pulls
                    # each deployed pack bundle (they are large — this runs in
                    # full verify and post-deploy validation only) and
                    # computes the same catalog-scheme CRC.
                    for e in entries:
                        me = manifest.get(e['bundle_key'])
                        if me is None:
                            continue
                        remote_bundle_path = f"{afr_base}/{title_id}/{e['patched_bundle']}"
                        bundle_tmp = os.path.join(tmpdir, e['patched_bundle'])
                        rb = sp.run(
                            ["lftp", "-u", user_part, "-p", str(ftp_port), ftp_host,
                             "-e", f"get {_ftp_quote(remote_bundle_path)} -o {_ftp_quote(bundle_tmp)}; quit"],
                            capture_output=True, text=True, timeout=600,
                        )
                        if rb.returncode != 0 or not os.path.exists(bundle_tmp):
                            log.warning(f"  ❌ Could not download deployed "
                                        f"{e['patched_bundle']} for CRC validation")
                            ok = False
                            continue
                        with open(bundle_tmp, 'rb') as f:
                            actual_crc = pm_b.crc_decompressed_stream(f.read())
                        if actual_crc != me['crc']:
                            log.warning(
                                f"  ❌ {e['pack']}: deployed bundle CRC {actual_crc} != "
                                f"manifest/catalog CRC {me['crc']} (size matches at "
                                f"{me['size']:,}) — the catalog describes DIFFERENT bytes "
                                f"than what is deployed. THIS IS THE CE-34878-0 CRASH "
                                f"SIGNATURE — re-deploy the pack (do NOT boot the game).")
                            ok = False
                        else:
                            log.info(f"  ✅ {e['pack']}: deployed bundle CRC matches "
                                     f"catalog ({actual_crc})")
        except Exception as exc:
            log.warning(f"  ❌ Catalog content validation errored: {exc}")
            ok = False
    else:
        log.info("  ℹ️  No pack_modes catalog configured — catalog content check skipped")

    if ok:
        log.info("🎉 Post-deploy validation PASSED")
    else:
        log.warning("⚠️  Post-deploy validation FAILED — see issues above")
    return ok

def manage_redirect_config(
    config: dict,
    target_name: str | None = None,
    generate: bool = False,
    deploy: bool = False,
    sync: bool = False,
    enforce_local: bool = False,
    packs: list | None = None,
    slots: list | None = None,
):
    """
    Manage the redirects.json configuration file.

    Modes:
      generate=True:  Create/update local redirects.json with the current target.
      sync=True:      Download existing config from PS4, merge, save locally, redeploy.
      enforce_local=True: Use only the local redirects.json as truth, deploy it to PS4.
      deploy=True:    Deploy the local redirects.json to PS4.

    When called without any mode flags, auto-generates if local file is missing
    or if a deploy/sync is happening.

    `packs`/`slots` optionally scope the pack-and-song redirects to a subset
    (single-song deploy); default (None) keeps all configured packs/slots.

    Song redirect VALUES always point at the exact deployed bundle filename
    (canonical slot casing + afr_target_suffix), so the game never loads a stale
    pre-.bundle build after a mass deploy.
    """
    cfg_paths = config.get('paths', {})
    cfg_title = config.get('title', {})
    title_id = cfg_title.get('id', 'CUSA12878')
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    local_path = _get_redirect_config_path()

    # Determine what to do
    should_generate = generate or (deploy and not os.path.exists(local_path))
    should_deploy = deploy or sync or enforce_local
    should_sync = sync

    redirect_data = None

    # SYNC mode: download from PS4 first
    if should_sync:
        log.info("🔄 Syncing redirect config from PS4...")
        ps4_data = _download_redirect_from_ps4(config)
        if ps4_data is not None:
            redirect_data = ps4_data
            log.info(f"  Downloaded config with {len(ps4_data.get('redirects', {}))} redirects")
        else:
            log.info("  No existing config on PS4, starting fresh")
            redirect_data = {
                "titleId": title_id,
                "afrBase": afr_base,
                "redirects": {}
            }
    else:
        # GENERATE mode: the LIVE PS4 state is the base, not the local file —
        # but ONLY when this call will DEPLOY. Exp 246: the local copy can lag
        # the PS4 (the release-validation clear-target round-trip restored
        # the PS4 but left the local file at 1 song). Basing generate+deploy
        # on the stale local file pushed it over the live 47-redirect state
        # and wiped 46 song redirects — the pull-before-push invariant
        # (Exp 237) applied to the pipeline itself. If a deploy is about to
        # happen and the PS4 is unreachable, ABORT rather than push a
        # possibly-stale local file (READ-FAILED is never empty-truth).
        # Local-only generate (no deploy) keeps the local-file base: it is
        # the "edit my local file" flow, and touching the network there
        # would break offline builds.
        if should_deploy:
            # Exp 281d: absent (clean console) raises nothing and returns
            # None; a GENUINE read failure raises. The distinction matters:
            # absent + a local file = the local file is the truth for an empty
            # console (this deploy just built it) — deploy it. Failed read +
            # a local file = unknown live state — refuse (Exp 246, unchanged).
            try:
                ps4_data = _download_redirect_from_ps4(config)
            except RuntimeError as e:
                log.error(f"❌ {e}")
                if os.path.exists(local_path):
                    log.error("   A local redirects.json exists that may be stale — "
                             "refusing to deploy it over unknown live state "
                             "(this exact path wiped 46 of 47 song redirects "
                             "once — Exp 246). Check the PS4 connection "
                             "(GoldHEN FTP) and re-run, or use --enforce-config "
                             "to deliberately push the local file.")
                sys.exit(1)
            if ps4_data is not None:
                redirect_data = ps4_data
                n_live = len(ps4_data.get('redirects', {}))
                n_local = (len(_load_local_redirects(local_path).get('redirects', {}))
                           if os.path.exists(local_path) else 0)
                if n_local != n_live:
                    log.info(f"  ℹ️  Local redirects.json was stale ({n_local} entries) — "
                             f"basing this deploy on the live PS4 state ({n_live} entries)")
                # Keep the local file in sync going forward (it is the cache
                # the pack-resolution paths read).
                with open(local_path, 'w') as f:
                    json.dump(redirect_data, f, indent=2)
                    f.write('\n')
            elif os.path.exists(local_path):
                # Exp 281d: clean console (absent live file) + a local file
                # (this deploy's scoping just built it) — the local file IS
                # the new state; deploy it.
                redirect_data = _load_local_redirects(local_path)
                log.info(f"  ℹ️  No redirects.json on the PS4 (clean console) — "
                         f"deploying the newly-built local set "
                         f"({len(redirect_data.get('redirects', {}))} entries)")
            else:
                # No local file at all and no PS4 state: genuinely fresh start
                # (clean slate / first deploy) — safe to begin empty.
                redirect_data = {
                    "titleId": title_id,
                    "afrBase": afr_base,
                    "redirects": {}
                }
        else:
            # Local-only generate (no deploy): the local file stays the base.
            redirect_data = _load_local_redirects(local_path)

    # Update redirect_data with current title/afr settings
    redirect_data['titleId'] = title_id
    redirect_data['afrBase'] = afr_base

    # ENFORCE LOCAL mode: reload from local file, ignoring any PS4 data
    if enforce_local and os.path.exists(local_path):
        redirect_data = _load_local_redirects(local_path)
        log.info(f"  Enforcing local config ({len(redirect_data.get('redirects', {}))} redirects)")

    # If we have a target, add/update the entry
    if target_name and should_generate:
        # Ensure target_name has the correct BeatmapLevelsData prefix
        if not target_name.startswith('BeatmapLevelsData/'):
            target_name = f"BeatmapLevelsData/{target_name}"

        bundle_name = _deployed_bundle_name(target_name.split('/')[-1], config)
        redirect_data.setdefault('redirects', {})[target_name] = bundle_name
        log.info(f"  Added redirect: {target_name} -> {bundle_name}")

    # ALWAYS keep the per-song redirects pointing at the exact deployed bundle
    # filenames (canonical slot casing + afr_target_suffix). This heals stale
    # pre-.bundle values and stale key casing after any config operation.
    # When this call will DEPLOY, pass the LIVE AFR listing so the healing can
    # never rewrite a value that already names a real file on the PS4 (Exp 263:
    # config-casing "healing" turned 11 healthy mixed-case values into dangling
    # lowercase ones because out-of-scope slots are not re-uploaded). Unreachable
    # PS4 during a deploy already aborted above; here the listing is belt-and-
    # suspenders — if it fails, healing stays config-driven exactly as before.
    remote_files = None
    if should_deploy:
        remote_files = _list_remote_dir(config) or None
    _ensure_mass_song_redirects(redirect_data, config, slots=slots,
                                remote_files=remote_files)

    # ALWAYS keep the pack bundle + catalog redirect pair consistent (Exp 180):
    # a config with a pack bundle redirect but no catalog redirect (or with a
    # stale pack target) crashes the game at startup. This runs on every save so
    # the pair can never be silently dropped by regeneration, sync, or enforce.
    _ensure_pack_bundle_redirects(redirect_data, config, packs=packs)

    # Save updated config locally
    os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)
    with open(local_path, 'w') as f:
        json.dump(redirect_data, f, indent=2)
        f.write('\n')
    count = len(redirect_data.get('redirects', {}))
    log.info(f"  Saved redirects.json ({count} redirects)")

    # Deploy to PS4 if requested
    if should_deploy:
        _deploy_redirect_to_ps4(config)

    return redirect_data


# ============================================================================
# Feature Flags Management
# ============================================================================

FEATURES_FILENAME = "features.json"
# Runtime feature flags read by the plugin at startup from features.json on PS4.
# NOTE (v0.5334): enable_beatmap_mode_mapping is NOW a runtime feature flag.
# The pipeline builds mode sets into bundles by default, but the plugin
# will only ENABLE the mode selector UI when this flag is true.
# This allows partial pack deployments (some songs custom, some stock) to
# coexist without crashes — stock songs won't show extra mode buttons.
DEFAULT_FEATURES = {
    # Fresh-install defaults: legacy flags ON (Exp 281), additive proof OFF
    # (Exp 289, explicit user-approved exception). A fresh
    # install works out of the box; the flag list IS the product's feature set.
    # The plugin's absent-file defaults and the webapp's DEFAULTS_TRUE mirror
    # this dict exactly — keep the three in sync.
    "enable_plugin": True,
    "enable_custom_song_replacements": True,
    "enable_song_metadata_modification": True,
    "enable_beatmap_mode_mapping": True,
    "enable_song_previews": True,
    # M11: the Move button+trigger 2s hotkey flips enable_plugin in place
    # (persist-only; restart to apply). The plugin's pull-before-push (Exp 248)
    # reads the LIVE file, so in-game flips flow into webapp/pipeline deploys.
    "enable_in_game_plugin_toggle": True,
    # M12: the in-console game-data extractor — the plugin copies the files the
    # pipeline needs out of the game's own mounts during a normal boot;
    # --pull-game-data mirrors them into the local game_data cache.
    "enable_game_data_extractor": True,
    # Exp 289: user-approved OFF-default runtime stock-reference experiment.
    "enable_additive_song_packs": False,
}

def _get_local_features_path(project_root: str = PROJECT_ROOT) -> str:
    """Return the local path to features.json in the project root."""
    return os.path.join(project_root, FEATURES_FILENAME)

def _get_remote_features_path(config: dict) -> str:
    """Return the remote AFR path for features.json."""
    cfg_paths = config.get('paths', {})
    cfg_title = config.get('title', {})
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = cfg_title.get('id', 'CUSA12878')
    return f"{afr_base}/{title_id}/{FEATURES_FILENAME}"

def _load_local_features(local_path: str) -> dict:
    """Load a local features.json file. Returns default structure if missing."""
    if not os.path.exists(local_path):
        return DEFAULT_FEATURES.copy()
    try:
        with open(local_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        log.warning(f"  ⚠️  Failed to parse {local_path}, using defaults")
        return DEFAULT_FEATURES.copy()

def _save_local_features(features: dict, local_path: str):
    """Save features dict to local features.json."""
    os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)
    with open(local_path, 'w') as f:
        json.dump(features, f, indent=2)
        f.write('\n')
    log.info(f"  Saved {local_path}")

def _deploy_features_to_ps4(config: dict):
    """Upload the local features.json to PS4 via FTP.

    The local file is first merged with DEFAULT_FEATURES so missing keys are
    materialized — a stale features.json written by an older pipeline (before a
    flag existed) must not deploy with that flag silently absent (Exp 221: the
    local file lacked enable_beatmap_mode_mapping → plugin booted 2/3 flags).
    """
    _ensure_afr_title_dir(config)
    import subprocess as sp

    ps4_cfg = config.get('ps4', {})
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')
    local_path = _get_local_features_path()
    remote_path = _get_remote_features_path(config)

    if not os.path.exists(local_path):
        log.warning(f"  ⚠️  Local features.json not found at {local_path} — creating from DEFAULT_FEATURES")
        _save_local_features(DEFAULT_FEATURES.copy(), local_path)
    else:
        # Merge missing keys from DEFAULT_FEATURES (never overwrite explicit values).
        features = _load_local_features(local_path)
        missing = {k: v for k, v in DEFAULT_FEATURES.items() if k not in features}
        if missing:
            features.update(missing)
            _save_local_features(features, local_path)
            log.info(f"  Feature defaults materialized: {sorted(missing)}")

    user_part = f"{user},{password}" if password else f"{user},"
    cmd = ["lftp", "-u", user_part, "-p", str(port), host,
           "-e", f"put {_ftp_quote(local_path)} -o {_ftp_quote(remote_path)}; quit"]
    log.info(f"  Deploying features.json to PS4: {remote_path}")
    result = sp.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        log.info("  ✅ Features config deployed")
    else:
        log.warning(f"  ⚠️  Features config deploy failed: {result.stderr}")

def _download_features_from_ps4(config: dict) -> dict | None:
    """
    Download features.json from the PS4 (banner-free transport).

    Returns the parsed features dict, or None when the file is absent.
    Raises RuntimeError on a read FAILURE (reachable-but-failed / parse
    error) — callers must ABORT, never treat a failed read as "no flags"
    (Exp 248: the READ-FAILED-as-empty-truth class).
    """
    import subprocess as sp
    import tempfile

    ps4_cfg = config.get('ps4', {})
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')
    remote_path = _get_remote_features_path(config)
    user_part = f"{user},{password}" if password else f"{user},"

    with tempfile.TemporaryDirectory() as tmpdir:  # mktemp -d, never mktemp (pitfall 2)
        local_tmp = os.path.join(tmpdir, "features.json")
        cmd = ["lftp", "-u", user_part, "-p", str(port), host,
               "-e", f"get {_ftp_quote(remote_path)} -o {_ftp_quote(local_tmp)}; quit"]
        result = sp.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(local_tmp) and os.path.getsize(local_tmp) > 0:
            # Banner-proof extraction (pitfall 1): a trailing banner can START
            # with '}' ('}156 bytes transferred'), so first-{ -to-last-} slicing
            # is not sufficient — use raw_decode scanning (the Exp 240/221
            # proven pattern): parse ONE complete object from each '{' until
            # one succeeds.
            raw = open(local_tmp, encoding='utf-8', errors='replace').read()
            decoder = json.JSONDecoder()
            pos = raw.find('{')
            while pos != -1:
                try:
                    obj, _ = decoder.raw_decode(raw, pos)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass
                pos = raw.find('{', pos + 1)
            raise RuntimeError("could not parse the PS4's features.json")
        if result.returncode == 0:
            # reachable, but the file is absent — clean slate, not an error
            return None
        if _ps4_output_looks_absent(
                (getattr(result, "stdout", "") or "")
                + (getattr(result, "stderr", "") or "")):
            # Exp 281c: a decisive 550 (absent) is the clean-slate state —
            # apply defaults, never abort (the flags Apply on a fresh console)
            return None
        raise RuntimeError(
            f"could not read features.json from the PS4 (lftp rc={result.returncode})")


def apply_feature_flags(set_features: list, config: dict):
    """
    Apply feature flag changes from --set-feature arguments.

    Exp 248 pull-before-push: the LIVE PS4 features.json is the base. The
    local file may be stale (it previously served as the base and pushed a
    stale `enable_song_metadata_modification=false` over the console's ON
    value — the 2/3-features boot toast + missing song metadata). The
    requested diffs apply ON TOP of the live state; the local file is then
    resynced from the result. If the PS4 is reachable but the read fails,
    ABORT — never apply blind.
    """
    if not set_features:
        return

    local_path = _get_local_features_path()

    # Parse the requested diffs first (fail on bad syntax before any I/O)
    diffs: dict[str, bool] = {}
    for entry in set_features:
        if '=' not in entry:
            log.error(f"  ❌ Invalid --set-feature format: '{entry}' (expected key=true/false)")
            return
        key, val_str = entry.split('=', 1)
        key = key.strip()
        val_str = val_str.strip().lower()
        if val_str in ('true', '1', 'yes', 'on'):
            diffs[key] = True
        elif val_str in ('false', '0', 'no', 'off'):
            diffs[key] = False
        else:
            log.error(f"  ❌ Invalid feature value: '{val_str}' (expected true/false)")
            return

    # Pull the live state (abort on failure — never blind-apply)
    try:
        live = _download_features_from_ps4(config)
    except RuntimeError as e:
        log.error(f"❌ Refusing to apply feature flags: {e}. The live state is "
                  f"unknown — pushing the local file now could silently flip "
                  f"flags you didn't ask to change (this exact path turned "
                  f"the user's metadata flag off once — Exp 248). Fix the PS4 "
                  f"connection and re-run.")
        sys.exit(1)
    if live is None:
        log.info("  ℹ️  No features.json on the PS4 — starting from defaults")
        live_flags = DEFAULT_FEATURES.copy()
    else:
        live_flags = live.get('features', live) if isinstance(live, dict) else {}

    # Materialize any flag the live file predates (Exp 221 merge rule)
    for k, v in DEFAULT_FEATURES.items():
        live_flags.setdefault(k, v)

    for key, val in diffs.items():
        live_flags[key] = val
        log.info(f"  Feature flag: {key} = {val}")

    _save_local_features(live_flags, local_path)
    _deploy_features_to_ps4(config)


# ============================================================================
# Song Metadata Management
# ============================================================================

SONG_METADATA_FILENAME = "song_metadata.json"
SONG_IDS_FILENAME = "beat_saber_song_ids.json"

# ============================================================================
# Game-Data Extraction Management (M12, Exp 280) — eliminates the PC-side
# dump requirement for USERS: the plugin extracts the files the pipeline
# needs from the game's own decrypted mounts (/archive/mount/point + /app0,
# log-proven) during a normal boot; the web app drives these two modes.
#
# OWNERSHIP (pull-before-push doctrine): game_data_requests.txt is
# PIPELINE/WEB-APP OWNED (we write it, the plugin only reads it — one
# relative path per line, # comments allowed); game_data_status.txt is
# PLUGIN OWNED (one extracted path per line; "ERR <rel> <reason>" lines mark
# failures — they never match a request line, so failures retry on the next
# boot automatically). No file is written by both sides.
#
# The local cache (paths.game_data_dir, default ./game_data) mirrors the
# dump's relative layout EXACTLY, so pointing paths.game_dump_dir at it is
# the only change a user (or the web app) makes.
# ============================================================================
GAMEDATA_REQUESTS_FILENAME = "game_data_requests.txt"
GAMEDATA_STATUS_FILENAME = "game_data_status.txt"
GAMEDATA_REMOTE_DIRNAME = "game_data"


def _get_remote_game_data_paths(config: dict) -> tuple[str, str, str]:
    """(requests, status, dir) remote AFR paths for the game-data flow."""
    cfg_paths = config.get('paths', {})
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = config.get('title', {}).get('id', 'CUSA12878')
    base = f"{afr_base}/{title_id}"
    return (f"{base}/{GAMEDATA_REQUESTS_FILENAME}",
            f"{base}/{GAMEDATA_STATUS_FILENAME}",
            f"{base}/{GAMEDATA_REMOTE_DIRNAME}")


def _get_local_game_data_dir(config: dict) -> str:
    """The local cache dir (paths.game_data_dir, PROJECT_ROOT-relative)."""
    gd = config.get('paths', {}).get('game_data_dir',
                                     os.path.join(PROJECT_ROOT, 'game_data'))
    if not os.path.isabs(gd):
        gd = os.path.join(PROJECT_ROOT, gd)
    return gd


def compute_game_data_manifest(config: dict, packs=None, slots=None) -> list[str]:
    """The relative paths (dump layout) the pipeline needs for the requested
    packs/slots: every targeted slot's template file + every involved pack's
    pack bundle + the origin catalog. Computed from beat_saber_song_ids.json
    (ships with the repo/release) — NO dump required to compute this."""
    ids_path = config.get('pack_modes', {}).get('song_ids_path')
    if not ids_path or not os.path.exists(ids_path):
        ids_path = os.path.join(PROJECT_ROOT, SONG_IDS_FILENAME)
    with open(ids_path, 'r', encoding='utf-8') as f:
        ids = json.load(f)
    packs = set(packs or [])
    slots = set(slots or [])
    rels: set[str] = set()
    involved_packs: set[str] = set()
    for album in ids.get('albums', []):
        pack_name = album.get('pack', '')
        pack_requested = pack_name in packs
        if pack_requested:
            involved_packs.add(pack_name)
        for song in album.get('songs', []):
            slot_id = song.get('songID', '')
            if pack_requested or slot_id in slots:
                # Per-slot template file (the PS4 FS is case-insensitive for
                # the plugin's read; the cached file keeps the ids-file casing
                # so --template resolves it on the case-sensitive PC side).
                rels.add(f"Media/StreamingAssets/BeatmapLevelsData/{slot_id}")
                if slot_id in slots:
                    involved_packs.add(pack_name)  # a slot request needs its pack bundle too
        if pack_name in involved_packs:
            bundle = album.get('packBundle', '')
            if bundle:
                rels.add(f"Media/StreamingAssets/aa/PS4/{bundle}")
    if rels:
        rels.add("Media/StreamingAssets/aa/catalog.json")
    return sorted(rels)


def request_game_data(config: dict, packs=None, slots=None):
    """Write the extraction manifest to the PS4 (game_data_requests.txt).
    REQUIRES the plugin's enable_game_data_extractor flag; the extraction
    happens on the next boot of the game. Safe to re-run (the file is fully
    owned by the pipeline/web app — the plugin never writes it)."""
    import subprocess as sp
    import tempfile

    rels = compute_game_data_manifest(config, packs, slots)
    if not rels:
        log.error("❌ Nothing to request — pass --game-data-packs and/or --game-data-slots "
                  "(comma-separated pack ids like 'lizzo,billieeilish' and/or slot ids like "
                  "'2BeLoved,AboutDamnTime').")
        sys.exit(1)

    req_remote, _status_remote, _dir_remote = _get_remote_game_data_paths(config)
    ps4_cfg = config.get('ps4', {})
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')
    user_part = f"{user},{password}" if password else f"{user},"

    n_templates = sum(1 for r in rels if 'BeatmapLevelsData' in r)
    n_packs = sum(1 for r in rels if '_pack_assets_all_' in r)
    log.info(f"🎮 Requesting game-data extraction: {n_templates} slot template(s), "
             f"{n_packs} pack bundle(s), catalog.json")

    with tempfile.TemporaryDirectory() as tmpdir:
        local_req = os.path.join(tmpdir, GAMEDATA_REQUESTS_FILENAME)
        with open(local_req, 'w', encoding='utf-8') as f:
            f.write("# game_data_requests v1 — one relative path per line\n")
            for r in rels:
                f.write(r + "\n")
        _ensure_afr_title_dir(config)  # fresh-console bootstrap (Exp 281b)
        cmd = ["lftp", "-u", user_part, "-p", str(port), host, "-e",
               f"put {_ftp_quote(local_req)} -o {_ftp_quote(req_remote)}; "
               f"ls -la {_ftp_quote(req_remote)}; quit"]
        result = sp.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            log.error(f"  ⚠️  Could not reach the PS4 to write the request: {result.stderr.strip()}")
            log.error("     To fix: check the PS4 is on + GoldHEN's FTP (see README Prerequisites).")
            sys.exit(1)
        # Verify the upload by the remote listing (never trust lftp's rc alone)
        want = os.path.getsize(local_req)
        if str(want) not in (result.stdout or ''):
            log.warning("  ⚠️  Request upload could not be verified via remote listing — "
                        "re-run or inspect with the web app's PS4 state tab.")

    log.info("  ✅ Request written to the PS4")
    log.info("")
    log.info("NEXT STEPS:")
    log.info("  1. Make sure the plugin's enable_game_data_extractor flag is ON "
             "(--features-only --set-feature enable_game_data_extractor=true)" +
             ("" if config.get('features', {}).get('enable_game_data_extractor') else
              "  ← it is currently OFF in the local features.json"))
    log.info("  2. Boot Beat Saber once — the plugin extracts the requested files "
             "to game_data/ on the console (idempotent; failures retry next boot)")
    log.info("  3. Run --pull-game-data to mirror them into the local cache, then "
             "point paths.game_dump_dir at it (the web app does both for you)")


def pull_game_data(config: dict):
    """Mirror the console's game_data/ (the extractor's output) into the local
    cache (paths.game_data_dir) — resumable (lftp mirror skips identical-size
    files), and a drop-in replacement for paths.game_dump_dir once pulled."""
    import subprocess as sp

    req_remote, status_remote, dir_remote = _get_remote_game_data_paths(config)
    local_dir = _get_local_game_data_dir(config)
    ps4_cfg = config.get('ps4', {})
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')
    user_part = f"{user},{password}" if password else f"{user},"

    # Read the plugin-owned status file first (banner-free get-to-temp).
    status_lines: list[str] = []
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        local_tmp = os.path.join(tmpdir, "status.txt")
        cmd = ["lftp", "-u", user_part, "-p", str(port), host, "-e",
               f"get {_ftp_quote(status_remote)} -o {_ftp_quote(local_tmp)}; quit"]
        result = sp.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(local_tmp) and os.path.getsize(local_tmp) > 0:
            status_lines = [line.strip() for line in
                            open(local_tmp, encoding='utf-8', errors='replace').read().splitlines()
                            if line.strip()]
        elif result.returncode != 0:
            log.error("❌ Could not reach the PS4 to read the extraction status.")
            log.error("   To fix: check the PS4 is on + GoldHEN's FTP (README Prerequisites).")
            sys.exit(1)

    done = [line for line in status_lines
            if not line.startswith('ERR ') and not line.startswith('#')]
    errors = [line for line in status_lines if line.startswith('ERR ')]
    if not done:
        log.error("❌ Nothing has been extracted yet (no game_data_status.txt entries).")
        log.error("   To fix: write a request first (--request-game-data ...), make sure "
                  "enable_game_data_extractor is ON, and boot Beat Saber once — "
                  "the plugin extracts during a normal boot.")
        sys.exit(1)

    log.info(f"📦 Extraction status on the console: {len(done)} file(s) ready")
    for e in errors:
        log.warning(f"  ⚠️  {e}")

    os.makedirs(local_dir, exist_ok=True)
    log.info(f"📥 Mirroring game_data/ → {local_dir} (resumable; identical files skip)")
    cmd = ["lftp", "-u", user_part, "-p", str(port), host, "-e",
           f"mirror --verbose --parallel=4 {_ftp_quote(dir_remote)} {_ftp_quote(local_dir)}; quit"]
    try:
        result = sp.run(cmd, capture_output=True, text=True, timeout=1800)
    except sp.TimeoutExpired:
        log.error("❌ The mirror transfer timed out after 30 minutes — re-run "
                  "--pull-game-data (it resumes where it left off).")
        sys.exit(1)
    if result.returncode != 0:
        log.error(f"❌ Mirror failed: {(result.stdout + result.stderr).strip()[:500]}")
        log.error("   To fix: re-run (mirror resumes); if it persists, check the FTP "
                  "connection and the web app's PS4 state tab.")
        sys.exit(1)

    # Verify: every status success line should exist locally now.
    missing = [r for r in done if not os.path.exists(os.path.join(local_dir, r))]
    if missing:
        log.warning(f"  ⚠️  {len(missing)} file(s) missing after the mirror — "
                    f"first: {missing[0]}")
        log.warning("     To fix: re-run --pull-game-data (mirror is resumable).")
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(local_dir) for f in fs)
    log.info(f"  ✅ Local cache: {len(done) - len(missing)}/{len(done)} files, "
             f"{total / 1e6:.1f} MB at {local_dir}")
    log.info("")
    log.info("The cache mirrors the dump layout — point paths.game_dump_dir at it")
    log.info(f"(the web app's game-data flow does this for you): "
             f"\"paths.game_dump_dir\": {local_dir!r}")

def _read_info_song_metadata(info: dict) -> tuple:
    """
    Extract (song_name, song_artist) from an Info.dat dict.

    Format-aware (Exp 228):
    - V2/V3 Info.dat: top-level "_songName" / "_songAuthorName"
    - V4 Info.dat (BeatSaver v4.0.x maps): nested "song" object with
      "title" / "author" — reading only the V2/V3 keys made the pipeline
      fall back to the map ID as the display name ('Oxytocin' -> '4dea2').

    Returns (None, None) when absent so callers keep their own fallbacks.
    """
    song_name = info.get("_songName")
    song_artist = info.get("_songAuthorName")
    if not song_name or not song_artist:
        v4_song = info.get("song") or {}
        if not song_name:
            song_name = v4_song.get("title") or v4_song.get("songName")
        if not song_artist:
            song_artist = v4_song.get("author") or v4_song.get("songAuthorName")
    return song_name, song_artist


def _read_info_bpm_from_dict(info: dict) -> float | None:
    """
    Extract the BPM from an Info.dat dict, format-aware.

    V2/V3: top-level "_beatsPerMinute"; V4: nested "audio" object's "bpm"
    (e.g. 4dea2/443f3 ship audio.bpm=111.0 with no _beatsPerMinute).
    Returns None when absent/unparsable so callers keep their own fallbacks.
    """
    bpm = info.get("_beatsPerMinute")
    if bpm is None:
        bpm = (info.get("audio") or {}).get("bpm")
    try:
        return float(bpm) if bpm is not None else None
    except (TypeError, ValueError):
        return None

def _get_song_metadata_path(project_root: str = PROJECT_ROOT) -> str:
    """Return the local path to song_metadata.json in the project root."""
    return os.path.join(project_root, SONG_METADATA_FILENAME)

def _get_song_ids_path(project_root: str = PROJECT_ROOT) -> str:
    """Return the local path to beat_saber_song_ids.json in the project root."""
    return os.path.join(project_root, SONG_IDS_FILENAME)

def _load_song_details() -> dict:
    """Load beat_saber_song_ids.json. Returns {slot_id: {songName, songAuthorName}} mapping."""
    path = _get_song_ids_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        mapping = {}
        for album in data.get('albums', []):
            for song in album.get('songs', []):
                slot_id = song.get('songID', '')
                song_name = song.get('songName', '').strip()
                author_name = song.get('songAuthorName', '').strip()
                if slot_id:
                    mapping[slot_id] = {
                        'songName': song_name,
                        'songAuthorName': author_name
                    }
        return mapping
    except Exception:
        return {}

def _load_song_ids() -> dict:
    """Load beat_saber_song_ids.json. Returns {slot_id: song_name} mapping."""
    details = _load_song_details()
    return {slot: d['songName'] for slot, d in details.items()}

def _lookup_song_name(slot_or_name: str, song_ids: dict) -> str:
    """Look up exact game song name from song IDs.

    Tries exact slot ID match first (e.g. 'StartMeUp'), then case-insensitive
    slot match, then falls back to the input string stripped of trailing spaces.
    """
    # Direct slot ID match (e.g. "StartMeUp" -> "Start Me Up")
    if slot_or_name in song_ids:
        return song_ids[slot_or_name]
    # Case-insensitive slot match
    lower = slot_or_name.lower()
    for slot, name in song_ids.items():
        if slot.lower() == lower:
            return name
    # Fall back to stripped input
    return slot_or_name.strip()

def _get_remote_song_metadata_path(config: dict) -> str:
    """Return the remote AFR path for song_metadata.json."""
    cfg_paths = config.get('paths', {})
    cfg_title = config.get('title', {})
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = cfg_title.get('id', 'CUSA12878')
    return f"{afr_base}/{title_id}/{SONG_METADATA_FILENAME}"

def _load_local_song_metadata(local_path: str) -> dict:
    """Load a local song_metadata.json file. Returns default structure if missing."""
    default = {"song_names": {}, "song_artists": {}}
    if not os.path.exists(local_path):
        return default
    try:
        with open(local_path, 'r') as f:
            data = json.load(f)
        data.setdefault('song_names', {})
        data.setdefault('song_artists', {})
        return data
    except (json.JSONDecodeError, IOError):
        log.warning(f"  ⚠️  Failed to parse {local_path}, starting fresh")
        return default

def _deploy_song_metadata_to_ps4(config: dict):
    """Upload the local song_metadata.json to PS4 via FTP."""
    import subprocess as sp

    ps4_cfg = config.get('ps4', {})
    host = ps4_cfg.get('ip', '192.168.100.117')
    port = ps4_cfg.get('ftp_port', 2121)
    user = ps4_cfg.get('ftp_user', 'anonymous')
    password = ps4_cfg.get('ftp_password', '')
    local_path = _get_song_metadata_path()
    remote_path = _get_remote_song_metadata_path(config)

    if not os.path.exists(local_path):
        log.warning(f"  ⚠️  Local song_metadata.json not found at {local_path}")
        return

    user_part = f"{user},{password}" if password else f"{user},"
    cmd = ["lftp", "-u", user_part, "-p", str(port), host,
           "-e", f"put {_ftp_quote(local_path)} -o {_ftp_quote(remote_path)}; quit"]
    log.info(f"  Deploying song_metadata.json to PS4: {remote_path}")
    result = sp.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        log.info("  ✅ Song metadata deployed")
    else:
        log.warning(f"  ⚠️  Song metadata deploy failed: {result.stderr}")

def manage_song_metadata(
    config: dict,
    song_name: str | None = None,
    artist: str | None = None,
    target_name: str | None = None,
    deploy: bool = False,
):
    """
    Manage the song_metadata.json configuration file.

    When song_name and target_name are provided, adds/updates the song_names entry.
    When artist and target_name are provided, adds/updates the song_artists entry.
    target_name can be a slot ID (e.g. "StartMeUp") or exact song name — it will
    be resolved to the exact game string via beat_saber_song_ids.json.
    Always deploys to PS4 when deploy=True.
    """
    local_path = _get_song_metadata_path()
    metadata = _load_local_song_metadata(local_path)

    song_details = _load_song_details()
    exact_song_name = target_name
    original_author = None

    if target_name:
        found = None
        if target_name in song_details:
            found = song_details[target_name]
        else:
            lower = target_name.lower()
            for s_id, details in song_details.items():
                if s_id.lower() == lower or details['songName'].lower() == lower:
                    found = details
                    break
        if found:
            exact_song_name = found['songName']
            original_author = found['songAuthorName']
            log.info(f"  Resolved target '{target_name}' -> songName='{exact_song_name}', author='{original_author}'")

    if song_name and exact_song_name:
        combined_name = f"{song_name} / {artist}" if artist else song_name
        metadata['song_names'][exact_song_name] = combined_name
        log.info(f"  Song metadata: '{exact_song_name}' -> '{combined_name}'")

    if original_author:
        metadata['song_artists'][original_author] = " "
        log.info(f"  Artist metadata: blanking out original author '{original_author}' -> ' '")
    elif artist and exact_song_name:
        metadata['song_artists'][exact_song_name] = artist
        log.info(f"  Artist metadata: '{exact_song_name}' -> '{artist}'")

    os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)
    # Exp 228: ensure_ascii=False so non-ASCII slot titles (e.g. '…Baby One
    # More Time') are written as raw UTF-8, not \uXXXX escapes. The plugin's
    # byte-level JSON parser gained \uXXXX unescape support for backward
    # compatibility, but raw UTF-8 keeps the file human-readable and the
    # plugin's key fold exact.
    with open(local_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write('\n')
    count_names = len(metadata.get('song_names', {}))
    count_artists = len(metadata.get('song_artists', {}))
    log.info(f"  Saved song_metadata.json ({count_names} names, {count_artists} artists)")

    if deploy:
        _deploy_song_metadata_to_ps4(config)

    return metadata

BEATSAVER_API_BASE = "https://api.beatsaver.com"

def download_beat_saver_song(map_id: str, output_dir: str | None = None,
                             api_base: str | None = None) -> str:
    """
    Download a song from BeatSaver by its map key and extract it.

    Args:
        map_id: The BeatSaver map key (e.g. '1d6c7c2' from beatsaver.com/maps/1d6c7c2)
        output_dir: Directory to extract into. If None, uses a temp directory.
        api_base: Override BeatSaver API base URL (default: https://api.beatsaver.com)

    Returns:
        Path to the extracted song directory containing info.dat/Easy.dat/etc.
    """
    import tempfile
    import urllib.error
    import urllib.request
    import zipfile

    base = api_base or BEATSAVER_API_BASE
    download_url = f"{base}/maps/id/{map_id}/download"
    info_url = f"{base}/maps/id/{map_id}"

    log.info(f"Downloading BeatSaver song: {map_id}")
    log.info(f"  API: {info_url}")

    # Try to fetch song info first (extracts download URL from the API response)
    song_name = map_id
    cdn_url = None
    try:
        req = urllib.request.Request(info_url, headers={"User-Agent": "BeatSaberDeluxe/0.54"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            info_data = json.loads(resp.read().decode('utf-8'))
            if info_data.get('name'):
                song_name = info_data['name']
                log.info(f"  Song: {song_name} by {info_data.get('metadata', {}).get('songAuthorName', '?')}")
            # Check if it has the required beatmap characteristics
            versions = info_data.get('versions', [])
            if versions:
                v0 = versions[0]
                diffs = v0.get('diffs', [])
                has_standard = any(d.get('characteristic','').lower() == 'standard' for d in diffs)
                if not has_standard:
                    log.warning("  ⚠️  Song has no Standard characteristic beatmaps (may not work)")
                # Extract download URL — BeatSaver uses CDN: cdn.beatsaver.com/<hash>.zip
                cdn_url = v0.get('downloadURL')
                if not cdn_url and v0.get('hash'):
                    cdn_url = f"https://cdn.beatsaver.com/{v0['hash']}.zip"
                if cdn_url:
                    log.info(f"  Download URL: {cdn_url}")
    except Exception as e:
        log.warning(f"  ⚠️  Could not fetch song info: {e}")
    if song_name == map_id:
        # Exp 228: the API name fetch failed — without this warning the map ID
        # silently became the deployed display name ('Oxytocin' -> '4dea2').
        log.warning(
            f"  ⚠️  Song display name will fall back to the map ID ('{map_id}'). "
            f"Pass --song-name/--artist to set them explicitly.")

    if not cdn_url:
        # Fallback: try the direct download endpoint
        cdn_url = download_url
        log.warning("  Using fallback download URL (may not work)")

    # Download the zip
    tmp_dir = output_dir or tempfile.mkdtemp(prefix="beatsaver_")
    zip_path = os.path.join(tmp_dir, f"{map_id}.zip")

    try:
        req = urllib.request.Request(cdn_url, headers={"User-Agent": "BeatSaberDeluxe/0.54"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            total_size = int(resp.headers.get('Content-Length', 0))
            log.info(f"  Downloading ({total_size / 1024 / 1024:.1f} MB)...")
            with open(zip_path, 'wb') as f:
                f.write(resp.read())
    except urllib.error.HTTPError as e:
        log.error(f"  ❌ Download failed (HTTP {e.code}): {e.reason}")
        raise RuntimeError(f"BeatSaver download failed for map {map_id}")
    except Exception as e:
        log.error(f"  ❌ Download failed: {e}")
        raise

    # Extract
    extract_dir = os.path.join(tmp_dir, map_id)
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_dir)

    os.unlink(zip_path)  # Remove zip to save space
    log.info(f"  ✅ Extracted to {extract_dir}")

    # Show found beatmap files
    files = [f for f in os.listdir(extract_dir) if f.endswith(('.dat', '.json'))]
    log.info(f"  Found {len(files)} beatmap files")

    return extract_dir


def clear_target_song(config: dict, slot_name: str):
    """
    Remove a custom song override and revert the slot to its stock state.

    This:
    1. Removes the custom song bundle from PS4 AFR directory
    2. Removes the redirect entry from redirects.json
    3. Removes the song metadata entries from song_metadata.json
    4. Removes the artist metadata entries from song_metadata.json
    5. Rebuilds and redeploys the pack bundle if this was the last custom song in the pack
    6. Deploys updated configs to PS4

    If this was the only custom song in the pack, the pack bundle is rebuilt
    from the original dump (no extra modes for any song) and redeployed.
    If other custom songs remain in the pack, the pack bundle is rebuilt
    with only those remaining custom songs getting extra modes.
    """
    import subprocess as sp

    log.info(f"🧹 Clearing custom song override for slot: {slot_name}")

    cfg_ps4 = config.get('ps4', {})
    cfg_title = config.get('title', {})
    cfg_paths = config.get('paths', {})

    host = cfg_ps4.get('ip', '192.168.100.117')
    port = cfg_ps4.get('ftp_port', 2121)
    user = cfg_ps4.get('ftp_user', 'anonymous')
    password = cfg_ps4.get('ftp_password', '')
    afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
    title_id = cfg_title.get('id', 'CUSA12878')
    suffix = cfg_paths.get('afr_target_suffix', '_v3.bundle')

    # 1. Remove custom song bundle from PS4 — ALL casing variants of the slot.
    # GoldHEN FTP is case-sensitive and different deploy paths have written
    # the slot with different casing (webapp deploys used the catalog's
    # 'MessItUp'; the example scripts/mass list used 'messitup'). A clear
    # reverts the SLOT — nothing named <slot><suffix> in any casing may
    # survive, or the loadout correctly reports the leftover as a stale
    # bundle (user-visible: "why does it show Stale when I cleared it?",
    # Exp 253).
    user_part = f"{user},{password}" if password else f"{user},"
    cmd = ["lftp", "-u", user_part, "-p", str(port), host,
           "-e", f"cls {_ftp_quote(afr_base + '/' + title_id)}; quit"]
    result = sp.run(cmd, capture_output=True, text=True, timeout=30)
    remote_names = []
    if result.returncode == 0:
        import re as _re
        for line in result.stdout.splitlines():
            m = _re.search(r"[^/\s]+\.(?:bundle|json)$", line.strip())
            if m:
                remote_names.append(m.group(0))
    removed_any = False
    for name in remote_names:
        if name.lower() == f"{slot_name.lower()}{suffix.lower()}":
            remote_path = f"{afr_base}/{title_id}/{name}"
            rm_cmd = ["lftp", "-u", user_part, "-p", str(port), host,
                      "-e", f"rm {_ftp_quote(remote_path)}; quit"]
            rm_result = sp.run(rm_cmd, capture_output=True, text=True, timeout=30)
            if rm_result.returncode == 0:
                removed_any = True
                log.info(f"  ✅ Removed {name} from PS4")
            else:
                log.warning(f"  ⚠️  Could not remove {name} from PS4: {rm_result.stderr}")
    if not removed_any and not remote_names:
        log.info(f"  ℹ️  No {slot_name}{suffix} (any casing) found on PS4 — nothing to remove")
    elif not removed_any:
        log.warning(f"  ⚠️  No casing variant of {slot_name}{suffix} was removed (found files: {remote_names[:5]})")

    # 2. Remove redirect entry from redirects.json
    # Download current redirects.json from PS4 first (local may be stale)
    local_redirect_path = _get_redirect_config_path()
    remote_redirect_path = _get_remote_redirect_path(config)
    cmd = ["lftp", "-u", user_part, "-p", str(port), host,
           "-e", f"get {_ftp_quote(remote_redirect_path)} -o {_ftp_quote(local_redirect_path)}; quit"]
    result = sp.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and os.path.exists(local_redirect_path):
        redirect_data = _load_local_redirects(local_redirect_path)
        log.info("  Downloaded current redirects.json from PS4")
    else:
        redirect_data = _load_local_redirects(local_redirect_path)
        log.warning("  Could not download redirects.json from PS4, using local")
    redirects = redirect_data.get('redirects', {})

    # Find and remove the redirect key (handles both with and without prefix)
    key_to_remove = None
    for key in list(redirects.keys()):
        if key == f"BeatmapLevelsData/{slot_name}" or key.lower() == f"BeatmapLevelsData/{slot_name}".lower():
            key_to_remove = key
            break
        # Also check if the slot name appears at the end of the key
        if key.startswith('BeatmapLevelsData/') and key[len('BeatmapLevelsData/'):].lower() == slot_name.lower():
            key_to_remove = key
            break

    if key_to_remove:
        del redirects[key_to_remove]
        log.info(f"  Removed redirect: {key_to_remove}")
    else:
        log.info(f"  No redirect found for {slot_name}")

    # Save updated redirects.json locally
    with open(local_redirect_path, 'w') as f:
        json.dump(redirect_data, f, indent=2)
        f.write('\n')
    log.info("  ✅ Updated local redirects.json")

    # 3. Remove song metadata entries
    local_metadata_path = _get_song_metadata_path()
    metadata = _load_local_song_metadata(local_metadata_path)

    # We need to find the exact song name and author from song_ids.json
    song_details = _load_song_details()
    exact_song_name = slot_name
    original_author = None

    if slot_name in song_details:
        exact_song_name = song_details[slot_name]['songName']
        original_author = song_details[slot_name]['songAuthorName']
        log.info(f"  Resolved '{slot_name}' -> songName='{exact_song_name}', author='{original_author}'")
    else:
        # Try case-insensitive match
        lower = slot_name.lower()
        for s_id, details in song_details.items():
            if s_id.lower() == lower or details['songName'].lower() == lower:
                exact_song_name = details['songName']
                original_author = details['songAuthorName']
                log.info(f"  Resolved '{slot_name}' -> songName='{exact_song_name}', author='{original_author}'")
                break

    # 4. Check if we need to rebuild the pack bundle (must be done BEFORE artist metadata removal)
    # This slot belongs to a pack - check if there are other custom songs in the same pack
    target_pack = _resolve_target_pack(config, slot_name)
    pack_needs_rebuild = False
    rebuild_slots = None
    other_custom_in_pack = False
    remaining_slots = []

    if target_pack:
        # Check if there are other custom song redirects for this pack
        for key in redirects:
            if key.startswith('BeatmapLevelsData/'):
                other_slot = key[len('BeatmapLevelsData/'):]
                other_pack = _resolve_target_pack(config, other_slot)
                if other_pack == target_pack:
                    other_custom_in_pack = True
                    remaining_slots.append(other_slot)

        if not other_custom_in_pack:
            # This was the last custom song in the pack - rebuild pack bundle from original dump
            pack_needs_rebuild = True
            rebuild_slots = []  # Empty = no extra modes for any song (stock state)
            log.info(f"  ℹ️  No other custom songs in pack '{target_pack}' — rebuilding pack bundle from original dump (stock state)")
        else:
            # Other custom songs exist - rebuild pack bundle with target_slots for remaining custom songs
            log.info(f"  ℹ️  Other custom songs in pack '{target_pack}': {remaining_slots} — rebuilding pack bundle for these slots only")
            pack_needs_rebuild = True
            rebuild_slots = remaining_slots

    # Save updated song_metadata.json locally (will be modified below)
    # Exp 228: ensure_ascii=False — non-ASCII titles stay raw UTF-8
    with open(local_metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write('\n')
    log.info("  ✅ Updated local song_metadata.json")

    # Remove from song_names
    if exact_song_name in metadata.get('song_names', {}):
        del metadata['song_names'][exact_song_name]
        log.info(f"  Removed song metadata: '{exact_song_name}'")

    # Remove from song_artists (blank out the original author)
    # Only remove artist metadata if this is the LAST custom song in the pack
    # (when no other custom songs remain, we restore the artist name)
    if not other_custom_in_pack:
        if original_author and original_author in metadata.get('song_artists', {}):
            del metadata['song_artists'][original_author]
            log.info(f"  Restored artist metadata (last custom song in pack): '{original_author}'")
        # Also try removing by exact song name
        if exact_song_name in metadata.get('song_artists', {}):
            del metadata['song_artists'][exact_song_name]
            log.info(f"  Restored artist metadata (last custom song in pack): '{exact_song_name}'")
    else:
        log.info("  Other custom songs remain in pack — keeping artist metadata blanked for pack")

    # Save updated song_metadata.json locally (after artist metadata changes)
    # Exp 228: ensure_ascii=False — non-ASCII titles stay raw UTF-8
    with open(local_metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write('\n')
    log.info("  ✅ Updated local song_metadata.json")

    # 5. Deploy updated configs to PS4
    log.info("  Deploying updated configs to PS4...")

    # Deploy redirects.json
    remote_redirect_path = _get_remote_redirect_path(config)
    cmd = ["lftp", "-u", user_part, "-p", str(port), host,
           "-e", f"put {_ftp_quote(local_redirect_path)} -o {_ftp_quote(remote_redirect_path)}; quit"]
    result = sp.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        log.info("  ✅ redirects.json deployed to PS4")
    else:
        log.warning(f"  ⚠️  Failed to deploy redirects.json: {result.stderr}")

    # Deploy song_metadata.json
    remote_metadata_path = _get_remote_song_metadata_path(config)
    cmd = ["lftp", "-u", user_part, "-p", str(port), host,
           "-e", f"put {_ftp_quote(local_metadata_path)} -o {_ftp_quote(remote_metadata_path)}; quit"]
    result = sp.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        log.info("  ✅ song_metadata.json deployed to PS4")
    else:
        log.warning(f"  ⚠️  Failed to deploy song_metadata.json: {result.stderr}")

    # 6. Rebuild and deploy pack bundle if needed
    if pack_needs_rebuild and target_pack:
        log.info(f"  🔨 Rebuilding pack bundle for '{target_pack}' from original dump...")
        deploy_cfg = {'ps4': cfg_ps4, 'title': cfg_title, 'paths': cfg_paths,
                      'pack_bundle': config.get('pack_bundle', {}),
                      'pack_modes': config.get('pack_modes', {}),
                      'mass_deploy': config.get('mass_deploy', {})}

        deploy_pack_bundle(deploy_cfg, packs=[target_pack], enable_modes=None, target_slots=rebuild_slots)
        # Also deploy redirects again to pick up pack bundle changes.
        # NOTE (Exp 226): slots must NOT be scoped to rebuild_slots here —
        # rebuild_slots is the PACK-MODE target list (empty when clearing the
        # last custom song in a pack), and passing it as the redirect scope
        # made _ensure_mass_song_redirects treat it as "empty scope" and wipe
        # EVERY song redirect from every pack (44 redirects destroyed).
        # Per-song redirects are managed by earlier steps; every existing
        # custom song must keep its redirect.
        # Scope the re-ensure to exactly the song redirects that still exist
        # (after the surgical removal in step 2) — no additions, no wipes.
        # Reading the just-saved local file (step 2 wrote it) gives precisely
        # the user's deployed song set.
        current_slots = []
        try:
            _cd = _load_local_redirects(local_redirect_path).get('redirects', {})
            current_slots = [k[len('BeatmapLevelsData/'):] for k in _cd
                             if k.startswith('BeatmapLevelsData/')]
        except Exception:
            pass
        manage_redirect_config(
            config,
            target_name=None,
            generate=True,
            deploy=True,
            sync=False,
            enforce_local=False,
            packs=None,
            slots=current_slots if current_slots else None,
        )

    log.info(f"✅ Slot '{slot_name}' reverted to stock state")


# ============================================================================
# Main
# ============================================================================

def main():
    # Print pipeline version
    ver_path = os.path.join(PROJECT_ROOT, 'VERSION')
    if os.path.exists(ver_path):
        with open(ver_path) as f:
            ver = f.read().strip()
    else:
        ver = "unknown"
    print(f"🎵 OrBeats Pipeline {ver}")
    print(f"   Project: {PROJECT_ROOT}")
    print()

    parser = argparse.ArgumentParser(
        description="Full Custom Song Pipeline for PS4 Beat Saber",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline: WAV + beatmaps -> bundle -> deploy
  python3 full_custom_song_pipeline.py --song-dir ./my_song --target startmeup --deploy

  # Just build the bundle (no deploy):
  python3 full_custom_song_pipeline.py --song-dir ./my_song --target startmeup

  # Use pre-encoded FSB5 (skip audio conversion):
  python3 full_custom_song_pipeline.py --audio custom.fsb5 --song-dir ./my_song --target startmeup

  # Build & deploy plugin (release — no verbose logging on PS4):
  python3 full_custom_song_pipeline.py --song-dir ./my_song --target startmeup --deploy-plugin

  # Build & deploy plugin (debug — verbose PS4 logging for development):
  python3 full_custom_song_pipeline.py --song-dir ./my_song --target startmeup --deploy-plugin --debug-logging

  # Just build & deploy plugin (song-dir still required for config):
  python3 full_custom_song_pipeline.py --song-dir ./my_song --target startmeup --deploy-plugin --preserve-metadata --no-pad

  # Build song AND generate/update redirects.json:
  python3 full_custom_song_pipeline.py --song-dir ./my_song --target startmeup --generate-config

  # Build song, update redirects.json, deploy both bundle + config to PS4:
  python3 full_custom_song_pipeline.py --song-dir ./my_song --target startmeup --deploy --deploy-config

  # Sync redirect config from PS4, merge with current build, redeploy:
  python3 full_custom_song_pipeline.py --song-dir ./my_song --target startmeup --sync-config

  # Enforce local redirects.json as truth and deploy to PS4 (no merge):
  python3 full_custom_song_pipeline.py --enforce-config --deploy

  # Download a song from BeatSaver and deploy to PS4 in one command:
  python3 full_custom_song_pipeline.py --download-beat-saver-song 1d6c7c2 --target BadGuy --pcm16 --no-pad --convert-to-v3 --deploy --generate-config --deploy-config
        """
    )
    parser.add_argument('--song-dir', default=None,
                        help='Folder containing the custom song (WAV + .dat/.json beatmaps)')
    parser.add_argument('--audio', default=None,
                        help='Pre-encoded FSB5 file (optional: skips WAV->FSB5 conversion)')
    parser.add_argument('--config', default=DEFAULT_CONFIG_PATH,
                        help='Path to PS4 config JSON (default: ./ps4_config.json)')
    parser.add_argument('--target', default=None,
                        help='Target song name (default from config: startmeup)')
    parser.add_argument('--template', default=None,
                        help='Path to the target song template bundle (default from config)')
    parser.add_argument('--output', default=None,
                        help='Output bundle path (default from config)')
    parser.add_argument('--deploy', action='store_true',
                        help='Deploy to PS4 via FTP after building')
    parser.add_argument('--target-ip', default=None,
                        help='PS4 IP address for FTP deployment (overrides config)')
    parser.add_argument('--pad-fsb5', action='store_true',
                        help='Pad FSB5 to the original 12MB resource size. '
                             'DANGER: with PCM16 this TRUNCATES songs longer than the '
                             'slot (partial song). Default is NO padding (full audio). '
                             'Opposes the no-pad default.')
    parser.add_argument('--no-pad', action='store_true',
                        help='[default] Do not pad FSB5 to 12MB. This is now the default; '
                             'flag kept for backward compatibility. See --pad-fsb5.')
    parser.add_argument('--preserve-metadata', action='store_true',
                        help='Do NOT update AudioClip or audio.gz metadata (uses original values)')
    parser.add_argument('--ignore-non-standard-beatmaps', action='store_true',
                        help='Only match beatmap files containing "Standard" in name '
                             '(ignores 90Degree, OneSaber variants)')
    parser.add_argument('--enable-modes', type=str, default=None,
                        help='Comma-separated list of additional beatmap characteristics to enable '
                             '(e.g. "OneSaber,90Degree"). Makes the song playable in those '
                             'modes by cloning the Standard beatmaps. 360Degree is not supported '
                             'on PS4 and is ignored.')
    parser.add_argument('--disable-beatmap-mode-mapping', action='store_true',
                        help='Disable the beatmap mode mapping default (Standard-only bundle). '
                             'Mode mapping is now ON by default: auto-detect custom song beatmap '
                             'files and map them to game characteristic slots (OneSaber, NoArrows, '
                             '90Degree) using a fallback chain, and generate missing mode beatmaps '
                             'from Standard (see --skip-mode-generation).')
    parser.add_argument('--enable-beatmap-mode-mapping', action='store_true',
                        help='[default] Auto-detect custom song beatmap files and map them to game '
                             'characteristic slots (OneSaber, NoArrows, 90Degree). '
                             'This is now the default; flag kept for backward compatibility. '
                             'Use --disable-beatmap-mode-mapping to opt out.')
    parser.add_argument('--skip-mode-generation', action='store_true',
                        help='Do not generate missing mode-specific beatmaps (only enable the '
                             'mode sets in the bundle; modes keep Standard data). Mode mapping '
                             'itself stays on. Opposes the generation default.')
    parser.add_argument('--one-saber-min-gap', type=float, default=_ONE_SABER_MIN_GAP,
                        help='OneSaber generator: minimum beat gap between same-cell '
                             'arrowed notes (default: 0.25)')
    parser.add_argument('--rotation-cycle-beats', type=float, default=_ROTATION_CYCLE_BEATS,
                        help='90Degree generator: beats between single-lane rotation events '
                             '(default: 8.0, i.e. 2 measures at 4/4; each event moves one '
                             '15° lane within the ±45° arc)')
    parser.add_argument('--fallback-mode-map', action='append', default=None,
                        help='Override fallback chain for a mode slot. Format: SRC=DEST '
                             '(e.g. "90Degree=Standard" or "NoArrows=Standard"). '
                             'Can be used multiple times.')
    parser.add_argument('--vorbis', action='store_true',
                        help='Use Vorbis format (mode=15) for the FSB5 audio instead of PCM16')
    parser.add_argument('--hevag', action='store_true',
                        help='Use HEVAG format for the FSB5 audio instead of PCM16 '
                             '(legacy; Sony proprietary)')
    parser.add_argument('--pcm16', action='store_true',
                        help='[default] Use PCM16 format (codec=2) for the FSB5 audio (lossless). '
                             'This is now the default; flag kept for backward compatibility. '
                             'Use --hevag or --vorbis to opt out.')
    parser.add_argument('--deploy-plugin', action='store_true',
                        help='Build and deploy the GoldHEN plugin to PS4 (and ensure plugins.ini entry)')
    parser.add_argument('--skip-plugin-deployment', action='store_true',
                        help='Skip building + deploying the plugin even in --deploy-full. Use when the '
                             'PS4 plugin is intentionally pinned (e.g. testing a specific plugin build). '
                             'Default behavior: every --deploy-full builds the LATEST plugin source and '
                             'installs it, so source changes always reach the PS4.')
    parser.add_argument('--skip-song-preview-management', action='store_true',
                        help='Skip building/deploying song-previews variants this run (Exp 269c). For '
                             'BATCHES: every --deploy-full rebuilds previews for packs whose inputs '
                             'changed, which across N batch songs wastes N-1 rebuilds — pass this flag '
                             'on all batch commands EXCEPT THE LAST so previews regenerate once, at '
                             'the end. (Preview builds are also dirty-checked per pack now: a variant '
                             'is rebuilt only when its modes base, slot set, or any song bundle md5 / '
                             'preview-start changed — untouched packs are skipped in seconds.) The '
                             'variant already deployed on the PS4 keeps serving previews meanwhile.')
    parser.add_argument('--deploy-features', action='store_true',
                        help='Deploy the local features.json to the PS4 (runtime feature flags)')
    parser.add_argument('--debug-logging', action='store_true',
                        help='Build plugin with verbose logging (VERBOSE_LOG define). '
                             'Only meaningful with --deploy-plugin.')
    parser.add_argument('--no-convert-to-v3', action='store_true',
                        help='Disable V2->V3.2.0 beatmap conversion. Conversion is now ON by '
                             'default (only converts V2 beatmaps, V3 are untouched). '
                             'Opposes the convert-to-v3 default.')
    parser.add_argument('--convert-to-v3', action='store_true',
                        help='[default] Auto-convert V2 beatmaps (_notes/_time) to V3.2.0 format '
                             '(colorNotes/b). This is now the default; flag kept for backward '
                             'compatibility. Use --no-convert-to-v3 to opt out.')

    # Plugin toggle flags
    parser.add_argument('--enable-plugin', action='store_true',
                        help='Enable the OrBeats plugin on PS4 '
                             '(uncomment .prx entry in plugins.ini)')
    parser.add_argument('--disable-plugin', action='store_true',
                        help='Disable the OrBeats plugin on PS4 '
                             '(comment out .prx entry in plugins.ini — play original songs)')

    # Clear target song: revert a custom song slot back to stock
    parser.add_argument('--clear-target-song', default=None, metavar='SLOT',
                        help='Remove custom song override for the given slot (e.g. "AllTheGoodGirlsGoToHell"). '
                             'Removes the song bundle from AFR, removes its redirect, cleans up song_metadata.json. '
                             'The slot reverts to the original game song with its original beatmaps only.')

    # Redirect config management flags
    parser.add_argument('--generate-config', action='store_true',
                        help='Generate/update redirects.json with the current --target entry '
                             '(creates file if missing)')
    parser.add_argument('--deploy-config', action='store_true',
                        help='Deploy the local redirects.json to PS4 via FTP')
    parser.add_argument('--sync-config', action='store_true',
                        help='Download config from PS4, merge with current target, save, redeploy')
    parser.add_argument('--enforce-config', action='store_true',
                        help='Use only the local redirects.json as truth and deploy it to PS4')

    # Pack bundle + post-deploy validation flags (Exp 180 crash fix)
    parser.add_argument('--deploy-pack-bundle', action='store_true',
                        help='Deploy the patched pack bundle + patched catalog.json to the PS4 '
                             '(must be done before redirects.json references them)')
    parser.add_argument('--build-pack-modes', action='store_true',
                        help='Build the generalized pack_modes bundles + merged catalog locally '
                             '(no deploy). Only builds packs whose bundle is missing, unless '
                             '--force-pack-modes is given.')
    parser.add_argument('--force-pack-modes', action='store_true',
                        help='Rebuild ALL configured pack_modes bundles even if they already exist '
                             '(used with --build-pack-modes or --deploy-pack-modes)')
    parser.add_argument('--pack-modes-packs', default=None, metavar='PACKS',
                        help='Comma-separated subset of pack_modes.packs to build/deploy '
                             '(default: all configured packs)')
    parser.add_argument('--deploy-pack-modes', action='store_true',
                        help='Build-if-missing + deploy the generalized pack_modes bundles and '
                             'the shared merged catalog to the PS4')
    parser.add_argument('--deploy-mass-bundles', action='store_true',
                        help='Deploy all custom song bundles from mass_deploy.bundle_dir to the PS4')
    parser.add_argument('--verify-ps4', action='store_true',
                        help='Run post-deploy PS4 validation (redirects match, all targets exist, '
                             'pack bundle + catalog pair present, sizes match)')
    parser.add_argument('--no-verify-ps4', action='store_true',
                        help='Skip the automatic post-deploy PS4 validation that runs whenever '
                             'any --deploy option is used')

    # Full orchestration flag (self-contained end-to-end deploy)
    parser.add_argument('--deploy-full', action='store_true',
                        help='Complete end-to-end deployment: build song bundle with all modes, '
                             'build pack mode bundles + merged catalog (if configured), deploy '
                             'song bundle + pack bundles + catalog, regenerate redirects.json, '
                             'run post-deploy validation. All in one command. Works with '
                             '--download-beat-saver-song or --song-dir.')

    # BeatSaver song download
    parser.add_argument('--download-beat-saver-song', default=None, metavar='MAP_ID',
                        help='Download a song from BeatSaver by map key (e.g. "1d6c7c2") '
                             'and run the full pipeline. Requires --target to specify the PS4 slot.')
    parser.add_argument('--beatsaver-api-base', default=None,
                        help='Override BeatSaver API base URL (default: https://api.beatsaver.com). '
                             'Useful for testing against a mirror or local server.')

    # Song metadata override for BeatmapLevelSO injection into CAB bundle
    parser.add_argument('--song-name', default=None,
                        help='Override song display name (default: extracted from Info.dat or BeatSaver)')
    parser.add_argument('--artist', default=None,
                        help='Override artist/song-author name (default: extracted from Info.dat or BeatSaver)')

    # Feature flags
    parser.add_argument('--set-feature', action='append', default=None,
                        help='Set a feature flag (format: feature_name=true/false). '
                             'Can be used multiple times. Flags are written to features.json '
                             'on PS4 at /data/GoldHEN/AFR/CUSA12878/features.json.')
    parser.add_argument('--features-only', action='store_true',
                        help='Apply feature flag changes (--set-feature) and deploy features.json '
                             'to PS4, then exit. No song processing, no plugin deploy. '
                             'Useful to toggle a runtime feature flag on the PS4 without '
                             'reprocessing a song or rebuilding the plugin.')
    # ── Game-data extraction management (M12, Exp 280) ────────────────────
    parser.add_argument('--request-game-data', action='store_true',
                        help='Write the game-data extraction manifest (game_data_requests.txt) '
                             'to the PS4, then exit. Requires the plugin flag '
                             'enable_game_data_extractor; the extraction happens on the '
                             'next boot of the game. Combine with --game-data-packs and/or '
                             '--game-data-slots to scope what is extracted (per-slot '
                             'templates + per-pack bundles + catalog.json).')
    parser.add_argument('--pull-game-data', action='store_true',
                        help='Mirror the console game_data/ (the extractor output) into the '
                             'local cache (paths.game_data_dir, default ./game_data), then '
                             'exit. Resumable (identical files skip). Point '
                             'paths.game_dump_dir at the cache afterwards — it is a '
                             'drop-in replacement for the dump.')
    parser.add_argument('--game-data-packs', default=None,
                        help='Comma-separated pack ids for --request-game-data '
                             '(e.g. lizzo,billieeilish) — requests every slot template of '
                             'those packs + their pack bundles.')
    parser.add_argument('--game-data-slots', default=None,
                        help='Comma-separated slot ids for --request-game-data '
                             '(e.g. 2BeLoved,AboutDamnTime) — requests those slots + '
                             'their packs bundles + catalog.')
    parser.add_argument('--metadata-only', action='store_true',
                        help='Update and/or deploy song_metadata.json to the PS4, then exit. '
                             'No song processing, no plugin deploy, no redirects. '
                             'Requires --song-name/--artist (add or update an entry) or '
                             '--deploy (deploy the existing local file). Use --target to '
                             'specify which PS4 slot the metadata applies to. '
                             'Example: --metadata-only --target "...Baby One More Time" '
                             '--song-name "Take On Me" --artist "A-ha" --deploy')

    parser.add_argument('--additive-install', action='store_true',
                        help='Append independent custom entry; closed game; no stock slot or plugin rebuild.')
    args = parser.parse_args()
    if args.additive_install:
        from additive_companion import install
        if args.target or args.pad_fsb5 or args.enable_modes or args.song_name or args.artist:
            parser.error('Additive install uses original metadata, Standard maps and full PCM; no target slot/overrides/mode generation.')
        with open(args.config, encoding='utf8') as file:
            additive_config=json.load(file)
        if args.target_ip:additive_config['ps4']['ip']=args.target_ip
        try:
            result=install(additive_config,map_id=args.download_beat_saver_song or '',song_dir=args.song_dir or '')
        except ValueError as exc:
            print(f'[additive] Import refused: {exc}',file=sys.stderr,flush=True)
            raise SystemExit(2)
        print(json.dumps(result,indent=2),flush=True)
        return


    # --deploy-full implies all deployment flags for complete orchestration.
    # A fully self-contained deploy builds+deploys the plugin, ensures the
    # plugins.ini entry, deploys features.json, and (in the song path) deploys a
    # mutually-consistent set of song bundle + that song's pack-mode bundle +
    # matching catalog + redirects scoped to the requested single song.
    if args.deploy_full:
        args.deploy = True
        args.deploy_config = True
        args.generate_config = True
        args.deploy_pack_modes = True
        # Build + deploy the LATEST plugin source on every --deploy-full so
        # plugin changes always reach the PS4 (Exp 221). Opt out with
        # --skip-plugin-deployment to keep the PS4's current .prx pinned.
        args.deploy_plugin = not args.skip_plugin_deployment
        args.deploy_features = True     # deploy features.json
        args.no_verify_ps4 = False      # ensure validation runs

    # Load PS4 config first
    config = load_config(args.config)
    cfg_ps4 = config.get('ps4', {})
    cfg_title = config.get('title', {})
    cfg_paths = config.get('paths', {})

    # Auto-download from BeatSaver if requested. This MUST run BEFORE the
    # plugin-only / deploy-only / toggle early-exit guards below, otherwise a
    # `--deploy-full --download-beat-saver-song <id> --target <slot>` invocation
    # (which sets deploy_plugin=True) is mis-routed into "plugin-only mode"
    # because args.song_dir is still None at the guard, and the song is never
    # downloaded or processed (Exp 214 root-cause fix).
    if args.download_beat_saver_song and not args.song_dir:
        log.info("Downloading song from BeatSaver...")
        extracted_dir = download_beat_saver_song(args.download_beat_saver_song,
                                                  api_base=args.beatsaver_api_base)
        args.song_dir = extracted_dir
    elif args.download_beat_saver_song and args.song_dir:
        log.info(f"Using local song directory: {args.song_dir} (ignoring --download-beat-saver-song)")

    # Features-only mode: change feature flags and exit (no song, no plugin, no redirects)
    if args.features_only:
        if not args.set_feature:
            log.error("--features-only requires at least one --set-feature key=value")
            sys.exit(1)
        apply_feature_flags(args.set_feature, {'ps4': cfg_ps4, 'title': cfg_title, 'paths': cfg_paths})
        log.info("Feature flags applied and deployed (features-only mode)")
        sys.exit(0)

    # Metadata-only mode: update and/or deploy song_metadata.json and exit
    # (Exp 228): no song processing, no plugin deploy, no redirect changes —
    # the surgical path for fixing a deployed song's display metadata.
    if args.metadata_only:
        if not (args.song_name or args.artist or args.deploy):
            log.error("--metadata-only requires --song-name/--artist "
                      "(to add/update an entry) or --deploy (to ship the local file)")
            sys.exit(1)
        manage_song_metadata(
            {'ps4': cfg_ps4, 'title': cfg_title, 'paths': cfg_paths,
             'pack_bundle': config.get('pack_bundle', {}),
             'pack_modes': config.get('pack_modes', {}),
             'mass_deploy': config.get('mass_deploy', {})},
            song_name=args.song_name,
            artist=args.artist,
            target_name=args.target,
            deploy=args.deploy,
        )
        log.info("Song metadata updated and/or deployed (metadata-only mode)")
        sys.exit(0)

    # Plugin-only mode: deploy plugin and exit
    if args.deploy_plugin and not args.song_dir:
        prx_path = build_plugin(PROJECT_ROOT, debug=args.debug_logging)
        deploy_plugin(
            prx_path,
            {'ps4': cfg_ps4, 'title': cfg_title},
            debug=args.debug_logging
        )
        log.info("Plugin deployment complete (no song processed)")

        # Handle redirect config in plugin-only mode
        if args.generate_config or args.deploy_config or args.sync_config or args.enforce_config or args.deploy:
            manage_redirect_config(
                {'ps4': cfg_ps4, 'title': cfg_title, 'paths': cfg_paths},
                target_name=None,
                generate=args.generate_config,
                deploy=(args.deploy_config or args.sync_config or args.enforce_config),
                sync=args.sync_config,
                enforce_local=args.enforce_config,
            )

        # Handle feature flags in plugin-only mode
        if args.set_feature:
            apply_feature_flags(args.set_feature, {'ps4': cfg_ps4, 'title': cfg_title, 'paths': cfg_paths})

        sys.exit(0)

    # Deploy-only modes (no song processing): mass bundles, pack bundle, validation.
    if (args.deploy_mass_bundles or args.deploy_pack_bundle or args.deploy_pack_modes
            or args.build_pack_modes or args.verify_ps4) and not args.song_dir:
        deploy_cfg = {'ps4': cfg_ps4, 'title': cfg_title, 'paths': cfg_paths,
                      'pack_bundle': config.get('pack_bundle', {}),
                      'pack_modes': config.get('pack_modes', {}),
                      'mass_deploy': config.get('mass_deploy', {})}
        pack_modes_packs = None
        if args.pack_modes_packs:
            pack_modes_packs = [p.strip() for p in args.pack_modes_packs.split(',') if p.strip()]
        if args.build_pack_modes:
            _ensure_pack_mode_bundles(deploy_cfg, force=args.force_pack_modes,
                                      packs=pack_modes_packs,
                                      skip_previews=args.skip_song_preview_management)
        if args.deploy_mass_bundles:
            deploy_mass_bundles(deploy_cfg)
        if args.deploy_pack_modes:
            deploy_pack_modes(deploy_cfg, skip_previews=args.skip_song_preview_management)
        if args.deploy_pack_bundle:
            if pack_modes_packs:
                # Pre-build the requested subset so deploy_pack_bundle's build-if-missing
                # and the redirect generation only cover exactly these packs.
                _ensure_pack_mode_bundles(deploy_cfg, force=args.force_pack_modes,
                                          packs=pack_modes_packs,
                                          skip_previews=args.skip_song_preview_management)
            deploy_pack_bundle(deploy_cfg, skip_previews=args.skip_song_preview_management)
        # Exp 270a: a pack deploy MUST also refresh the pack redirect pair. The
        # redirect VALUES name the bundle variant (modes-only vs modes+previews)
        # derived from the CURRENT flag state — deploying bundles without
        # refreshing redirects leaves the live redirects pointing at the OLD
        # variant while the new catalog describes the NEW one → catalog/bundle
        # CRC mismatch → CE-34878-0 at boot (the exact landmine the release
        # validation caught: --deploy-pack-modes shipped variant bundles + a
        # variant catalog while the live redirects still named the modes
        # bundles). --deploy-full always runs manage_redirect_config, which is
        # why full deploys were safe; the deploy-only paths get the same
        # ensure here.
        if args.deploy_pack_modes or args.deploy_pack_bundle:
            manage_redirect_config(
                deploy_cfg,
                target_name=None,
                generate=True,
                deploy=True,
            )
        if args.generate_config or args.deploy_config or args.sync_config or args.enforce_config or args.deploy:
            manage_redirect_config(
                deploy_cfg,
                target_name=None,
                generate=(args.generate_config or args.deploy_config or args.sync_config or args.deploy),
                deploy=(args.deploy_config or args.sync_config or args.enforce_config),
                sync=args.sync_config,
                enforce_local=args.enforce_config,
            )
        if args.verify_ps4 or (args.deploy or args.deploy_config or args.sync_config or args.enforce_config):
            if not args.no_verify_ps4:
                verify_ps4_deployment(deploy_cfg)
        sys.exit(0)

    # Game-data extraction management (M12): standalone modes before the
    # song-processing requirement (mirror the --features-only pattern).
    if args.request_game_data:
        packs = ([p.strip() for p in args.game_data_packs.split(',') if p.strip()]
                 if args.game_data_packs else None)
        slots = ([s.strip() for s in args.game_data_slots.split(',') if s.strip()]
                 if args.game_data_slots else None)
        request_game_data(config, packs=packs, slots=slots)
        sys.exit(0)
    if args.pull_game_data:
        pull_game_data(config)
        sys.exit(0)

    # Plugin toggle mode: enable/disable without processing any song
    if args.enable_plugin and not args.disable_plugin:
        enable_plugin(config, debug=args.debug_logging)
        log.info("Plugin enabled. Restart the game or press PS+Triangle to reload plugins.")
        sys.exit(0)
    if args.disable_plugin:
        disable_plugin(config)
        log.info("Plugin disabled. Restart the game or press PS+Triangle to reload plugins.")
        sys.exit(0)

    # Clear target song: revert a custom song slot back to stock
    if args.clear_target_song:
        if not args.song_dir:
            # Allow running without --song-dir for clear operation
            pass
        clear_target_song(config, args.clear_target_song)
        sys.exit(0)

    # --song-dir is required for song processing
    if not args.song_dir:
        parser.error('--song-dir is required (or use --deploy-plugin to deploy plugin only)')
    cfg_pipe = config.get('pipeline', {})

    if args.target is None:
        args.target = cfg_pipe.get('default_target', 'startmeup')
    if args.template is None:
        game_dump = cfg_paths.get('game_dump_dir', '/workspace/ps4_dump/CUSA12878-patch')
        tmpl_dir = cfg_paths.get('template_dir', 'Media/StreamingAssets/BeatmapLevelsData')
        args.template = f"{game_dump}/{tmpl_dir}/{args.target}"
    if args.output is None:
        out_dir = cfg_paths.get('output_dir', '/workspace/orbeats/custom_songs')
        args.output = f"{out_dir}/{args.target}_custom.bundle"
    if args.target_ip is None:
        args.target_ip = cfg_ps4.get('ip', '192.168.100.117')
    # Override config IP with --target-ip if explicitly provided
    cfg_ps4['ip'] = args.target_ip

    if not os.path.isdir(args.song_dir):
        log.error(f"Song directory not found: {args.song_dir}")
        sys.exit(1)

    # Pre-load song metadata from Info.dat (used in Step 6.5 and beatmap counting)
    song_name = os.path.basename(args.song_dir)
    song_artist = ""
    bpm = 120.0
    note_count_standard = 0
    # BeatSaver uses lowercase info.dat; custom songs use uppercase Info.dat
    info_dat_path = os.path.join(args.song_dir, "Info.dat")
    if not os.path.isfile(info_dat_path):
        info_dat_path = os.path.join(args.song_dir, "info.dat")
    if os.path.isfile(info_dat_path):
        with open(info_dat_path) as f:
            info = json.load(f)
        # Exp 228: format-aware read (V4 maps use song.title/author + audio.bpm)
        v4_name, v4_artist = _read_info_song_metadata(info)
        song_name = v4_name or song_name
        song_artist = v4_artist or song_artist
        v4_bpm = _read_info_bpm_from_dict(info)
        bpm = v4_bpm if v4_bpm is not None else bpm

    # -----------------------------------------------------------------------
    # Step 0: Audio conversion (WAV -> FSB5)
    # -----------------------------------------------------------------------
    actual_sample_rate = SAMPLE_RATE
    if args.audio:
        log.info(f"Using pre-encoded FSB5: {args.audio}")
        with open(args.audio, 'rb') as f:
            fsb5_bytes = f.read()
        if fsb5_bytes[:4] != b'FSB5':
            log.error("File does not start with FSB5 magic!")
            sys.exit(1)
        # Extract duration from sample descriptor (works for all codecs)
        sd_raw = struct.unpack_from('<Q', fsb5_bytes, 60)[0]
        total_frames = (sd_raw >> 34) & ((1 << 30) - 1)
        # Try to get sample rate from FREQUENCY metadata chunk (offset 77)
        freq = struct.unpack_from('<I', fsb5_bytes, 77)[0]
        actual_sample_rate = freq if 8000 < freq < 192000 else SAMPLE_RATE
        duration = total_frames / float(actual_sample_rate) if actual_sample_rate > 0 else 0
    else:
        log.info("Searching for audio file in song directory (.wav, .ogg, ...)...")
        audio_files = [f for f in os.listdir(args.song_dir)
                       if f.endswith(('.wav', '.ogg', '.flac', '.mp3', '.aiff', '.egg'))]
        if not audio_files:
            log.error(f"No audio files found in {args.song_dir}")
            sys.exit(1)

        audio_path = os.path.join(args.song_dir, audio_files[0])
        # Get sample rate via soundfile before full conversion
        info = sf.info(audio_path)

        # -------------------------------------------------------------------
        # Step 0b: Detect & handle lapped-up audio
        # -------------------------------------------------------------------
        lap_info = detect_lapped(args.song_dir, info.duration)
        if lap_info['is_lapped']:
            audio_path = lap_audio(audio_path, lap_info)
            info = sf.info(audio_path)

        codec = resolve_audio_codec(hevag=args.hevag, vorbis=args.vorbis)
        # Default = no padding (full song audio). --pad-fsb5 restores 12MB truncation.
        pad_to = resolve_pad_to_size(pad_fsb5=args.pad_fsb5)

        if codec == 'vorbis':
            log.info("Using VORBIS format (mode=15) for FSB5")
            actual_sample_rate = min(info.samplerate, 44100)
            fsb5_bytes = build_vorbis_fsb5(audio_path,
                                            clip_seconds=30,
                                            pad_to_size=pad_to)
            # Get PCM frame count from FSB5 sample descriptor
            sd_raw = struct.unpack_from('<Q', fsb5_bytes, 60)[0]
            total_frames = (sd_raw >> 34) & ((1 << 30) - 1)
            duration = total_frames / float(actual_sample_rate) if actual_sample_rate > 0 else 0
            log.info(f"  Vorbis FSB5: {len(fsb5_bytes)} bytes, {duration:.1f}s")
        elif codec == 'hevag':
            log.info("Using HEVAG format for FSB5 (legacy)")
            actual_sample_rate = info.samplerate
            fsb5_bytes = audio_to_fsb5(audio_path, pad_to_size=pad_to)
            # Get data_size from FSB5 header (before padding)
            ds = struct.unpack_from('<I', fsb5_bytes[16:], 4)[0]
            duration = (ds / (16 * 2)) * 28 / float(actual_sample_rate)
        else:  # 'pcm16' (default)
            log.info("Using PCM16 format (codec=2) for FSB5 (lossless)")
            actual_sample_rate = min(info.samplerate, 44100)
            fsb5_bytes = build_pcm16_fsb5(audio_path, pad_to_size=pad_to)
            # Get frame count from FSB5 sample descriptor
            sd_raw = struct.unpack_from('<Q', fsb5_bytes, 60)[0]
            total_frames = (sd_raw >> 34) & ((1 << 30) - 1)
            duration = total_frames / float(actual_sample_rate) if actual_sample_rate > 0 else 0
            log.info(f"  PCM16 FSB5: {len(fsb5_bytes)} bytes, {duration:.1f}s")

    # -----------------------------------------------------------------------
    # Step 1: Load template bundle
    # -----------------------------------------------------------------------
    if not os.path.isfile(args.template):
        log.error(f"Template bundle not found: {args.template}")
        sys.exit(1)

    bf, cab, cab_key, resource_key = load_target_bundle(args.template)
    log.info(f"Target: {args.target}")

    # -----------------------------------------------------------------------
    # Step 2: Replace .resource
    # -----------------------------------------------------------------------
    replace_resource(bf, fsb5_bytes, resource_key)

    if args.preserve_metadata:
        log.info("  --preserve-metadata: Skipping AudioClip and audio.gz updates")
    else:
        # -----------------------------------------------------------------------
        # Step 3: Update AudioClip
        # -----------------------------------------------------------------------
        update_audioclip(cab, fsb5_bytes, duration, actual_sample_rate)

        # -----------------------------------------------------------------------
        # Step 4: Update audio.gz (with correct BPM region data)
        # -----------------------------------------------------------------------
        sample_count = int(duration * actual_sample_rate)
        bpm_regions = load_bpm_regions(args.song_dir, sample_count)
        update_audio_gz(cab, duration, actual_sample_rate, bpm_regions)

    # -----------------------------------------------------------------------
    # Step 5a: Beatmap mode mapping — detect modes and generate missing
    # mode-specific beatmaps BEFORE beatmap replacement, so the generated
    # files are available to the bundle build (Step 5) and the mode sets
    # added in Step 6a. Generation is the default behavior whenever
    # --enable-beatmap-mode-mapping is enabled.
    # -----------------------------------------------------------------------
    mode_map_enabled = False
    mode_map_detected = {}
    mode_map_enabled_modes = ["Standard"]
    generated = []

    # Step 5a-0: Fill missing Standard difficulties FIRST (Exp 218). Maps that
    # provide fewer than 5 diffs would otherwise leave the STOCK beatmap in the
    # unreplaced bundle slots — stock timing over custom audio = "notes wayyy
    # too late / BPM too slow". Clones the map's closest difficulty so every
    # slot gets content on the custom song's own beat grid.
    filled = fill_missing_standard_difficulties(args.song_dir)
    if filled:
        log.info(f"  Filled missing Standard difficulties: {filled}")

    if resolve_mode_mapping(disable_beatmap_mode_mapping=args.disable_beatmap_mode_mapping):
        log.info("  Beatmap mode mapping enabled (default) — auto-detecting modes...")
        mode_map_detected = detect_song_modes(args.song_dir)
        log.info(f"  Detected modes: {mode_map_detected}")
        mode_map_enabled_modes = build_mode_mapping(mode_map_detected, args.fallback_mode_map)
        log.info(f"  Modes to enable: {mode_map_enabled_modes}")
        mode_map_enabled = True

        if args.skip_mode_generation:
            log.info("  --skip-mode-generation: not generating missing mode beatmaps")
        else:
            generated = generate_missing_mode_beatmaps(
                args.song_dir,
                mode_map_detected,
                mode_map_enabled_modes,
                bpm=bpm,
                min_gap=args.one_saber_min_gap,
                cycle_beats=args.rotation_cycle_beats,
            )
            log.info(f"  Generated missing mode beatmaps: {generated}")

    # -----------------------------------------------------------------------
    # Step 5: Replace beatmaps
    # -----------------------------------------------------------------------
    replaced = replace_beatmaps(cab, args.song_dir,
                                  ignore_non_standard=args.ignore_non_standard_beatmaps,
                                  auto_convert=resolve_convert_to_v3(args.no_convert_to_v3))
    log.info(f"Beatmaps replaced: {replaced}/5")

    # Count notes from Standard beatmaps for metadata
    for diff_file in ['Hard.dat', 'Normal.dat', 'Easy.dat', 'Expert.dat', 'ExpertPlus.dat',
                       'HardStandard.dat', 'NormalStandard.dat', 'EasyStandard.dat',
                       'ExpertStandard.dat', 'ExpertPlusStandard.dat']:
        diff_path = os.path.join(args.song_dir, diff_file)
        if os.path.isfile(diff_path):
            try:
                with open(diff_path) as f:
                    bm = json.load(f)
                note_count_standard += len(bm.get('notes', []))
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Step 6: Add mode characteristics (OneSaber, 90Degree, etc.)
    # -----------------------------------------------------------------------
    enable_modes = args.enable_modes.split(',') if args.enable_modes else None
    if enable_modes:
        # Filter out unsupported 360Degree (PS4 camera cannot track full rotation)
        valid_modes = [m.strip() for m in enable_modes if m.strip()]
        filtered = [m for m in valid_modes if m not in ("360Degree", "360")]
        if filtered != valid_modes:
            log.info("  Removed 360Degree from --enable-modes (unsupported on PS4)")
        add_mode_characteristics(cab, filtered, song_dir=args.song_dir,
                                 generated_files=generated or None, bpm=bpm,
                                 target_name=args.target)

    # -----------------------------------------------------------------------
    # Step 6a: Apply beatmap mode mapping to the BeatmapLevel
    # -----------------------------------------------------------------------
    if mode_map_enabled:
        mode_count = apply_mode_mapping(cab, mode_map_enabled_modes,
                                         song_dir=args.song_dir,
                                         generated_files=generated or None,
                                         bpm=bpm,
                                         target_name=args.target)
        log.info(f"  Mode sets added: {mode_count}")

    # -----------------------------------------------------------------------
    # Step 6.5: Inject BeatmapLevelSO metadata for song menu display
    # -----------------------------------------------------------------------
    # Resolve song name and artist — from CLI args, Info.dat, or BeatSaver
    # Re-read Info.dat after download (was loaded before song_dir was set)
    info_dat_path = os.path.join(args.song_dir, "Info.dat")
    if not os.path.isfile(info_dat_path):
        info_dat_path = os.path.join(args.song_dir, "info.dat")
    if os.path.isfile(info_dat_path):
        with open(info_dat_path) as f:
            info = json.load(f)
        # Exp 228: format-aware read (V4 maps use song.title/author + audio.bpm)
        v4_name, v4_artist = _read_info_song_metadata(info)
        song_name = v4_name or song_name
        song_artist = v4_artist or song_artist
        v4_bpm = _read_info_bpm_from_dict(info)
        bpm = v4_bpm if v4_bpm is not None else bpm
    custom_name = args.song_name or song_name
    custom_artist = args.artist or song_artist

    # BeatmapLevelSO injection (experimental — needs PS4 testing)
    inject_level_so = True  # always try to inject; game should just ignore unknown SOs
    if inject_level_so:
        note_data = b''  # empty diff data — the preview array will use Standard's data
        inject_beatmap_level_so(
            cab,
            song_name=custom_name or song_name,
            song_artist=custom_artist or song_artist,
            duration_seconds=duration,
            bpm=bpm,
            note_count_standard=note_count_standard,
            note_count_diff_data=note_data,
        )

    # -----------------------------------------------------------------------
    # Step 7: Save bundle
    # -----------------------------------------------------------------------
    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    save_bundle(bf, args.output)

    # -----------------------------------------------------------------------
    # Step 7: Deploy bundle to PS4
    # -----------------------------------------------------------------------
    deploy_cfg = {'ps4': cfg_ps4, 'title': cfg_title, 'paths': cfg_paths,
                  'pack_bundle': config.get('pack_bundle', {}),
                  'pack_modes': config.get('pack_modes', {}),
                  'mass_deploy': config.get('mass_deploy', {})}
    if args.deploy:
        deploy_to_ps4(args.output, args.target, config)

    # -----------------------------------------------------------------------
    # Step 8: Build & deploy plugin to PS4
    # -----------------------------------------------------------------------
    if args.deploy_plugin:
        prx_path = build_plugin(PROJECT_ROOT, debug=args.debug_logging)
        deploy_plugin(prx_path, config, debug=args.debug_logging)

    # -----------------------------------------------------------------------
    # Step 9a: Deploy the patched pack bundles + catalogs (single pack + pack_modes)
    # whenever anything is being deployed. This runs BEFORE redirects.json is
    # generated so that the pack_modes redirects (which are only emitted for packs
    # whose patched bundles exist locally) are picked up, and so the redirected
    # files are already on the PS4 when the game boots (Exp 180 crash rule).
    # -----------------------------------------------------------------------
    should_generate = args.generate_config or args.deploy_config or args.sync_config or args.deploy
    should_deploy = args.deploy_config or args.sync_config or args.enforce_config or args.deploy

    # Single-song deploy scoping: resolve which pack the requested target slot
    # belongs to, and scope the pack-mode bundle deploy + catalog + redirects to
    # exactly that pack. This keeps a `--deploy-full` single-song install surgical
    # — it deploys the target song + its music pack, while preserving existing
    # custom songs in the same pack. Full-fleet behavior (all packs) is preserved
    # when no target song is being processed.
    deploy_packs = None
    deploy_slots = None
    deploy_enable_modes = None
    if args.target:
        target_pack = _resolve_target_pack(config, args.target)
        if target_pack:
            deploy_packs = [target_pack]
            log.info(f"ℹ️  Single-song deploy: scoping to pack '{target_pack}' for target '{args.target}'")

        # For scoped deployment, we need to include ALL custom songs from ALL packs
        # so their redirects and pack bundle modifications are preserved.
        # Download current redirects.json from PS4 to find ALL existing custom songs.
        deploy_slots = [args.target.split('/')[-1]]
        deploy_packs = [target_pack] if target_pack else None
        # Download current redirects.json from PS4 to find ALL existing custom songs
        ps4_cfg = config.get('ps4', {})
        cfg_title = config.get('title', {})
        cfg_paths = config.get('paths', {})
        host = ps4_cfg.get('ip', '192.168.100.117')
        port = ps4_cfg.get('ftp_port', 2121)
        user = ps4_cfg.get('ftp_user', 'anonymous')
        password = ps4_cfg.get('ftp_password', '')
        afr_base = cfg_paths.get('afr_base', '/data/GoldHEN/AFR')
        title_id = cfg_title.get('id', 'CUSA12878')
        remote_redirect_path = f"{afr_base}/{title_id}/redirects.json"

        import subprocess as sp
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            local_redirect_path = os.path.join(tmpdir, "redirects.json")
            user_part = f"{user},{password}" if password else f"{user},"
            cmd = ["lftp", "-u", user_part, "-p", str(port), host,
                   "-e", f"get {_ftp_quote(remote_redirect_path)} -o {_ftp_quote(local_redirect_path)}; quit"]
            result = sp.run(cmd, capture_output=True, text=True, timeout=30)
            # Exp 246: a failed PS4 read must ABORT the deploy, never silently
            # fall back to "just the new target". The old fallback turned
            # "couldn't read state" into "wipe every other song's redirect"
            # (READ-FAILED rendered as empty-truth — the Exp 237/239/240
            # lesson, violated in the pipeline itself). The 10:34 deploy wiped
            # 46 of 47 song redirects this way.
            # Exp 281c: ABSENT is not FAILED. A decisive 550 (the file does
            # not exist) is the clean-slate state: a fresh console has NO
            # customs to preserve, so the scope is exactly the target song +
            # its pack. Only a genuine read failure aborts.
            ps4_redirects = None
            if result.returncode == 0 and os.path.exists(local_redirect_path):
                try:
                    # Banner-proof extraction (lftp-ftp-pitfalls #1): banners on
                    # slow links contaminate raw streams; slice first-{ to last-}.
                    raw = open(local_redirect_path, encoding='utf-8', errors='replace').read()
                    start = raw.find('{')
                    end = raw.rfind('}')
                    ps4_redirects = json.loads(raw[start:end + 1]).get('redirects', {})
                except Exception:
                    ps4_redirects = None
            elif _ps4_output_looks_absent(
                     (getattr(result, "stdout", "") or "")
                     + (getattr(result, "stderr", "") or "")):
                ps4_redirects = {}
                log.info("  ℹ️  No redirects.json on the PS4 (clean console) — "
                         "scoping to the target song + its pack (nothing else "
                         "exists to preserve)")
            if ps4_redirects is None:
                log.error("❌ Could not read the PS4's redirects.json while scoping "
                          "this single-song deploy. Refusing to continue: without "
                          "the live state, preserving your existing custom songs "
                          "cannot be guaranteed. Check the PS4 connection "
                          "(GoldHEN FTP) and re-run the deploy.")
                sys.exit(1)
            try:
                # Find ALL custom songs (from any pack) and their packs
                other_packs = set()
                for key in ps4_redirects:
                    if key.startswith('BeatmapLevelsData/'):
                        slot = key[len('BeatmapLevelsData/'):]
                        if slot not in deploy_slots:
                            deploy_slots.append(slot)
                        # Also track which pack this slot belongs to
                        other_pack = _resolve_target_pack(config, slot)
                        if other_pack and other_pack not in (deploy_packs or []):
                            other_packs.add(other_pack)
                # Include all packs that have existing custom songs
                if other_packs:
                    if deploy_packs is None:
                        deploy_packs = []
                    for p in other_packs:
                        if p not in deploy_packs:
                            deploy_packs.append(p)
                    log.info(f"  Preserving existing packs with custom songs: {', '.join(other_packs)}")
                if len(deploy_slots) > 1:
                    log.info(f"  Preserving existing custom songs: {', '.join([s for s in deploy_slots if s != args.target.split('/')[-1]])}")
            except Exception as e:
                # Exp 246: the PS4 read succeeded but the merge failed —
                # same rule as above: ABORT, never fall back to a scope
                # that would drop other songs' redirects.
                log.error(f"❌ Failed to process the PS4's redirects.json "
                          f"while scoping this deploy ({e}). Refusing to "
                          f"continue — your existing custom songs cannot "
                          f"be safely preserved. Fix the issue and re-run.")
                sys.exit(1)

        # Determine which modes to enable for this pack bundle.
        # We only want to add extra modes for the custom song(s) being deployed,
        # not for the stock songs that remain unmodified. This prevents crashes
        # when selecting an unmodified song and trying to play a non-Standard mode.
        # The pack bundle is patched to include extra mode sets ONLY for the
        # custom songs that have been deployed. The plugin's feature flag
        # enable_beatmap_mode_mapping gates whether these mode sets are visible.
        if mode_map_enabled:
            # Use the modes we detected/generated for this specific custom song
            deploy_enable_modes = [m for m in mode_map_enabled_modes if m != "Standard"]
            log.info(f"  Pack bundle will enable extra modes for custom songs: {deploy_enable_modes}")

        # Exp 283d: register the target's song metadata LOCALLY BEFORE the
        # pack/preview pass. build_preview_map gates slots on the local
        # song_metadata.json, and Step 11 (the metadata step) runs at the
        # END of the deploy — so the preview pass treated the JUST-DEPLOYED
        # slot as "not custom" and baked NO preview for it. Every deploy
        # baked the PREVIOUS deploys' previews, never its own (the user's
        # field report: Open Road's preview appeared only after the NEXT
        # deploy ran; the theme song on StartMeUp kept the stock preview).
        # The local write is idempotent — Step 11 still performs the upload
        # (and its own idempotent local write).
        if (args.song_name or args.artist or args.deploy) and should_deploy:
            manage_song_metadata(
                config,
                song_name=args.song_name or custom_name,
                artist=args.artist or custom_artist,
                target_name=args.target,
                deploy=False,
            )

    if should_deploy:
        deploy_pack_bundle(deploy_cfg, packs=deploy_packs, enable_modes=deploy_enable_modes, target_slots=deploy_slots, skip_previews=args.skip_song_preview_management)

    # -----------------------------------------------------------------------
    # Step 9: Manage redirect config (redirects.json)
    # -----------------------------------------------------------------------
    # Auto-generate and auto-deploy config when deploying bundles
    if should_generate or should_deploy or args.sync_config or args.enforce_config:
        manage_redirect_config(
            config,
            target_name=args.target,
            generate=should_generate,
            deploy=should_deploy,
            sync=args.sync_config,
            enforce_local=args.enforce_config,
            packs=deploy_packs,
            slots=deploy_slots,
        )

    # Step 9c: Post-deploy validation (self-validating pipeline, Exp 180).
    # Runs automatically whenever any --deploy option was used, unless
    # --no-verify-ps4 is passed. Reports PASS/FAIL for every check.
    # A FAILED validation ABORTS the pipeline with a non-zero exit (Exp 225):
    # the console previously printed "⚠️ FAILED" but continued to "Pipeline
    # complete!" and exit 0 — the example scripts' `if [ $? -ne 0 ]` guards
    # never fired, and a CRC-crash-prone state (missing catalog) shipped to
    # the PS4 with a green-looking log.
    deploy_verified = True
    if should_deploy and not args.no_verify_ps4:
        deploy_verified = verify_ps4_deployment(deploy_cfg, packs=deploy_packs)
    elif args.verify_ps4:
        deploy_verified = verify_ps4_deployment(deploy_cfg, packs=deploy_packs)
    if not deploy_verified and should_deploy:
        log.error("❌ Post-deploy validation FAILED — the PS4 state is inconsistent "
                  "and the game may crash at boot (CE-34878-0). Fix the issues "
                  "above and re-run the deploy before launching the game.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 9d: --deploy-full note (handled by flags set at arg parse time)
    # -----------------------------------------------------------------------
    if args.deploy_full:
        log.info("✅ --deploy-full orchestration complete (flags: deploy, deploy-config, generate-config, deploy-pack-modes)")

    # -----------------------------------------------------------------------
    # Step 10: Feature flags
    # -----------------------------------------------------------------------
    if args.set_feature:
        apply_feature_flags(args.set_feature, config)
    elif args.deploy_features:
        # Deploy the local features.json (runtime feature flags) so the plugin
        # picks up the correct feature set. _deploy_features_to_ps4 merges
        # DEFAULT_FEATURES into the local file first (materializing missing
        # keys) and creates it when absent — a deploy always ships a complete
        # flag set (Exp 221 fix).
        _deploy_features_to_ps4(config)
        log.info("  ✅ features.json deployed to PS4")

    # -----------------------------------------------------------------------
    # Step 11: Song metadata (song_metadata.json)
    # -----------------------------------------------------------------------
    if args.song_name or args.artist or args.deploy:
        manage_song_metadata(
            config,
            song_name=args.song_name or custom_name,
            artist=args.artist or custom_artist,
            target_name=args.target,
            deploy=args.deploy,
        )

    log.info("Pipeline complete!")
    log.info(f"  Bundle: {args.output}")
    log.info(f"  Size: {os.path.getsize(args.output)} bytes")
    log.info(f"  Audio: {len(fsb5_bytes)} bytes, {duration:.1f}s")
    log.info(f"  Beatmaps: {replaced}/5 replaced")


if __name__ == "__main__":
    main()
