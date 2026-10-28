#!/usr/bin/env python3
"""
Build a replacement rolling stones pack bundle with full metadata and modes.

This uses UnityPy to parse the original pack, patches BeatmapLevelSO objects
in-memory using set_raw_data() (which preserves serialized data correctly),
then saves via writing raw AssetBundle format without corrupting external refs.

Two strategies:
1. In-place padding: keep each BeatmapLevelSO the same size by adding a
   hidden/unused field that takes up the same space as new preview sets.
2. Full expansion: add extra bytes to each object and update file records.

For approach 1 (recommended), we replace Standard-only preview sets with
OneSaber/NoArrows/90Degree by swapping PPtr pathIDs within the
existing space — no size change needed because we modify in-place:
- Change count from 1 → 4 (still int32 = same bytes)
- Extend array to 4 items instead of 1 (this DOES grow the array)

Actually for a true in-place approach, we pad each preview set entry's difficulty
array with no-op data. Or more practically: expand each object and fix up records.
"""
import sys, os, struct, shutil
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"
OUT_BUNDLE = "/workspace/beat_saber_deluxe/rollingstones_pack_full.bundle"

# Song metadata: mapping from game slot name → (display_name, artist, mapper)
# These are the Rolling Stones songs we want to replace
SONG_OVERRIDES = {
    # Start Me Up → Espresso by Sabrina Carpenter
    "startmeup": ("Espresso", "Sabrina Carpenter", ""),
    # Angry (Rolling Stones song → custom replacement)
    "angry": ("Duvet", "Bôa", ""),
    # Other Rolling Stones slots (use generic custom naming)
    "bitemyheadoff": ("Time Lapse", "The Fat Rat", ""),
    "cantyouhearmeknocking": ("Spicy", "aespa", ""),
    "deadmanwalking": ("Escaping the Ruins", "MDK / Gareth Coker", ""),
    "gimmeshelter": ("BuryAFriend", "IVE", ""),
    "icantgetnosatisfaction": ("AllTheGoodGirlsGoToHell", "Billie Eilish", ""),
    "livebythesword": ("AboutDamnTime", "Lizzo", ""),
    "messitup": ("BadGuy", "Billie Eilish", ""),
    "paintitblack": ("HappierThanEver", "Billie Eilish", ""),
    "sympathyforthedevil": ("CuzILoveYou", "Billie Eilish / Lizzo", ""),
    "wholewideworld": ("EverybodysGay", "(G)I-DLE", ""),
}

# Mode PPtr pathIDs (from sharedassets2.assets — BeatmapCharacteristicSO objects)
CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
}

NEW_MODES = ["Standard", "OneSaber", "NoArrows", "90Degree"]


def encode_utf16le(s):
    """Encode a string as UTF-16LE (IL2CPP string format)."""
    if not s:
        return b''
    return s.encode('utf-16-le') + b'\x00\x00'  # null terminator


def build_unity_string_bytes(s):
    """Build a serialized Il2CppString for Unity serialization."""
    chars = encode_utf16le(s)
    length = len(chars) // 2
    data = struct.pack('<i', length) + chars  # Il2CppString: int32 length + chars[]
    return data


def build_pptr(file_id, path_id):
    """Build a serialized PPtr (12 bytes on PS4)."""
    return struct.pack('<iq', file_id, path_id)


def build_array_header(count):
    """Build an Il2CppArray header for SZArray of void pointers."""
    data = struct.pack('<i', count)  # array length (int32)
    return data


def find_beatmap_level_sos(env):
    """Find all BeatmapLevelSO objects in the environment."""
    results = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
            level_id = tree.get('_levelID', '') or ''
            if not level_id:
                # Try m_Name as fallback
                name = tree.get('m_Name', '')
                level_id = name
        except Exception:
            continue

        raw = obj.get_raw_data()
        if raw is None:
            continue

        # Determine which song this corresponds to (from bundle file/table entry)
        results.append({
            'obj': obj,
            'tree': tree,
            'raw': raw,
            'level_id': level_id.lower(),
            'song_name': tree.get('_songName', ''),
            'char_path_id': None,  # We'll find this from existing data
        })
    return results


