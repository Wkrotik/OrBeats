"""
Unit tests for inject_pack_bundle.py
=====================================
Tests the BeatmapLevelSO blob builder and Unity string encoding
for the pack bundle injector.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from inject_pack_bundle import (
    _CHAR_PATH_IDS,
    _CORRECT_MONOSCRIPT_PATHID,
    build_beatmap_levelso_blob,
    encode_utf8_string,
)


# ======================================================================
# Unity UTF-8 String Encoding
# ======================================================================
class TestEncodeUTF8String:
    """Test Unity serialized UTF-8 string encoding."""

    def test_empty_string(self):
        result = encode_utf8_string("")
        assert result == b'\x00\x00'

    def test_basic_string(self):
        result = encode_utf8_string("Hi")
        # Size = length of UTF-8 bytes + 1 null terminator
        size = struct.unpack_from('<i', result, 0)[0]
        assert size == 3  # "Hi" = 2 bytes + 1 null
        assert result[4:6] == b'Hi'
        assert result[6:7] == b'\x00'

    def test_unicode_string(self):
        result = encode_utf8_string("Ü")
        size = struct.unpack_from('<i', result, 0)[0]
        # Ü in UTF-8 is 2 bytes
        assert size == 3  # 2 bytes + 1 null

    def test_single_char(self):
        result = encode_utf8_string("A")
        size = struct.unpack_from('<i', result, 0)[0]
        assert size == 2  # 1 byte + 1 null

    def test_length_field_is_int32(self):
        result = encode_utf8_string("Test")
        # First 4 bytes should be the size
        size = struct.unpack_from('<i', result, 0)[0]
        assert size == 5  # "Test" = 4 bytes + 1 null


# ======================================================================
# Characteristic Path IDs
# ======================================================================
class TestCharacteristicPathIDs:
    """Test that characteristic path IDs are defined."""

    def test_has_4_modes(self):
        assert len(_CHAR_PATH_IDS) == 4

    def test_standard_mode(self):
        assert "Standard" in _CHAR_PATH_IDS

    def test_all_modes_present(self):
        expected = ["Standard", "OneSaber", "NoArrows", "90Degree"]
        for mode in expected:
            assert mode in _CHAR_PATH_IDS

    def test_no_360degree(self):
        assert "360Degree" not in _CHAR_PATH_IDS

    def test_values_are_integers(self):
        for mode, pid in _CHAR_PATH_IDS.items():
            assert isinstance(pid, int)

    def test_verified_characteristic_pids(self):
        """PIDs must match the real BeatmapCharacteristicSO objects (Exp 182, verified
        from sharedassets_assets_all_068cd59e9a6fba13da706dc9269bf759.bundle, CAB
        cb38b3e2985c65d4cf8a63437da74a89). 90Degree points at the 90Degree characteristic
        (requires360=0) — NOT the 360Degree one, which the game hides from the selector."""
        verified = {
            "Standard": -7286399427822119286,
            "OneSaber": -5623662769225589684,
            "NoArrows": -8583864861369561029,
            "90Degree": -5995858427784384822,
        }
        for mode, pid in verified.items():
            assert _CHAR_PATH_IDS[mode] == pid, (
                f"{mode} pid changed to {_CHAR_PATH_IDS[mode]} (expected {pid})"
            )


# ======================================================================
# BeatmapLevelSO Blob Building
# ======================================================================
class TestBuildBeatmapLevelSOBlob:
    """Test the BeatmapLevelSO blob builder for pack bundle injection."""

    def test_returns_bytes(self):
        blob = build_beatmap_levelso_blob("Song", "Artist", 120.0, "custom/song")
        assert isinstance(blob, bytes)

    def test_starts_with_zero_header(self):
        """First 24 bytes should be the fixed header (m_GameObject + class/metadata + m_Script)."""
        blob = build_beatmap_levelso_blob("Song", "Artist", 120.0, "custom/song")
        # m_GameObject: fileID=0, pathID=0
        assert blob[0:4] == b'\x00\x00\x00\x00'
        assert blob[4:12] == b'\x00\x00\x00\x00\x00\x00\x00\x00'
        # class/metadata = 1
        assert struct.unpack_from('<I', blob, 12)[0] == 1

    def test_m_script_pptr(self):
        """m_Script should use correct MonoScript pathID."""
        blob = build_beatmap_levelso_blob("Song", "Artist", 120.0, "custom/song")
        # m_Script at offset 16: fileID=1, pathID=_CORRECT_MONOSCRIPT_PATHID
        file_id = struct.unpack_from('<i', blob, 16)[0]
        path_id = struct.unpack_from('<q', blob, 20)[0]
        assert file_id == 1
        assert path_id == _CORRECT_MONOSCRIPT_PATHID

    def test_m_name_contains_song_name(self):
        """m_Name should contain the song name."""
        blob = build_beatmap_levelso_blob("Espresso", "SC", 126.5, "custom/espresso")
        # Fixed header is 28 bytes: m_GameObject(12) + class(4) + m_Script(12)
        # m_Name starts at offset 28: [int32 sizeIncludingNull][utf8_bytes][null]
        size = struct.unpack_from('<i', blob, 28)[0]
        content = blob[32:32 + size - 1].decode('utf-8')
        assert "Espresso" in content

    def test_level_id_in_blob(self):
        blob = build_beatmap_levelso_blob("Song", "Artist", 120.0, "custom/mysong")
        assert b'custom/mysong' in blob

    def test_song_name_in_blob(self):
        blob = build_beatmap_levelso_blob("TestSong", "Artist", 120.0, "id")
        assert b'TestSong' in blob

    def test_artist_in_blob(self):
        blob = build_beatmap_levelso_blob("Song", "MyArtist", 120.0, "id")
        assert b'MyArtist' in blob

    def test_bpm_stored_correctly(self):
        """BPM should be stored as a float64 in the blob."""
        bpm = 142.5
        blob = build_beatmap_levelso_blob("Song", "Artist", bpm, "id")
        # BPM is after the string fields — scan for it
        found = False
        for i in range(24, len(blob) - 8):
            val = struct.unpack_from('<d', blob, i)[0]
            if abs(val - bpm) < 0.01:
                found = True
                break
        assert found, f"BPM {bpm} not found in blob"

    def test_version_byte(self):
        """The _version field should start with 0x78."""
        blob = build_beatmap_levelso_blob("Song", "Artist", 120.0, "id")
        # Fixed header is 28 bytes. m_Name at offset 28: [int32 sizeIncludingNull][utf8+null]
        name_size = struct.unpack_from('<i', blob, 28)[0]
        # version_offset = 28 (header) + 4 (size field) + name_size (content + null)
        version_offset = 28 + 4 + name_size
        assert version_offset < len(blob), f"version_offset {version_offset} >= blob len {len(blob)}"
        assert blob[version_offset] == 0x78

    def test_preview_modes_count(self):
        """Should have 4 preview difficulty beatmap sets."""
        blob = build_beatmap_levelso_blob("Song", "Artist", 120.0, "id")
        # Count is at the very end (before mode data)
        # 4 modes: each has 4+8+4+5*36 = 196 bytes
        total_mode_data = 4 * (4 + 8 + 4 + 5 * 36)
        count_offset = len(blob) - total_mode_data - 4
        count = struct.unpack_from('<i', blob, count_offset)[0]
        assert count == 4

    def test_all_characteristic_modes_present(self):
        """Each mode's pathID should match the _CHAR_PATH_IDS."""
        blob = build_beatmap_levelso_blob("Song", "Artist", 120.0, "id")
        modes = ["Standard", "OneSaber", "NoArrows", "90Degree"]
        total_mode_data = 4 * (4 + 8 + 4 + 5 * 36)
        start = len(blob) - total_mode_data
        for i, mode in enumerate(modes):
            offset = start + i * (4 + 8 + 4 + 5 * 36)
            file_id = struct.unpack_from('<i', blob, offset)[0]
            path_id = struct.unpack_from('<q', blob, offset + 4)[0]
            assert file_id == 3  # fileID for characteristic PPtrs
            assert path_id == _CHAR_PATH_IDS[mode]

    def test_diff_count_per_mode(self):
        """Each mode should have 5 difficulties."""
        blob = build_beatmap_levelso_blob("Song", "Artist", 120.0, "id")
        total_mode_data = 4 * (4 + 8 + 4 + 5 * 36)
        start = len(blob) - total_mode_data
        for i in range(4):
            offset = start + i * (4 + 8 + 4 + 5 * 36) + 12  # skip fileID + pathID
            diff_count = struct.unpack_from('<i', blob, offset)[0]
            assert diff_count == 5

    def test_empty_song_name(self):
        """Should handle empty song name."""
        blob = build_beatmap_levelso_blob("", "Artist", 120.0, "id")
        assert isinstance(blob, bytes)

    def test_unicode_song_name(self):
        """Should handle Unicode song names."""
        blob = build_beatmap_levelso_blob("Ünïcödé", "Ärtïst", 120.0, "id")
        assert isinstance(blob, bytes)
        assert b'\xc3\x9c' in blob  # UTF-8 for Ü

    def test_zero_bpm(self):
        """Should handle zero BPM."""
        blob = build_beatmap_levelso_blob("Song", "Artist", 0.0, "id")
        found = False
        for i in range(24, len(blob) - 8):
            val = struct.unpack_from('<d', blob, i)[0]
            if abs(val) < 0.001:
                found = True
                break
        assert found

    def test_negative_bpm(self):
        """Should handle negative BPM (edge case)."""
        blob = build_beatmap_levelso_blob("Song", "Artist", -1.0, "id")
        found = False
        for i in range(24, len(blob) - 8):
            val = struct.unpack_from('<d', blob, i)[0]
            if abs(val - (-1.0)) < 0.01:
                found = True
                break
        assert found
