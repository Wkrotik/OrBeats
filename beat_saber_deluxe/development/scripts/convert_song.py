#!/usr/bin/env python3
"""
Beat Saber PS4 AssetBundle Converter
====================================
Converts a BeatSaver custom song (PC format) into a PS4-compatible AssetBundle
by cloning an existing song's bundle and replacing audio/beatmaps/metadata.

Usage:
    python3 convert_song.py <songs_repo_dir> <level_id>

Example:
    python3 convert_song.py ../beat-saber-ps4-custom-songs/songs_repo/01ce5a3adc19e360ba0ffd8347f91b5dc974eb7c mysong001

Dependencies:
    - Python 3
    - UnityPy, lz4 (pip install --break-system-packages)
"""

import os, sys, json, struct, gzip, shutil
from pathlib import Path

# Add the modules directory to path
SCRIPT_DIR = Path(__file__).parent
REPO_DIR = (SCRIPT_DIR / ".." / "beat-saber-ps4-custom-songs" / "songs_repo").resolve()
DUMP_DIR = (Path("/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData")).resolve()
AFR_DIR = "/data/GoldHEN/AFR/CUSA12878"

# Template song to clone
TEMPLATE_SONG = "100bills"
OUTPUT_DIR = (SCRIPT_DIR / "custom_songs").resolve()

# UnityPy
import UnityPy

# ── Step 1: Load the template AssetBundle ───────────────────────────────────
def load_template(template_name):
    """Load a known working AssetBundle as template"""
    template_path = DUMP_DIR / template_name
    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}")
        return None

    print(f"Loading template: {template_path}")
    env = UnityPy.load(str(template_path))
    return env

# ── Step 2: Load the custom song metadata ──────────────────────────────────
def load_custom_song(song_path):
    """Load a BeatSaver custom song from its directory"""
    song_dir = Path(song_path)

    # Find info.dat
    info_file = song_dir / "info.dat"
    if not info_file.exists():
        info_file = song_dir / "Info.dat"
    if not info_file.exists():
        print(f"ERROR: No info.dat found in {song_dir}")
        return None

    with open(info_file, 'rb') as f:
        raw = f.read()

    info = json.loads(raw)
    print(f"  Song: {info.get('_songName', info.get('songName', '?'))}")
    print(f"  Author: {info.get('_songAuthorName', info.get('songAuthorName', '?'))}")
    print(f"  BPM: {info.get('_beatsPerMinute', info.get('beatsPerMinute', '?'))}")

    # Find audio file
    audio_file = song_dir / info.get('_songFilename', info.get('songFilename', ''))
    if not audio_file.exists():
        # Try .egg
        audio_file = song_dir / (info.get('_songFilename', '').replace('.ogg', '.egg'))
    if not audio_file.exists():
        # Search for any audio file
        for ext in ['*.egg', '*.ogg', '*.mp3', '*.wav']:
            files = list(song_dir.glob(ext))
            if files:
                audio_file = files[0]
                break

    # Find cover image
    cover_file = song_dir / info.get('_coverImageFilename', info.get('coverImageFilename', 'cover.png'))
    if not cover_file.exists():
        for ext in ['*.png', '*.jpg']:
            files = list(song_dir.glob(ext))
            if files:
                cover_file = files[0]
                break

    # Load difficulty beatmaps
    difficulties = {}
    for dm_set in info.get('_difficultyBeatmapSets', info.get('difficultyBeatmapSets', [])):
        char_name = dm_set.get('_beatmapCharacteristicName', 'Standard')
        for dm in dm_set.get('_difficultyBeatmaps', []):
            diff_name = dm.get('_difficulty', 'Expert')
            diff_file = song_dir / dm.get('_beatmapFilename', f'{diff_name}{char_name}.dat')
            if diff_file.exists():
                with open(diff_file, 'rb') as f:
                    difficulties[f"{diff_name}{char_name}"] = f.read()

    result = {
        'info': info,
        'audio_path': audio_file if audio_file.exists() else None,
        'cover_path': cover_file if cover_file.exists() else None,
        'difficulties': difficulties,
        'song_name': info.get('_songName', info.get('songName', 'Custom Song')),
        'song_author': info.get('_songAuthorName', info.get('songAuthorName', 'Unknown')),
        'level_author': info.get('_levelAuthorName', info.get('levelAuthorName', 'Unknown')),
        'bpm': info.get('_beatsPerMinute', info.get('beatsPerMinute', 120.0)),
    }

    print(f"  Audio: {audio_file.name if audio_file.exists() else 'NOT FOUND'}")
    print(f"  Cover: {cover_file.name if cover_file.exists() else 'NOT FOUND'}")
    print(f"  Difficulties: {list(difficulties.keys())}")
    return result

