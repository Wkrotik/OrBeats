#!/usr/bin/env python3
"""
Beat Saber PS4 AssetBundle Converter v3
=======================================
Converts a BeatSaver custom song into a PS4-compatible AssetBundle.
Replaces beatmap data and renames assets. Audio stays as template audio
(needs FSB5 tools to replace).

Usage:
    python3 convert_song_v3.py <song_directory> <level_id>
"""

import os, sys, json, struct, gzip
from pathlib import Path

import UnityPy

DUMP_DIR = Path("/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData")
TEMPLATE = "100bills"
OUTPUT_DIR = Path(__file__).parent / "custom_songs"

# Difficulty rank mapping (Beat Saber standard)
DIFFICULTY_RANKS = {0: "Easy", 1: "Normal", 2: "Hard", 3: "Expert", 4: "ExpertPlus"}

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    song_path = sys.argv[1]
    level_id = sys.argv[2] if len(sys.argv) > 2 else "custom001"

    print(f"Converting: {song_path}")
    print(f"Level ID: {level_id}")

    # ── Load custom song ────
    song_dir = Path(song_path)
    info_file = song_dir / "info.dat"
    if not info_file.exists():
        info_file = song_dir / "Info.dat"
    info = json.loads(info_file.read_bytes())

    song_name = info.get('_songName', '?')
    author = info.get('_songAuthorName', '?')
    print(f"  Song: {song_name} by {author}")

    # Load difficulties keyed by difficulty name (e.g., "Easy", "Normal")
    custom_diffs = {}
    for dm_set in info.get('_difficultyBeatmapSets', []):
        char_name = dm_set.get('_beatmapCharacteristicName', 'Standard')
        for dm in dm_set.get('_difficultyBeatmaps', []):
            diff_name = dm.get('_difficulty', 'Expert')
            diff_file = song_dir / dm.get('_beatmapFilename', f"{diff_name}{char_name}.dat")
            if diff_file.exists():
                custom_diffs[diff_name] = diff_file.read_bytes()
    print(f"  Difficulties: {sorted(custom_diffs.keys())}")

    # ── Load template ────
    template_path = DUMP_DIR / TEMPLATE
    print(f"  Template: {template_path}")
    env = UnityPy.load(str(template_path))
    bf = list(env.files.values())[0]
    cab = next(v for v in bf.files.values() if hasattr(v, 'objects'))

    # ── Modify objects ────
    changes = 0
    template_diffs_map = {}  # maps template diff name to path_id

    for path_id, reader in cab.objects.items():
        tt = reader.read_typetree()
        m_name = tt.get('m_Name', '')
        if not m_name:
            continue

        new_name = m_name

        # Rename: replace "100Bills" / "100bills" / "$100Bills" with level_id equivalent
        if m_name.startswith("100Bills"):
            new_name = m_name.replace("100Bills", level_id.capitalize(), 1)
        elif m_name.startswith("100bills"):
            new_name = m_name.replace("100bills", level_id, 1)
        elif m_name == "$100Bills" and reader.class_id == 83:
            new_name = f"${level_id}"

        if new_name != m_name:
            tt['m_Name'] = new_name
            reader.save_typetree(tt)
            changes += 1

        # Process beatmap data
        if reader.class_id == 49 and ('.beatmap' in m_name):
            raw = reader.get_raw_data()
            if len(raw) > 8:
                fn_len = struct.unpack_from('<I', raw, 0)[0]
                fn_end = 4 + fn_len + 1
                if fn_end + 4 <= len(raw):
                    decomp_size = struct.unpack_from('<I', raw, fn_end)[0]
                    gz_data = raw[fn_end + 4:]

                    if gz_data[:2] == b'\x1f\x8b':
                        # Extract difficulty name from the original file path
                        # Format: "100BillsEasy.beatmap.gz" -> "Easy"
                        orig_fn = raw[4:4 + fn_len].decode('ascii', errors='replace')
                        # Extract difficulty name: after "100Bills", before ".beatmap"
                        diff_key = orig_fn
                        for pfx in ['100Bills', '100bills']:
                            if diff_key.startswith(pfx):
                                diff_key = diff_key[len(pfx):]
                        diff_key = diff_key.split('.')[0]  # remove extension

                        # Map difficulty rank to name (from _difficulty field in BeatmapLevelData)
                        # The template uses numeric difficulty ranks (0-4)
                        # Custom songs use difficulty names ("Easy", "Normal", etc.)
                        template_diffs_map[diff_key] = path_id

    # ── Replace beatmaps for matching difficulties ────
    # The template has number-based difficulty references (0-4)
    # Custom songs have name-based difficulties
    # We need to match by difficulty name
    replaced = 0
    for path_id, reader in cab.objects.items():
        tt = reader.read_typetree()
        m_name = tt.get('m_Name', '')

        if reader.class_id == 49 and '.beatmap' in m_name:
            raw = reader.get_raw_data()
            if len(raw) > 8:
                fn_len = struct.unpack_from('<I', raw, 0)[0]
                fn_end = 4 + fn_len + 1

                orig_fn = raw[4:4 + fn_len].decode('ascii', errors='replace')
                diff_key = orig_fn
                for pfx in ['100Bills', '100bills']:
                    if diff_key.startswith(pfx):
                        diff_key = diff_key[len(pfx):]
                diff_key = diff_key.split('.')[0]

                # Map numeric difficulty rank to name
                if diff_key.isdigit():
                    diff_name = DIFFICULTY_RANKS.get(int(diff_key), diff_key)
                else:
                    diff_name = diff_key

                # Check if custom song has this difficulty
                if diff_name in custom_diffs:
                    custom_data = custom_diffs[diff_name]
                    # Strip _events (PS4 uses separate lightshow data) and _customData
                    try:
                        beatmap_json = json.loads(custom_data)
                        if '_events' in beatmap_json:
                            del beatmap_json['_events']
                        if '_customData' in beatmap_json:
                            del beatmap_json['_customData']
                        # V2→V3 conversion: _notes → colorNotes + colorNotesData
                        v3 = {'version': '4.0.0'}
                        data_map = {}; data_list = []; notes = []
                        for n in beatmap_json.get('_notes', []):
                            key = (n.get('_lineIndex',0), n.get('_lineLayer',0), n.get('_type',0), n.get('_cutDirection',1))
                            if key not in data_map:
                                data_map[key] = len(data_list)
                                entry = {}
                                if key[0]!=0: entry['x']=key[0]
                                if key[1]!=0: entry['y']=key[1]
                                if key[2]!=0: entry['c']=key[2]
                                if key[3]!=1: entry['d']=key[3]
                                data_list.append(entry)
                            note = {'b': n['_time']}
                            idx = data_map[key]
                            if idx != 0: note['i'] = idx
                            notes.append(note)
                        v3['colorNotes'], v3['colorNotesData'] = notes, data_list
                        # Obstacles
                        obs_map = {}; obs_list = []; v3_obs = []
                        for o in beatmap_json.get('_obstacles', []):
                            entry = {'d':o.get('_duration',1.0), 'w':o.get('_width',1), 'h':5}
                            key = (entry['d'],entry['w'],entry['h'])
                            if key not in obs_map:
                                obs_map[key]=len(obs_list); obs_list.append(entry)
                            idx = obs_map[key]
                            ob = {'b': o['_time']}
                            if idx != 0: ob['i'] = idx
                            v3_obs.append(ob)
                        v3['obstacles'], v3['obstaclesData'] = v3_obs, obs_list
                        for t in ['bombNotes','bombNotesData','chains','chainsData','arcs','arcsData','spawnRotations','spawnRotationsData']:
                            v3[t] = []
                        custom_data = json.dumps(v3).encode('utf-8')
                    except:
                        pass

                    # FIX: m_Script is JUST gzip data — no decompressed_size prefix!
                    compressed = gzip.compress(custom_data)

                    # Use save_typetree for proper serialization (avoids set_raw_data bugs)
                    tt = reader.read_typetree()
                    tt['m_Script'] = compressed.decode('utf-8', 'surrogateescape')
                    reader.save_typetree(tt)
                    replaced += 1
                    print(f"  ✅ Replaced: {diff_name} ({orig_fn})")

    changes += replaced
    cab.mark_changed()

    # ── Save ────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{level_id}.bundle"
    result = bf.save()
    if isinstance(result, bytes):
        output.write_bytes(result)
        print(f"\n  Saved: {output} ({len(result):,} bytes)")
    else:
        print(f"\n  Save returned: {result}")

    print(f"\n=== Converted: {song_name} -> {level_id} ({changes} changes, {replaced} beatmaps) ===")

if __name__ == '__main__':
    main()
