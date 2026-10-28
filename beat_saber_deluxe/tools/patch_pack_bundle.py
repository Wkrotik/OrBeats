#!/usr/bin/env python3
"""
Patch the Rolling Stones pack bundle to add OneSaber, NoArrows, and 90Degree
to _previewDifficultyBeatmapSets for every BeatmapLevelSO.
(360Degree is excluded — unsupported on PS4 camera tracking.)

Uses binary patching on the Unity SerializedFile within the AssetBundle.
"""
import sys, os, struct, shutil
from UnityPy import Environment

RS_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/rollingstones_pack_modified.bundle"

# PPtr for characteristics (fileID=2 for sharedassets2.assets)
CHARS = [
    ("OneSaber",  -5623662769225589684),
    ("NoArrows",  -8583864861369561029),
    ("90Degree",  -5995858427784384822),
]

def get_raw_data(env):
    """Get raw byte data for each BeatmapLevelSO object."""
    results = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
            if not tree.get('_levelID'):
                continue
        except:
            continue

        raw = obj.get_raw_data()
        if raw is None:
            continue

        results.append({
            'obj': obj,
            'tree': tree,
            'raw': raw,
            'name': tree.get('_songName', '?'),
            'levelID': tree.get('_levelID', '?'),
            'preview_count': len(tree.get('_previewDifficultyBeatmapSets', [])),
        })
    return results

def find_array_offset(raw):
    """
    Find the _previewDifficultyBeatmapSets array in the raw byte data.
    The array length follows the PPtr for _beatmapCharacteristic in the
    last field before _previewDifficultyBeatmapSets.

    We look for the pattern: int32 length (will be 1) followed by a
    PPtr (int32 + int64) for the characteristic.

    Since we know the BeatmapLevelSO should have exactly 1 preview set,
    and the PPtr for Standard has specific values, we search for those.
    """
    # The _previewDifficultyBeatmapSets is a later field in BeatmapLevelSO.
    # After _cuttableBeatmapObjectsCount comes _previewDifficultyBeatmapSets.
    # The array starts with int32 length.
    # We search for the pattern: all bytes before the array + length field.

    # For a 1-element preview set array, the Standard PPtr is:
    # fileID=2 (int32), pathID=-7286399427822119286 (int64)
    # But this is inside the array item, so we need to find the array first.

    # Simpler approach: find the array length byte by scanning for int32=1
    # that could be an array length. We know the preview set array is large
    # (at least 200+ bytes for 1 set with 5 difficulties).

    # Look for int32=1 near the end of the raw data, followed by a PPtr-like
    # pattern (int32 + int64 with plausible values) + another array length.

    for i in range(len(raw) - 20):
        # Check: this int32 is 1 (array length)
        length = struct.unpack_from('<i', raw, i)[0]
        if length != 1:
            continue

        # After the length should be the preview set items.
        # Each item starts with a PPtr (int32 fileID + int64 pathID).
        # For Standard: fileID=2, pathID=-7286399427822119286
        file_id = struct.unpack_from('<i', raw, i + 4)[0]
        path_id = struct.unpack_from('<q', raw, i + 8)[0]

        if file_id == 2 and path_id == -7286399427822119286:
            # Check that after the PPtr comes another array length
            after_pptr = i + 4 + 8  # skip fileID + pathID
            if after_pptr + 4 <= len(raw):
                diff_len = struct.unpack_from('<i', raw, after_pptr)[0]
                if 1 <= diff_len <= 5:  # difficulty count
                    return i  # found it!

    return -1

