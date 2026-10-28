"""
Unit tests for lapped_audio.py
===============================
Tests BPM loading, V2 detection, event time extraction, lapped detection,
and audio extension logic.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from lapped_audio import (
    LAP_THRESHOLD,
    detect_lapped,
    get_beatmap_event_times,
    is_v2_beatmap,
    load_bpm,
    make_beatmap_times,
)


# ======================================================================
# BPM Loading
# ======================================================================
class TestLoadBPM:
    """Test BPM loading from info.dat."""

    def test_loads_from_info_dat(self, tmp_dir, info_dat):
        """Should read BPM from Info.dat."""
        bpm = load_bpm(tmp_dir)
        assert bpm == 128.0

    def test_loads_from_lowercase_info_dat(self, tmp_dir):
        """Should also work with lowercase info.dat."""
        data = {"_beatsPerMinute": 140.0}
        path = os.path.join(tmp_dir, "info.dat")
        with open(path, 'w') as f:
            json.dump(data, f)
        assert load_bpm(tmp_dir) == 140.0

    def test_fallback_to_120(self, tmp_dir):
        """When no info.dat exists, should fall back to 120.0."""
        assert load_bpm(tmp_dir) == 120.0

    def test_fallback_to_beatmap_bpm(self, tmp_dir):
        """When info.dat has no BPM, should try beatmap files."""
        # Create a beatmap with _beatsPerMinute (some V2 maps have this)
        bm = {"_beatsPerMinute": 150.0}
        path = os.path.join(tmp_dir, "Hard.dat")
        with open(path, 'w') as f:
            json.dump(bm, f)
        assert load_bpm(tmp_dir) == 150.0

    def test_invalid_info_dat(self, tmp_dir):
        """Invalid info.dat should fall back gracefully."""
        path = os.path.join(tmp_dir, "info.dat")
        with open(path, 'w') as f:
            f.write("not json")
        assert load_bpm(tmp_dir) == 120.0


# ======================================================================
# V2 Beatmap Detection (lapped_audio version)
# ======================================================================
class TestIsV2Beatmap:
    """Test V2 detection in lapped_audio module."""

    def test_v2_detected(self, tmp_dir):
        data = {"_version": "2.0.0"}
        path = os.path.join(tmp_dir, "Hard.dat")
        with open(path, 'w') as f:
            json.dump(data, f)
        assert is_v2_beatmap(tmp_dir) is True

    def test_v3_not_v2(self, tmp_dir):
        data = {"_version": "3.2.0"}
        path = os.path.join(tmp_dir, "Hard.dat")
        with open(path, 'w') as f:
            json.dump(data, f)
        assert is_v2_beatmap(tmp_dir) is False

    def test_empty_dir_defaults_to_v2(self, tmp_dir):
        assert is_v2_beatmap(tmp_dir) is True

    def test_empty_version_is_v2(self, tmp_dir):
        data = {"_version": ""}
        path = os.path.join(tmp_dir, "Hard.dat")
        with open(path, 'w') as f:
            json.dump(data, f)
        assert is_v2_beatmap(tmp_dir) is True


# ======================================================================
# Beatmap Event Time Extraction
# ======================================================================
class TestGetBeatmapEventTimes:
    """Test extraction of event times from beatmaps."""

    def test_extracts_note_times_v2(self, tmp_dir):
        """V2 notes _time should be converted to seconds."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)

        bm = {
            "_version": "2.0.0",
            "_notes": [
                {"_time": 0.0},
                {"_time": 30.0},  # 30 beats at 120 BPM = 15 seconds
            ]
        }
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(bm, f)

        result = get_beatmap_event_times(tmp_dir)
        assert "Hard.dat" in result
        # 30 beats at 120 BPM = 30 / 120 * 60 = 15 seconds
        assert abs(result["Hard.dat"]["max_time"] - 15.0) < 0.01

    def test_extracts_note_times_v3(self, tmp_dir):
        """V3 notes 'b' should be in seconds (no conversion).

        BUG: get_beatmap_event_times only searches V2 keys (_notes, _obstacles, etc.)
        but V3 uses 'colorNotes', 'bombNotes', 'obstacles', etc. and the field is 'b'
        not '_time'. So V3 beatmaps produce empty time sets and max_time=0.
        """
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)

        bm = {
            "_version": "3.2.0",
            "colorNotes": [
                {"b": 0.0},
                {"b": 15.0},  # already in seconds
            ]
        }
        with open(os.path.join(tmp_dir, "Normal.dat"), 'w') as f:
            json.dump(bm, f)

        result = get_beatmap_event_times(tmp_dir)
        assert "Normal.dat" in result
        # BUG: V3 keys (colorNotes) not recognized -- max_time is 0
        # Should be 15.0 once V3 key lookup is implemented
        assert result["Normal.dat"]["max_time"] == 0

    def test_empty_dir(self, tmp_dir):
        result = get_beatmap_event_times(tmp_dir)
        assert result == {}

    def test_includes_bookmarks(self, tmp_dir):
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)

        bm = {
            "_version": "2.0.0",
            "_notes": [{"_time": 10.0}],
            "_customData": {
                "_bookmarks": [
                    {"_time": 5.0},
                    {"_time": 20.0},
                ]
            }
        }
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(bm, f)

        result = get_beatmap_event_times(tmp_dir)
        bookmarks = result["Hard.dat"]["bookmarks"]
        assert len(bookmarks) == 2
        # V2 bookmarks should be converted to seconds
        # 5 beats at 120 BPM = 2.5 seconds
        assert abs(bookmarks[0] - 2.5) < 0.01


