#!/usr/bin/env python3
"""Offline, opt-in Vorbis passthrough experiment; never connects to a console.

Retain source Ogg audio packets (NO additional lossy encode), but wrap them in a
new FSB5 with their OWN setup CRC and sample count. Never reuse a stock codebook,
seek table, sample header, padding target or clip duration. Unsupported source
profiles fail in this explicit probe; normal imports now use the proven wrapper
with a safe PCM fallback for unsupported audio.

Developer validation uses python-fsb5/libvorbis and UnityPy's existing FMOD
extractor; this is NOT a plan to distribute proprietary FMOD build tools.
Format reference: vgmstream d9875b1fff307e4759dfb85e49e3d5e6fb196f7c,
src/meta/fsb5.c and src/coding/vorbis_custom_utils_fsb.c.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json

# Reuse the production packet wrapper; FMOD remains a developer-only cross-check.
import sys
import tempfile
import zlib  # noqa: F401 -- historical developer test API
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from vorbis_audio import build_fsb, page_crc, parse_ogg, seek_table  # noqa: F401,E402

MAX_BYTES = 200_000_000
PROFILE = "vorbis-passthrough-preload-probe-v2"


def verify_audio(fsb, original, expected_frames, *, sample_rate=44100):
    import fmod_toolkit
    import numpy as np
    import soundfile as sf

    source, rate = sf.read(io.BytesIO(original), dtype="float32", always_2d=True)
    decoded = fmod_toolkit.raw_to_wav(fsb, "compressed-probe", 2, sample_rate, False)
    if len(decoded) != 1:
        raise ValueError("expected exactly one FMOD subsound")
    actual, rate2 = sf.read(io.BytesIO(next(iter(decoded.values()))), dtype="float32", always_2d=True)
    if rate != sample_rate or rate2 != rate or source.shape != actual.shape or actual.shape != (expected_frames, 2):
        raise ValueError("FMOD decoder changed audio rate/channels/sample count")
    # FMOD's decoded PCM16 clamps source Vorbis overshoots; don't misreport them
    # as new encoding loss. The existing FFmpeg->PCM path clamps them too.
    clipped = np.clip(source, -1, 32767 / 32768)
    error = actual - clipped
    maximum = float(np.max(np.abs(error)))
    if not np.isfinite(actual).all() or maximum > 4 / 32768:
        raise ValueError(f"independent FMOD audio roundtrip mismatch: {maximum}")
    # Exercise FMOD's compressed decoder random access, not just slicing a
    # successfully predecoded PCM buffer. No playback device or console access.
    from pyfmodex.flags import INIT_FLAGS, MODE
    from pyfmodex.structure_declarations import CREATESOUNDEXINFO

    system, lock = fmod_toolkit.get_pyfmodex_system_instance(2, INIT_FLAGS.NORMAL)
    checks = []
    with lock:
        sound = system.create_sound(
            fsb,
            MODE.OPENMEMORY | MODE.OPENONLY,
            exinfo=CREATESOUNDEXINFO(length=len(fsb)),
        )
        try:
            sub = sound.get_subsound(0)
            for start in (
                0,
                min(sample_rate + 37, expected_frames - 4096),
                expected_frames // 2,
                expected_frames - 4096,
                expected_frames // 3,
                0,
            ):
                sub.seek_data(start)
                raw, count = sub.read_data(4096 * 4)
                if count != 4096 * 4:
                    raise ValueError("FMOD seek returned truncated PCM")
                readback = np.frombuffer(raw[:count], dtype="<i2").reshape(-1, 2) / 32768
                difference = float(np.max(np.abs(readback - clipped[start : start + 4096])))
                if difference > 4 / 32768:
                    raise ValueError(f"FMOD compressed random-access mismatch at {start}: {difference}")
                checks.append({"sample": start, "max_error": difference})
        finally:
            sound.release()
    return {
        "decoded_frames": len(actual),
        "max_clipped_source_error": maximum,
        "compressed_seek_checks": checks,
        "rms_clipped_source_error": float(np.sqrt(np.mean(error**2))),
        "source_overrange_samples": int(np.count_nonzero(np.abs(source) > 1)),
        "source_peak": float(np.max(np.abs(source))),
        "packets_reencoded": False,
    }


def _renamed(value, old_id, new_id, old_cab, new_cab):
    if isinstance(value, str):
        return value.replace(old_id, new_id).replace(old_cab, new_cab)
    if isinstance(value, dict):
        return {k: _renamed(v, old_id, new_id, old_cab, new_cab) for k, v in value.items()}
    if isinstance(value, list):
        return [_renamed(v, old_id, new_id, old_cab, new_cab) for v in value]
    if isinstance(value, tuple):
        return tuple(_renamed(v, old_id, new_id, old_cab, new_cab) for v in value)
    return value


def prepare_candidate(pcm_candidate, audio, output, *, sample_rate=44100):
    import prepare_additive_bundle as pcm
    import UnityPy
    from UnityPy.files import BundleFile
    from UnityPy.streams import EndianBinaryReader

    source_folder, output = Path(pcm_candidate).resolve(), Path(output).resolve()
    audio = Path(audio).resolve()
    if output.exists() or output.is_relative_to(source_folder) or output.is_relative_to(audio.parent):
        raise ValueError("output must be new and outside source directories")
    manifest = pcm.validate(source_folder)
    original = audio.read_bytes()
    fsb, frames, crc = build_fsb(original, sample_rate=sample_rate)
    if abs(frames / sample_rate - manifest["pcm_frames"] / 44100) > 1 / 44100:
        raise ValueError("compressed and existing PCM clip sample counts disagree")
    verification = verify_audio(fsb, original, frames, sample_rate=sample_rate)
    profile = PROFILE if sample_rate == 44100 else "vorbis-passthrough-preload-48k-probe-v1"
    old_id, old_cab = manifest["level_id"], manifest["cab_name"]
    identity = hashlib.sha256((profile + old_id).encode() + original).hexdigest()
    new_id, new_cab = "bsd_additive_" + identity[:24], "CAB-" + identity[:32]
    env = UnityPy.load(str(source_folder / manifest["bundle"]["file"]))
    bundle = next(iter(env.files.values()))
    if not isinstance(bundle, BundleFile):
        raise ValueError("expected source UnityFS bundle")
    cab = bundle.files[old_cab]
    audio_pid = next(
        o.read_typetree()["_audioDataAsset"]["m_PathID"]
        for o in cab.objects.values()
        if o.class_id == 114 and "_audioDataAsset" in o.read_typetree()
    )
    for obj in cab.objects.values():
        tree = _renamed(obj.read_typetree(), old_id, new_id, old_cab, new_cab)
        if obj.class_id == 83:
            tree["m_Frequency"] = sample_rate
            tree["m_Length"] = frames / sample_rate
            tree["m_CompressionFormat"] = 1  # Unity Vorbis, not FSB's codec enum
            tree["m_Resource"]["m_Size"] = len(fsb)
        if obj.path_id == audio_pid and sample_rate != 44100:
            data = json.loads(gzip.decompress(tree["m_Script"].encode("utf-8", "surrogateescape")))
            data.update(
                songSampleCount=frames,
                songFrequency=sample_rate,
                bpmData=[{"si": 0, "ei": frames, "sb": 0.0, "eb": frames / sample_rate * manifest["bpm"] / 60}],
            )
            tree["m_Script"] = gzip.compress(pcm.canonical(data), mtime=0).decode("utf-8", "surrogateescape")
        obj.save_typetree(tree)
    bundle.files.pop(old_cab)
    bundle.files.pop(old_cab + ".resource")
    bundle.files[new_cab] = cab
    resource: Any = EndianBinaryReader(fsb)
    resource.flags = 0
    resource.BaseOffset = 0
    bundle.files[new_cab + ".resource"] = resource
    blob = bundle.save(packer="none")
    # Independently reopen the saved UnityFS (not merely the in-memory FSB).
    reopened = next(iter(UnityPy.load(blob).files.values()))
    if not isinstance(reopened, BundleFile):
        raise ValueError("expected saved UnityFS bundle")
    stored = reopened.files[new_cab + ".resource"].bytes
    if stored != fsb:
        raise ValueError("saved UnityFS changed FSB bytes")
    objects = [o for o in reopened.files[new_cab].objects.values()]
    clips = [o.read_typetree() for o in objects if o.class_id == 83]
    if len(clips) != 1 or clips[0]["m_CompressionFormat"] != 1 or clips[0]["m_LoadType"] != 0:
        raise ValueError("saved UnityFS lost Vorbis/decompress-on-load settings")
    if clips[0]["m_Frequency"] != sample_rate or abs(clips[0]["m_Length"] - frames / sample_rate) > 0.0001:
        raise ValueError("saved UnityFS sample-rate/length mismatch")
    audio_tree = reopened.files[new_cab].objects[audio_pid].read_typetree()
    audio_data = json.loads(gzip.decompress(audio_tree["m_Script"].encode("utf-8", "surrogateescape")))
    if (
        audio_data["songSampleCount"] != frames
        or audio_data["songFrequency"] != sample_rate
        or audio_data["bpmData"][0]["ei"] != frames
    ):
        raise ValueError("saved beatmap AudioData sample coordinates mismatch")
    manifest = _renamed(manifest, old_id, new_id, old_cab, new_cab)
    manifest.update(
        kind="orbeats_compressed_audio_probe",
        audio_codec="vorbis",
        audio_format=f"FSB5 Vorbis source packet passthrough stereo {sample_rate}",
        audio_load_settings="decompress-on-load, preload TRUE; PS4 playback NOT yet validated",
        reason="offline codec experiment; NOT accepted by the normal installer",
        song_name=(manifest["song_name"][:160] + " [Vorbis test]"),
    )
    if sample_rate != 44100:
        manifest["baseline_pcm_frames"] = manifest.pop("pcm_frames")
        manifest.update(
            audio_sample_rate=sample_rate,
            decoded_frames=frames,
            duration_seconds=frames / sample_rate,
            song_name=manifest["song_name"].replace("[Vorbis test]", "[48k Vorbis test]"),
        )
    manifest["bundle"] = {"file": new_id + ".bundle", "bytes": len(blob), "sha256": pcm.digest(blob)}
    report = {
        "profile": profile,
        "sample_rate": sample_rate,
        "setup_crc32": f"{crc:08x}",
        "pcm_bundle_bytes": json.loads((source_folder / "manifest.json").read_text())["bundle"]["bytes"],
        "compressed_bundle_bytes": len(blob),
        "original_ogg_bytes": len(original),
        "compressed_fsb_bytes": len(fsb),
        "verification": verification,
        "runtime_ready": False,
        "deployment_attempted": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vorbis-probe-", dir=output.parent) as tmp:
        stage = Path(tmp) / "output"
        stage.mkdir()
        (stage / manifest["bundle"]["file"]).write_bytes(blob)
        (stage / "manifest.json").write_bytes(pcm.canonical(manifest) + b"\n")
        (stage / "verification.json").write_bytes(pcm.canonical(report) + b"\n")
        stage.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experimental", action="store_true", required=True)
    parser.add_argument("--pcm-candidate", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-rate", type=int, choices=(44100, 48000), default=44100)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare_candidate(args.pcm_candidate, args.audio, args.output, sample_rate=args.sample_rate), indent=2
        )
    )


if __name__ == "__main__":
    main()
