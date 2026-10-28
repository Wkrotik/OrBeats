"""
Lapped Audio Detection & Generation for PS4 Beat Saber
=======================================================

Some BeatSaver beatmaps extend far beyond the audio duration (lapped-up).
The mapper repeated chart sections across an extended timeline. For PS4,
we must extend the audio to match so the engine doesn't freeze when audio ends.

Algorithm:
  1. Scan beatmaps for max_note_time vs audio_duration
  2. If max_note_time > audio_duration * 1.3 → lapped
  3. Extract _customData._bookmarks from beatmaps
  4. Find the loop section: last two bookmarks fully within audio_duration
  5. Generate extended audio: original + loop_section * N

Usage:
    from lapped_audio import lap_audio_if_needed
    extended_wav = lap_audio_if_needed(beatmap_dir, audio_path)
"""

import json
import logging
import os

import numpy as np
import soundfile as sf

log = logging.getLogger('lapped_audio')

LAP_THRESHOLD = 1.3  # max_note_time / audio_duration ratio to trigger lapping


def load_bpm(beatmap_dir: str) -> float:
    """Load BPM from info.dat, falling back to 120."""
    info_path = os.path.join(beatmap_dir, 'info.dat')
    if os.path.isfile(info_path):
        try:
            info = json.load(open(info_path))
            bpm = info.get('_beatsPerMinute')
            if bpm and bpm > 0:
                return float(bpm)
        except Exception:
            pass
    # Fallback: try reading a beatmap file
    import glob
    for path in sorted(glob.glob(os.path.join(beatmap_dir, '*.dat'))):
        if path.endswith('info.dat'):
            continue
        try:
            data = json.load(open(path))
            bpm = data.get('_beatsPerMinute')
            if bpm and bpm > 0:
                return float(bpm)
        except Exception:
            continue
    return 120.0


def is_v2_beatmap(beatmap_dir: str) -> bool:
    """Check if beatmaps are V2 format (_time in beats)."""
    import glob
    for path in sorted(glob.glob(os.path.join(beatmap_dir, '*.dat'))):
        if path.endswith('info.dat'):
            continue
        try:
            data = json.load(open(path))
            ver = data.get('_version', '')
            if ver.startswith('3'):
                return False
            if ver.startswith('2') or ver == '':
                return True
        except Exception:
            continue
    return True  # assume V2 if unknown


def get_beatmap_event_times(beatmap_dir: str) -> dict:
    """Load all beatmap .dat files and return per-difficulty event times.

    For V2 beatmaps (_version 2.x), _time is in BEATS.
    This function converts beats to seconds using the BPM from info.dat.
    """
    import glob

    bpm = load_bpm(beatmap_dir)
    v2 = is_v2_beatmap(beatmap_dir)

    dat_files = sorted(glob.glob(os.path.join(beatmap_dir, '*.dat')))
    infos = {}
    for path in dat_files:
        if path.endswith('info.dat'):
            continue
        try:
            data = json.load(open(path))
        except Exception:
            continue
        name = os.path.basename(path)
        times_sec = set()
        for key in ('_notes', '_obstacles', '_bombs', '_sliders', '_burstSliders'):
            for item in data.get(key, []):
                t = item.get('_time', 0)
                if isinstance(t, (int, float)):
                    if v2:
                        t = t / bpm * 60  # beats → seconds
                    times_sec.add(t)
        # Bookmarks: in the beatmap they match the _time unit (beats or secs)
        bookmarks = [b.get('_time', 0) for b in data.get('_customData', {}).get('_bookmarks', [])]
        if v2:
            bookmarks = [b / bpm * 60 for b in bookmarks]
        infos[name] = {
            'times': sorted(times_sec),
            'max_time': max(times_sec) if times_sec else 0,
            'bookmarks': sorted(set(bookmarks)),
        }

    return infos


def make_beatmap_times(beatmap_dir: str) -> dict:
    """Alias for get_beatmap_event_times."""
    return get_beatmap_event_times(beatmap_dir)