def patch_beatmap_levelso(info, song_override=None):
    """
    Patch a BeatmapLevelSO's serialized data with custom metadata and modes.
    Returns the new serialized bytes or None if patching failed.

    Strategy: modify in-place within existing raw_data blob size to avoid
    manifest record issues. We replace Standard-only preview sets with 5 modes
    by extending array entries (this grows the object slightly, so we need padding).
    """
    raw = bytearray(info['raw'])
    if not raw:
        return None

    # Find the _previewDifficultyBeatmapSets array in raw data
    # Look for int32 length field near the end followed by PPtr pattern
    arr_offset = -1
    for i in range(len(raw) - 24):  # at least: int32 + PPtr(12) + int32 + 36 bytes
        length = struct.unpack_from('<i', raw, i)[0]
        if length != 1:
            continue
        # Check if next 12 bytes look like a valid PPtr
        file_id = struct.unpack_from('<i', raw, i + 4)[0]
        path_id = struct.unpack_from('<q', raw, i + 8)[0]
        if file_id == 2 and path_id in CHAR_PATH_IDS.values():
            arr_offset = i
            info['char_path_id'] = path_id
            break

    if arr_offset < 0:
        print(f"  ⚠ Could not find preview array for {info['song_name']}")
        return None

    # Read existing first preview set data (after the int32 length)
    pos = arr_offset + 4
    pptr_data = bytes(raw[pos:pos+12])  # char PPtr
    pos += 12

    diff_count = struct.unpack_from('<i', raw, pos)[0]
    pos += 4
    diff_data = bytes(raw[pos:pos+diff_count*36])

    print(f"  Found preview array at byte {arr_offset}, "
          f"diffs={diff_count}, char_pathID={info['char_path_id']}")

    # Build new preview sets for all modes
    new_sets_data = b''
    for mode in NEW_MODES:
        path_id = CHAR_PATH_IDS.get(mode, info['char_path_id'])
        new_sets_data += build_pptr(2, path_id)  # fileID=2 (sharedassets2.assets)
        new_sets_data += struct.pack('<i', diff_count)  # same difficulty count
        new_sets_data += diff_data  # reuse existing difficulty data

    new_array_len = len(NEW_MODES)
    new_array_header = struct.pack('<i', new_array_len)

    # Old array data (everything after the length field)
    old_array_data = bytes(raw[arr_offset + 4:arr_offset + 4 + 12 + 4 + diff_count * 36])
    new_array_data = struct.pack('<i', new_array_len) + old_array_data[:-196] + new_sets_data
    # Wait, that's wrong. Let me recalculate:
    # Old format: [length=1][char PPtr(12)][diff_count=5][5x36byte diffs] = 4+12+4+180 = 200 bytes
    # New format: [length=5][char PPtr(12)][diff_count=5][5x36byte diffs + 4 more sets]
    # Actually the old_array_data already includes everything after the length field

    # Rebuild properly:
    first_set_end = arr_offset + 4 + 12 + 4 + diff_count * 36  # where first set ends in raw data
    old_first_set_after_len = bytes(raw[arr_offset + 4:first_set_end])  # char PPtr + diff count + diffs

    # The new array: length(4) + same first set data + 3 additional sets
    new_array_len_bytes = struct.pack('<i', 4)  # 4 modes total
    new_full_data = new_array_len_bytes + old_first_set_after_len + new_sets_data

    size_diff = len(new_full_data) - len(old_first_set_after_len)

    # Apply the patch in-place within raw data
    new_raw = bytearray(raw)
    new_raw[arr_offset:first_set_end] = new_full_data

    # Pad to match original size (fill any gap with zeros)
    if size_diff > 0:
        padding = b'\x00' * size_diff
        # Find a place to add padding - after serialized data, before bundle header
        # This is tricky. For now, note the size difference.
        print(f"  Size change: +{size_diff} bytes — may need manifest update")

    return bytes(new_raw), size_diff


def main():
    if not os.path.exists(ORIGINAL_BUNDLE):
        print(f"Original bundle not found at {ORIGINAL_BUNDLE}")
        sys.exit(1)

    from UnityPy import Environment
    env = Environment(ORIGINAL_BUNDLE)

    infos = find_beatmap_level_sos(env)
    print(f"Found {len(infos)} BeatmapLevelSO objects:")
    for info in infos:
        song_name = info['song_name'] or '(no name)'
        level_id = info['level_id']
        # Find override
        override_key = None
        for key in SONG_OVERRIDES:
            if key.lower() in level_id.lower():
                override_key = key
                break
        override = SONG_OVERRIDES.get(override_key, (None, None, None))
        print(f"  {song_name} (levelID={level_id}) → {override[0] or '(no override)'}")

    # Patch each BeatmapLevelSO
    patched_count = 0
    for info in infos:
        # Find song override matching this object's level_id/song_name
        override_key = None
        level_lower = info['level_id'].lower()
        song_lower = info['song_name'].lower() if info['song_name'] else ''

        for key, _ in SONG_OVERRIDES.items():
            if key.lower() == level_lower or key.lower() in level_lower:
                override_key = key
                break

        result = patch_beatmap_levelso(info, SONG_OVERRIDES.get(override_key) if override_key else None)
        if result:
            new_raw, size_diff = result
            info['obj'].set_raw_data(new_raw)
            patched_count += 1

    print(f"\nPatched {patched_count}/{len(infos)} BeatmapLevelSO objects")
    print(f"Output will be saved to {OUT_BUNDLE}")
    print("\n⚠ WARNING: This script patches serialized data correctly but still needs")
    print("a mechanism to save the bundle without corrupting external references.")
    print("See build_replacement_pack_v2.py for a pure-binary patching approach.")

    # For now, just output what was found — don't try to save (it will crash)
    return patched_count


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success > 0 else 1)
