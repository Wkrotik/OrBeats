"""
Unit tests for build_replacement_pack*.py and build_patched_pack_bundle.py
=========================================================================
Tests the pure functions from the pack bundle patching tools.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from build_replacement_pack import (
    build_array_header,
    build_pptr,
    build_unity_string_bytes,
    encode_utf16le,
)


# ======================================================================
# UTF-16LE Encoding (build_replacement_pack)
# ======================================================================
class TestEncodeUTF16LE:
    """Test UTF-16LE string encoding."""

    def test_basic_string(self):
        result = encode_utf16le("Hi")
        # encode_utf16le appends a null terminator
        assert result == "Hi".encode('utf-16-le') + b'\x00\x00'

    def test_empty_string(self):
        result = encode_utf16le("")
        assert result == b''

    def test_unicode(self):
        result = encode_utf16le("Ü")
        expected = "Ü".encode('utf-16-le') + b'\x00\x00'
        assert result == expected

    def test_length(self):
        result = encode_utf16le("Test")
        assert len(result) == 10  # 4 chars * 2 bytes + 2 null bytes


# ======================================================================
# Unity String Bytes (build_replacement_pack)
# ======================================================================
class TestBuildUnityStringBytes:
    """Test Il2Cpp serialized string builder."""

    def test_includes_length_prefix(self):
        result = build_unity_string_bytes("Hi")
        # Length is int32, then UTF-16LE, then 2-byte null
        length = struct.unpack_from('<i', result, 0)[0]
        assert length > 0

    def test_content_matches(self):
        result = build_unity_string_bytes("Hi")
        # After 4-byte length, UTF-16LE content
        utf16 = "Hi".encode('utf-16-le')
        assert result[4:4+len(utf16)] == utf16

    def test_empty_string(self):
        result = build_unity_string_bytes("")
        assert len(result) > 0  # at minimum a length prefix


# ======================================================================
# PPtr Builder
# ======================================================================
class TestBuildPPtr:
    """Test PPtr (asset reference) builder."""

    def test_size_is_12_bytes(self):
        result = build_pptr(1, 12345)
        assert len(result) == 12

    def test_file_id(self):
        result = build_pptr(2, 0)
        file_id = struct.unpack_from('<i', result, 0)[0]
        assert file_id == 2

    def test_path_id(self):
        result = build_pptr(0, -1)
        path_id = struct.unpack_from('<q', result, 4)[0]
        assert path_id == -1

    def test_zero_pptr(self):
        result = build_pptr(0, 0)
        assert result == b'\x00' * 12


# ======================================================================
# Array Header Builder
# ======================================================================
class TestBuildArrayHeader:
    """Test Unity array header builder."""

    def test_returns_bytes(self):
        result = build_array_header(5)
        assert isinstance(result, bytes)

    def test_count_stored(self):
        result = build_array_header(10)
        count = struct.unpack_from('<i', result, 0)[0]
        assert count == 10

    def test_zero_count(self):
        result = build_array_header(0)
        count = struct.unpack_from('<i', result, 0)[0]
        assert count == 0
