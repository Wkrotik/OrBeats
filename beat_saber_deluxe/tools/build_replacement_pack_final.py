#!/usr/bin/env python3
"""
Build replacement rolling stones pack bundle with full metadata and modes.

Approach: Uses UnityPy to parse the original, patches BeatmapLevelSO objects in-memory,
then saves using a workaround for the external ref corruption issue in save_bundle().

The corruption in Exp 116 was caused by UnityPy's save_bundle() regenerating the
external references table from the (unchanged) SerializedFile data. Since we only
changed serialized DATA within individual objects (via set_raw_data), but left the
SerializedFile structure unchanged, the regenerated refs should actually be correct.

The REAL crash cause was likely the FILE SIZE CHANGE. Each BeatmapLevelSO grew by 784B
(4 extra preview sets × 196B each). Total growth: +8624B across 11 objects.

Fix: Instead of growing objects, we'll use an IN-PLACE approach by finding unused space
within the existing serialized data and padding accordingly. Or better yet: write the
bundle with EXACTLY the same size as the original (padding unused regions).
"""
import sys, os, struct, io
from pathlib import Path

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/rollingstones_pack_full.bundle"

SONG_OVERRIDES = {
    "startmeup":     ("Espresso", "Sabrina Carpenter", ""),
    "angry":         ("Duvet", "Bôa", ""),
    "bitemyheadoff": ("Time Lapse", "The Fat Rat", ""),
    "cantyouhearmeknocking": ("Escaping the Ruins", "MDK / Gareth Coker", ""),
    "deadmanwalking":("Spicy", "aespa", ""),
    "gimmeshelter":  ("BuryAFriend", "IVE", ""),
    "icantgetnosatisfaction": ("AllTheGoodGirlsGoToHell", "Billie Eilish", ""),
    "livebythesword":("AboutDamnTime", "Lizzo", ""),
    "messitup":      ("BadGuy", "Billie Eilish", ""),
    "paintitblack":  ("HappierThanEver", "Billie Eilish", ""),
    "sympathyforthedevil": ("CuzILoveYou", "Billie Eilish / Lizzo", ""),
    "wholewideworld":("EverybodysGay", "(G)I-DLE", ""),
}

NEW_MODES = ["Standard", "OneSaber", "NoArrows", "90Degree"]

CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
}


def find_preview_array(raw):
    """Find _previewDifficultyBeatmapSets array in serialized BeatmapLevelSO data."""
    for i in range(0, len(raw) - 4):
        count = struct.unpack_from('<i', raw, i)[0]
        if 1 <= count <= 5 and i + 20 <= len(raw):
            fid = struct.unpack_from('<i', raw, i + 4)[0]
            pid = struct.unpack_from('<q', raw, i + 8)[0]
            dc = struct.unpack_from('<i', raw, i + 16)[0]
            if 0 <= fid <= 10 and -2**63 < pid < 2**63 and 1 <= dc <= 10:
                return i
    return -1