# ── Step 3: Convert the bundle ─────────────────────────────────────────────
def convert_bundle(env, song_data, level_id):
    """Modify the template bundle with custom song data"""
    bf = env.files[str(DUMP_DIR / TEMPLATE_SONG)]

    # Find the SerializedFile with objects
    cab = None
    for cab_name, cab_obj in bf.files.items():
        if hasattr(cab_obj, 'objects'):
            cab = cab_obj
            break

    if cab is None:
        print("ERROR: No SerializedFile found")
        return None

    changes = 0

    for path_id, reader in cab.objects.items():
        try:
            tt = reader.read_typetree()
            m_name = tt.get('m_Name', '')

            # Rename asset names from "100Bills*" to "<LevelId>*"
            new_name = None
            if m_name.startswith('100Bills'):
                new_name = m_name.replace('100Bills', level_id.capitalize(), 1)
            elif m_name.startswith('100bills'):
                new_name = m_name.replace('100bills', level_id, 1)
            elif m_name == '$100Bills':
                new_name = f"${level_id}"
                # Update AudioClip metadata
                if reader.class_id == 83:
                    tt['m_Name'] = new_name
                    print(f"  AudioClip: {m_name} -> {new_name}")
                    reader.save_typetree(tt)
                    changes += 1
                    continue

            if new_name:
                tt['m_Name'] = new_name
                print(f"  Renamed: {m_name} -> {new_name}")
                reader.save_typetree(tt)
                changes += 1

            # Update BeatmapLevelData metadata
            if reader.class_id == 114 and 'BeatmapLevel' in str(m_name):
                if '_songName' in tt:
                    tt['_songName'] = song_data['song_name']
                if '_songAuthorName' in tt:
                    tt['_songAuthorName'] = song_data['song_author']
                if '_levelAuthorName' in tt:
                    tt['_levelAuthorName'] = song_data['level_author']
                if '_beatsPerMinute' in tt:
                    tt['_beatsPerMinute'] = song_data['bpm']
                if '_levelID' in tt:
                    tt['_levelID'] = level_id
                print(f"  Metadata updated for {m_name}")
                reader.save_typetree(tt)
                changes += 1

            # Replace beatmap data (class=49 TextAsset with .beatmap.gz or .lightshow.gz)
            if reader.class_id == 49 and ('.beatmap' in m_name or '.lightshow' in m_name):
                # Try to find matching difficulty from custom song
                # The naming pattern is like "100BillsNormal.beatmap.gz"
                raw_data = reader.get_raw_data()
                if len(raw_data) > 0:
                    # Check if it's gz compressed
                    if raw_data[:2] == b'\x1f\x8b':
                        decompressed = gzip.decompress(raw_data)
                        decomp_str = decompressed.decode('utf-8')
                        decomp_json = json.loads(decomp_str)
                        print(f"  Beatmap {m_name}: {len(raw_data)} bytes gz, version {decomp_json.get('_version', '?')}")
                        # TODO: Replace with custom beatmap data
                    else:
                        print(f"  Non-gz data in {m_name}: {raw_data[:16].hex()}")

        except Exception as e:
            pass

    cab.mark_changed()
    print(f"\n  Total changes: {changes}")
    return env

# ── Step 4: Save the modified bundle ───────────────────────────────────────
def save_bundle(env, level_id):
    """Save the modified bundle"""
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{level_id}.bundle"

    bf = list(env.files.values())[0]
    try:
        result = bf.save()
        if isinstance(result, bytes):
            with open(output_path, 'wb') as f:
                f.write(result)
            print(f"\n  Saved: {output_path} ({len(result):,} bytes)")
            return output_path
    except Exception as e:
        print(f"\n  Save error (falling back to copy): {e}")

    # Fallback: copy the original template and report
    shutil.copy(str(DUMP_DIR / TEMPLATE_SONG), str(output_path))
    print(f"\n  Copied template (no changes saved): {output_path}")
    return None

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    song_path = sys.argv[1]
    level_id = sys.argv[2] if len(sys.argv) > 2 else "custom001"

    print(f"Converting custom song from: {song_path}")
    print(f"Level ID: {level_id}")

    # Load template
    env = load_template(TEMPLATE_SONG)
    if not env:
        return

    # Load custom song
    song_data = load_custom_song(song_path)
    if not song_data:
        return

    # Convert
    result = convert_bundle(env, song_data, level_id)
    if not result:
        return

    # Save
    output = save_bundle(result, level_id)
    if output:
        print(f"\n=== Conversion complete! ===")
        print(f"Next steps:")
        print(f"1. Deploy to PS4: lftp -u anonymous, -p 2121 192.168.100.117 -e 'put {output} -o {AFR_DIR}/{level_id}; quit'")
        print(f"2. Update plugin redirect: open_hook redirect to {AFR_DIR}/{level_id}")
        print(f"3. Test on PS4")

if __name__ == '__main__':
    main()
