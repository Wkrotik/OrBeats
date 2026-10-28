#!/usr/bin/env python3
"""
make_rights_clean_test_song.py — CLI wrapper: synthesize the original,
rights-clean "BSD Deluxe Theme" test song on demand (M13 validation asset).

Everything is generated math (sine oscillators + envelopes — see
webapp/adapters/testsong.py, the production home of the synth core): the
output is unconditionally ours — no samples, no recordings, no MIDI of
existing music — so uploading it to beatsage.com satisfies the rights
assertion in the web app.

The 48s default produced the map that's now "BSD Deluxe Theme (An Original)"
on the console; shorter values (e.g. 8) make a quick live-contract probe
polite to their free queue.

Usage:
    python3 development/scripts/make_rights_clean_test_song.py out.wav [seconds]
"""

from __future__ import annotations

import sys
from pathlib import Path

WEBAPP = Path(__file__).resolve().parents[2] / "webapp"
sys.path.insert(0, str(WEBAPP))

from adapters import testsong  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "bsd_original_test_song.wav")
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 48.0
    data = testsong.generate_wav(out, seconds)
    dur = len(data) / (testsong.SR * 2)  # 16-bit mono
    print(f"✅ {out} — {dur:.0f}s, {testsong.SR}Hz mono, original synthesis "
          f"(rights-clean; deterministic — the same seconds value always "
          f"yields the same song)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
