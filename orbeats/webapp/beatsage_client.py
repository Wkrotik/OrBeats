#!/usr/bin/env python3
"""
beatsage_client.py — the Beat Sage Tier-1 generation job (M13.3).

Invoked by the web app's Beat Sage section (never by users directly):
    python3 webapp/beatsage_client.py --job '<json spec>'

The spec (built by server.py from the user's form):
    {
      "audio_path": "<temp file the server saved the upload to>",
      "title": "...", "artist": "...",
      "difficulties": [...], "modes": [...], "events": [...],
      "environment": "...", "system_tag": "v2"
    }

Flow (the ladder's Tier 1 — the web app drives beatsage.com on the user's
behalf): upload → poll their heartbeat at THEIR OWN UI's cadence (3s,
3-failure tolerance) with live status lines → download the zip → validate +
stage it via the shared intake (adapters/songs.py) → the last line is
"STAGED <id>" so the UI can refresh the staged list. ANY failure prints a
clear message and exits non-zero — the UI then shows the guided flow
(Tier 2), which always works.

Single-job doctrine: this runs as THE one job (runner.start_script) — the
web app's cancel button kills the whole process group like any other.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

WEBAPP = Path(__file__).resolve().parent
if str(WEBAPP) not in sys.path:
    sys.path.insert(0, str(WEBAPP))

from adapters import beatsage, songs  # noqa: E402

_DONE_STATUSES = {"PENDING", "LOADING_AUDIO", "CREATING_LEVEL", "FORMATTING_LEVEL"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True,
                        help="JSON job spec (see module docstring)")
    args = parser.parse_args()
    try:
        spec = json.loads(args.job)
    except json.JSONDecodeError as e:
        print(f"❌ Bad job spec: {e}")
        return 2

    audio_path = spec.get("audio_path", "")
    if not audio_path or not Path(audio_path).is_file():
        print(f"❌ The uploaded audio file is missing: {audio_path}")
        return 2
    title = str(spec.get("title", "") or Path(audio_path).stem)
    artist = str(spec.get("artist", "") or "Unknown Artist")
    options = {
        "difficulties": spec.get("difficulties") or beatsage.RECOMMENDED_DIFFICULTIES,
        "modes": spec.get("modes") or beatsage.RECOMMENDED_MODES,
        "events": spec.get("events") or beatsage.RECOMMENDED_EVENTS,
        "environment": spec.get("environment") or beatsage.RECOMMENDED_ENVIRONMENT,
        "system_tag": spec.get("system_tag") or beatsage.RECOMMENDED_SYSTEM_TAG,
    }
    problems = beatsage.validate_options(options)
    if problems:
        print("❌ " + " ".join(problems))
        return 2

    print(f" powered by beatsage.com — uploading “{title}” by {artist}…")
    print(f"   difficulties={options['difficulties']} modes={options['modes']} "
          f"events={options['events']} env={options['environment']} "
          f"system={options['system_tag']}")
    try:
        job_id = beatsage.create_job(audio_path, title, artist, options)
    except beatsage.BeatSageError as e:
        print(f"❌ {e}")
        print("   The guided flow below always works — you can generate on "
              "beatsage.com yourself and drop the zip back.")
        return 1
    print(f" ✅ Job accepted — Beat Sage id {job_id}. Their AI needs a few "
          "minutes; polling at their own UI's cadence…")

    # Poll — their cadence, their failure budget (3s / 3 misses)
    status = "PENDING"
    failures = 0
    started = time.time()
    while True:
        try:
            doc = beatsage.heartbeat(job_id)
        except beatsage.BeatSageError as e:
            failures += 1
            if failures >= beatsage.HEARTBEAT_MAX_FAILURES:
                print(f"❌ {e}")
                print("   The guided flow below always works — you can generate on "
                      "beatsage.com yourself and drop the zip back.")
                return 1
            print(f"   (heartbeat hiccup {failures}/{beatsage.HEARTBEAT_MAX_FAILURES} — retrying)")
        else:
            failures = 0
            new = str(doc.get("status", ""))
            if new != status:
                status = new
                elapsed = int(time.time() - started)
                print(f"   [{elapsed}s] {status}")
            if status == "DONE":
                break
            if status and status not in _DONE_STATUSES:
                print(f"❌ Beat Sage job reported an unknown status: {status!r} — "
                      "their service may have changed. Use the guided flow below.")
                return 1
        time.sleep(beatsage.HEARTBEAT_INTERVAL_SECONDS)

    print(" ✅ Generation complete — downloading the map zip…")
    try:
        data = beatsage.download_zip(job_id)
    except beatsage.BeatSageError as e:
        print(f"❌ {e}")
        return 1
    print(f"   ({len(data):,} bytes) — validating and staging…")
    try:
        entry = songs.stage_zip_bytes(data, source="beatsage",
                                      display_name=f"{title} — {artist}")
    except ValueError as e:
        print(f"❌ Beat Sage's zip didn't validate:\n{e}")
        return 1
    # Record the generation options on the staged entry (the user asked for
    # the full Beat Sage context on every staged song — what was requested,
    # with which model, is part of the map's story)
    songs.annotate_staged(entry["id"], {"generation": {
        "system_tag": options["system_tag"],
        "difficulties": options["difficulties"],
        "modes": options["modes"],
        "events": options["events"],
        "environment": options["environment"],
        "title": title, "artist": artist,
    }})
    print(f" ✅ STAGED {entry['id']} — “{entry['name']}” by {entry['artist']} "
          f"({entry['schema']}, {'/'.join(entry['difficulties'])})")
    print("   Pick it in the staged list below, then Deploy as usual.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
