#!/usr/bin/env python3
"""
Memory Injection Prototype — Test Script

This script tests the memory scanning and patching logic for BeatmapLevelSO objects.
It simulates what the plugin would do in RAM after Addressables loads a bundle.

Key insight: We need to find BeatmapLevelSO objects by their type signature,
then patch their fields (song name, artist, modes) with Espresso metadata.
"""

import struct

# Simulated IL2CPP heap layout (what we'd see in actual PS4 memory)
class MockIL2CppHeap:
    """Simulates the IL2CPP managed object heap on PS4."""
    
    def __init__(self):
        self.objects = {}  # offset -> object_data
    
    def create_object(self, obj_type_id, fields):
        """Create a mock IL2CPP object with given type and fields."""
        import random
        offset = random.randint(0x10000, 0xFFFFFFFF)
        self.objects[offset] = {
            'type_id': obj_type_id,
            'fields': fields,
            'size': sum(len(v) if isinstance(v, bytes) else 8 for v in fields.values()) + 0x10  # header
        }
        return offset
    
    def get_object(self, offset):
        """Get object at given offset."""
        return self.objects.get(offset)

# BeatmapLevelSO field offsets (from il2cpp dump)
BEATMAP_LEVEL_SO_FIELDS = {
    'version': 0x18,      # int32
    'levelID': 0x20,      # string*
    'songName': 0x28,     # string*
    'songSubName': 0x30,  # string*
    'songAuthorName': 0x38,  # string*
    'levelAuthorName': 0x40,  # string*
    'previewAudioClip': 0x48,  # AudioClip*
    'beatsPerMinute': 0x50,  # float
    'integratedLufs': 0x54,  # float
    'songTimeOffset': 0x58,  # float
    'shuffle': 0x5C,  # float
    'shufflePeriod': 0x60,  # float
    'previewStartTime': 0x64,  # float
    'previewDuration': 0x68,  # float
    'songDuration': 0x6C,  # float
    'coverImage': 0x70,  # Sprite*
    'environmentName': 0x78,  # EnvironmentName (int)
    'allDirectionsEnvironmentName': 0x80,  # EnvironmentName (int)
    'environmentNames': 0x88,  # EnvironmentName[]*
    'colorSchemes': 0x90,  # ColorScheme[]*
    'previewDifficultyBeatmapSets': 0x98,  # PreviewDifficultyBeatmapSet[]*
}

# Type IDs (from il2cpp dump)
TYPE_BEATMAP_LEVEL_SO = 11680
TYPE_STRING = 4  # System.String
TYPE_FLOAT = 7  # System.Single
TYPE_INT32 = 5  # System.Int32

def encode_utf8_string(s):
    """Encode string as UTF-8 with null terminator (IL2CPP string format)."""
    return s.encode('utf-8') + b'\x00'

def build_espresso_blob():
    """Build Espresso BeatmapLevelSO blob (same as in pipeline)."""
    # This is the same blob builder used in full_custom_song_pipeline.py
    SCRIPT_PATHID_CORRECT = 2140275054477726686
    
    CHAR_PATH_IDS = {
        "Standard": -7286399427822119286,
        "OneSaber": -5623662769225589684,
        "NoArrows": -8583864861369561029,
        "90Degree": -5995858427784384822,
        "360Degree": 4533580413116749821,
    }
    
    b = bytearray()
    b += struct.pack('<i', 0) + struct.pack('<q', 0) + struct.pack('<I', 1)
    b += struct.pack('<i', 1) + struct.pack('<q', SCRIPT_PATHID_CORRECT)
    # ... (rest of blob builder — same as in pipeline)
    
    return bytes(b)

def scan_for_beatmap_levels(heap, target_level_id=None):
    """
    Scan IL2CPP heap for BeatmapLevelSO objects.
    
    Args:
        heap: MockIL2CppHeap instance
        target_level_id: Optional level ID to filter by (e.g., "custom/espresso")
    
    Returns:
        List of (offset, object_data) tuples for matching BeatmapLevelSO instances
    """
    results = []
    
    for offset, obj in heap.objects.items():
        # Check if this is a BeatmapLevelSO by type ID
        if obj['type_id'] != TYPE_BEATMAP_LEVEL_SO:
            continue
        
        # If target_level_id specified, check _levelID field (offset 0x20)
        if target_level_id and 'levelID' in obj['fields']:
            level_id = obj['fields']['levelID']
            if isinstance(level_id, bytes):
                # Decode UTF-8 string (strip null terminator)
                try:
                    decoded = level_id.decode('utf-8').rstrip('\x00')
                    if decoded != target_level_id:
                        continue
                except:
                    continue
        
        results.append((offset, obj))
    
    return results

