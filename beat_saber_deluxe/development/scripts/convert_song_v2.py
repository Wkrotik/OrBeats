#!/usr/bin/env python3
"""
Beat Saber PS4 AssetBundle Converter v2
=======================================
Full conversion: replaces beatmap data, metadata, and asset names.
Audio replacement requires FSB5 tools (not included in this version).

Usage:
    python3 convert_song_v2.py <songs_repo_dir> <level_id>

Example:
    python3 convert_song_v2.py ../beat-saber-ps4-custom-songs/songs_repo/01ce5a3adc19e360ba0ffd8347f91b5dc974eb7c test001
"""

import os, sys, json, struct, gzip, shutil
from pathlib import Path

import UnityPy

SCRIPT_DIR = Path(__file__).parent
DUMP_DIR = Path("/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData")
TEMPLATE_SONG = "100bills"
OUTPUT_DIR = SCRIPT_DIR / "custom_songs"

def load_template():
    """Load the template 100bills bundle"""
    template_path = DUMP_DIR / TEMPLATE_SONG
    print(f"Loading template: {template_path}")
    return UnityPy.load(str(template_path))

def load_custom_song(song_path):
    """Load a BeatSaver custom song"""
    song_dir = Path(song_path)

    # Find info.dat
    info_file = song_dir / "info.dat"
    if not info_file.exists():
        info_file = song_dir / "Info.dat"
    if not info_file.exists():
        print(f"ERROR: No info.dat in {song_dir}")
        return None

    with open(info_file, 'rb') as f:
        info = json.loads(f.read())

    print(f"  Song: {info.get('_songName', '?')}")
    print(f"  Author: {info.get('_songAuthorName', '?')}")

    # Load difficulty beatmaps
    difficulties = {}
    for dm_set in info.get('_difficultyBeatmapSets', info.get('difficultyBeatmapSets', [])):
        char_name = dm_set.get('_beatmapCharacteristicName', 'Standard')
        for dm in dm_set.get('_difficultyBeatmaps', []):
            diff_name = dm.get('_difficulty', 'Expert')
            diff_file = song_dir / dm.get('_beatmapFilename', f'{diff_name}{char_name}.dat')
            if diff_file.exists():
                with open(diff_file, 'rb') as f:
                    data = f.read()
                # Store with key matching our naming pattern
                key = f"{diff_name}{char_name}"
                difficulties[key] = data

    # Find audio
    audio_file = None
    audio_name = info.get('_songFilename', '')
    for candidate in [song_dir / audio_name, song_dir / audio_name.replace('.ogg', '.egg')]:
        if candidate.exists():
            audio_file = candidate
            break
    if not audio_file:
        for ext in ['*.egg', '*.ogg']:
            files = list(song_dir.glob(ext))
            if files:
                audio_file = files[0]
                break

    return {
        'info': info,
        'song_name': info.get('_songName', 'Custom'),
        'song_author': info.get('_songAuthorName', 'Unknown'),
        'level_author': info.get('_levelAuthorName', 'Unknown'),
        'bpm': info.get('_beatsPerMinute', 120.0),
        'difficulties': difficulties,
        'audio_path': audio_file,
    }

