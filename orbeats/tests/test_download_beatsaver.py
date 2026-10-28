"""
Unit tests for download_beatsaver_songs.py
==========================================
Tests the API client functions, song searching, and missing audio detection.
Network-dependent functions are mocked.
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

# Import the module
import download_beatsaver_songs as dbs


def _make_urlopen_response(data_dict, status_code=200):
    """Create a mock context manager for urllib.request.urlopen."""
    resp = MagicMock()
    resp.status = status_code
    resp.read.return_value = json.dumps(data_dict).encode('utf-8')
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ======================================================================
# API Helper Functions
# ======================================================================
class TestAPIGet:
    """Test the api_get function."""

    @patch('urllib.request.urlopen')
    def test_successful_request(self, mock_urlopen):
        mock_urlopen.return_value = _make_urlopen_response(
            {"id": "abc123", "name": "TestSong"}
        )
        result = dbs.api_get("/maps/id/abc123")
        assert result is not None
        assert result['id'] == "abc123"

    @patch('urllib.request.urlopen')
    def test_404_returns_none(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=None
        )
        result = dbs.api_get("/maps/id/nonexistent")
        assert result is None

    @patch('urllib.request.urlopen')
    def test_network_error_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        result = dbs.api_get("/maps/id/abc123")
        assert result is None


# ======================================================================
# Missing Audio Detection
# ======================================================================
class TestListMissingAudio:
    """Test detection of songs missing audio files."""

    def test_finds_missing_audio(self, tmp_dir):
        """Songs with beatmaps but no audio should be detected."""
        song_dir = os.path.join(tmp_dir, "song1")
        os.makedirs(song_dir)
        with open(os.path.join(song_dir, "info.dat"), 'w') as f:
            json.dump({"_songName": "Test"}, f)
        with open(os.path.join(song_dir, "Hard.dat"), 'w') as f:
            json.dump({}, f)

        orig = dbs.REPO_DIR
        dbs.REPO_DIR = tmp_dir
        try:
            result = dbs.list_missing_audio()
            assert len(result) >= 1
            # list_missing_audio returns tuples (dirname, beatmap_count, dir_path)
            assert any("song1" in t[0] for t in result)
        finally:
            dbs.REPO_DIR = orig

    def test_song_with_audio_not_missing(self, tmp_dir):
        """Songs with audio should not be listed as missing."""
        song_dir = os.path.join(tmp_dir, "song_with_audio")
        os.makedirs(song_dir)
        with open(os.path.join(song_dir, "info.dat"), 'w') as f:
            json.dump({"_songName": "Test"}, f)
        with open(os.path.join(song_dir, "song.ogg"), 'wb') as f:
            f.write(b'\x00' * 100)

        orig = dbs.REPO_DIR
        dbs.REPO_DIR = tmp_dir
        try:
            result = dbs.list_missing_audio()
            assert len(result) == 0
        finally:
            dbs.REPO_DIR = orig


# ======================================================================
# Song Hash Download
# ======================================================================
class TestDownloadByHash:
    """Test download by hash (mocked)."""

    @patch('urllib.request.urlopen')
    def test_not_found(self, mock_urlopen, tmp_dir):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=None
        )
        result = dbs.download_by_hash("deadbeef" * 5, tmp_dir)
        assert result is None

    @patch('urllib.request.urlopen')
    def test_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("timeout")
        result = dbs.download_by_hash("deadbeef" * 5)
        assert result is None
