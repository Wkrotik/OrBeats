"""
Unit tests for build_patched_pack_bundle.py
===========================================
Tests the blob builder and CRC/GF(2) linear algebra functions.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from build_patched_pack_bundle import build_blob, encode_utf8_string


# ======================================================================
# UTF-8 String Encoding
# ======================================================================
class TestEncodeUTF8String:
    """Test the UTF-8 string encoding for patched pack bundle."""

    def test_empty_string(self):
        result = encode_utf8_string("")
        assert result == b'\x00\x00'

    def test_basic_string(self):
        result = encode_utf8_string("Hi")
        size = struct.unpack_from('<i', result, 0)[0]
        assert size == 2  # char count only, null is appended separately

    def test_content(self):
        result = encode_utf8_string("Hi")
        assert result[4:6] == b'Hi'
        assert result[6:7] == b'\x00'


# ======================================================================
# Blob Builder
# ======================================================================
class TestBuildBlob:
    """Test the BeatmapLevelSO blob builder for patched pack."""

    def test_returns_bytes(self):
        blob = build_blob("TestSong", "Artist", 120.0, "custom/test")
        assert isinstance(blob, bytes)

    def test_returns_deterministic_size(self):
        """The blob should be deterministic -- same args produce same size."""
        blob1 = build_blob("TestSong", "Artist", 120.0, "custom/test")
        blob2 = build_blob("TestSong", "Artist", 120.0, "custom/test")
        assert len(blob1) == len(blob2)
        # Should be a reasonable size for a BeatmapLevelSO blob
        assert len(blob1) > 200

    def test_returns_1061_bytes_production(self):
        """The production blob (Espresso) should be exactly 1061 bytes (4 modes)."""
        blob = build_blob("Espresso", "Sabrina Carpenter", 126.5, "custom/espresso")
        assert len(blob) == 1061

    def test_starts_with_zero_gameobject(self):
        """m_GameObject (first 12 bytes) should be zeroed."""
        blob = build_blob("Song", "A", 120.0, "id")
        assert blob[:12] == b'\x00' * 12

    def test_monoscript_pathid(self):
        """m_Script should use MonoScript pathID."""
        blob = build_blob("Song", "A", 120.0, "id")
        file_id = struct.unpack_from('<i', blob, 16)[0]
        path_id = struct.unpack_from('<q', blob, 20)[0]
        assert file_id == 1
        assert path_id == 2140275054477726686

    def test_song_name_in_blob(self):
        blob = build_blob("Espresso", "SC", 126.5, "custom/espresso")
        assert b'Espresso' in blob

    def test_artist_in_blob(self):
        blob = build_blob("Song", "MyArtist", 120.0, "id")
        assert b'MyArtist' in blob

    def test_level_id_in_blob(self):
        blob = build_blob("Song", "A", 120.0, "custom/mysong")
        assert b'custom/mysong' in blob

    def test_bpm_stored(self):
        bpm = 142.5
        blob = build_blob("Song", "A", bpm, "id")
        found = False
        for i in range(24, len(blob) - 8):
            val = struct.unpack_from('<d', blob, i)[0]
            if abs(val - bpm) < 0.01:
                found = True
                break
        assert found

    def test_version_byte(self):
        blob = build_blob("Song", "A", 120.0, "id")
        # Fixed header is 28 bytes. m_Name at offset 28.
        # patched_pack encode_utf8_string: [int32 char_count][utf8 bytes][null byte]
        name_size = struct.unpack_from('<i', blob, 28)[0]
        version_offset = 28 + 4 + name_size + 1  # header + size_field + content + null
        assert version_offset < len(blob), f"version_offset {version_offset} >= blob len {len(blob)}"
        assert blob[version_offset] == 0x78

    def test_preview_modes_count(self):
        blob = build_blob("Song", "A", 120.0, "id")
        total_mode_data = 4 * (4 + 8 + 4 + 5 * 36)
        count_offset = len(blob) - total_mode_data - 4
        count = struct.unpack_from('<i', blob, count_offset)[0]
        assert count == 4

    def test_all_modes_use_fileid_3(self):
        """All characteristic PPtrs should use fileID=3."""
        blob = build_blob("Song", "A", 120.0, "id")
        total_mode_data = 4 * (4 + 8 + 4 + 5 * 36)
        start = len(blob) - total_mode_data
        for i in range(4):
            file_id = struct.unpack_from('<i', blob, start + i * 196)[0]
            assert file_id == 3

    def test_1061_is_consistent(self):
        """Blob size should be consistent for same inputs, and 1061 for production args."""
        # Same inputs produce same size
        b1 = build_blob("Espresso", "Sabrina Carpenter", 126.5, "custom/espresso")
        b2 = build_blob("Espresso", "Sabrina Carpenter", 126.5, "custom/espresso")
        assert len(b1) == len(b2) == 1061
        # Shorter inputs produce smaller blobs (strings vary in length)
        b3 = build_blob("A", "B", 120.0, "id")
        assert len(b3) < len(b1)
