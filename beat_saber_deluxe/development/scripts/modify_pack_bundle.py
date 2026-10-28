#!/usr/bin/env python3
import UnityPy, os, shutil, sys

aa_dir = '/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/'
bundle_path = os.path.join(aa_dir, 'therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle')

# Create a working copy
work_path = '/tmp/rolling_modded.bundle'
shutil.copy2(bundle_path, work_path)

env = UnityPy.load(work_path)
bf = env.files[list(env.files.keys())[0]]
cab = bf.files['CAB-d32c331c74cd56a737f31cd4824898fc']

# Find the startmeup BeatmapLevelSO and modify it
found_target = False
for pid, reader in cab.objects.items():
    try:
        tt = reader.read_typetree()
        if '_previewDifficultyBeatmapSets' not in tt:
            continue

        name = tt.get('m_Name', '')
        song_name = tt.get('_songName', '')

        # Find startmeup
        if 'startmeup' not in name.lower() and 'start me up' not in song_name.lower():
            continue

        print(f"Found: {name} (PID={pid})")
        print(f"  songName: {song_name}")
        found_target = True

        existing_sets = tt['_previewDifficultyBeatmapSets']
        print(f"  Existing preview sets: {len(existing_sets)}")

        # Get the Standard characteristic reference
        standard_set = existing_sets[0]
        standard_char_ref = standard_set['_beatmapCharacteristic']
        print(f"  Standard char ref: m_FileID={standard_char_ref.get('m_FileID', '?')}, m_PathID={standard_char_ref.get('m_PathID', '?')}")

        # Clone the preview difficulties from Standard
        standard_diffs = list(standard_set.get('_previewDifficultyBeatmaps', []))

        # Add OneSaber and 90Degree preview sets
        for mode in ['OneSaber', '90Degree']:
            new_set = {
                '_beatmapCharacteristic': {
                    'm_FileID': standard_char_ref['m_FileID'],
                    'm_PathID': standard_char_ref['m_PathID'],
                },
                '_previewDifficultyBeatmaps': standard_diffs
            }
            existing_sets.append(new_set)
            print(f"  Added preview set for: {mode}")

        tt['_previewDifficultyBeatmapSets'] = existing_sets
        reader.save_typetree(tt)
        print("  Saved modified BeatmapLevelSO")
        break
    except Exception as e:
        print(f"  Error: {e}")

if not found_target:
    print("StartMeUp BeatmapLevelSO not found!")
    # List all BeatmapLevelSOs
    print("\nAll BeatmapLevelSOs in bundle:")
    for pid, reader in cab.objects.items():
        try:
            tt = reader.read_typetree()
            if '_previewDifficultyBeatmapSets' in tt:
                print(f"  PID={pid}: m_Name='{tt.get('m_Name', '?')}', songName='{tt.get('_songName', '?')}'")
        except:
            pass
else:
    # Save the modified bundle
    output_path = '/workspace/beat_saber_deluxe/custom_songs/rolling_pack_modded.bundle'
    # Save using save_bundle from the pipeline
    sys.path.insert(0, '/workspace/beat_saber_deluxe/tools')
    from full_custom_song_pipeline import save_bundle
    save_bundle(bf, output_path)
    print(f"\nSaved modified bundle to: {output_path}")

    # Verify
    env2 = UnityPy.load(output_path)
    bf2 = env2.files[list(env2.files.keys())[0]]
    cab2 = bf2.files['CAB-d32c331c74cd56a737f31cd4824898fc']
    for pid, reader in cab2.objects.items():
        try:
            tt = reader.read_typetree()
            if tt.get('m_Name', '').lower().startswith('startmeup'):
                sets = tt.get('_previewDifficultyBeatmapSets', [])
                print(f"\nVerification - Preview sets: {len(sets)}")
                for s in sets:
                    print(f"  Char ref m_PathID={s['_beatmapCharacteristic']['m_PathID']}, diffs={len(s.get('_previewDifficultyBeatmaps', []))}")
        except:
            pass