def patch_beatmap_level(heap, offset, espresso_data):
    """
    Patch a BeatmapLevelSO object with Espresso metadata.
    
    Args:
        heap: MockIL2CppHeap instance
        offset: Object offset in heap
        espresso_data: Dictionary of field values to patch
    
    Returns:
        True if successful, False otherwise
    """
    obj = heap.get_object(offset)
    if not obj:
        print(f"  ✗ Object at offset {hex(offset)} not found")
        return False
    
    # Patch fields
    for field_name, value in espresso_data.items():
        if field_name in BEATMAP_LEVEL_SO_FIELDS:
            field_offset = BEATMAP_LEVEL_SO_FIELDS[field_name]
            obj['fields'][field_name] = value
            print(f"  ✓ Patched {field_name} at offset +{hex(field_offset)}")
    
    return True

def main():
    print("="*70)
    print("Memory Injection Prototype — Test Script")
    print("="*70)
    
    # Create simulated heap with some BeatmapLevelSO objects
    heap = MockIL2CppHeap()
    
    # Add some test objects (simulating loaded songs)
    print("\nCreating test BeatmapLevelSO objects...")
    
    # Original Rolling Stones song
    heap.create_object(TYPE_BEATMAP_LEVEL_SO, {
        'version': 3,
        'levelID': b'custom/rollingstones\0',
        'songName': b'Think You Know\0',
        'songAuthorName': b'The Rolling Stones\0',
    })
    
    # Another original song
    heap.create_object(TYPE_BEATMAP_LEVEL_SO, {
        'version': 3,
        'levelID': b'custom/anotherstone\0',
        'songName': b'Street Fighting Man\0',
        'songAuthorName': b'The Rolling Stones\0',
    })
    
    # Non-BeatmapLevelSO object (should be ignored)
    heap.create_object(4, {  # System.String type
        'value': b'Hello World\0',
    })
    
    print(f"Created {len(heap.objects)} objects in simulated heap")
    
    # Scan for BeatmapLevelSO objects
    print("\nScanning for BeatmapLevelSO objects...")
    results = scan_for_beatmap_levels(heap)
    
    print(f"\nFound {len(results)} BeatmapLevelSO object(s):")
    for offset, obj in results:
        level_id = obj['fields'].get('levelID', b'unknown')
        if isinstance(level_id, bytes):
            try:
                level_id_str = level_id.decode('utf-8').rstrip('\x00')
            except:
                level_id_str = str(level_id)
        else:
            level_id_str = str(level_id)
        
        song_name = obj['fields'].get('songName', b'unknown')
        if isinstance(song_name, bytes):
            try:
                song_name_str = song_name.decode('utf-8').rstrip('\x00')
            except:
                song_name_str = str(song_name)
        else:
            song_name_str = str(song_name)
        
        print(f"  Offset {hex(offset)}: levelID={level_id_str}, songName={song_name_str}")
    
    # Patch the first object with Espresso metadata
    if results:
        print("\nPatching first BeatmapLevelSO with Espresso metadata...")
        offset, obj = results[0]
        
        espresso_data = {
            'songName': encode_utf8_string("Espresso"),
            'songAuthorName': encode_utf8_string("Sabrina Carpenter"),
            'levelID': encode_utf8_string("custom/espresso"),
        }
        
        success = patch_beatmap_level(heap, offset, espresso_data)
        
        if success:
            print(f"\n✓ Successfully patched object at {hex(offset)}")
            
            # Verify patch
            patched_obj = heap.get_object(offset)
            song_name = patched_obj['fields'].get('songName', b'unknown')
            if isinstance(song_name, bytes):
                try:
                    song_name_str = song_name.decode('utf-8').rstrip('\x00')
                except:
                    song_name_str = str(song_name)
            else:
                song_name_str = str(song_name)
            
            print(f"  Verified: songName now = {song_name_str}")

if __name__ == '__main__':
    main()
