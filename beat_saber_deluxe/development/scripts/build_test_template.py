#!/usr/bin/env python3
"""Build the minimal test template bundle (no audio).

The template bundle is used by TestModeBeatmapInjection to exercise
add_mode_characteristics() against a real Unity CAB without shipping a
12 MB song bundle in the repo.

This script takes any per-song Beat Saber bundle (e.g. the deployed
startmeup_v3.bundle) and produces a ~3 KB template containing ONLY:

  - BeatmapLevel (class 114) with a single Standard characteristic set
  - 5 beatmap TextAssets (class 49) with minimal placeholder beatmap JSON
  - 1 lightshow TextAsset (class 49) with minimal placeholder JSON
  - BeatmapLevelDataSO MonoBehaviour (class 115, m_Script target)

All audio is stripped: AudioClip objects, the audio TextAsset, and the
external ``.resource`` file are removed; ``_audioClip``/``_audioDataAsset``
PPtrs are nulled. Mode sets beyond Standard are removed.

Usage:
    python3 development/scripts/build_test_template.py \
        <source.bundle> [output.bundle]

Example:
    python3 development/scripts/build_test_template.py \
        ../../startmeup_v3.bundle tests/test_data/template_standard.bundle
"""
import gzip
import io
import json
import sys
from pathlib import Path

from UnityPy import load
from UnityPy.files.ObjectReader import ObjectReader
from UnityPy.streams.EndianBinaryReader import EndianBinaryReader
from UnityPy.streams.EndianBinaryWriter import EndianBinaryWriter

MIN_BEATMAP = {
    "_version": "3.2.0",
    "bpmEvents": [{"b": 0, "m": 120.0}],
    "colorNotes": [], "bombs": [], "obstacles": [],
    "sliders": [], "rotationEvents": [],
}
MIN_LIGHTSHOW = {"_version": "3.2.0", "events": [], "lightshowEvents": []}

DEFAULT_SRC = "/workspace/startmeup_v3.bundle"
DEFAULT_DST = Path(__file__).resolve().parent.parent.parent / "tests" / "test_data" / "template_standard.bundle"


def _shrink_text_asset(cab, obj, new_gz_bytes):
    endian = '>' if cab.header.endian == '>' else '<'
    name = obj.read_typetree().get("m_Name", "asset")
    writer = EndianBinaryWriter(endian=endian)
    writer.write_aligned_string(name)
    writer.write_int(len(new_gz_bytes))
    writer.write(new_gz_bytes)
    writer.align_stream(4)
    raw_data = writer.bytes
    reader = EndianBinaryReader(raw_data, endian)

    text_asset_type = None
    text_asset_type_index = 0
    for i, t in enumerate(cab.types):
        if t.class_id == 49:
            text_asset_type = t
            text_asset_type_index = i
            break
    if text_asset_type is None:
        raise RuntimeError("CAB has no TextAsset (class 49) serialized type")

    new_obj = ObjectReader(
        assets_file=cab, reader=reader, path_id=obj.path_id,
        type_id=text_asset_type_index, serialized_type=text_asset_type,
        class_id=49, type=49, byte_start=0, byte_size=len(raw_data),
        is_destroyed=0, is_stripped=0, data=raw_data,
    )
    cab.objects[obj.path_id] = new_obj


def build(src: Path, dst: Path) -> int:
    env = load(str(src))
    bf = list(env.files.values())[0]
    cab = None
    for k, sub in bf.files.items():
        if hasattr(sub, "objects") and sub.objects:
            cab = sub
            break
    if cab is None:
        raise RuntimeError(f"No CAB with objects found in {src}")

    for pid, obj in list(cab.objects.items()):
        if obj.class_id != 49:
            continue
        nm = obj.read_typetree().get("m_Name", "")
        if "audio" in nm.lower():
            continue
        if "lightshow" in nm.lower():
            _shrink_text_asset(cab, obj, gzip.compress(json.dumps(MIN_LIGHTSHOW, separators=(',', ':')).encode()))
        else:
            _shrink_text_asset(cab, obj, gzip.compress(json.dumps(MIN_BEATMAP, separators=(',', ':')).encode()))

    # Collect pids referenced by the Standard set from the ORIGINAL typetree
    # (read_typetree after save_typetree returns stale data in some UnityPy
    # versions, so capture the keep-set before modifying anything).
    keep = set()
    for pid, obj in cab.objects.items():
        if obj.class_id == 114:
            tt = obj.read_typetree()
            keep.add(pid)
            keep.add(tt["m_Script"]["m_PathID"])
            for s in tt["_difficultyBeatmapSets"]:
                if s["_beatmapCharacteristicSerializedName"] != "Standard":
                    continue
                for e in s["_difficultyBeatmaps"]:
                    keep.add(e["_beatmapAsset"]["m_PathID"])
                    keep.add(e["_lightshowAsset"]["m_PathID"])

    # Strip the BeatmapLevel to Standard-only and null audio PPtrs
    for pid, obj in cab.objects.items():
        if obj.class_id == 114:
            tt = obj.read_typetree()
            tt["_audioClip"] = {"m_FileID": 0, "m_PathID": 0}
            tt["_audioDataAsset"] = {"m_FileID": 0, "m_PathID": 0}
            std = [s for s in tt["_difficultyBeatmapSets"]
                   if s["_beatmapCharacteristicSerializedName"] == "Standard"]
            tt["_difficultyBeatmapSets"] = std
            obj.save_typetree(tt)

    # Drop every object not referenced by the Standard-only BeatmapLevel:
    # audio objects, other-mode beatmap TextAssets, etc.
    remove = [pid for pid in cab.objects.keys() if pid not in keep]
    for pid in remove:
        del cab.objects[pid]

    for k in [k for k in bf.files.keys() if k.endswith(".resource")]:
        del bf.files[k]

    dst.parent.mkdir(parents=True, exist_ok=True)
    out = bf.save(packer="lz4")
    dst.write_bytes(out)
    print(f"Wrote minimal template ({len(out):,} B) -> {dst}")

    env2 = load(io.BytesIO(out))
    bf2 = list(env2.files.values())[0]
    cab2 = next(sub for sub in bf2.files.values() if hasattr(sub, "objects") and sub.objects)
    n_49 = sum(1 for o in cab2.objects.values() if o.class_id == 49)
    n_114 = sum(1 for o in cab2.objects.values() if o.class_id == 114)
    audio = [o for o in cab2.objects.values() if o.class_id in (83, 142)]
    print(f"Verified: objects={len(cab2.objects)} TextAssets={n_49} BeatmapLevels={n_114} audio_objs={len(audio)}")
    return 0


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SRC)
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DST
    sys.exit(build(src, dst))