def detect_lapped(beatmap_dir: str, audio_duration: float) -> dict:
    """
    Detect if a song is lapped and find the loop section.

    Returns dict with keys:
        is_lapped: bool
        max_note_time: float (max event time in SECONDS across all diffs)
        loop_start: float (start of loop section in original audio)
        loop_end: float (end of loop section in original audio)
        loop_duration: float
        repeats_needed: int
        extended_duration: float
    """
    infos = make_beatmap_times(beatmap_dir)

    if not infos:
        return {'is_lapped': False, 'max_note_time': 0}

    max_note_time = max(v['max_time'] for v in infos.values())

    if max_note_time <= audio_duration * LAP_THRESHOLD:
        log.info(f"Song is NOT lapped: max_note={max_note_time:.1f}s <= "
                 f"audio={audio_duration:.1f}s * {LAP_THRESHOLD}")
        return {'is_lapped': False, 'max_note_time': max_note_time}

    log.info(f"Song IS lapped: max_note={max_note_time:.1f}s > "
             f"audio={audio_duration:.1f}s * {LAP_THRESHOLD}")

    # Collect all bookmarks from all difficulties
    all_bookmarks = set()
    for info in infos.values():
        all_bookmarks.update(info['bookmarks'])

    all_bookmarks = sorted(all_bookmarks)

    # Remove bookmarks that seem like section markers (0.0 is usually the start)
    all_bookmarks = [b for b in all_bookmarks if b > 0.01]

    log.info(f"  Bookmarks across difficulties: {[f'{b:.1f}' for b in all_bookmarks]}")

    # Find the loop section.
    # Strategy: the section from bookmarks_within[-1] to audio_end is the
    # "drop/chorus" cue in the original audio.  We loop it to extend.
    # If it's shorter than 15s though that gets jarring, so we prefer
    # a longer section from bookmarks_within[-2] to audio_end.
    bookmarks_within_audio = [b for b in all_bookmarks if b < audio_duration]

    if len(bookmarks_within_audio) >= 2:
        # Prefer longer loop (penultimate bookmark to audio_end)
        candidate_start = bookmarks_within_audio[-2]
        candidate_dur = audio_duration - candidate_start
        # If candidate is at least 20s, use it; otherwise use last bookmark
        if candidate_dur >= 20.0:
            loop_start = candidate_start
        else:
            loop_start = bookmarks_within_audio[-1]
        loop_end = audio_duration
    elif len(bookmarks_within_audio) == 1:
        # One bookmark: loop from it to audio_end
        loop_start = bookmarks_within_audio[0]
        loop_end = audio_duration
    else:
        # No bookmarks: use last half of audio as the loop section
        loop_start = audio_duration * 0.5
        loop_end = audio_duration

    loop_duration = loop_end - loop_start

    if loop_duration <= 0:
        log.warning(f"  Invalid loop section: {loop_start}-{loop_end}, "
                     f"falling back to full audio loop")
        loop_start = 0
        loop_end = audio_duration
        loop_duration = audio_duration

    # Calculate repeats needed
    audio_portion = loop_start  # audio before loop section starts
    gap = max_note_time - audio_portion
    repeats_needed = int(np.ceil(gap / loop_duration))
    extended_duration = audio_portion + repeats_needed * loop_duration

    log.info(f"  Loop section: {loop_start:.1f}s - {loop_end:.1f}s "
             f"({loop_duration:.1f}s)")
    log.info(f"  Repeats needed: {repeats_needed}")
    log.info(f"  Extended duration: {extended_duration:.1f}s "
             f"(vs audio {audio_duration:.1f}s)")

    return {
        'is_lapped': True,
        'max_note_time': max_note_time,
        'loop_start': loop_start,
        'loop_end': loop_end,
        'loop_duration': loop_duration,
        'repeats_needed': repeats_needed,
        'extended_duration': extended_duration,
    }


def lap_audio(audio_path: str, lap_info: dict) -> str:
    """
    Generate a lapped (extended) WAV file.

    Args:
        audio_path: Path to original audio file (WAV/OGG/FLAC)
        lap_info: Dict from detect_lapped()

    Returns:
        Path to extended WAV file (temporary)
    """
    if not lap_info.get('is_lapped'):
        return audio_path  # not lapped, return original

    loop_start = lap_info['loop_start']
    loop_end = lap_info['loop_end']
    repeats = lap_info['repeats_needed']

    log.info(f"Generating lapped audio: repeating {loop_start:.1f}s-{loop_end:.1f}s "
             f"x{repeats}...")

    # Read original audio
    data, sr = sf.read(audio_path, dtype='int16')
    if data.ndim == 1:
        data = np.column_stack((data, data))

    # Extract sections
    start_sample = int(loop_start * sr)
    end_sample = int(loop_end * sr)

    if end_sample > len(data):
        end_sample = len(data)
    if start_sample >= len(data):
        log.error(f"  Loop start ({start_sample}samples) beyond audio length "
                  f"({len(data)}samples)! Using full audio as loop.")
        start_sample = 0

    # Audio before loop section (0 to loop_start)
    pre_loop = data[:start_sample]

    # Loop section audio
    loop_section = data[start_sample:end_sample]

    if len(loop_section) == 0:
        log.error("  Empty loop section! Using full audio.")
        pre_loop = np.array([], dtype=data.dtype).reshape(0, data.shape[1] if data.ndim > 1 else 1)
        loop_section = data

    log.info(f"  Pre-loop: {len(pre_loop)} samples, "
             f"Loop: {len(loop_section)} samples x{repeats}")

    # Build extended audio
    extended_parts = [pre_loop]
    for i in range(repeats):
        extended_parts.append(loop_section)

    extended_data = np.concatenate(extended_parts)

    log.info(f"  Extended: {len(extended_data)} samples "
             f"({len(extended_data)/sr:.1f}s)")

    # Write temporary WAV
    out_path = '/tmp/lapped_audio_output.wav'
    sf.write(out_path, extended_data, sr)
    log.info(f"  Written: {out_path}")

    return out_path


def lap_audio_if_needed(beatmap_dir: str, audio_path: str) -> str:
    """
    High-level function: detect lapped song and generate extended audio if needed.

    Args:
        beatmap_dir: Directory containing beatmap .dat files
        audio_path: Path to audio file (.wav, .ogg, .flac)

    Returns:
        Path to audio file to use (original or extended WAV)
    """
    info = sf.info(audio_path)
    audio_duration = info.duration

    lap_info = detect_lapped(beatmap_dir, audio_duration)

    if not lap_info['is_lapped']:
        return audio_path

    return lap_audio(audio_path, lap_info)


def test():
    """Quick test with Bruises data."""
    dir = '/workspace/beat-saber-ps4-custom-songs/songs_repo/71eff19ed6d32fd0a446e1a32303c77aa7f646f2'
    audio = os.path.join(dir, 'song.ogg')
    result = lap_audio_if_needed(dir, audio)
    print(f"\nResult: {result}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    test()