def patch_bundle():
    print(f"Loading RS pack bundle...")
    env = Environment(RS_BUNDLE)

    infos = get_raw_data(env)
    print(f"Found {len(infos)} BeatmapLevelSO objects")

    for info in infos:
        print(f"  {info['name']}: {info['preview_count']} preview sets")

    if not infos:
        print("ERROR: No BeatmapLevelSO objects found!")
        return False

    # Get the raw file data from the BundleFile
    file_key = list(env.files.keys())[0]
    bundle_file = env.files[file_key]

    # Read the bundle file
    with open(RS_BUNDLE, 'rb') as f:
        bundle_data = bytearray(f.read())

    total_patch_size = 0
    patched_count = 0

    for info in infos:
        raw = info['raw']
        arr_offset = find_array_offset(raw)

        if arr_offset < 0:
            print(f"  ⚠ {info['name']}: Could not find preview array!")
            continue

        arr_len = struct.unpack_from('<i', raw, arr_offset)[0]
        if arr_len != 1:
            print(f"  - {info['name']}: array has {arr_len} entries, skipping")
            continue

        # The raw data for the 1st preview set (Standard)
        # Structure after array length (int32=1):
        #   PPtr _beatmapCharacteristic: int32 fileID + int64 pathID
        #   Array _previewDifficultyBeatmaps: int32 length + items
        #     Each item: _difficulty(int), _environmentNameIdx(int),
        #       _beatmapColorSchemeIdx(int), _noteJumpMovementSpeed(float),
        #       _noteJumpStartBeatOffset(float), _notesCount(int),
        #       _obstaclesCount(int), _bombsCount(int), _cuttableBeatmapObjectsCount(int)

        # Extract the Standard preview set data (everything after the length field)
        # We need to know where it ends to calculate the offset for new items.

        # Parse the first preview set:
        pos = arr_offset + 4  # skip array length (int32)

        # PPtr _beatmapCharacteristic: int32 + int64 = 12 bytes
        pptr_file_id = struct.unpack_from('<i', raw, pos)[0]
        pptr_path_id = struct.unpack_from('<q', raw, pos + 4)[0]
        pos += 12

        # Array _previewDifficultyBeatmaps: int32 length + items
        if pos >= len(raw):
            print(f"  ⚠ {info['name']}: raw data too short!")
            continue

        diff_count = struct.unpack_from('<i', raw, pos)[0]
        pos += 4  # skip length

        # Skip difficulty items (each is 9 fields × 4 bytes = 36 bytes)
        diff_data_size = diff_count * 36
        first_set_end = pos + diff_data_size

        print(f"  {info['name']}: array at byte {arr_offset}, "
              f"Standard char pathID={pptr_path_id}, "
              f"{diff_count} difficuties, first_set_end={first_set_end}")

        # Clalculate additional data for new preview sets
        # Each new set: PPtr(12 bytes) + diff_array_length(4) + diff_data
        # We'll add 1 difficulty entry per new set (36 bytes) for minimal size
        NEW_SETS = len(CHARS)
        new_sets_data = b''
        for name, path_id in CHARS:
            # PPtr: fileID=2
            new_sets_data += struct.pack('<iq', 2, path_id)
            # Array length: 1 (just one difficulty)
            new_sets_data += struct.pack('<i', 1)
            # Copy just the first difficulty entry from Standard
            first_diff_start = arr_offset + 4 + 12 + 4  # skip array_len + PPtr + diff_count
            new_sets_data += bytes(raw[first_diff_start:first_diff_start + 36])

        new_array_length = 1 + NEW_SETS  # 4 total
        new_array_data_size = (first_set_end - arr_offset - 4) + len(new_sets_data)

        print(f"    Adding {NEW_SETS} new preview sets, "
              f"total array data: {new_array_data_size} bytes")

        # Build the new array data
        old_array_data = bytes(raw[arr_offset + 4:first_set_end])
        new_array = struct.pack('<i', new_array_length) + old_array_data + new_sets_data

        # The size different between old and new array
        old_array_size = first_set_end - arr_offset
        new_array_size = len(new_array)
        size_diff = new_array_size - old_array_size

        # Replace in the raw data
        new_raw = bytearray(raw)
        new_raw[arr_offset:first_set_end] = new_array

        print(f"    Size change: {old_array_size} -> {new_array_size} "
              f"(+{size_diff} bytes)")

        # Now update the raw bytes in the object
        info['obj'].set_raw_data(bytes(new_raw))
        total_patch_size += size_diff
        patched_count += 1

    print(f"\nPatched {patched_count}/{len(infos)} objects, "
          f"total size increase: {total_patch_size} bytes")

    # Save the modified bundle
    if patched_count > 0:
        try:
            # Use UnityPy to re-pack the bundle
            result = bundle_file.save()
            if result:
                with open(OUT_BUNDLE, 'wb') as f:
                    f.write(result)
                print(f"Bundle saved to {OUT_BUNDLE} ({len(result)} bytes)")
                return True

            # Try alternative save method
            result = bundle_file.save_fs()
            if result:
                with open(OUT_BUNDLE, 'wb') as f:
                    f.write(result)
                print(f"Bundle saved via save_fs ({len(result)} bytes)")
                return True

        except Exception as e:
            print(f"Bundle save failed: {e}")

    return False

if __name__ == '__main__':
    success = patch_bundle()
    sys.exit(0 if success else 1)
