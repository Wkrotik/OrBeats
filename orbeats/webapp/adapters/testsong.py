"""
testsong.py — the original, rights-clean "BSD Deluxe Theme" test song (M13).

100% mathematical synthesis: sine oscillators + envelopes only — no samples,
no recordings, no MIDI of existing music. The output is unconditionally
ours, which makes it the perfect Beat Sage validation song (uploading it
satisfies the rights assertion) and the perfect web-app demo asset.

The song: a 4-chord loop (Am–F–C–G) at 120 BPM with bass, soft chords, a
pentatonic melody, and a kick/hat groove — musical enough for Beat Sage's
AI to find beats (their mapper needs tempo), short enough (default 48s) to
be polite to their free queue.

Promoted from development/scripts/make_rights_clean_test_song.py (proven in
Exp 283's live Tier-1 verification + the real PS4 deploy of the generated
map). The CLI wrapper remains in development/scripts/ for validation runs;
the web app serves it on demand via GET /api/songs/test-song.
"""

from __future__ import annotations

import wave
from pathlib import Path

SR = 44100
BPM = 120.0
BEAT = 60.0 / BPM


def generate_wav(out: Path | None = None, seconds: float = 48.0) -> bytes:
    """Synthesize the theme song → bytes (and optionally write `out`).
    Deterministic: the same seconds value always yields the same song."""
    import numpy as np  # lazy: numpy is a pipeline requirement, not server-startup

    total_n = max(1, int(seconds * SR))
    mix = np.zeros(total_n)

    A, C, D, E, F, G = 220.0, 261.63, 293.66, 329.63, 174.61, 196.0
    chords = [
        (A, [A, C, E]),          # Am
        (F, [F, A, C]),          # F
        (C, [C, E, G]),          # C
        (G, [G, C, E]),          # G (inverted for voice leading)
    ]
    chord_beats = 4  # one bar per chord
    melody_notes = [E, G, A, C, D, C, A, G]  # Am pentatonic-ish contour

    def add(freq_hz, start_s, dur_s, amp, harmonics):
        n = int(dur_s * SR)
        if n <= 0:
            return
        t = np.arange(n) / SR
        wave_sum = np.zeros(n)
        for mult, weight in harmonics:
            wave_sum += weight * np.sin(2 * np.pi * freq_hz * mult * t)
        env = np.minimum(1.0, t / 0.008) * np.exp(-t / (dur_s * 0.45))
        release = int(0.02 * SR)
        if n > release:
            env[-release:] *= np.linspace(1, 0, release)
        seg = amp * env * wave_sum
        idx0 = int(start_s * SR)
        idx1 = min(idx0 + n, total_n)
        if idx1 > idx0:
            mix[idx0:idx1] += seg[:idx1 - idx0]

    harmonics = ((1, 1.0), (2, 0.35), (3, 0.12))
    beat_i = 0
    while beat_i * BEAT < seconds - 2:
        root, triad = chords[(beat_i // chord_beats) % len(chords)]
        pos = beat_i * BEAT
        in_bar = beat_i % 4
        add(root / 2, pos, BEAT * 0.9, 0.32, harmonics)            # bass
        if in_bar in (0, 2):
            add(55.0, pos, 0.18, 0.5, ((1, 1.0),))                 # kick
        add(6000.0 + 400 * in_bar, pos, 0.03,
            0.06 if in_bar % 2 else 0.04, harmonics)               # hat
        if in_bar == 0:
            for f in triad:
                add(f * 2, pos, BEAT * chord_beats * 0.95, 0.06, harmonics)
        mel = melody_notes[(beat_i * 3) % len(melody_notes)]
        add(mel * 2, pos + BEAT * 0.25, BEAT * 0.6, 0.16, harmonics)
        beat_i += 1

    peak = np.max(np.abs(mix)) or 1.0
    mix = 0.85 * mix / peak
    fade = min(int(1.0 * SR), total_n // 4)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    pcm = (mix * 32767).astype(np.int16).tobytes()

    import io
    buf = io.BytesIO()
    with wave.open(buf, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    data = buf.getvalue()
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return data
