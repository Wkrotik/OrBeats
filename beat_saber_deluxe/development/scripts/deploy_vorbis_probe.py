#!/usr/bin/env python3
"""Explicit developer-only compressed-audio deployment, never a normal import mode.

Rebuild and compare the offline candidate before connecting. Reuse the production
wire codec, closed-title checks, full readback, lock and manifest CAS/rollback.
Requires an existing canonical library (empty is fine); no legacy migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
import uuid
from ftplib import FTP, error_perm
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import additive_companion as core
import additive_library as lib
import probe_vorbis_audio as probe


def prepare_payload(pcm_candidate, audio, source, candidate, *, sample_rate=44100):
    """Bind media/source/PCM and deterministic compressed bytes before FTP."""
    pcm_candidate, audio, source, candidate = map(Path, (pcm_candidate, audio, source, candidate))
    pcm = core.helper("prepare_additive_bundle.py")
    media = core.helper("prepare_additive_media.py")
    with tempfile.TemporaryDirectory(prefix="orbeats-verified-vorbis-") as tmp:
        tmp = Path(tmp)
        normalized = tmp / "normalized"
        core.helper("import_v3_additive.py").import_song(source, normalized)
        expected = pcm.load_song(normalized)
        manifest = pcm.validate(pcm_candidate, expected)
        if expected["source_sha256"] != manifest["source_sha256"]:
            raise ValueError("PCM candidate and original source map disagree")
        probe.prepare_candidate(pcm_candidate, audio, tmp / "rebuilt", sample_rate=sample_rate)
        rebuilt = json.loads((tmp / "rebuilt/manifest.json").read_bytes())
        supplied = json.loads((candidate / "manifest.json").read_bytes())
        if supplied != rebuilt or supplied.get("kind") != "orbeats_compressed_audio_probe":
            raise ValueError("candidate is not the independently rebuilt experiment")
        name = rebuilt["bundle"]["file"]
        blob = (tmp / "rebuilt" / name).read_bytes()
        if (candidate / name).read_bytes() != blob:
            raise ValueError("compressed candidate bytes disagree with fresh verification")
        menu = tmp / "media"
        m = media.prepare(source, pcm_candidate / "manifest.json", menu)
        # PCM manifests describe the normalized WAV; bind the preview to the
        # actual original Vorbis input rather than comparing unlike encodings.
        if m["source_audio_sha256"] != hashlib.sha256(audio.read_bytes()).hexdigest():
            raise ValueError("compressed audio and source preview belong to different files")
        blobs = [blob, (menu / "song-cover.png").read_bytes(), (menu / "preview.wav").read_bytes()]
        song = lib.decode(lib.encode([lib.descriptor(rebuilt, *blobs, m["preview_duration_seconds"])]))[0]
        return song, blobs


def service_idle():
    # Paused pending work is retained. An active/unpaused queue must not race this
    # test; the console .install-lock additionally serializes independent clients.
    snapshots = []
    for endpoint in ("/api/install-queue", "/api/jobs/status"):
        with urllib.request.urlopen("http://127.0.0.1:8765" + endpoint, timeout=5) as response:
            snapshots.append(json.load(response))
    queue, job = snapshots
    if job.get("running") or queue.get("active") or (queue.get("pending") and not queue.get("paused")):
        raise ValueError("finish or pause the companion queue before this explicit test")


def deploy_payload(ftp, song, blobs, report_dir):
    """Append only this verified test entry. Do not replace/delete any existing ID."""
    core.closed(ftp)
    cap = json.loads(core.read(ftp, lib.BASE + "/companion-protocol.json", 4096))
    if cap.get("schema") != 1 or cap.get("title") != "CUSA12878":
        raise ValueError("companion capability mismatch")
    plugin = core.read(ftp, "/data/GoldHEN/plugins/orbeats.prx", 2000000)
    if hashlib.sha256(plugin).hexdigest() != cap.get("active_elf_sha256"):
        raise ValueError("active plugin/capability digest mismatch")
    flags = json.loads(core.read(ftp, "/data/GoldHEN/AFR/CUSA12878/features.json", 65536))
    if flags.get("enable_plugin") is not True or flags.get("enable_additive_song_packs") is not True:
        raise ValueError("additive plugin must already be enabled")
    if any(
        flags.get(k)
        for k in (
            "enable_custom_song_replacements",
            "enable_song_metadata_modification",
            "enable_beatmap_mode_mapping",
            "enable_song_previews",
        )
    ):
        raise ValueError("legacy replacement features must remain OFF")
    lib.encode([song])
    if (
        len(blobs) != 3
        or any(
            len(blob) != spec["bytes"] or lib.fnv(blob) != spec["fnv"]
            for blob, spec in zip(blobs, (song, song["cover"], song["preview"]))
        )
        or hashlib.sha256(blobs[0]).hexdigest() != song["sha256"]
    ):
        raise ValueError("local test payload digest mismatch")
    core.closed(ftp)
    try:
        ftp.mkd(lib.BASE + "/.install-lock")
    except error_perm as exc:
        raise ValueError("another import or interrupted test holds .install-lock; inspect before recovery") from exc
    run = uuid.uuid4().hex
    try:
        songs, old = core.load_library(ftp)
        if old is None:
            raise ValueError("explicit test requires an existing canonical library; no legacy migration")
        same = next((s for s in songs if s["id"] == song["id"]), None)
        if same:
            if same != song:
                raise ValueError("listed ID already has different content")
            core.checked(ftp, song)
            return {"already_present": True, "id": song["id"], "title": song["title"], "count": len(songs)}
        candidate = songs + [song]
        # Original verified v0.8068 markers predate max_songs and support eight
        # entries. Match the production installer's conservative legacy default.
        capacity = cap.get("max_songs", 8)
        if type(capacity) is not int or not 1 <= capacity <= lib.MAX_SONGS or len(candidate) > capacity:
            raise ValueError("test exceeds active plugin capacity")
        lib.encode(candidate)
        for path, blob in zip(lib.paths(song), blobs):
            core.closed(ftp)
            parent = path.rsplit("/", 1)[0]
            if parent != lib.BASE:
                try:
                    ftp.mkd(parent)
                except error_perm as exc:
                    if not str(exc).startswith("550"):
                        raise
                    ftp.nlst(parent)
            before = core.read(ftp, path, len(blob) + 1, missing=True)
            if before is not None:
                if before != blob:
                    raise ValueError("immutable test path collision: " + path)
                continue
            staged = core.stage(ftp, path, blob, run)
            core.closed(ftp)
            if core.read(ftp, path, len(blob) + 1, missing=True) is not None:
                raise ValueError("test path appeared concurrently")
            ftp.rename(staged, path)
            if core.read(ftp, path, len(blob) + 1) != blob:
                raise ValueError("final test file readback failed")
        core.checked(ftp, song)
        core.commit_library(ftp, candidate, old, run, report_dir)
        result = {
            "already_present": False,
            "id": song["id"],
            "title": song["title"],
            "count": len(candidate),
            "bundle_bytes": song["bytes"],
            "hardware_playback_verified": False,
            "stock_changed": False,
            "plugin_changed": False,
            "existing_entries_preserved": len(songs),
        }
        (Path(report_dir) / ("vorbis-install-" + run + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        # Releasing our owned lock is allowed only while the title remains closed.
        # Preserve it as an interrupted-test marker if the user launched mid-write.
        core.closed(ftp)
        ftp.rmd(lib.BASE + "/.install-lock")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--experimental", action="store_true", required=True)
    ap.add_argument("--deploy", action="store_true", required=True)
    for name in ("pcm-candidate", "audio", "source", "candidate", "config", "report-dir"):
        ap.add_argument("--" + name, type=Path, required=True)
    ap.add_argument("--sample-rate", type=int, choices=(44100, 48000), default=44100)
    args = ap.parse_args()
    config = json.loads(args.config.read_bytes())
    if config.get("title", {}).get("id") != "CUSA12878":
        raise ValueError("only CUSA12878 2.04 supported")
    song, blobs = prepare_payload(
        args.pcm_candidate, args.audio, args.source, args.candidate, sample_rate=args.sample_rate
    )
    args.report_dir.mkdir(parents=True, exist_ok=True)
    service_idle()
    address = config["ps4"]
    ftp = FTP()
    try:
        ftp.connect(address["ip"], int(address.get("ftp_port", 2121)), timeout=45)
        ftp.login(address.get("ftp_user", "anonymous"), address.get("ftp_password", ""))
        print(json.dumps(deploy_payload(ftp, song, blobs, args.report_dir), indent=2), flush=True)
    finally:
        ftp.close()


if __name__ == "__main__":
    main()
