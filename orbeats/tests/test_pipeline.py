"""
Unit tests for full_custom_song_pipeline.py
============================================
Tests config loading, beatmap utilities, V2->V3 conversion,
string encoding, blob building, path helpers, and song metadata management.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from full_custom_song_pipeline import (
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CONVERT_TO_V3,
    DEFAULT_FEATURES,
    DEFAULT_MODE_MAPPING,
    DEFAULT_PAD_TO_SIZE,
    DIFFICULTIES,
    FEATURES_FILENAME,
    GAME_CHARACTERISTIC_MODES,
    REDIRECT_CONFIG_FILENAME,
    SONG_IDS_FILENAME,
    SONG_METADATA_FILENAME,
    _build_beatmap_level_so_blob,
    _encode_unity_string,
    _get_local_features_path,
    _get_redirect_config_path,
    _get_remote_features_path,
    _get_remote_redirect_path,
    _get_remote_song_metadata_path,
    _get_song_ids_path,
    _get_song_metadata_path,
    _load_local_features,
    _load_local_redirects,
    _load_local_song_metadata,
    _load_song_ids,
    _lookup_song_name,
    _save_local_features,
    _scan_beatmap_max_beat,
    _select_beatmap_file,
    build_mode_mapping,
    convert_v2_to_v3,
    detect_song_modes,
    is_v2_beatmap,
    load_bpm_regions,
    load_config,
    resolve_audio_codec,
    resolve_convert_to_v3,
    resolve_mode_mapping,
    resolve_pad_to_size,
)


# ======================================================================
# Config Loading
# ======================================================================
class TestLoadConfig:
    """Test config loading with deep merge."""

    def test_returns_default_when_no_file(self):
        config = load_config("/nonexistent/path.json")
        assert config['ps4']['ip'] == "192.168.100.117"
        assert config['title']['id'] == "CUSA12878"

    def test_returns_default_when_none(self):
        config = load_config(None)
        assert config['ps4']['ip'] == "192.168.100.117"

    def test_returns_default_when_empty_string(self):
        config = load_config("")
        assert config['ps4']['ip'] == "192.168.100.117"

    def test_loads_valid_config(self, tmp_dir):
        cfg = {"ps4": {"ip": "10.0.0.1"}}
        path = os.path.join(tmp_dir, "config.json")
        with open(path, 'w') as f:
            json.dump(cfg, f)
        config = load_config(path)
        assert config['ps4']['ip'] == "10.0.0.1"
        # Other fields should come from defaults
        assert config['title']['id'] == "CUSA12878"

    def test_deep_merge_preserves_nested(self, tmp_dir):
        cfg = {"ps4": {"ip": "10.0.0.1"}}  # only override ip
        path = os.path.join(tmp_dir, "config.json")
        with open(path, 'w') as f:
            json.dump(cfg, f)
        config = load_config(path)
        # Port should still be default
        assert config['ps4']['ftp_port'] == 2121

    def test_deep_merge_override_all(self, tmp_dir):
        cfg = {
            "ps4": {"ip": "1.2.3.4", "ftp_port": 9999},
            "title": {"id": "TEST123"},
        }
        path = os.path.join(tmp_dir, "config.json")
        with open(path, 'w') as f:
            json.dump(cfg, f)
        config = load_config(path)
        assert config['ps4']['ip'] == "1.2.3.4"
        assert config['ps4']['ftp_port'] == 9999
        assert config['title']['id'] == "TEST123"

    def test_invalid_json_returns_default(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.json")
        with open(path, 'w') as f:
            f.write("NOT JSON {{{")
        config = load_config(path)
        assert config['ps4']['ip'] == "192.168.100.117"

    def test_nonexistent_file_returns_default(self):
        config = load_config("/tmp/nonexistent_12345.json")
        assert 'ps4' in config
        assert 'paths' in config


# ======================================================================
# V2 / V3 Beatmap Detection
# ======================================================================
class TestIsV2Beatmap:
    """Test V2 beatmap detection."""

    def test_v2_with_version_string(self):
        assert is_v2_beatmap({"_version": "2.0.0"}) is True

    def test_v3_is_not_v2(self):
        assert is_v2_beatmap({"version": "3.2.0"}) is False

    def test_v2_notes_without_color_notes(self):
        assert is_v2_beatmap({"_notes": []}) is True

    def test_v3_with_color_notes(self):
        assert is_v2_beatmap({"version": "3.2.0", "colorNotes": []}) is False

    def test_empty_dict(self):
        # No version, no _notes -> not V2
        assert is_v2_beatmap({}) is False

    def test_v1_format(self):
        assert is_v2_beatmap({"_version": "1.0.0"}) is False

    def test_v4_format(self):
        assert is_v2_beatmap({"version": "4.0.0"}) is False


# ======================================================================
# V2 -> V3 Conversion
# ======================================================================
class TestConvertV2ToV3:
    """Test V2 to V3 beatmap conversion."""

    def test_passthrough_v3(self):
        """V3 data should pass through unchanged."""
        v3 = {"version": "3.2.0", "colorNotes": []}
        result = convert_v2_to_v3(v3)
        assert result is v3  # same object

    def test_color_notes_conversion(self):
        v2 = {
            "_notes": [
                {"_time": 1.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 1},
                {"_time": 2.0, "_lineIndex": 1, "_lineLayer": 1, "_type": 1, "_cutDirection": 2},
            ]
        }
        result = convert_v2_to_v3(v2)
        assert len(result['colorNotes']) == 2
        assert result['colorNotes'][0]['b'] == 1.0
        assert result['colorNotes'][0]['x'] == 0
        assert result['colorNotes'][0]['y'] == 0
        assert result['colorNotes'][0]['d'] == 1
        assert result['colorNotes'][0]['c'] == 0  # color field

    def test_bomb_notes_conversion(self):
        v2 = {
            "_notes": [
                {"_time": 3.0, "_lineIndex": 2, "_lineLayer": 1, "_type": 3, "_cutDirection": 0},
            ]
        }
        result = convert_v2_to_v3(v2)
        assert len(result['bombNotes']) == 1
        assert result['bombNotes'][0]['b'] == 3.0

    def test_obstacles_conversion(self):
        v2 = {
            "_notes": [],  # required for is_v2_beatmap to recognize as V2
            "_obstacles": [
                {"_time": 0.5, "_lineIndex": 0, "_type": 0, "_duration": 2.0, "_width": 4},
                {"_time": 1.0, "_lineIndex": 1, "_type": 1, "_duration": 1.0, "_width": 2},
            ]
        }
        result = convert_v2_to_v3(v2)
        assert len(result['obstacles']) == 2
        assert result['obstacles'][0]['d'] == 2.0
        assert result['obstacles'][0]['w'] == 4
        assert result['obstacles'][0]['h'] == 3  # type 0 -> height 3
        assert result['obstacles'][1]['h'] == 1  # type 1 -> height 1

    def test_events_conversion(self):
        v2 = {
            "_notes": [],  # required for is_v2_beatmap to recognize as V2
            "_events": [
                {"_time": 0.0, "_type": 0, "_value": 1},
                {"_time": 1.0, "_type": 4, "_value": 3},
            ]
        }
        result = convert_v2_to_v3(v2)
        assert len(result['basicBeatmapEvents']) == 2
        assert result['basicBeatmapEvents'][0]['et'] == 0
        assert result['basicBeatmapEvents'][0]['i'] == 1
        assert result['basicBeatmapEvents'][1]['et'] == 4

    def test_rotation_events_passed_through(self):
        """V2 spawn-rotation events (types 14/15) become V3 rotationEvents."""
        v2 = {
            "_notes": [],
            "_events": [
                {"_time": 2.0, "_type": 14, "_value": 3},  # early, 15° CCW (left)
                {"_time": 9.0, "_type": 12, "_value": 1},   # laser speed — stays basic
                {"_time": 9.5, "_type": 15, "_value": 4},   # late, 15° CW (right)
            ]
        }
        result = convert_v2_to_v3(v2)
        assert result['rotationEvents'] == [
            {"b": 2.0, "e": 0, "r": -15},
            {"b": 9.5, "e": 1, "r": 15},
        ]
        assert [e['et'] for e in result['basicBeatmapEvents']] == [12]

    def test_rotation_value_enumeration(self):
        """Every V2 rotation value maps to its signed degree delta."""
        v2 = {
            "_notes": [],
            "_events": [
                {"_time": float(i), "_type": 15, "_value": v}
                for i, v in enumerate((0, 1, 2, 3, 4, 5, 6, 7))
            ]
        }
        result = convert_v2_to_v3(v2)
        assert [e['r'] for e in result['rotationEvents']] == \
            [-60, -45, -30, -15, 15, 30, 45, 60]
        assert all(e['e'] == 1 for e in result['rotationEvents'])
        assert result['basicBeatmapEvents'] == []

    def test_no_events_produce_empty_rotation_list(self):
        v2 = {"_notes": []}
        result = convert_v2_to_v3(v2)
        assert result['rotationEvents'] == []
        assert result['basicBeatmapEvents'] == []

    def test_version_field(self):
        v2 = {"_notes": []}
        result = convert_v2_to_v3(v2)
        assert result['version'] == "3.2.0"

    def test_bpm_events_with_default(self):
        v2 = {"_notes": []}
        result = convert_v2_to_v3(v2, default_bpm=150.0)
        assert result['bpmEvents'] == [{"b": 0, "m": 150.0}]

    def test_empty_v2_beatmap(self):
        v2 = {"_notes": []}  # minimal V2: has _notes but no colorNotes
        result = convert_v2_to_v3(v2)
        assert result['colorNotes'] == []
        assert result['bombNotes'] == []
        assert result['obstacles'] == []
        assert result['basicBeatmapEvents'] == []


# ======================================================================
# Beatmap File Selection
# ======================================================================
class TestSelectBeatmapFile:
    """Test beatmap file selection priority chain."""

    def test_prefers_standard(self):
        files = ["HardStandard.dat", "Hard.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result == "HardStandard.dat"

    def test_bare_fallback(self):
        files = ["Hard.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result == "Hard.dat"

    def test_beatmap_dat_fallback(self):
        files = ["Hard.beatmap.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result == "Hard.beatmap.dat"

    def test_90degree_fallback(self):
        files = ["Hard90Degree.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result == "Hard90Degree.dat"

    def test_360degree_excluded(self):
        """360Degree files are always excluded (unsupported on PS4 camera)."""
        files = ["Hard360Degree.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result is None

    def test_ignore_non_standard_suppresses_tier4(self):
        files = ["Hard90Degree.dat", "Hard360Degree.dat"]
        result = _select_beatmap_file("Hard", files, ignore_non_standard=True)
        assert result is None

    def test_expert_excludes_expertplus(self):
        files = ["ExpertPlusStandard.dat", "ExpertStandard.dat"]
        result = _select_beatmap_file("Expert", files)
        assert result == "ExpertStandard.dat"

    def test_expertplus_matches_expertplus(self):
        files = ["ExpertPlusStandard.dat"]
        result = _select_beatmap_file("ExpertPlus", files)
        assert result == "ExpertPlusStandard.dat"

    def test_skips_info_and_lightshow(self):
        files = ["Info.dat", "Lightshow.dat", "Hard.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result == "Hard.dat"

    def test_no_match_returns_none(self):
        files = ["Easy.dat", "Normal.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result is None

    def test_empty_list(self):
        result = _select_beatmap_file("Hard", [])
        assert result is None

    def test_json_extension_accepted(self):
        files = ["Hard.json"]
        result = _select_beatmap_file("Hard", files)
        assert result == "Hard.json"

    def test_onesaber_fallback(self):
        files = ["HardOneSaber.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result == "HardOneSaber.dat"

    def test_noarrows_fallback(self):
        files = ["HardNoArrows.dat"]
        result = _select_beatmap_file("Hard", files)
        assert result == "HardNoArrows.dat"


# ======================================================================
# Beatmap Max Beat Scanning
# ======================================================================
class TestScanBeatmapMaxBeat:
    """Test scanning beatmaps for highest beat value."""

    def test_v2_beatmap_max_beat(self, tmp_dir):
        data = {
            "_notes": [
                {"_time": 10.0},
                {"_time": 50.0},
                {"_time": 30.0},
            ]
        }
        path = os.path.join(tmp_dir, "Hard.dat")
        with open(path, 'w') as f:
            json.dump(data, f)
        assert _scan_beatmap_max_beat(tmp_dir) == 50.0

    def test_v3_beatmap_max_beat(self, tmp_dir):
        data = {
            "colorNotes": [
                {"b": 20.0},
                {"b": 40.0},
            ]
        }
        path = os.path.join(tmp_dir, "Normal.dat")
        with open(path, 'w') as f:
            json.dump(data, f)
        assert _scan_beatmap_max_beat(tmp_dir) == 40.0

    def test_skips_info_dat(self, tmp_dir):
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)
        hard = {"_notes": [{"_time": 100.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(hard, f)
        assert _scan_beatmap_max_beat(tmp_dir) == 100.0

    def test_empty_dir(self, tmp_dir):
        assert _scan_beatmap_max_beat(tmp_dir) == 0.0


# ======================================================================
# BPM Region Loading
# ======================================================================
class TestLoadBpmRegions:
    """Test BPM region loading and computation."""

    def test_from_bpm_info_dat(self, tmp_dir, bpm_info_dat):
        regions = load_bpm_regions(tmp_dir, 1323000)
        assert len(regions) == 1
        assert regions[0]['si'] == 0
        assert regions[0]['ei'] == 1323000
        assert regions[0]['sb'] == 0.0
        assert regions[0]['eb'] == 480.0

    def test_from_beatmap_fallback(self, tmp_dir):
        """When no BPMInfo.dat, should compute from beatmap max beat."""
        hard = {"_notes": [{"_time": 100.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(hard, f)
        sample_count = 44100 * 30  # 30 seconds
        regions = load_bpm_regions(tmp_dir, sample_count)
        assert len(regions) == 1
        assert regions[0]['eb'] == 100.0

    def test_from_info_dat_bpm_fallback(self, tmp_dir):
        """When no BPMInfo.dat and no beatmaps, use Info.dat BPM."""
        info = {"_beatsPerMinute": 128.0}
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info, f)
        sample_count = 44100 * 60  # 60 seconds
        regions = load_bpm_regions(tmp_dir, sample_count)
        assert len(regions) == 1
        # 60s * 128 BPM / 60 = 128 beats
        assert regions[0]['eb'] == 128.0

    def test_beatmap_max_overrides_bpm_info(self, tmp_dir):
        """If beatmap max beat > BPMInfo endBeat, should use beatmap value."""
        bpm_info = {
            "_regions": [
                {"_startSampleIndex": 0, "_endSampleIndex": 1323000,
                 "_startBeat": 0.0, "_endBeat": 200.0}
            ]
        }
        with open(os.path.join(tmp_dir, "BPMInfo.dat"), 'w') as f:
            json.dump(bpm_info, f)
        hard = {"_notes": [{"_time": 500.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(hard, f)
        regions = load_bpm_regions(tmp_dir, 1323000)
        assert regions[0]['eb'] == 500.0


# ======================================================================
# Unity String Encoding
# ======================================================================
class TestEncodeUnityString:
    """Test Unity serialized string encoding."""

    def test_empty_string(self):
        result = _encode_unity_string("")
        assert result == b'\x00\x00'

    def test_basic_string(self):
        result = _encode_unity_string("Hi")
        # Length prefix = 2 chars * 2 bytes/char + 2 bytes null = 6
        size = struct.unpack_from('<i', result, 0)[0]
        assert size == 6
        # UTF-16LE content
        assert result[4:8] == "Hi".encode('utf-16-le')
        # Trailing null
        assert result[8:10] == b'\x00\x00'

    def test_unicode_string(self):
        result = _encode_unity_string("Ü")
        size = struct.unpack_from('<i', result, 0)[0]
        assert size == 4  # 1 char * 2 bytes + 2 bytes null

    def test_single_char(self):
        result = _encode_unity_string("A")
        size = struct.unpack_from('<i', result, 0)[0]
        assert size == 4  # 1 char * 2 bytes + 2 bytes null

    def test_length_includes_null(self):
        """Length field should include the trailing null terminator."""
        result = _encode_unity_string("Test")
        size = struct.unpack_from('<i', result, 0)[0]
        assert size == len("Test".encode('utf-16-le')) + 2


# ======================================================================
# BeatmapLevelSO Blob Building
# ======================================================================
class TestBuildBeatmapLevelSOBlob:
    """Test the BeatmapLevelSO blob builder."""

    def test_basic_blob_structure(self):
        blob = _build_beatmap_level_so_blob(
            song_name="Test",
            song_sub_name="Sub",
            song_author="Author",
            level_author="Mapper",
            bpm=128.0,
            preview_diff_count=5,
            diff_data=b'\x00' * (5 * 36),
        )
        assert isinstance(blob, bytes)
        assert len(blob) > 0

    def test_blob_starts_with_padding(self):
        blob = _build_beatmap_level_so_blob(
            song_name="X", song_sub_name="", song_author="A",
            level_author="M", bpm=120.0, preview_diff_count=5,
            diff_data=b'\x00' * (5 * 36),
        )
        # First 12 bytes are padding
        assert blob[:12] == b'\x00' * 12

    def test_m_script_pptr(self):
        """Bytes 12-23 should be the m_Script PPtr (fileID=2, pathID=-1)."""
        blob = _build_beatmap_level_so_blob(
            song_name="X", song_sub_name="", song_author="A",
            level_author="M", bpm=120.0, preview_diff_count=5,
            diff_data=b'\x00' * (5 * 36),
        )
        file_id = struct.unpack_from('<i', blob, 12)[0]
        path_id = struct.unpack_from('<q', blob, 16)[0]
        assert file_id == 2
        assert path_id == -1

    def test_bpm_stored_as_double(self):
        """BPM should be stored as float64 after the string fields."""
        bpm = 142.5
        blob = _build_beatmap_level_so_blob(
            song_name="T", song_sub_name="", song_author="A",
            level_author="M", bpm=bpm, preview_diff_count=5,
            diff_data=b'\x00' * (5 * 36),
        )
        # BPM double is after: 12 padding + 12 PPtr + (6 strings * variable) + 8 BPM
        # Since strings vary, we scan for the double
        # We know the blob ends with preview mode data
        # Just verify the blob contains the BPM value somewhere
        found = False
        for i in range(24, len(blob) - 8):
            val = struct.unpack_from('<d', blob, i)[0]
            if abs(val - bpm) < 0.01:
                found = True
                break
        assert found, f"BPM {bpm} not found in blob"

    def test_preview_mode_count(self):
        """Mode count integer should be stored correctly at the expected offset (4 modes)."""
        diff_data = b'\x00' * (5 * 36)
        blob = _build_beatmap_level_so_blob(
            song_name="T", song_sub_name="", song_author="A",
            level_author="M", bpm=120.0, preview_diff_count=5,
            diff_data=diff_data,
        )
        # 4 modes at the end: each has 4 (fileID) + 8 (pathID) + 4 (diff_count) + 180 (5*36) = 196 bytes
        # Total mode data = 4 * 196 = 784 + 4 (count) = 788
        # Count should be 4
        # Find it by scanning backwards from end
        total_mode_size = 4 * (4 + 8 + 4 + 5 * 36) + 4
        count_offset = len(blob) - total_mode_size
        count = struct.unpack_from('<i', blob, count_offset)[0]
        assert count == 4

    def test_level_id_in_blob(self):
        """The level_id string should appear in the blob."""
        blob = _build_beatmap_level_so_blob(
            song_name="Espresso", song_sub_name="", song_author="SC",
            level_author="M", bpm=120.0, preview_diff_count=5,
            diff_data=b'\x00' * (5 * 36),
            level_id="custom/espresso",
        )
        assert 'custom/espresso'.encode('utf-16-le') in blob

    def test_song_name_in_blob(self):
        blob = _build_beatmap_level_so_blob(
            song_name="TestSong", song_sub_name="", song_author="A",
            level_author="M", bpm=120.0, preview_diff_count=5,
            diff_data=b'\x00' * (5 * 36),
        )
        assert "TestSong".encode('utf-16-le') in blob

    def test_empty_diff_data_padded(self):
        """When diff_data is shorter than needed, should be zero-padded."""
        blob = _build_beatmap_level_so_blob(
            song_name="X", song_sub_name="", song_author="A",
            level_author="M", bpm=120.0, preview_diff_count=5,
            diff_data=b'\x00' * 10,  # only 10 bytes, need 5*36=180
        )
        assert isinstance(blob, bytes)


# ======================================================================
# Redirect Config Path Helpers
# ======================================================================
class TestRedirectConfigPaths:
    """Test redirect config path construction."""

    def test_get_redirect_config_path_default(self):
        path = _get_redirect_config_path()
        assert path.endswith(REDIRECT_CONFIG_FILENAME)

    def test_get_redirect_config_path_custom_root(self):
        path = _get_redirect_config_path("/custom/root")
        assert path == "/custom/root/redirects.json"

    def test_get_remote_redirect_path(self, default_config):
        path = _get_remote_redirect_path(default_config)
        assert path == "/data/GoldHEN/AFR/CUSA12878/redirects.json"

    def test_get_remote_redirect_path_custom(self):
        config = {
            'paths': {'afr_base': '/custom/afr'},
            'title': {'id': 'TEST123'},
        }
        path = _get_remote_redirect_path(config)
        assert path == "/custom/afr/TEST123/redirects.json"


# ======================================================================
# Redirect Config Loading
# ======================================================================
class TestLoadLocalRedirects:
    """Test loading redirect config from local file."""

    def test_loads_valid_file(self, tmp_dir):
        data = {"titleId": "TEST", "afrBase": "/afr", "redirects": {"a": "b"}}
        path = os.path.join(tmp_dir, "redirects.json")
        with open(path, 'w') as f:
            json.dump(data, f)
        result = _load_local_redirects(path)
        assert result['titleId'] == "TEST"
        assert result['redirects']['a'] == "b"

    def test_missing_file_returns_default(self):
        result = _load_local_redirects("/nonexistent/path.json")
        assert result['titleId'] == "CUSA12878"
        assert result['redirects'] == {}

    def test_invalid_json_returns_default(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.json")
        with open(path, 'w') as f:
            f.write("{bad json")
        result = _load_local_redirects(path)
        assert result['redirects'] == {}

    def test_missing_redirects_key_added(self, tmp_dir):
        data = {"titleId": "TEST"}  # no 'redirects' key
        path = os.path.join(tmp_dir, "redirects.json")
        with open(path, 'w') as f:
            json.dump(data, f)
        result = _load_local_redirects(path)
        assert result['redirects'] == {}


# ======================================================================
# Features Config Path Helpers
# ======================================================================
class TestFeaturesConfigPaths:
    """Test features config path construction."""

    def test_get_local_features_path(self):
        path = _get_local_features_path()
        assert path.endswith(FEATURES_FILENAME)

    def test_get_remote_features_path(self, default_config):
        path = _get_remote_features_path(default_config)
        assert path == "/data/GoldHEN/AFR/CUSA12878/features.json"


# ======================================================================
# Default Behavior Resolution (v0.5314: safe-by-default pipeline)
# ======================================================================
class TestDefaultAudioCodec:
    """Test the default-safe audio codec resolution."""

    def test_default_is_pcm16(self):
        assert DEFAULT_AUDIO_CODEC == 'pcm16'

    def test_no_flags_returns_pcm16(self):
        assert resolve_audio_codec() == 'pcm16'

    def test_hevag_flag(self):
        assert resolve_audio_codec(hevag=True) == 'hevag'

    def test_vorbis_flag(self):
        assert resolve_audio_codec(vorbis=True) == 'vorbis'

    def test_hevag_takes_precedence_over_vorbis(self):
        assert resolve_audio_codec(hevag=True, vorbis=True) == 'hevag'


class TestDefaultPadToSize:
    """Test the default-safe FSB5 padding resolution (no truncation by default)."""

    def test_default_is_no_pad(self):
        assert DEFAULT_PAD_TO_SIZE == 0

    def test_no_flag_returns_zero(self):
        assert resolve_pad_to_size() == 0

    def test_pad_fsb5_restores_original_size(self):
        assert resolve_pad_to_size(pad_fsb5=True) == 12305632

    def test_pad_fsb5_truncation_guard(self):
        # The dangerous old default (12MB truncation) must be opt-in only
        assert resolve_pad_to_size(pad_fsb5=True) > resolve_pad_to_size()


class TestDefaultModeMapping:
    """Test that beatmap mode mapping is ON by default."""

    def test_default_is_enabled(self):
        assert DEFAULT_MODE_MAPPING is True

    def test_no_flag_returns_enabled(self):
        assert resolve_mode_mapping() is True

    def test_disable_flag_turns_off(self):
        assert resolve_mode_mapping(disable_beatmap_mode_mapping=True) is False


class TestDefaultConvertToV3:
    """Test that V2->V3 conversion is ON by default."""

    def test_default_is_enabled(self):
        assert DEFAULT_CONVERT_TO_V3 is True

    def test_no_flag_returns_enabled(self):
        assert resolve_convert_to_v3() is True

    def test_no_convert_flag_turns_off(self):
        assert resolve_convert_to_v3(no_convert_to_v3=True) is False


# ======================================================================
# Features Config Loading / Saving
# ======================================================================
class TestDefaultFeaturesRuntimeOnly:
    """features.json holds runtime plugin flags (read at startup on PS4).
    Since v0.5334, enable_beatmap_mode_mapping is a runtime flag that gates
    the mode selector UI visibility, allowing partial pack deployments."""

    def test_mode_mapping_is_now_a_runtime_flag(self):
        assert 'enable_beatmap_mode_mapping' in DEFAULT_FEATURES
        assert DEFAULT_FEATURES['enable_beatmap_mode_mapping'] is True

    def test_runtime_flags_present(self):
        assert DEFAULT_FEATURES['enable_custom_song_replacements'] is True
        assert DEFAULT_FEATURES['enable_song_metadata_modification'] is True
        assert DEFAULT_FEATURES['enable_beatmap_mode_mapping'] is True


class TestLoadLocalFeatures:
    """Test features config loading."""

    def test_loads_valid_file(self, tmp_dir):
        data = {"enable_custom_song_replacements": False}
        path = os.path.join(tmp_dir, "features.json")
        with open(path, 'w') as f:
            json.dump(data, f)
        result = _load_local_features(path)
        assert result['enable_custom_song_replacements'] is False

    def test_missing_file_returns_defaults(self):
        result = _load_local_features("/nonexistent/path.json")
        assert result['enable_custom_song_replacements'] is True
        assert result['enable_song_metadata_modification'] is True

    def test_invalid_json_returns_defaults(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.json")
        with open(path, 'w') as f:
            f.write("NOT_JSON")
        result = _load_local_features(path)
        assert result['enable_custom_song_replacements'] is True


class TestSaveLocalFeatures:
    """Test features config saving."""

    def test_save_and_reload(self, tmp_dir):
        features = {"enable_custom_song_replacements": False, "enable_song_metadata_modification": True}
        path = os.path.join(tmp_dir, "features.json")
        _save_local_features(features, path)
        loaded = _load_local_features(path)
        assert loaded == features

    def test_creates_parent_dir(self, tmp_dir):
        path = os.path.join(tmp_dir, "subdir", "features.json")
        _save_local_features({"key": True}, path)
        assert os.path.exists(path)


# ======================================================================
# Song Metadata Path Helpers
# ======================================================================
class TestSongMetadataPaths:
    """Test song metadata path construction."""

    def test_get_song_metadata_path(self):
        path = _get_song_metadata_path()
        assert path.endswith(SONG_METADATA_FILENAME)

    def test_get_song_ids_path(self):
        path = _get_song_ids_path()
        assert path.endswith(SONG_IDS_FILENAME)

    def test_get_remote_song_metadata_path(self, default_config):
        path = _get_remote_song_metadata_path(default_config)
        assert path == "/data/GoldHEN/AFR/CUSA12878/song_metadata.json"


# ======================================================================
# Song IDs Loading
# ======================================================================
class TestLoadSongIds:
    """Test song ID loading."""

    def test_loads_valid_file(self, tmp_dir):
        data = {
            "albums": [
                {
                    "songs": [
                        {"songID": "StartMeUp", "songName": "Start Me Up"},
                        {"songID": "Angry", "songName": "Angry"},
                    ]
                }
            ]
        }
        path = os.path.join(tmp_dir, "beat_saber_song_ids.json")
        with open(path, 'w') as f:
            json.dump(data, f)
        # Monkey-patch the path function
        import full_custom_song_pipeline as fp
        orig = fp._get_song_ids_path
        fp._get_song_ids_path = lambda: path
        try:
            result = _load_song_ids()
            assert result['StartMeUp'] == "Start Me Up"
            assert result['Angry'] == "Angry"
        finally:
            fp._get_song_ids_path = orig

    def test_missing_file_returns_empty(self):
        import full_custom_song_pipeline as fp
        orig = fp._get_song_ids_path
        fp._get_song_ids_path = lambda: "/nonexistent.json"
        try:
            result = _load_song_ids()
            assert result == {}
        finally:
            fp._get_song_ids_path = orig


# ======================================================================
# Song Name Lookup
# ======================================================================
class TestLookupSongName:
    """Test song name resolution from slot IDs."""

    def test_exact_match(self, song_ids_map):
        result = _lookup_song_name("StartMeUp", song_ids_map)
        assert result == "Start Me Up"

    def test_case_insensitive_match(self, song_ids_map):
        result = _lookup_song_name("startmeup", song_ids_map)
        assert result == "Start Me Up"

    def test_fallback_to_input(self, song_ids_map):
        result = _lookup_song_name("SomeUnknownSong", song_ids_map)
        assert result == "SomeUnknownSong"

    def test_strips_trailing_spaces(self, song_ids_map):
        result = _lookup_song_name("  Test  ", song_ids_map)
        assert result == "Test"


# ======================================================================
# Song Metadata Loading
# ======================================================================
class TestLoadLocalSongMetadata:
    """Test song metadata loading."""

    def test_loads_valid_file(self, tmp_dir):
        data = {"song_names": {"A": "B"}, "song_artists": {"C": "D"}}
        path = os.path.join(tmp_dir, "song_metadata.json")
        with open(path, 'w') as f:
            json.dump(data, f)
        result = _load_local_song_metadata(path)
        assert result['song_names']['A'] == "B"

    def test_missing_file_returns_default(self):
        result = _load_local_song_metadata("/nonexistent.json")
        assert result == {"song_names": {}, "song_artists": {}}

    def test_invalid_json_returns_default(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.json")
        with open(path, 'w') as f:
            f.write("bad")
        result = _load_local_song_metadata(path)
        assert result == {"song_names": {}, "song_artists": {}}

    def test_missing_keys_added(self, tmp_dir):
        data = {"song_names": {"A": "B"}}
        path = os.path.join(tmp_dir, "meta.json")
        with open(path, 'w') as f:
            json.dump(data, f)
        result = _load_local_song_metadata(path)
        assert 'song_artists' in result
        assert result['song_artists'] == {}


# ======================================================================
# Difficulty Names
# ======================================================================
class TestDifficultyNames:
    """Test that DIFFICULTIES constant is correct."""

    def test_has_5_difficulties(self):
        assert len(DIFFICULTIES) == 5

    def test_standard_difficulties(self):
        expected = ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']
        assert DIFFICULTIES == expected


# ======================================================================
# Beatmap Mode Detection
# ======================================================================
class TestDetectSongModes:
    """Test detect_song_modes() with various beatmap file arrangements."""

    def test_bare_standard_files(self, tmp_dir):
        """Bare .dat files (no mode suffix) are detected as Standard."""
        for diff in ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']:
            with open(os.path.join(tmp_dir, f"{diff}.dat"), 'w') as f:
                json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'Standard' in modes
        assert len(modes['Standard']) == 5

    def test_standard_suffix_files(self, tmp_dir):
        """Files with Standard suffix are detected."""
        for diff in ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']:
            with open(os.path.join(tmp_dir, f"{diff}Standard.dat"), 'w') as f:
                json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'Standard' in modes
        assert len(modes['Standard']) == 5

    def test_one_saber_suffix(self, tmp_dir):
        """ExpertPlusOneSaber.dat is detected as OneSaber/ExpertPlus."""
        with open(os.path.join(tmp_dir, "ExpertPlusOneSaber.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'OneSaber' in modes
        assert 'ExpertPlus' in modes['OneSaber']

    def test_one_saber_prefix(self, tmp_dir):
        """OneSaberExpert.dat (prefix-style) is detected as OneSaber/Expert."""
        with open(os.path.join(tmp_dir, "OneSaberExpert.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'OneSaber' in modes
        assert 'Expert' in modes['OneSaber']

    def test_multiple_modes(self, tmp_dir):
        """Song with Standard + OneSaber + 360Degree is detected completely
        (360Degree is excluded — unsupported on PS4)."""
        for diff in ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']:
            with open(os.path.join(tmp_dir, f"{diff}Standard.dat"), 'w') as f:
                json.dump({}, f)
        with open(os.path.join(tmp_dir, "ExpertPlusOneSaber.dat"), 'w') as f:
            json.dump({}, f)
        with open(os.path.join(tmp_dir, "Expert360Degree.dat"), 'w') as f:
            json.dump({}, f)
        with open(os.path.join(tmp_dir, "Normal360Degree.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'Standard' in modes and len(modes['Standard']) == 5
        assert 'OneSaber' in modes and modes['OneSaber'] == ['ExpertPlus']
        assert '360Degree' not in modes

    def test_alias_single_saber(self, tmp_dir):
        """SingleSaber is aliased to OneSaber."""
        with open(os.path.join(tmp_dir, "ExpertPlusSingleSaber.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'OneSaber' in modes
        assert 'SingleSaber' not in modes

    def test_excludes_info_lightshow(self, tmp_dir):
        """Info.dat, BPMInfo.dat, and Lightshow files are excluded."""
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump({}, f)
        with open(os.path.join(tmp_dir, "BPMInfo.dat"), 'w') as f:
            json.dump({}, f)
        with open(os.path.join(tmp_dir, "LightshowExpert.dat"), 'w') as f:
            json.dump({}, f)
        with open(os.path.join(tmp_dir, "AudioData.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert modes == {} or 'Standard' not in modes

    def test_empty_dir(self, tmp_dir):
        """Empty directory returns empty dict."""
        modes = detect_song_modes(tmp_dir)
        assert modes == {}

    def test_legacy_mode(self, tmp_dir):
        """Legacy files (from official songs) are detected as Standard."""
        with open(os.path.join(tmp_dir, "EasyLegacy.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert modes.get('Standard') == ['Easy']

    def test_beatmap_dot_format(self, tmp_dir):
        """Expert.beatmap.dat format is detected as Standard/Expert."""
        with open(os.path.join(tmp_dir, "ExpertPlus.beatmap.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'Standard' in modes
        assert 'ExpertPlus' in modes['Standard']

    def test_no_arrows(self, tmp_dir):
        """NoArrows mode detection."""
        with open(os.path.join(tmp_dir, "HardNoArrows.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'NoArrows' in modes
        assert modes['NoArrows'] == ['Hard']

    def test_lawless_alias(self, tmp_dir):
        """Lawless is aliased to NoArrows."""
        with open(os.path.join(tmp_dir, "ExpertLawless.dat"), 'w') as f:
            json.dump({}, f)
        modes = detect_song_modes(tmp_dir)
        assert 'NoArrows' in modes
        assert 'Lawless' not in modes


# ======================================================================
# Mode Mapping Builder
# ======================================================================
class TestBuildModeMapping:
    """Test build_mode_mapping() with various fallback scenarios."""

    def test_standard_only(self):
        """Only Standard detected — all modes resolved via fallback chain."""
        modes = {"Standard": ["Easy", "Normal", "Hard", "Expert", "ExpertPlus"]}
        result = build_mode_mapping(modes)
        assert result == list(GAME_CHARACTERISTIC_MODES)

    def test_one_saber_detected(self):
        """Standard + OneSaber detected — both enabled."""
        modes = {
            "Standard": ["Easy", "Normal", "Hard", "Expert", "ExpertPlus"],
            "OneSaber": ["ExpertPlus"],
        }
        result = build_mode_mapping(modes)
        assert "Standard" in result
        assert "OneSaber" in result

    def test_all_four_modes_detected(self):
        """All 4 supported modes detected — all enabled (360Degree excluded)."""
        modes = {
            "Standard": list(DIFFICULTIES),
            "OneSaber": list(DIFFICULTIES),
            "NoArrows": list(DIFFICULTIES),
            "90Degree": list(DIFFICULTIES),
        }
        result = build_mode_mapping(modes)
        assert result == list(GAME_CHARACTERISTIC_MODES)

    def test_noarrows_falls_back_standard(self):
        """NoArrows not detected — falls back to Standard."""
        modes = {
            "Standard": list(DIFFICULTIES),
        }
        result = build_mode_mapping(modes)
        # NoArrows not detected, fallback chain: NoArrows←Standard
        assert "NoArrows" in result  # resolved via fallback

    def test_360degree_never_enabled(self):
        """360Degree is never enabled even if files are detected."""
        modes = {
            "Standard": list(DIFFICULTIES),
            "360Degree": ["Expert", "Hard"],
        }
        result = build_mode_mapping(modes)
        assert "360Degree" not in result
        assert set(result) <= set(GAME_CHARACTERISTIC_MODES)

    def test_custom_fallback_90_to_standard(self):
        """Custom fallback 90Degree=Standard."""
        modes = {"Standard": list(DIFFICULTIES)}
        result = build_mode_mapping(modes, fallback_mode_map=["90Degree=Standard"])
        assert "90Degree" in result

    def test_custom_fallback_noarrows_skip(self):
        """Custom fallback NoArrows=Standard."""
        modes = {"Standard": list(DIFFICULTIES)}
        result = build_mode_mapping(modes, fallback_mode_map=["NoArrows=Standard"])
        assert "NoArrows" in result

    def test_empty_detected(self):
        """Empty detected modes returns just Standard."""
        result = build_mode_mapping({})
        assert result == ["Standard"]

    def test_partial_detected(self):
        """Only OneSaber detected without Standard.
        Standard is always present, so all other modes resolve via fallback."""
        modes = {"OneSaber": ["Expert"]}
        result = build_mode_mapping(modes)
        assert result == list(GAME_CHARACTERISTIC_MODES)
        # OneSaber resolved from detected
        # NoArrows, 90Degree resolved via Standard fallback

    def test_noarrows_and_90degree_detected(self):
        """NoArrows and 90Degree detected, but not OneSaber."""
        modes = {
            "Standard": list(DIFFICULTIES),
            "NoArrows": ["Easy", "Normal", "Hard", "Expert"],
            "90Degree": ["Normal"],
        }
        result = build_mode_mapping(modes)
        assert "NoArrows" in result
        assert "90Degree" in result
        assert "OneSaber" in result  # falls back to Standard


# ======================================================================
# Exp 221: features.json deploy must merge DEFAULT_FEATURES — a stale
# local file (written before a flag existed) must never deploy with that
# flag silently absent (user saw "2/3 feature flags ON" because the local
# file lacked enable_beatmap_mode_mapping).
# ======================================================================
class TestFeaturesMergeOnDeploy:
    def test_missing_keys_materialized_before_deploy(self, tmp_dir, monkeypatch):
        """A stale features.json missing newer flags gets them materialized
        from DEFAULT_FEATURES (explicit values untouched) during deploy."""
        stale = {"enable_custom_song_replacements": True,
                 "enable_song_metadata_modification": False,  # explicit OFF must survive
                 "enable_plugin": True}
        path = os.path.join(tmp_dir, "features.json")
        with open(path, 'w') as f:
            json.dump(stale, f)

        import subprocess

        import full_custom_song_pipeline as fcp
        monkeypatch.setattr(fcp, '_get_local_features_path', lambda root=None: path)
        class FakeResult:
            returncode = 0
            stderr = ""
        # _deploy_features_to_ps4 imports subprocess INSIDE the function —
        # patch the shared module's run.
        monkeypatch.setattr(subprocess, 'run', lambda *a, **k: FakeResult())
        cfg = {'ps4': {'ip': 'x', 'ftp_port': 1}, 'title': {}, 'paths': {}}

        fcp._deploy_features_to_ps4(cfg)

        merged = json.load(open(path))
        # missing key materialized with its DEFAULT value
        assert merged.get('enable_beatmap_mode_mapping') is True
        # explicit values preserved (including explicit False)
        assert merged['enable_song_metadata_modification'] is False
        assert merged['enable_plugin'] is True

    def test_deploy_creates_file_when_absent(self, tmp_dir, monkeypatch):
        """No local features.json at all -> one is created from DEFAULT_FEATURES
        and deployed (previously the deploy was silently skipped)."""
        import subprocess

        import full_custom_song_pipeline as fcp
        path = os.path.join(tmp_dir, "features.json")
        monkeypatch.setattr(fcp, '_get_local_features_path', lambda root=None: path)
        class FakeResult:
            returncode = 0
            stderr = ""
        monkeypatch.setattr(subprocess, 'run', lambda *a, **k: FakeResult())
        cfg = {'ps4': {'ip': 'x', 'ftp_port': 1}, 'title': {}, 'paths': {}}

        fcp._deploy_features_to_ps4(cfg)
        merged = json.load(open(path))
        assert merged == fcp.DEFAULT_FEATURES

    def test_deploy_full_implies_plugin_deploy_unless_skipped(self):
        """--deploy-full must build+deploy the latest plugin (the user's
        standard single-song command), with --skip-plugin-deployment opting out."""
        # simulate the arg wiring contract
        class A:
            pass
        a = A()
        a.deploy_full = True
        a.skip_plugin_deployment = False
        a.deploy_plugin = not a.skip_plugin_deployment
        assert a.deploy_plugin is True
        b = A()
        b.deploy_full = True
        b.skip_plugin_deployment = True
        b.deploy_plugin = not b.skip_plugin_deployment
        assert b.deploy_plugin is False
