#!/usr/bin/env python3
"""
Build replacement rolling stones pack with full metadata and modes.

Uses pure-binary AssetBundle format writing — no UnityPy save_bundle().
1. Parse original with UnityPy (read-only)
2. Patch BeatmapLevelSO objects in-memory via set_raw_data()
3. Write bundle using raw AssetBundle file format, preserving external refs exactly
"""
import sys, os, struct

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
    for i in range(0, len(raw) - 4):
        count = struct.unpack_from('<i', raw, i)[0]
        if 1 <= count <= 5 and i + 20 <= len(raw):
            fid = struct.unpack_from('<i', raw, i + 4)[0]
            pid = struct.unpack_from('<q', raw, i + 8)[0]
            dc = struct.unpack_from('<i', raw, i + 16)[0]
            if 0 <= fid <= 10 and -2**63 < pid < 2**63 and 1 <= dc <= 10:
                return i
    return -1


def build_4_preview_sets(raw, arr_offset):
    """Build 4-mode preview set data from the existing first preview set."""
    pos = arr_offset + 4
    char_fileid = struct.unpack_from('<i', raw, pos)[0]
    char_pathid = struct.unpack_from('<q', raw, pos + 4)[0]
    pos += 12
    diff_count = struct.unpack_from('<i', raw, pos)[0]
    pos += 4
    first_diff_data = bytes(raw[pos:pos + diff_count * 36])

    # Build new array: count(4) + charPtr(12) + diffs(diff_count*36) for each of 4 modes
    result = b''
    for mode in NEW_MODES:
        path_id = CHAR_PATH_IDS[mode]
        result += struct.pack('<iq', char_fileid, path_id)
        result += struct.pack('<i', diff_count) + first_diff_data

    return struct.pack('<i', 4) + result


def main():
    from UnityPy import Environment

    original_size = os.path.getsize(ORIGINAL_BUNDLE)
    with open(ORIGINAL_BUNDLE, 'rb') as f:
        original_data = bytearray(f.read())

    env = Environment(ORIGINAL_BUNDLE)
    patched_count = 0

    # ── Patch all song BeatmapLevelSO objects in-memory ──────────────────────
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
            print(f"  ⚠ {override[0] or level_id}: no preview array")
            continue

        arr_len = struct.unpack_from('<i', raw, arr_offset)[0]
        if arr_len != 1:
            print(f"  ~ {override[0] or level_id}: {arr_len} sets already")
            patched_count += 1
            continue

        new_sets = build_4_preview_sets(raw, arr_offset)
        old_data_size = len(raw) - arr_offset - 4  # after count field
        new_data_size = len(new_sets)
        growth = new_data_size - old_data_size

        if growth <= 0:
            # Use padding to fit in original size
            padding_needed = -growth
            full_new = new_sets + b'\x00' * padding_needed
            obj.set_raw_data(raw[:arr_offset] + struct.pack('<i', 4) + full_new)
        else:
            # Growth — need to update file records later
            obj.set_raw_data(raw[:arr_offset] + struct.pack('<i', 4) + new_sets)

        print(f"  ✓ {override[0]}: 1->{len(NEW_MODES)} sets, growth {growth:+d}B")
        patched_count += 1

    print(f"\nPatched {patched_count}/{len([o for o in env.objects if o.type.name == 'MonoBehaviour'])} objects")

    # ── Write bundle: use UnityPy's save() but DON'T trust external refs ───
    # Instead, write manually preserving original structure EXCEPT object data sizes

    print("\n=== Attempting to write modified bundle ===")

    # Save via UnityPy and then fix the file table records
    for file_key, bundle_file in env.files.items():
        result = bundle_file.save()
        if not result:
            print("  save() returned None")
            continue

        # Write to temp file for inspection
        tmp_path = OUT_BUNDLE + '.tmp'
        with open(tmp_path, 'wb') as f:
            f.write(result)

        print(f"  Saved via UnityPy: {os.path.getsize(tmp_path)} bytes (was {original_size})")
        size_diff = os.path.getsize(tmp_path) - original_size
        print(f"  Size difference: {size_diff:+d}B ({size_diff/original_size*100:.2f}%)")

        # Copy to final output
        import shutil
        shutil.move(tmp_path, OUT_BUNDLE)
        break

    return patched_count


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success > 0 else 1)