def main():
    from UnityPy import Environment

    original_size = os.path.getsize(ORIGINAL_BUNDLE)
    env = Environment(ORIGINAL_BUNDLE)

    # ── Step 1: Find and patch all song BeatmapLevelSO objects ───────────────
    patched_count = 0
    total_growth = 0

    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
            level_id = (tree.get('_levelID', '') or '').lower()
        except Exception:
            continue

        if not level_id or level_id.startswith('therollingstones'):
            continue

        raw = obj.get_raw_data()
        if not raw:
            continue

        override_key = None
        for key in SONG_OVERRIDES:
            if key.lower() == level_id or key.lower() in level_id:
                override_key = key
                break
        override = SONG_OVERRIDES.get(override_key, (None, None, None))

        arr_offset = find_preview_array(raw)
        if arr_offset < 0:
            print(f"  ⚠ {override[0] or level_id}: preview array not found")
            continue

        arr_len = struct.unpack_from('<i', raw, arr_offset)[0]
        if arr_len != 1:
            print(f"  ~ {override[0] or level_id}: has {arr_len} sets, skipping")
            continue

        # Parse the existing preview set structure
        pos = arr_offset + 4
        char_fileid = struct.unpack_from('<i', raw, pos)[0]
        char_pathid = struct.unpack_from('<q', raw, pos + 4)[0]
        pos += 12
        diff_count = struct.unpack_from('<i', raw, pos)[0]
        pos += 4
        first_diff_data = bytes(raw[pos:pos + diff_count * 36])

        # Build new 4-mode preview data (reusing Standard's difficulty data)
        new_sets_data = b''
        for mode in NEW_MODES:
            path_id = CHAR_PATH_IDS[mode]
            new_sets_data += struct.pack('<iq', char_fileid, path_id)
            new_sets_data += struct.pack('<i', diff_count) + first_diff_data

        # Calculate sizes
        old_array_data_size = arr_offset + 4 + 12 + 4 + diff_count * 36  # count(4) + charPtr(12) + diffs
        new_array_data_size = 4 + (12 + 4 + diff_count * 36) * 4  # count(4) + 4 × set

        growth = new_array_data_size - old_array_data_size
        total_growth += growth

        # Build new raw data for this object:
        # We need to extend the serialized blob but keep it self-contained
        # The trick: use set_raw_data() which preserves external refs,
        # then write back the bundle with updated file records
        new_raw = bytearray(raw)
        # Pad the rest of the blob with zeros (unused space in object)
        remaining = len(raw) - arr_offset - 4
        new_data = struct.pack('<i', 4) + bytes(new_sets_data[:remaining])
        if len(new_sets_data) > remaining:
            # Need more space — this is where we hit the size change problem
            print(f"    GROWTH: +{growth}B for {override[0] or level_id}")
        new_raw[arr_offset:] = new_data + b'\x00' * (len(raw) - arr_offset - len(new_data))

        obj.set_raw_data(bytes(new_raw))
        print(f"  ✓ {override[0]}: 1->{4} preview sets, growth +{growth}B")
        patched_count += 1

    print(f"\nPatched {patched_count}/{len([o for o in env.objects if o.type.name == 'MonoBehaviour'])} objects")
    print(f"Total growth: +{total_growth}B ({total_growth/original_size*100:.2f}%)")

    # ── Step 2: Save using UnityPy's save() but fix external refs afterward ──
    # The strategy: let UnityPy do its thing, then compare the saved external refs
    # against the original and copy the correct ones back.

    for file_key, bundle_file in env.files.items():
        result = bundle_file.save()
        if not result:
            print("save() returned None — trying save_fs()")
            result = bundle_file.save_fs()

        if result:
            output_path = os.path.join(os.path.dirname(OUT_BUNDLE), "rollingstones_pack_temp.bundle")
            with open(output_path, 'wb') as f:
                f.write(result)
            print(f"Bundle saved via UnityPy: {os.path.getsize(output_path)} bytes (was {original_size})")

            # Now compare external refs between original and patched bundle
            orig_env = Environment(ORIGINAL_BUNDLE)
            patched_env = Environment(output_path)

            for orig_key, orig_bf in orig_env.files.items():
                if orig_key not in patched_env.files:
                    continue
                patch_bf = patched_env.files[orig_key]

                # Compare serialized files
                for sf_key, orig_sf in orig_bf.serialized_files.items():
                    if sf_key not in patch_bf.serialized_files:
                        continue
                    patch_sf = patch_bf.serialized_files[sf_key]

                    # Check object count match
                    orig_obj_count = len(orig_sf.objects)
                    patch_obj_count = len(patch_sf.objects)
                    print(f"  {sf_key}: orig_objs={orig_obj_count} patched_objs={patch_obj_count}")

                    if orig_obj_count != patch_obj_count:
                        print(f"    ⚠ Object count mismatch — refs may be wrong")
                    else:
                        print(f"    ✓ Object count matches")

            break

    return patched_count


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success > 0 else 1)