def convert(env, song_data, level_id):
    """Modify the template bundle with custom song data"""
    bf = list(env.files.values())[0]
    cab = next(v for v in bf.files.values() if hasattr(v, 'objects'))

    # Prefix for renamed assets
    old_prefix = "100Bills"
    new_prefix = level_id.capitalize()
    old_prefix_lower = "100bills"
    new_prefix_lower = level_id

    changes = 0

    for path_id, reader in cab.objects.items():
        try:
            tt = reader.read_typetree()
            m_name = tt.get('m_Name', '')
            if not m_name:
                continue

            new_name = m_name

            # Track what we need to replace
            replace_beatmap = False
            difficulty_key = None

            # Rename asset names
            if m_name.startswith(old_prefix):
                new_name = m_name.replace(old_prefix, new_prefix, 1)
            elif m_name.startswith(old_prefix_lower):
                new_name = m_name.replace(old_prefix_lower, new_prefix_lower, 1)
            elif m_name == '$100Bills' and reader.class_id == 83:
                new_name = f"${level_id}"
                # Update AudioClip metadata is handled below

            # Update the name
            if new_name != m_name:
                tt['m_Name'] = new_name
                changes += 1

            # Replace beatmap data (class=49 TextAsset with .beatmap.gz or .lightshow.gz)
            if reader.class_id == 49 and ('.beatmap' in m_name or '.lightshow' in m_name):
                raw = reader.get_raw_data()
                if len(raw) > 4:
                    # Parse: [4 bytes filename_len][filename_str][1 byte null][4 bytes decomp_size][gz data]
                    fn_len = struct.unpack_from('<I', raw, 0)[0]
                    fn_end = 4 + fn_len + 1  # +1 for null

                    if fn_end + 4 <= len(raw):
                        decomp_size = struct.unpack_from('<I', raw, fn_end)[0]
                        gz_data_start = fn_end + 4
                        gz_data = raw[gz_data_start:]

                        # Check if it's gzip
                        if gz_data[:2] == b'\x1f\x8b':
                            # It's gzip data - try to find matching difficulty
                            # Parse the beatmap filename to get difficulty+characteristic
                            orig_fn = raw[4:4+fn_len].decode('ascii', errors='replace')
                            orig_fn = orig_fn.replace('.beatmap.gz', '').replace('.lightshow.gz', '')

                            # Mapping: our naming uses "DifficultyCharName" like "EasyStandard"
                            # The original format has "100BillsEasy.beatmap.gz" -> extract "Easy"
                            # Remove the "100Bills" prefix to get the difficulty name
                            diff_key = orig_fn.replace('100Bills', '').replace('100bills', '')

                            if diff_key in song_data['difficulties']:
                                custom_data = song_data['difficulties'][diff_key]
                                # Gzip compress the custom beatmap data
                                compressed = gzip.compress(custom_data)

                                # Build new raw data with updated filename
                                new_fn_bytes = new_name.encode('ascii')
                                new_raw = bytearray()
                                new_raw += struct.pack('<I', len(new_fn_bytes))
                                new_raw += new_fn_bytes
                                new_raw += b'\x00'
                                new_raw += struct.pack('<I', len(custom_data))
                                new_raw += compressed

                                reader.set_raw_data(bytes(new_raw))
                                print(f"  ✅ Replaced: {orig_fn} -> {diff_key} ({len(compressed)} bytes gz)")
                                changes += 1
                            else:
                                print(f"  Skipping {orig_fn}: no matching difficulty '{diff_key}' found in custom song")

            # Update BeatmapLevelData metadata
            if reader.class_id == 114 and 'BeatmapLevel' in str(m_name):
                for field, value in [('_songName', song_data['song_name']),
                                     ('_songAuthorName', song_data['song_author']),
                                     ('_levelAuthorName', song_data['level_author']),
                                     ('_beatsPerMinute', song_data['bpm']),
                                     ('_levelID', level_id)]:
                    if field in tt:
                        tt[field] = value
                        changes += 1
                print(f"  Metadata updated for {m_name}")

            # Save changes back if we modified the typetree
            if new_name != m_name or reader.class_id == 114:
                reader.save_typetree(tt)

        except Exception as e:
            pass

    cab.mark_changed()
    print(f"\n  Total changes: {changes}")
    return env

def save_bundle(env, level_id):
    """Save the modified bundle"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{level_id}.bundle"

    bf = list(env.files.values())[0]
    result = bf.save()
    if isinstance(result, bytes):
        with open(output_path, 'wb') as f:
            f.write(result)
        print(f"  Saved: {output_path} ({len(result):,} bytes)")
        return output_path
    else:
        shutil.copy(str(DUMP_DIR / TEMPLATE_SONG), str(output_path))
        print(f"  Fallback: copied template to {output_path}")
        return output_path

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    song_path = sys.argv[1]
    level_id = sys.argv[2] if len(sys.argv) > 2 else "custom001"

    print(f"Converting: {song_path}")
    print(f"Level ID: {level_id}")

    env = load_template()
    song_data = load_custom_song(song_path)
    if not env or not song_data:
        return

    convert(env, song_data, level_id)
    output = save_bundle(env, level_id)

    if output:
        # Verify the saved bundle
        try:
            env2 = UnityPy.load(str(output))
            for p, o in env2.container.items():
                tt = o.read_typetree()
                print(f"\nVerified: path={p}")
                print(f"  m_Name={tt.get('m_Name', '?')}")
                print(f"  _levelID={tt.get('_levelID', 'N/A')}")
                print(f"  _songName={tt.get('_songName', 'N/A')}")
        except Exception as e:
            print(f"Verify error: {e}")

        print(f"\n=== Converted: {song_data['song_name']} -> {level_id} ===")
        print(f"File: {output}")

if __name__ == '__main__':
    main()
