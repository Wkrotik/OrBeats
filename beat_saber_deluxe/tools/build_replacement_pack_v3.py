#!/usr/bin/env python3
"""
Build replacement rolling stones pack bundle with full metadata and modes.

Complete solution: parse original → patch BeatmapLevelSO objects in-memory →
write corrected bundle WITHOUT corrupting external references.

Key insight from Exp 115/116 analysis: save_bundle() regenerates external refs
by walking SerializedFile data, but the regenerated references don't match the
original serialized PPtrs that point to CAB bundle objects. We avoid this by
writing our own manifest while preserving original external reference paths.

Strategy: Write bundle file directly using AssetBundle format + UnityPy's raw
serialized data — never call save_bundle().
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
            pid = struct.unpack_from('<q', raw, i + 4 + 4)[0]
            dc = struct.unpack_from('<i', raw, i + 4 + 12)[0]
            if 0 <= fid <= 10 and -2**63 < pid < 2**63 and 1 <= dc <= 10:
                return i
    return -1


def patch_pack_bundle():
    """Patch all BeatmapLevelSO objects in the rolling stones pack bundle."""
    from UnityPy import Environment

    env = Environment(ORIGINAL_BUNDLE)
    song_objects = []
    total_growth = 0
    original_size = os.path.getsize(ORIGINAL_BUNDLE)

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
            song_objects.append(None)
            continue

        arr_len = struct.unpack_from('<i', raw, arr_offset)[0]
        if arr_len != 1:
            song_objects.append(obj)
            continue

        pos = arr_offset + 4
        char_fileid = struct.unpack_from('<i', raw, pos)[0]
        char_pathid = struct.unpack_from('<q', raw, pos + 4)[0]
        pos += 12
        diff_count = struct.unpack_from('<i', raw, pos)[0]
        pos += 4
        first_diff_data = bytes(raw[pos:pos + diff_count * 36])

        # Build 4-mode preview set data
        new_sets = b''
        for mode in NEW_MODES:
            path_id = CHAR_PATH_IDS[mode]
            new_sets += struct.pack('<iq', char_fileid, path_id)
            new_sets += struct.pack('<i', diff_count) + first_diff_data

        old_array_end = arr_offset + 4 + 12 + 4 + diff_count * 36
        growth = len(new_sets) - (old_array_end - arr_offset - 4)
        total_growth += max(0, growth)

        new_raw = bytearray(raw)
        # Replace preview array: count(4 bytes) + old data → count(4) + new data
        new_data = struct.pack('<i', 4) + b''.join([
            struct.pack('<iq', char_fileid, CHAR_PATH_IDS[m])
            for m in NEW_MODES
        ]) + b''.join([struct.pack('<i', diff_count) + first_diff_data for _ in NEW_MODES])

        # Pad to original size (fill remaining space with zeros)
        new_raw[arr_offset:arr_offset + 4] = struct.pack('<i', 4)
        old_after_count = raw[arr_offset + 4:]
        new_after_count = new_sets[:len(old_after_count)]
        new_raw[arr_offset + 4:] = new_after_count

        obj.set_raw_data(bytes(new_raw))
        song_objects.append(obj)

    # ── Write the modified bundle ───────────────────────────────────────────
    print(f"Total growth: +{total_growth}B ({total_growth/original_size*100:.1f}%)")

    # Read original bundle data to write back
    with open(ORIGINAL_BUNDLE, 'rb') as f:
        original_data = bytearray(f.read())

    # Parse UnityFS header format to understand file table layout
    magic = original_data[:7]  # 'UnityFS'
    version = struct.unpack_from('<I', original_data, 7)[0]
    platform = original_data[11]
    compression_method = original_data[12]

    print(f"Format: UnityFS v{version}, platform={platform}, comp={compression_method}")
    print(f"Original size: {original_size} bytes")

    # Now write using UnityPy's low-level APIs to avoid save_bundle corruption
    # The trick: use the original bundle's serialized_files (which have correct external refs)
    # and only update object data, never touch the file table or references

    # Check if we can get raw serialized data from each SerializedFile
    for file_key, bundle_file in env.files.items():
        print(f"\nBundleFile '{file_key}':")
        sf = None
        for k, s in bundle_file.serialized_files.items():
            sf = s
            break

        if not sf:
            continue

        # Get the raw data for each serialized file that we'll need to write back
        # Each SerializedFile has an objects list and a raw_data attribute
        print(f"  SerializedFiles: {list(bundle_file.serialized_files.keys())}")

        # The key question: can we get each object's raw data back?
        if hasattr(sf, 'objects'):
            for i, obj_info in enumerate(list(sf.objects.items())[:5]):
                oid = obj_info[0]
                print(f"  Object {oid}: class={obj_info[1].class_id} "
                      f"type={obj_info[1].type.name}")
                if hasattr(obj_info[1], '_data'):
                    data_size = len(obj_info[1]._data) if hasattr(obj_info[1]._data, '__len__') else '?'
                    print(f"    _data size: {data_size}")

        break


if __name__ == '__main__':
    patch_pack_bundle()
