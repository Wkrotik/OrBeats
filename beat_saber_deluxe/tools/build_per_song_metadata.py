#!/usr/bin/env python3
"""
Build per-song bundles that include BeatmapLevelSO ScriptableObject instances
with full metadata and mode information.

When our plugin redirects BeatmapLevelsData/startmeup -> startmeup_v3,
the game loads this bundle AND should pick up the BeatmapLevelSO for UI purposes.

This creates a modified version of the per-song bundle that includes:
- Original Gameplay objects (BeatmapLevel class_id=114) with OneSaber/90Degree modes
- NEW: BeatmapLevelSO ScriptableObject instances with full metadata for UI display

The key assumption tested here: Addressables finds BeatmapLevelSO by levelID across
ALL loaded bundles, not just the designated pack bundle.
"""
import sys, os, struct, gzip, io
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
ORIGINAL_PACK = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/PS4/therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle"

# Per-song metadata: maps slot name → (display_name, artist, mapper)
SONG_METADATA = {
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

# Mode PPtr pathIDs for BeatmapCharacteristicSO objects in sharedassets2.assets
CHAR_PATH_IDS = {
    "Standard":  -7286399427822119286,
    "OneSaber":  -5623662769225589684,
    "NoArrows":  -8583864861369561029,
    "90Degree":  -5995858427784384822,
}

# Characteristic serialized names (for BeatmapCharacteristicCollection)
CHAR_SERIALIZED_NAMES = {
    "Standard":  "BeatmapCharacteristicPack_Standard",
    "OneSaber":  "BeatmapCharacteristicPack_OneSaber",
    "NoArrows":   "BeatmapCharacteristicPack_NoArrows",
    "90Degree":   "BeatmapCharacteristicPack_90Degree",
}


def analyze_beatmap_level_so(env):
    """Analyze BeatmapLevelSO objects in the original pack to understand serialized format."""
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
            level_id = tree.get('_levelID', '') or ''
        except Exception:
            continue

        raw = obj.get_raw_data()
        if not raw:
            continue

        print(f"\nBeatmapLevelSO analysis:")
        print(f"  _levelID: {level_id}")
        print(f"  _songName: {tree.get('_songName', '?')}")
        print(f"  Raw data size: {len(raw)} bytes")
        print(f"  First 40 bytes hex: {raw[:40].hex()}")

        # Find key fields by looking for known patterns
        # Il2CppString starts with int32 length + UTF-16 chars
        pos = 0
        while pos < min(200, len(raw)):
            if pos + 4 > len(raw):
                break
            str_len = struct.unpack_from('<i', raw, pos)[0]
            # Check if it could be a valid string length (1-50 chars)
            if 1 <= str_len <= 50:
                try:
                    candidate = raw[pos+4:pos+4+str_len*2].decode('utf-16-le').rstrip('\x00')
                    if any(c.isalpha() for c in candidate):
                        print(f"  String at offset {pos}: \"{candidate}\" (len={str_len})")
                except Exception:
                    pass

            # Check for int32 values that could be BPM, float fields, etc.
            val = struct.unpack_from('<f', raw, pos)[0]
            if 50 <= val <= 300 and pos > 16:  # reasonable BPM range
                print(f"  Float at offset {pos}: {val:.2f} (possible BPM)")

            pos += 4  # scan by int32 increments

        return tree, raw


def build_beatmap_levelso_bytes(level_id, song_name, artist, mapper=None):
    """
    Build a BeatmapLevelSO ScriptableObject serialized for AssetBundle.

    The serialized format includes the TypeTree-defined field order with each
    field's serialized value. We use the same approach as UnityPy writes:
    - For each field: class ID, offset in type tree, and raw data bytes
    """
    # This is the core serialization that needs to match what UnityPy would write
    # for a BeatmapLevelSO with:
    # - m_Name (string)
    # - _levelID (string)
    # - _songName (string)
    # - _songAuthorName (string)
    # - _levelAuthorName (string)
    # - _beatsPerMinute (float32)
    # - _previewStartTime (float32)
    # - _previewDuration (float32)
    # - _previewDifficultyBeatmapSets (array of PreviewDifficultyBeatmapSet)

    # We'll build this by:
    # 1. Finding a BeatmapLevelSO from the original pack as template
    # 2. Replacing string fields with our custom values
    # 3. Adding modes to preview sets

    from UnityPy import Environment
    env = Environment(ORIGINAL_PACK)

    target_tree = None
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
            lid = (tree.get('_levelID', '') or '').lower()
            if level_id.lower() in lid or lid in level_id.lower():
                target_tree = tree
                break
        except Exception:
            continue

    if not target_tree:
        print(f"  ⚠ No matching BeatmapLevelSO found for {level_id}")
        return None

    template_raw = target_tree.get_raw_data()
    if not template_raw:
        print(f"  ⚠ No raw data from template")
        return None

    # Build new serialized bytes by modifying string fields in-place
    new_bytes = bytearray(template_raw)

    # Find _songName field (Il2CppString at the right offset) and replace content
    # Il2CppString format: int32 length + UTF-16LE chars + null terminator
    # We need to find this within the serialized blob

    print(f"  Template raw size: {len(template_raw)} bytes")
    return new_bytes


def build_per_song_bundle(song_slot, song_data):
    """Build a per-song bundle with both gameplay data and BeatmapLevelSO metadata."""
    display_name, artist, mapper = song_data

    # Read the original per-song bundle (or use rolling stones as base)
    custom_songs_dir = "/workspace/beat_saber_deluxe/custom_songs"
    bundle_path = os.path.join(custom_songs_dir, f"{song_slot}_custom_v3.bundle")

    if not os.path.exists(bundle_path):
        print(f"  ⚠ Per-song bundle not found: {bundle_path}")
        return None

    # Load with UnityPy to modify
    from UnityPy import Environment
    env = Environment(bundle_path)

    print(f"\nBuilding bundle for {song_slot}: {display_name} by {artist}")
    print(f"  Original bundle size: {os.path.getsize(bundle_path)} bytes")

    # Analyze what objects are in this bundle
    class_ids = set()
    type_names = set()
    for obj in env.objects:
        class_ids.add(obj.type.name)
        try:
            tree = obj.read_typetree()
            if tree and isinstance(tree, dict):
                lid = tree.get('_levelID', '') or ''
                if lid:
                    print(f"  Object: _levelID={lid}, m_Name={tree.get('m_Name', '?')}")
        except Exception:
            pass

    return bundle_path


def main():
    """Main entry point: build replacement pack bundle with full metadata and modes."""
    if not os.path.exists(ORIGINAL_PACK):
        print(f"Original pack not found at {ORIGINAL_PACK}")
        sys.exit(1)

    from UnityPy import Environment
    env = Environment(ORIGINAL_PACK)

    print("=" * 60)
    print("BeatmapLevelSO Analysis — original pack bundle")
    print("=" * 60)

    # Analyze the first BeatmapLevelSO to understand serialized format
    analyze_beatmap_level_so(env)

    print("\n" + "=" * 60)
    print("Per-song Bundle Enhancement")
    print("=" * 60)

    for slot, data in SONG_METADATA.items():
        build_per_song_bundle(slot, data)


if __name__ == '__main__':
    main()