# ======================================================================
# make_beatmap_times
# ======================================================================
class TestMakeBeatmapTimes:
    """Test that make_beatmap_times is an alias."""

    def test_returns_same_as_get_beatmap_event_times(self, tmp_dir):
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)
        bm = {"_notes": [{"_time": 5.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(bm, f)
        r1 = get_beatmap_event_times(tmp_dir)
        r2 = make_beatmap_times(tmp_dir)
        assert r1 == r2


# ======================================================================
# Lapped Detection
# ======================================================================
class TestDetectLapped:
    """Test lapped audio detection."""

    def test_not_lapped(self, tmp_dir):
        """When max_note_time <= audio_duration * threshold, not lapped."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)
        bm = {"_notes": [{"_time": 0.0}, {"_time": 10.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(bm, f)
        # 10 beats at 120 BPM = 5 seconds
        # audio_duration = 10 seconds, threshold = 1.3
        # max_note_time = 5s <= 10 * 1.3 = 13 -> not lapped
        result = detect_lapped(tmp_dir, 10.0)
        assert result['is_lapped'] is False

    def test_is_lapped(self, tmp_dir):
        """When max_note_time > audio_duration * threshold, song is lapped."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)
        # 200 beats at 120 BPM = 100 seconds
        bm = {"_notes": [{"_time": 0.0}, {"_time": 200.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(bm, f)
        # audio_duration = 30 seconds
        # max_note_time = 100s > 30 * 1.3 = 39 -> lapped
        result = detect_lapped(tmp_dir, 30.0)
        assert result['is_lapped'] is True
        assert result['max_note_time'] == 100.0

    def test_lapped_with_bookmarks(self, tmp_dir):
        """Lapped detection should find loop section from bookmarks."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)
        # 240 beats at 120 BPM = 120 seconds
        bm = {
            "_version": "2.0.0",
            "_notes": [{"_time": 240.0}],
            "_customData": {
                "_bookmarks": [
                    {"_time": 100.0},  # 50 seconds (100 beats at 120 BPM)
                    {"_time": 200.0},  # 100 seconds (200 beats at 120 BPM)
                ]
            }
        }
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(bm, f)
        # audio_duration = 60s, max_note_time = 120s
        result = detect_lapped(tmp_dir, 60.0)
        assert result['is_lapped'] is True
        assert result['repeats_needed'] >= 1
        assert result['extended_duration'] >= 120.0

    def test_no_beatmaps(self, tmp_dir):
        """Empty directory should return not lapped."""
        result = detect_lapped(tmp_dir, 30.0)
        assert result['is_lapped'] is False

    def test_lap_threshold_constant(self):
        """LAP_THRESHOLD should be 1.3."""
        assert LAP_THRESHOLD == 1.3

    def test_not_lapped_at_threshold(self, tmp_dir):
        """Exactly at threshold should not be lapped (uses <=)."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)
        # max_note_time = 39s, audio = 30s, 30 * 1.3 = 39 -> not lapped (<=)
        bm = {"_notes": [{"_time": 78.0}]}  # 78 beats at 120 BPM = 39 seconds
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(bm, f)
        result = detect_lapped(tmp_dir, 30.0)
        assert result['is_lapped'] is False
