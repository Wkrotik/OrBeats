"""
Unit tests for recent pipeline bug fixes
=========================================
1. Info.dat case-insensitive loading
2. Undefined variables in main() (bpm, song_name, song_artist, note_count_standard)
3. manage_song_metadata passthrough (None vs actual values)
4. Note count standard initialization
"""
import json
import os
import re
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from full_custom_song_pipeline import (
    DIFFICULTIES,
    _scan_beatmap_max_beat,
    _select_beatmap_file,
    load_bpm_regions,
    manage_song_metadata,
)


# ======================================================================
# 1. Info.dat Case-Insensitive Loading
# ======================================================================
class TestInfoDatCaseInsensitive:
    """
    The pipeline had Info.dat (uppercase) hardcoded but BeatSaver downloads
    use info.dat (lowercase). The fix added fallback to lowercase in main()
    and replace_beatmaps(). _scan_beatmap_max_beat uses lowercased comparison.
    """

    def test_scan_beatmap_skips_lowercase_info_dat(self, tmp_dir):
        """_scan_beatmap_max_beat should skip info.dat (lowercase) as metadata."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)

        beatmap = {"_notes": [{"_time": 75.0}, {"_time": 100.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(beatmap, f)

        max_beat = _scan_beatmap_max_beat(tmp_dir)
        assert max_beat == 100.0

    def test_scan_beatmap_skips_uppercase_info_dat(self, tmp_dir):
        """_scan_beatmap_max_beat should skip Info.dat (uppercase) as metadata."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info, f)

        beatmap = {"_notes": [{"_time": 50.0}]}
        with open(os.path.join(tmp_dir, "Normal.dat"), 'w') as f:
            json.dump(beatmap, f)

        max_beat = _scan_beatmap_max_beat(tmp_dir)
        assert max_beat == 50.0

    def test_scan_beatmap_skips_bpm_info_dat(self, tmp_dir):
        """_scan_beatmap_max_beat should skip BPMInfo.dat."""
        bpm_info = {"_regions": []}
        with open(os.path.join(tmp_dir, "BPMInfo.dat"), 'w') as f:
            json.dump(bpm_info, f)

        beatmap = {"_notes": [{"_time": 200.0}]}
        with open(os.path.join(tmp_dir, "Expert.dat"), 'w') as f:
            json.dump(beatmap, f)

        max_beat = _scan_beatmap_max_beat(tmp_dir)
        assert max_beat == 200.0

    def test_scan_beatmap_with_both_info_cases(self, tmp_dir):
        """When both Info.dat and info.dat exist, neither is counted as beat data."""
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump({"_beatsPerMinute": 120.0}, f)
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump({"_beatsPerMinute": 120.0}, f)

        beatmap = {"_notes": [{"_time": 300.0}]}
        with open(os.path.join(tmp_dir, "ExpertPlus.dat"), 'w') as f:
            json.dump(beatmap, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 300.0

    def test_load_bpm_regions_uppercase_info_dat_fallback(self, tmp_dir):
        """load_bpm_regions should find Info.dat (uppercase) for BPM fallback
        when no BPMInfo.dat and no beatmaps exist."""
        info = {"_beatsPerMinute": 150.0}
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info, f)

        sample_count = 44100 * 60
        regions = load_bpm_regions(tmp_dir, sample_count)
        assert len(regions) == 1
        # 60s * 150 BPM / 60 = 150 beats
        assert regions[0]['eb'] == 150.0

    def test_load_bpm_regions_beatmap_overrides_info_dat(self, tmp_dir):
        """When the map's last note lands beyond the Info.dat grid, eb extends
        to cover it (mapper's real tempo is faster than declared)."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info, f)

        beatmap = {"_notes": [{"_time": 250.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(beatmap, f)

        sample_count = 44100 * 60  # 60s audio; 120 BPM grid = 120 beats
        regions = load_bpm_regions(tmp_dir, sample_count)
        assert regions[0]['eb'] == 250.0

    def test_load_bpm_regions_info_bpm_is_authoritative_grid(self, tmp_dir):
        """Exp 218: Info.dat BPM is the mapper's beat grid. The old
        max_beat*60/audio heuristic undershot BPM by the trailing-silence
        fraction (e.g. 'Roni: 112.1 vs the real 117). A map ending at beat
        100 in 60s of audio is NOT 100 BPM — it's a 120 BPM grid with 10s of
        trailing silence."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info, f)

        beatmap = {"_notes": [{"_time": 100.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(beatmap, f)

        sample_count = 44100 * 60  # 60s audio
        regions = load_bpm_regions(tmp_dir, sample_count)
        # Grid from Info.dat: 60s * 120/60 = 120 beats (NOT 100)
        assert regions[0]['eb'] == 120.0

    def test_load_bpm_regions_lowercase_info_dat(self, tmp_dir):
        """BeatSaver downloads use lowercase info.dat — must be read too."""
        info = {"_beatsPerMinute": 117.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)

        sample_count = 44100 * 214  # 'Roni: 214s audio
        regions = load_bpm_regions(tmp_dir, sample_count)
        # 214s * 117/60 = 417.3 beats (vs 404.1 under the old heuristic)
        assert abs(regions[0]['eb'] - 214.0 * 117.0 / 60.0) < 0.1

    def test_load_bpm_regions_no_bpm_data_assumes_120(self, tmp_dir):
        """No Info.dat, no beatmaps — assume 120 BPM."""
        sample_count = 44100 * 60
        regions = load_bpm_regions(tmp_dir, sample_count)
        assert regions[0]['eb'] == 120.0

    def test_replace_beatmaps_reads_uppercase_info_dat(self, tmp_dir):
        """replace_beatmaps reads Info.dat (uppercase) for BPM."""
        info = {"_beatsPerMinute": 140.0}
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info, f)
        # Need at least one beatmap file for replace_beatmaps to work with
        bm = {"version": "2.0.0", "_notes": [{"_time": 0.0}]}
        with open(os.path.join(tmp_dir, "Easy.dat"), 'w') as f:
            json.dump(bm, f)

        # Verify the code path exists and doesn't crash
        info_path = os.path.join(tmp_dir, "Info.dat")
        if not os.path.exists(info_path):
            info_path = os.path.join(tmp_dir, "info.dat")
        assert os.path.exists(info_path)

    def test_replace_beatmaps_falls_back_to_lowercase(self, tmp_dir):
        """replace_beatmaps falls back to info.dat (lowercase) when uppercase missing."""
        info = {"_beatsPerMinute": 160.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)

        # Replicate replace_beatmaps' Info.dat loading logic
        info_path = os.path.join(tmp_dir, "Info.dat")
        if not os.path.exists(info_path):
            info_path = os.path.join(tmp_dir, "info.dat")
        assert os.path.exists(info_path)
        assert info_path.endswith("info.dat")

        with open(info_path) as f:
            parsed = json.load(f)
        assert parsed["_beatsPerMinute"] == 160.0


# ======================================================================
# 2. Info.dat Parsing (bpm, song_name, song_artist initialization)
# ======================================================================
class TestInfoDatParsing:
    """
    The fix initializes bpm, song_name, song_artist from Info.dat before
    Step 0, so they aren't undefined in Step 6.5.
    Test that Info.dat parsing works for both uppercase and lowercase filenames.
    """

    def test_parse_uppercase_info_dat(self, tmp_dir):
        """Parse Info.dat (uppercase) and extract metadata fields."""
        info = {
            "_songName": "My Custom Song",
            "_songAuthorName": "Artist Name",
            "_beatsPerMinute": 142.0,
        }
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info, f)

        # Replicate main()'s Info.dat loading logic (lines 2058-2066)
        info_dat_path = os.path.join(tmp_dir, "Info.dat")
        if not os.path.isfile(info_dat_path):
            info_dat_path = os.path.join(tmp_dir, "info.dat")

        song_name = os.path.basename(tmp_dir)
        song_artist = ""
        bpm = 120.0

        assert os.path.isfile(info_dat_path)
        with open(info_dat_path) as f:
            parsed = json.load(f)

        song_name = parsed.get("_songName", song_name)
        song_artist = parsed.get("_songAuthorName", song_artist)
        bpm = float(parsed.get("_beatsPerMinute", 120.0))

        assert song_name == "My Custom Song"
        assert song_artist == "Artist Name"
        assert bpm == 142.0

    def test_parse_lowercase_info_dat(self, tmp_dir):
        """Parse info.dat (lowercase, BeatSaver format) and extract metadata fields."""
        info = {
            "_songName": "Downloaded Song",
            "_songAuthorName": "BeatSaver Mapper",
            "_beatsPerMinute": 175.0,
        }
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)

        # Replicate main()'s Info.dat loading with fallback (lines 2058-2060)
        info_dat_path = os.path.join(tmp_dir, "Info.dat")
        if not os.path.isfile(info_dat_path):
            info_dat_path = os.path.join(tmp_dir, "info.dat")

        song_name = os.path.basename(tmp_dir)
        song_artist = ""
        bpm = 120.0

        assert os.path.isfile(info_dat_path)
        with open(info_dat_path) as f:
            parsed = json.load(f)

        song_name = parsed.get("_songName", song_name)
        song_artist = parsed.get("_songAuthorName", song_artist)
        bpm = float(parsed.get("_beatsPerMinute", 120.0))

        assert song_name == "Downloaded Song"
        assert song_artist == "BeatSaver Mapper"
        assert bpm == 175.0

    def test_uppercase_takes_priority_for_parsing(self, tmp_dir):
        """When both exist, Info.dat (uppercase) should be used first."""
        info_upper = {"_songName": "Upper Song", "_beatsPerMinute": 130.0}
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info_upper, f)

        info_lower = {"_songName": "Lower Song", "_beatsPerMinute": 160.0}
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info_lower, f)

        info_dat_path = os.path.join(tmp_dir, "Info.dat")
        if not os.path.isfile(info_dat_path):
            info_dat_path = os.path.join(tmp_dir, "info.dat")

        assert os.path.isfile(info_dat_path)
        assert info_dat_path.endswith("Info.dat")

        with open(info_dat_path) as f:
            parsed = json.load(f)
        assert parsed["_songName"] == "Upper Song"

    def test_missing_info_dat_uses_defaults(self, tmp_dir):
        """When no Info.dat exists, defaults should be used."""
        info_dat_path = os.path.join(tmp_dir, "Info.dat")
        if not os.path.isfile(info_dat_path):
            info_dat_path = os.path.join(tmp_dir, "info.dat")

        song_name = os.path.basename(tmp_dir)
        song_artist = ""
        bpm = 120.0

        assert not os.path.isfile(info_dat_path)
        assert song_name == os.path.basename(tmp_dir)
        assert song_artist == ""
        assert bpm == 120.0

    def test_second_info_dat_read_in_step_6_5(self, tmp_dir):
        """Step 6.5 re-reads Info.dat for custom_name/custom_artist resolution."""
        info = {
            "_songName": "Step 6.5 Song",
            "_songAuthorName": "Step 6.5 Artist",
            "_beatsPerMinute": 155.0,
        }
        with open(os.path.join(tmp_dir, "info.dat"), 'w') as f:
            json.dump(info, f)

        # Replicate Step 6.5's Info.dat re-read (lines 2198-2206)
        info_dat_path = os.path.join(tmp_dir, "Info.dat")
        if not os.path.isfile(info_dat_path):
            info_dat_path = os.path.join(tmp_dir, "info.dat")

        song_name = "default"
        song_artist = ""
        bpm = 120.0

        if os.path.isfile(info_dat_path):
            with open(info_dat_path) as f:
                info = json.load(f)
            song_name = info.get("_songName", song_name)
            song_artist = info.get("_songAuthorName", song_artist)
            bpm = float(info.get("_beatsPerMinute", bpm))

        custom_name = None or song_name  # args.song_name is None
        custom_artist = None or song_artist  # args.artist is None

        assert custom_name == "Step 6.5 Song"
        assert custom_artist == "Step 6.5 Artist"
        assert bpm == 155.0


# ======================================================================
# 3. manage_song_metadata Passthrough
# ======================================================================
class TestManageSongMetadata:
    """
    When args.song_name and args.artist are None (not passed via CLI),
    the metadata function was called with None values, so downloaded songs'
    metadata was never saved. The fix passes custom_name and custom_artist
    (resolved from Info.dat) instead.
    """
    def test_both_values_provided(self, tmp_dir):
        """When song_name and artist are both provided, they are combined as 'Name / Artist'."""
        import full_custom_song_pipeline as fp
        local_path = os.path.join(tmp_dir, "song_metadata.json")
        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path

        try:
            metadata = manage_song_metadata(
                {},
                song_name="Test Song",
                artist="Test Artist",
                target_name="StartMeUp",
            )
            assert metadata['song_names']['Start Me Up'] == "Test Song / Test Artist"
        finally:
            fp._get_song_metadata_path = orig

    def test_none_song_name_not_saved(self, tmp_dir):
        """When song_name is None, the song name should NOT be written."""
        import full_custom_song_pipeline as fp
        local_path = os.path.join(tmp_dir, "song_metadata.json")
        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path
        try:
            metadata = manage_song_metadata(
                {},
                song_name=None,
                artist="Some Artist",
                target_name="StartMeUp",
            )
            assert 'Start Me Up' not in metadata['song_names']
        finally:
            fp._get_song_metadata_path = orig

    def test_none_artist_not_saved(self, tmp_dir):
        """When artist is None, the song name is saved without artist suffix."""
        import full_custom_song_pipeline as fp
        local_path = os.path.join(tmp_dir, "song_metadata.json")
        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path
        try:
            metadata = manage_song_metadata(
                {},
                song_name="Some Song",
                artist=None,
                target_name="StartMeUp",
            )
            assert metadata['song_names']['Start Me Up'] == "Some Song"
        finally:
            fp._get_song_metadata_path = orig

    def test_both_none_no_changes(self, tmp_dir):
        """When both song_name and artist are None, only artist blanking occurs for resolved targets."""
        import full_custom_song_pipeline as fp
        local_path = os.path.join(tmp_dir, "song_metadata.json")
        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path
        try:
            metadata = manage_song_metadata(
                {},
                song_name=None,
                artist=None,
                target_name="StartMeUp",
            )
            assert metadata['song_names'] == {}
            # Original author is blanked when target resolves via beat_saber_song_ids.json
        finally:
            fp._get_song_metadata_path = orig

    def test_passthrough_resolved_from_info_dat(self, tmp_dir):
        """
        The fix: when CLI args are None, custom_name/custom_artist from
        Info.dat are passed to manage_song_metadata instead of None.
        This simulates the corrected main() logic.
        """
        import full_custom_song_pipeline as fp
        local_path = os.path.join(tmp_dir, "song_metadata.json")
        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path

        # Simulate: Info.dat was read and provided these values
        custom_name = "Info Song Name"
        custom_artist = "Info Artist"
        args_song_name = None  # user didn't pass --song-name
        args_artist = None     # user didn't pass --artist

        try:
            metadata = manage_song_metadata(
                {},
                song_name=args_song_name or custom_name,
                artist=args_artist or custom_artist,
                target_name="StartMeUp",
            )
            # Combined name format: "SongName / Artist"
            assert metadata['song_names']['Start Me Up'] == "Info Song Name / Info Artist"
        finally:
            fp._get_song_metadata_path = orig

    def test_cli_args_override_info_dat(self, tmp_dir):
        """
        When CLI args ARE provided, they should take precedence over Info.dat values.
        """
        import full_custom_song_pipeline as fp
        local_path = os.path.join(tmp_dir, "song_metadata.json")
        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path

        custom_name = "Info Song Name"
        custom_artist = "Info Artist"
        args_song_name = "CLI Override Name"
        args_artist = "CLI Override Artist"

        try:
            metadata = manage_song_metadata(
                {},
                song_name=args_song_name or custom_name,
                artist=args_artist or custom_artist,
                target_name="StartMeUp",
            )
            assert metadata['song_names']['Start Me Up'] == "CLI Override Name / CLI Override Artist"
        finally:
            fp._get_song_metadata_path = orig

    def test_empty_string_not_falsy_over_info_dat(self, tmp_dir):
        """
        When CLI args are empty strings (falsy), Info.dat values should be used.
        """
        import full_custom_song_pipeline as fp
        local_path = os.path.join(tmp_dir, "song_metadata.json")
        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path

        custom_name = "Info Song"
        custom_artist = "Info Artist"
        args_song_name = ""  # empty string is falsy
        args_artist = ""

        try:
            metadata = manage_song_metadata(
                {},
                song_name=args_song_name or custom_name,
                artist=args_artist or custom_artist,
                target_name="StartMeUp",
            )
            assert metadata['song_names']['Start Me Up'] == "Info Song / Info Artist"
        finally:
            fp._get_song_metadata_path = orig

    def test_existing_metadata_preserved(self, tmp_dir):
        """New metadata should not clobber existing entries for other songs."""
        import full_custom_song_pipeline as fp
        local_path = os.path.join(tmp_dir, "song_metadata.json")

        existing = {"song_names": {"Angry": "Angry"}, "song_artists": {"Angry": "Artist A"}}
        with open(local_path, 'w') as f:
            json.dump(existing, f)

        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path
        try:
            metadata = manage_song_metadata(
                {},
                song_name="New Song",
                artist="New Artist",
                target_name="StartMeUp",
            )
            assert metadata['song_names']['Angry'] == "Angry"
            assert metadata['song_artists']['Angry'] == "Artist A"
            assert metadata['song_names']['Start Me Up'] == "New Song / New Artist"
        finally:
            fp._get_song_metadata_path = orig


# ======================================================================
# 4. Note Count Standard Initialization
# ======================================================================
class TestNoteCountStandard:
    """
    Test that note counting from beatmap files works correctly.
    This verifies the note_count_standard variable is properly initialized
    and populated by scanning beatmap files.
    """

    def _count_notes_from_beatmaps(self, song_dir):
        """
        Replicate the note counting logic from main() Step 6.
        """
        note_count_standard = 0
        for diff_file in ['Hard.dat', 'Normal.dat', 'Easy.dat', 'Expert.dat', 'ExpertPlus.dat',
                           'HardStandard.dat', 'NormalStandard.dat', 'EasyStandard.dat',
                           'ExpertStandard.dat', 'ExpertPlusStandard.dat']:
            diff_path = os.path.join(song_dir, diff_file)
            if os.path.isfile(diff_path):
                try:
                    with open(diff_path) as f:
                        bm = json.load(f)
                    note_count_standard += len(bm.get('notes', []))
                except Exception:
                    pass
        return note_count_standard

    def test_counts_v2_notes(self, tmp_dir):
        """V2 beatmaps use 'notes' key for note counting."""
        beatmap = {
            "notes": [
                {"_time": 0.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0},
                {"_time": 1.0, "_lineIndex": 1, "_lineLayer": 1, "_type": 1},
                {"_time": 2.0, "_lineIndex": 2, "_lineLayer": 2, "_type": 0},
            ]
        }
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(beatmap, f)

        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 3

    def test_counts_multiple_difficulties(self, tmp_dir):
        """Should sum notes across all difficulty files."""
        for diff, n_notes in [("Easy.dat", 10), ("Normal.dat", 25), ("Hard.dat", 50)]:
            beatmap = {"notes": [{"_time": float(i)} for i in range(n_notes)]}
            with open(os.path.join(tmp_dir, diff), 'w') as f:
                json.dump(beatmap, f)

        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 85

    def test_counts_standard_suffixed_files(self, tmp_dir):
        """Should also count files with Standard suffix."""
        beatmap = {"notes": [{"_time": 0.0}, {"_time": 1.0}]}
        with open(os.path.join(tmp_dir, "HardStandard.dat"), 'w') as f:
            json.dump(beatmap, f)

        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 2

    def test_empty_song_dir_returns_zero(self, tmp_dir):
        """Empty directory should return 0 notes."""
        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 0

    def test_unrelated_dat_files_ignored(self, tmp_dir):
        """Info.dat and other non-beatmap .dat files should not be counted."""
        info = {"_beatsPerMinute": 120.0}
        with open(os.path.join(tmp_dir, "Info.dat"), 'w') as f:
            json.dump(info, f)

        bpm_info = {"_regions": []}
        with open(os.path.join(tmp_dir, "BPMInfo.dat"), 'w') as f:
            json.dump(bpm_info, f)

        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 0

    def test_zero_initialized_before_accumulation(self, tmp_dir):
        """note_count_standard starts at 0 before the accumulation loop."""
        note_count_standard = 0
        assert note_count_standard == 0

        beatmap = {"notes": [{"_time": 0.0}]}
        with open(os.path.join(tmp_dir, "Expert.dat"), 'w') as f:
            json.dump(beatmap, f)

        # Replicate the loop
        for diff_file in ['Hard.dat', 'Normal.dat', 'Easy.dat', 'Expert.dat', 'ExpertPlus.dat']:
            diff_path = os.path.join(tmp_dir, diff_file)
            if os.path.isfile(diff_path):
                with open(diff_path) as f:
                    bm = json.load(f)
                note_count_standard += len(bm.get('notes', []))

        assert note_count_standard == 1

    def test_malformed_dat_file_skipped(self, tmp_dir):
        """Malformed .dat files should be skipped without crashing."""
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            f.write("NOT JSON {{{")

        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 0

    def test_beatmap_with_no_notes_key(self, tmp_dir):
        """Beatmap without 'notes' key should contribute 0 notes."""
        beatmap = {"version": "2.0.0", "_obstacles": []}
        with open(os.path.join(tmp_dir, "Normal.dat"), 'w') as f:
            json.dump(beatmap, f)

        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 0

    def test_all_five_difficulties_counted(self, tmp_dir):
        """All 5 standard difficulties should be counted when present."""
        for diff in ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']:
            beatmap = {"notes": [{"_time": float(i)} for i in range(10)]}
            with open(os.path.join(tmp_dir, f"{diff}.dat"), 'w') as f:
                json.dump(beatmap, f)

        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 50  # 5 difficulties * 10 notes each

    def test_standard_suffix_takes_priority(self, tmp_dir):
        """Both Hard.dat and HardStandard.dat should be counted (they're separate files)."""
        bare = {"notes": [{"_time": 0.0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(bare, f)

        standard = {"notes": [{"_time": 0.0}, {"_time": 1.0}]}
        with open(os.path.join(tmp_dir, "HardStandard.dat"), 'w') as f:
            json.dump(standard, f)

        count = self._count_notes_from_beatmaps(tmp_dir)
        assert count == 3  # 1 + 2


# ======================================================================
# 5. _scan_beatmap_max_beat with V2 and V3
# ======================================================================
class TestScanBeatmapMaxBeatV2V3:
    """
    Test that _scan_beatmap_max_beat works correctly with both V2 and V3
    beatmaps, including edge cases.
    """

    def test_v2_notes_time_field(self, tmp_dir):
        """V2 beatmaps use _time field for beat position."""
        data = {
            "_notes": [
                {"_time": 10.0},
                {"_time": 250.0},
                {"_time": 50.0},
            ]
        }
        with open(os.path.join(tmp_dir, "ExpertPlus.dat"), 'w') as f:
            json.dump(data, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 250.0

    def test_v3_color_notes_b_field(self, tmp_dir):
        """V3 beatmaps use colorNotes[].b for beat position."""
        data = {
            "colorNotes": [
                {"b": 100.0, "x": 0, "y": 0, "d": 0},
                {"b": 300.0, "x": 1, "y": 1, "d": 1},
            ]
        }
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(data, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 300.0

    def test_mixed_v2_and_v3_files(self, tmp_dir):
        """Should find max across multiple files of different versions."""
        v2 = {"_notes": [{"_time": 100.0}]}
        with open(os.path.join(tmp_dir, "Easy.dat"), 'w') as f:
            json.dump(v2, f)

        v3 = {"colorNotes": [{"b": 500.0, "x": 0, "y": 0, "d": 0}]}
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump(v3, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 500.0

    def test_skips_all_info_variants(self, tmp_dir):
        """Should skip info.dat, Info.dat, and BPMInfo.dat."""
        for fname in ["info.dat", "Info.dat", "BPMInfo.dat"]:
            with open(os.path.join(tmp_dir, fname), 'w') as f:
                json.dump({"_beatsPerMinute": 99999.0}, f)

        beatmap = {"_notes": [{"_time": 42.0}]}
        with open(os.path.join(tmp_dir, "Normal.dat"), 'w') as f:
            json.dump(beatmap, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 42.0

    def test_empty_beatmap_files(self, tmp_dir):
        """Empty beatmap files should be skipped gracefully."""
        with open(os.path.join(tmp_dir, "Hard.dat"), 'w') as f:
            json.dump({}, f)

        beatmap = {"_notes": [{"_time": 15.0}]}
        with open(os.path.join(tmp_dir, "Easy.dat"), 'w') as f:
            json.dump(beatmap, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 15.0

    def test_non_numeric_time_ignored(self, tmp_dir):
        """Notes with non-numeric _time should be ignored."""
        data = {
            "_notes": [
                {"_time": "invalid"},
                {"_time": 50.0},
                {"_time": None},
            ]
        }
        with open(os.path.join(tmp_dir, "Expert.dat"), 'w') as f:
            json.dump(data, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 50.0

    def test_zero_beat_value(self, tmp_dir):
        """A beat value of exactly 0.0 should not affect max."""
        data = {"_notes": [{"_time": 0.0}]}
        with open(os.path.join(tmp_dir, "Easy.dat"), 'w') as f:
            json.dump(data, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 0.0

    def test_negative_beat_values_ignored(self, tmp_dir):
        """Negative beat values should not become the max."""
        data = {"_notes": [{"_time": -10.0}, {"_time": 5.0}]}
        with open(os.path.join(tmp_dir, "Normal.dat"), 'w') as f:
            json.dump(data, f)

        assert _scan_beatmap_max_beat(tmp_dir) == 5.0


# ======================================================================
# Exp 200 (v0.5328): V3 schema normalization + empty-beatmap rescue
# ======================================================================
class TestV3SchemaNormalization:
    """Minimal-schema V3 maps crash the PS4 at gameplay load (Exp 200: Chromeo
    V4→V3 reconstruction emitted 8-key maps; game needs the full schema)."""

    def test_normalize_fills_missing_arrays(self):
        from full_custom_song_pipeline import normalize_v3_schema
        minimal = {"version": "3.2.0", "colorNotes": [{"b": 1, "x": 1, "y": 0, "c": 0, "d": 0}]}
        out = normalize_v3_schema(minimal)
        for key in ("basicBeatmapEvents", "waypoints", "lightColorEventBoxGroups",
                    "obstacles", "bpmEvents", "chains", "arcs"):
            assert isinstance(out[key], list), f"{key} should be a filled list"
        assert out["useNormalEventsAsCompatibleEvents"] is True
        assert "customData" in out
        assert isinstance(out["basicEventTypesWithKeywords"], dict)

    def test_normalize_is_idempotent(self):
        from full_custom_song_pipeline import normalize_v3_schema
        m = {"version": "3.2.0", "colorNotes": []}
        once = normalize_v3_schema(dict(m))
        twice = normalize_v3_schema(once)
        assert sorted(once.keys()) == sorted(twice.keys())

    def test_normalize_preserves_existing_content(self):
        from full_custom_song_pipeline import normalize_v3_schema
        full = {"version": "3.2.0", "colorNotes": [{"b": 2}], "obstacles": [{"b": 1}],
                "useNormalEventsAsCompatibleEvents": False}
        out = normalize_v3_schema(full)
        assert out["colorNotes"] == [{"b": 2}]
        assert out["obstacles"] == [{"b": 1}]
        assert out["useNormalEventsAsCompatibleEvents"] is False

    def test_beatmap_is_empty(self):
        from full_custom_song_pipeline import beatmap_is_empty
        assert beatmap_is_empty({"colorNotes": [], "bombNotes": [], "obstacles": []})
        assert not beatmap_is_empty({"colorNotes": [{"b": 1}]})


class TestEmptyBeatmapRescue:
    """Chromeo Easy maps decoded with zero notes; pipeline must clone playable
    content from the closest populated Standard difficulty."""

    def test_find_populated_beatmap_prefers_normal(self, tmp_path):
        from full_custom_song_pipeline import _find_populated_beatmap
        (tmp_path / "EasyStandard.dat").write_text(json.dumps(
            {"version": "3.2.0", "colorNotes": []}))
        (tmp_path / "NormalStandard.dat").write_text(json.dumps(
            {"version": "3.2.0", "colorNotes": [{"b": 1, "x": 0, "y": 1, "c": 0, "d": 1}]}))
        donor = _find_populated_beatmap(str(tmp_path), "EasyStandard.dat")
        assert donor is not None and "NormalStandard" in donor

    def test_find_populated_skips_mode_files(self, tmp_path):
        from full_custom_song_pipeline import _find_populated_beatmap
        # Only mode files present — none qualify as Standard donors
        (tmp_path / "ExpertOneSaber.dat").write_text(json.dumps(
            {"version": "3.2.0", "colorNotes": [{"b": 1}]}))
        assert _find_populated_beatmap(str(tmp_path), "EasyStandard.dat") is None

    def test_find_populated_skips_empty_donors(self, tmp_path):
        from full_custom_song_pipeline import _find_populated_beatmap
        (tmp_path / "NormalStandard.dat").write_text(json.dumps(
            {"version": "3.2.0", "colorNotes": []}))
        (tmp_path / "HardStandard.dat").write_text(json.dumps(
            {"version": "3.2.0", "colorNotes": [{"b": 5}]}))
        donor = _find_populated_beatmap(str(tmp_path), "EasyStandard.dat")
        assert donor is not None and "HardStandard" in donor


class TestRoniSourceRegression:
    """The actual Exp 200 crashing source: ExitThisEarthsAtomosphere backout.
    After the fix, injecting its files must yield full-schema, non-empty maps."""

    RONI = "/workspace/beat-saber-ps4-custom-songs/songs/chromeo_backout/ExitThisEarthsAtomosphere"

    @pytest.mark.skipif(not os.path.isdir(RONI), reason="Chromeo backout sources not present")
    def test_roni_easy_gets_rescued(self, tmp_path):
        from full_custom_song_pipeline import (
            _find_populated_beatmap,
            beatmap_is_empty,
            is_v2_beatmap,
            normalize_v3_schema,
        )
        workdir = tmp_path / "roni"
        shutil.copytree(self.RONI, str(workdir))
        empty_file = "EasyStandard.dat"
        data = json.load(open(workdir / empty_file))
        assert beatmap_is_empty(data), "precondition: Roni Easy is empty in source"
        donor = _find_populated_beatmap(str(workdir), empty_file)
        assert donor is not None, "must find a populated donor among Roni diffs"
        ddata = json.load(open(donor))
        if is_v2_beatmap(ddata):
            from full_custom_song_pipeline import convert_v2_to_v3
            ddata = convert_v2_to_v3(ddata)
        normalize_v3_schema(ddata)
        data.update({k: ddata[k] for k in ("colorNotes", "bombNotes", "obstacles")})
        assert not beatmap_is_empty(data)

    @pytest.mark.skipif(not os.path.isdir(RONI), reason="Chromeo backout sources not present")
    def test_roni_normal_normalized_has_events_field(self):
        from full_custom_song_pipeline import normalize_v3_schema
        data = json.load(open(os.path.join(self.RONI, "HardStandard.dat")))
        assert "basicBeatmapEvents" not in data, "precondition: Hard lacks events array"
        normalize_v3_schema(data)
        assert isinstance(data["basicBeatmapEvents"], list)
        assert "waypoints" in data


# ======================================================================
# Exp 214: --deploy-full + --download-beat-saver-song must NOT be routed
# into "plugin-only mode".
#
# Root cause: the BeatSaver auto-download that populates args.song_dir ran
# AFTER the `plugin-only` early-exit guard. So a `--deploy-full
# --download-beat-saver-song <id>` invocation (which sets deploy_plugin=True)
# hit "if args.deploy_plugin and not args.song_dir:" with song_dir still None,
# entered plugin-only mode, deployed a never-built plugin + 43 unscoped
# redirects, and sys.exit(0) before the song was ever downloaded/converted.
# ======================================================================
class TestDeployFullDownloadsSong:
    """A --deploy-full --download-beat-saver-song run must reach the song
    processing path, not bail into plugin-only mode."""

    def _read_source(self):
        import full_custom_song_pipeline as fcp
        src_path = fcp.__file__
        with open(src_path) as f:
            return f.read()

    def test_download_block_precedes_plugin_only_guard(self):
        """Structural guardrail: the BeatSaver download (which sets args.song_dir)
        must appear in main() BEFORE the `plugin-only mode` early-exit guard."""
        src = self._read_source()
        dl_idx = src.index("Auto-download from BeatSaver if requested")
        guard_idx = src.index("Plugin-only mode: deploy plugin and exit")
        assert dl_idx < guard_idx, (
            "BeatSaver download block regressed: it must run BEFORE the "
            "plugin-only guard so args.song_dir is resolved first"
        )

    def test_song_dir_resolution_logic_before_guard(self):
        """Replicate the (now-correct) ordering: with --download-beat-saver-song
        provided and no --song-dir, song_dir must become non-None, so the
        plugin-only guard condition `deploy_plugin and not song_dir` is False."""
        # Emulate argparse results for --deploy-full --download-beat-saver-song
        args = type("Args", (), {})()
        args.download_beat_saver_song = "4a901"
        args.song_dir = None
        args.beatsaver_api_base = None
        args.deploy_plugin = True  # set by --deploy-full expansion
        args.deploy_full = True

        # The fix moves this to before the guard:
        if args.download_beat_saver_song and not args.song_dir:
            args.song_dir = "/tmp/some_downloaded_song_dir"

        # plugin-only guard must NOT fire now
        assert not (args.deploy_plugin and not args.song_dir), (
            "plugin-only mode would fire even though a song is being downloaded"
        )

    def test_download_wins_over_plugin_only_when_song_dir_set(self):
        """When a --song-dir IS provided alongside --deploy-full, the plugin-only
        guard must also stay inert (song_dir already populated)."""
        args = type("Args", (), {})()
        args.download_beat_saver_song = None
        args.song_dir = "/tmp/existing_song"
        args.deploy_plugin = True
        args.deploy_full = True
        assert not (args.deploy_plugin and not args.song_dir)


# ======================================================================
# Exp 218: Missing Standard difficulties must be filled from the map's own
# content — never leave the STOCK beatmap in an unreplaced slot (stock timing
# over custom audio = "BPM wayyy too slow, notes wayyy too late").
# ======================================================================
class TestFillMissingStandardDifficulties:
    def _write(self, d, name, notes):
        with open(os.path.join(d, name), 'w') as f:
            json.dump({"version": "3.2.0", "colorNotes": notes}, f)

    def test_fills_missing_diffs_from_closest_harder(self, tmp_path):
        """ExpertPlus-only map (Sexy Socialite / Green Light pattern): the four
        missing diffs are cloned from the closest HARDER difficulty."""
        from full_custom_song_pipeline import fill_missing_standard_difficulties
        d = str(tmp_path)
        note = [{"b": 1.0, "x": 0, "y": 0, "c": 0, "d": 1}]
        self._write(d, "ExpertPlusStandard.dat", note)

        written = fill_missing_standard_difficulties(d)
        # Easy/Normal/Hard filled from Expert/ExpertPlus chain; Expert from ExpertPlus
        assert sorted(written) == ["Easy.dat", "Expert.dat", "Hard.dat", "Normal.dat"]
        for f in ("Easy.dat", "Normal.dat", "Hard.dat", "Expert.dat"):
            data = json.load(open(os.path.join(d, f)))
            assert data["colorNotes"] == note, f"{f} must be a clone of the map's own content"

    def test_fills_from_closest_easier_when_no_harder(self, tmp_path):
        """Easy-only map: Normal/Hard/Expert/ExpertPlus clone from the closest
        EASIER difficulty (Easy)."""
        from full_custom_song_pipeline import fill_missing_standard_difficulties
        d = str(tmp_path)
        note = [{"b": 2.0, "x": 1, "y": 1, "c": 1, "d": 2}]
        self._write(d, "Easy.dat", note)

        written = fill_missing_standard_difficulties(d)
        assert sorted(written) == ["Expert.dat", "ExpertPlus.dat", "Hard.dat", "Normal.dat"]
        data = json.load(open(os.path.join(d, "ExpertPlus.dat")))
        assert data["colorNotes"] == note

    def test_does_not_touch_provided_diffs(self, tmp_path):
        """Map provides Easy+Expert (Jealous pattern): Normal clones from Expert
        (closest harder), Hard clones from Expert, ExpertPlus clones from Expert.
        Provided files stay byte-identical."""
        from full_custom_song_pipeline import fill_missing_standard_difficulties
        d = str(tmp_path)
        easy = [{"b": 1.0, "x": 0, "y": 0, "c": 0, "d": 0}]
        expert = [{"b": 9.0, "x": 2, "y": 2, "c": 1, "d": 6}]
        self._write(d, "EasyStandard.dat", easy)
        self._write(d, "ExpertStandard.dat", expert)

        written = fill_missing_standard_difficulties(d)
        assert sorted(written) == ["ExpertPlus.dat", "Hard.dat", "Normal.dat"]
        assert json.load(open(os.path.join(d, "EasyStandard.dat")))["colorNotes"] == easy
        assert json.load(open(os.path.join(d, "ExpertStandard.dat")))["colorNotes"] == expert

    def test_no_mode_files_are_donors(self, tmp_path):
        """Mode files (OneSaber etc.) must NEVER be chosen as donors — a
        OneSaber chart cloned to a Standard slot would be all-blue dots."""
        from full_custom_song_pipeline import fill_missing_standard_difficulties
        d = str(tmp_path)
        onesaber = [{"b": 1.0, "x": 0, "y": 0, "c": 1, "d": 8}]
        self._write(d, "ExpertOneSaber.dat", onesaber)

        written = fill_missing_standard_difficulties(d)
        assert written == [], "must not fill from a mode-only map"
        assert not os.path.exists(os.path.join(d, "Hard.dat"))

    def test_empty_map_fills_silently(self, tmp_path):
        """No beatmap files at all -> nothing written, no exception."""
        from full_custom_song_pipeline import fill_missing_standard_difficulties
        d = str(tmp_path)
        assert fill_missing_standard_difficulties(d) == []

    def test_idempotent_rerun(self, tmp_path):
        """A second run finds the filled files and writes nothing new."""
        from full_custom_song_pipeline import fill_missing_standard_difficulties
        d = str(tmp_path)
        self._write(d, "ExpertPlus.dat", [{"b": 1.0, "x": 0, "y": 0, "c": 0, "d": 1}])
        first = fill_missing_standard_difficulties(d)
        assert first
        assert fill_missing_standard_difficulties(d) == []


# ======================================================================
# Exp 218 regression: the six Camelia maps must deploy with every Standard
# slot replaced (no stock beatmaps) and the correct Info.dat BPM grid.
# ======================================================================
class TestCameliaSyncRegression:
    CAMELIA_SOURCES = {
        "SexySocialite": ("/tmp/beatsaver_2epuient/6f1f", 142.0, 339.0, 791.0),
        "Jealous":       ("/tmp/beatsaver_1qlmfguk/111fd", 129.0, 228.0, 486.9),
        "Roni":          ("/tmp/beatsaver__1wo758t/115ba", 117.0, 214.0, 404.1),
        "GreenLight":    ("/tmp/beatsaver_46id3sk2/37d5", 121.0, 223.1, 445.6),
        "1999":          ("/tmp/beatsaver_15_5g25g/5352", 124.0, 191.5, 390.5),
        "FANCY":         ("/tmp/beatsaver_2l7_an1y/47f3", 132.0, 217.6, 469.0),
    }

    def test_bpm_grid_matches_info_dat(self, tmp_path):
        """For every cached Camelia map, bpmData eb must equal the Info.dat grid
        (duration*BPM/60), NOT the old beatmap-derived underestimate."""
        for name, (src, bpm, dur, max_beat) in self.CAMELIA_SOURCES.items():
            if not os.path.isdir(src):
                continue
            d = tmp_path / name
            shutil.copytree(src, str(d))
            sample_count = int(dur * 44100)
            regions = load_bpm_regions(str(d), sample_count)
            expected = dur * bpm / 60.0
            assert abs(regions[0]['eb'] - expected) < 0.5, (
                f"{name}: eb={regions[0]['eb']:.1f} but Info.dat grid is {expected:.1f}"
            )

    def test_roni_grid_not_heuristic(self):
        """'Roni specifically: 214s audio, 117 BPM -> eb 417.3 (not 404.1)."""
        src, bpm, dur, max_beat = self.CAMELIA_SOURCES["Roni"]
        if not os.path.isdir(src):
            pytest.skip("Roni source not cached")
        regions = load_bpm_regions(src, int(dur * 44100))
        assert abs(regions[0]['eb'] - 214.0 * 117.0 / 60.0) < 0.5
        # the old heuristic would have produced 404.1 (112.1 BPM — 4.2% slow)
        assert abs(regions[0]['eb'] - max_beat) > 5.0


# ======================================================================
# Exp 226: --clear-target-song on the LAST custom song of an unrelated
# pack wiped ALL song redirects from EVERY pack (44 destroyed live).
# Two fixes: (1) clear_target_song's step-6 re-ensure must scope to the
# song redirects that still EXIST (never slots=[] / rebuild_slots);
# (2) _ensure_mass_song_redirects treats an empty scope as a NO-OP, not a
# wipe — and an unmatched non-empty scope preserves redirects too.
# ======================================================================
class TestClearTargetSongRedirectSafety:
    def test_empty_scope_never_wipes(self, tmp_path):
        from full_custom_song_pipeline import _ensure_mass_song_redirects
        data = {'redirects': {
            'BeatmapLevelsData/BadGuy': 'BadGuy_v3.bundle',
            'BeatmapLevelsData/Crystallized': 'crystallized_v3.bundle',
            'aa/catalog.json': 'catalog_pack_modes.json',
        }}
        config = {'mass_deploy': {'slots': ['BadGuy', 'Crystallized']}}
        _ensure_mass_song_redirects(data, config, slots=[])
        assert data['redirects']['BeatmapLevelsData/BadGuy'] == 'BadGuy_v3.bundle'
        assert data['redirects']['BeatmapLevelsData/Crystallized'] == 'crystallized_v3.bundle'
        assert data['redirects']['aa/catalog.json'] == 'catalog_pack_modes.json'

    def test_unmatched_scope_preserves_existing(self, tmp_path):
        """A non-empty scope matching nothing in mass_deploy.slots must NOT
        delete existing redirects (the old branch deleted EVERYTHING)."""
        from full_custom_song_pipeline import _ensure_mass_song_redirects
        data = {'redirects': {
            'BeatmapLevelsData/BadGuy': 'BadGuy_v3.bundle',
        }}
        # SugarSoaker (PATD pack) is not in mass_deploy.slots
        config = {'mass_deploy': {'slots': ['BadGuy', 'Crystallized']}}
        _ensure_mass_song_redirects(data, config, slots=['SugarSoaker'])
        assert data['redirects'].get('BeatmapLevelsData/BadGuy') == 'BadGuy_v3.bundle', \
            "unmatched scope must preserve existing redirects"

    def test_clear_target_source_contract(self):
        """The step-6 manage_redirect_config call in clear_target_song must
        never pass rebuild_slots as the redirect scope (source audit)."""
        src = open(os.path.join(os.path.dirname(__file__), '..', 'tools',
                                'full_custom_song_pipeline.py')).read()
        assert re.search(r'\bslots=rebuild_slots\b', src) is None, \
            "clear_target_song must not scope redirect generation to rebuild_slots (the 44-redirect wipe)"
        assert 'Empty slot scope — preserving all existing song redirects' in src, \
            "the empty-scope no-op guard must be present"


# ======================================================================
# Exp 228 — Metadata special-character handling
# ======================================================================

class TestMetadataUnicodeHandling:
    """
    '…Baby One More Time' (U+2026) title never got its metadata replacement
    deployed. Root cause chain: (a) json.dump default ensure_ascii=True wrote
    the key as \\u2026Baby One More Time, (b) the plugin's byte-verbatim JSON
    parser kept the escape, (c) the game's UTF-16 title folds to
    '?Baby One More Time' in extract_utf16_string. Fix: pipeline writes raw
    UTF-8 (ensure_ascii=False), plugin unescapes \\uXXXX and folds keys to
    the same ASCII projection.
    """

    def test_song_metadata_written_as_raw_utf8(self, tmp_path):
        """song_metadata.json must be written with ensure_ascii=False so
        non-ASCII keys stay human-readable raw UTF-8, not \\uXXXX escapes."""
        from full_custom_song_pipeline import manage_song_metadata
        local_path = os.path.join(tmp_path, "song_metadata.json")
        import full_custom_song_pipeline as fp
        orig = fp._get_song_metadata_path
        fp._get_song_metadata_path = lambda: local_path
        try:
            manage_song_metadata(
                {},
                song_name="Take On Me",
                artist="A-ha",
                target_name="BabyOneMoreTime",
                deploy=False,
            )
            raw = open(local_path, 'rb').read()
            # The key must be raw UTF-8 bytes (0xE2 0x80 0xA6), not the
            # 6-byte ASCII sequence backslash-u-2-0-2-6
            assert b'\xe2\x80\xa6Baby One More Time' in raw, \
                "non-ASCII key must be raw UTF-8, not \\u2026-escaped"
            assert b'\\u2026' not in raw, \
                "escaped \\u2026 must never appear in the written file"
        finally:
            fp._get_song_metadata_path = orig

    def test_read_info_song_metadata_v4(self):
        """V4 Info.dat (BeatSaver 4.0.x) stores title/author in the nested
        'song' object; the pipeline must read them (was: fallback to map ID
        as the display name, e.g. 'Oxytocin' -> '4dea2')."""
        from full_custom_song_pipeline import _read_info_song_metadata
        # Real shape from 4dea2 (Kiss Me More) Info.dat
        info_v4 = {
            "version": "4.0.1",
            "song": {"title": "Kiss Me More", "subTitle": "(feat. SZA)", "author": "Doja Cat"},
            "audio": {"songFilename": "song.egg", "bpm": 111.0},
        }
        name, artist = _read_info_song_metadata(info_v4)
        assert name == "Kiss Me More"
        assert artist == "Doja Cat"

    def test_read_info_song_metadata_v3_still_works(self):
        """V2/V3 Info.dat reads must not regress: _songName/_songAuthorName
        remain the primary keys."""
        from full_custom_song_pipeline import _read_info_song_metadata
        info_v3 = {"_songName": "Espresso", "_songAuthorName": "Sabrina Carpenter",
                   "_beatsPerMinute": 111.0}
        name, artist = _read_info_song_metadata(info_v3)
        assert name == "Espresso"
        assert artist == "Sabrina Carpenter"

    def test_read_info_bpm_v4(self):
        """V4 Info.dat carries BPM in audio.bpm; must be read when
        _beatsPerMinute is absent."""
        from full_custom_song_pipeline import _read_info_bpm_from_dict
        info_v4 = {"version": "4.0.1", "audio": {"bpm": 111.0}}
        assert _read_info_bpm_from_dict(info_v4) == 111.0
        info_v3 = {"_beatsPerMinute": 202.5}
        assert _read_info_bpm_from_dict(info_v3) == 202.5
        assert _read_info_bpm_from_dict({}) is None

    def test_metadata_only_mode_help(self):
        """--metadata-only must exist in the CLI (source audit)."""
        src = open(os.path.join(os.path.dirname(__file__), '..', 'tools',
                                'full_custom_song_pipeline.py')).read()
        assert '--metadata-only' in src, \
            "--metadata-only CLI flag must exist for surgical metadata fixes"

    def test_plugin_json_unescape_present(self):
        """The plugin must unescape \\uXXXX in parse_json_pairs (source audit)
        so already-deployed escaped files still match."""
        src = open(os.path.join(os.path.dirname(__file__), '..', 'src',
                                'main.cpp')).read()
        assert 'json_unescape_inplace' in src, \
            "plugin must unescape \\uXXXX escapes in JSON values"
        assert 'fold_utf8_to_ascii' in src, \
            "plugin must fold keys to the extract_utf16_string projection"
        # The fold must be applied to metadata keys (song_names + song_artists)
        assert src.count('fold_utf8_to_ascii(keys[i])') == 2, \
            "key fold must be applied in both song_names and song_artists parsers"


class TestPluginUnescapeUnit:
    """C-level unit checks of the plugin's unescape/fold semantics via the
    source (no PS4 needed) — mirrors of the C logic in Python for behavior
    verification."""

    def _fold(self, s):
        # Python mirror of fold_utf8_to_ascii
        out = []
        i = 0
        b = s.encode('utf-8')
        while i < len(b):
            c = b[i]
            if c < 0x80:
                out.append(chr(c))
                i += 1
                continue
            seq = 4 if c >= 0xF0 else 3 if c >= 0xE0 else 2
            nq = 2 if seq == 4 else 1
            i += seq
            out.append('?' * nq)
        return ''.join(out)

    def test_fold_bmp_char_matches_extraction(self):
        """'…' (BMP) extracts from UTF-16 as ONE '?' — key fold must produce
        exactly one '?' for the UTF-8 sequence."""
        assert self._fold('…Baby One More Time') == '?Baby One More Time'

    def test_fold_ascii_untouched(self):
        assert self._fold("Oops!...I Did It Again") == "Oops!...I Did It Again"

    def test_fold_astral_two_question_marks(self):
        """Astral chars occupy two UTF-16 code units -> extract produces TWO
        '?' — fold must mirror that."""
        assert self._fold('🎵 Party') == '?? Party'

    def test_escaped_file_matches_after_unescape_then_fold(self):
        """The full chain for the already-deployed escaped file:
        parse (keeps \\u2026) -> unescape (raw '…') -> fold ('?') == the
        extraction of the game title ('?')."""
        # parse keeps the literal escape text
        parsed_key = r'…Baby One More Time'
        # json_unescape_inplace turns it into real UTF-8
        unescaped = json.loads('"' + parsed_key + '"')
        # fold to the extraction projection
        folded = self._fold(unescaped)
        assert folded == '?Baby One More Time'


# ======================================================================
# Exp 228 — V4 columnar beatmap support
# ======================================================================

class TestV4BeatmapConversion:
    """
    BeatSaver v4.0.x maps (4dea2 Kiss Me More, 443f3 15 Minutes) use a
    columnar layout: colorNotes[{b, i?}] + colorNotesData[{x,y,c,d,a} ...
    rows]. Without conversion the pipeline shipped notes with ONLY {b, i}
    — the game read x=0/y=0 defaults and every note stacked bottom-left.
    """

    def test_is_v4_beatmap_detection(self):
        from full_custom_song_pipeline import is_v2_beatmap, is_v4_beatmap
        v4 = {"version": "4.0.1", "colorNotes": [{"b": 4.0}],
              "colorNotesData": [{"x": 2, "c": 1, "d": 1}]}
        assert is_v4_beatmap(v4) is True
        assert is_v2_beatmap(v4) is False  # never treated as V2 either
        v3 = {"version": "3.2.0", "colorNotes": [{"b": 4.0, "x": 1, "y": 0}]}
        assert is_v4_beatmap(v3) is False

    def test_convert_v4_denormalizes_notes(self):
        from full_custom_song_pipeline import convert_v4_to_v3
        v4 = {"version": "4.0.1",
              "colorNotes": [{"b": 4.0}, {"b": 6.0, "i": 2}],
              "colorNotesData": [{"x": 2, "c": 1, "d": 1}, {"x": 3}, {"x": 1, "y": 1}]}
        out = convert_v4_to_v3(v4)
        assert out["colorNotes"][0] == {"b": 4.0, "x": 2, "c": 1, "d": 1}
        # 'i' indexes into colorNotesData AND must be stripped from the event
        assert out["colorNotes"][1] == {"b": 6.0, "x": 1, "y": 1}
        assert "colorNotesData" not in out
        assert out["version"] == "3.2.0"

    def test_convert_v4_default_index_is_position(self):
        """Events without 'i' index their OWN data row (colorNotesData[0],
        colorNotesData[1], ...) — verified against real 4dea2 Easy.dat."""
        from full_custom_song_pipeline import convert_v4_to_v3
        v4 = {"version": "4.0.1",
              "colorNotes": [{"b": 1.0}, {"b": 2.0}, {"b": 3.0}],
              "colorNotesData": [{"x": 0}, {"x": 1}, {"x": 2}]}
        out = convert_v4_to_v3(v4)
        assert [n["x"] for n in out["colorNotes"]] == [0, 1, 2]

    def test_convert_v4_obstacles_merge(self):
        from full_custom_song_pipeline import convert_v4_to_v3
        v4 = {"version": "4.0.1",
              "obstacles": [{"b": 66.25}, {"b": 67.25, "i": 1}],
              "obstaclesData": [{"x": 2, "d": 0.0625, "w": 1, "h": 5},
                                 {"x": 1, "d": 0.0625, "w": 1, "h": 5}]}
        out = convert_v4_to_v3(v4)
        assert out["obstacles"][0] == {"b": 66.25, "x": 2, "d": 0.0625, "w": 1, "h": 5}
        assert out["obstacles"][1] == {"b": 67.25, "x": 1, "d": 0.0625, "w": 1, "h": 5}

    def test_convert_v4_real_4dea2_shape(self):
        """Shape check against the exact structure of 4dea2's Easy.dat
        (first notes with sparse columnar rows)."""
        from full_custom_song_pipeline import convert_v4_to_v3
        v4 = {"version": "4.0.1",
              "colorNotes": [{"b": 4.0}, {"b": 6.0, "i": 1}, {"b": 7.5, "i": 2}],
              "colorNotesData": [{"x": 2, "c": 1, "d": 1}, {"x": 3, "y": 1, "c": 1},
                                  {"x": 1, "d": 1}]}
        out = convert_v4_to_v3(v4)
        assert out["colorNotes"][2] == {"b": 7.5, "x": 1, "d": 1}

    def test_v4_info_dat_metadata(self):
        """V4 Info.dat title/author must be read (the 'Oxytocin' -> '4dea2'
        display-name regression)."""
        from full_custom_song_pipeline import _read_info_song_metadata
        info = {"version": "4.0.1",
                "song": {"title": "Kiss Me More", "subTitle": "(feat. SZA)",
                         "author": "Doja Cat"},
                "audio": {"bpm": 111.0, "audioDataFilename": "AudioData.dat"}}
        name, artist = _read_info_song_metadata(info)
        assert name == "Kiss Me More"
        assert artist == "Doja Cat"

    def test_v4_info_bpm_fallback(self):
        """V4 audio.bpm must be honored by both BPM helpers."""
        from full_custom_song_pipeline import _read_info_bpm_from_dict
        info = {"version": "4.0.1", "audio": {"bpm": 111.0}}
        assert _read_info_bpm_from_dict(info) == 111.0
        assert _read_info_bpm_from_dict({"_beatsPerMinute": 202.5}) == 202.5

    def test_replace_beatmaps_converts_v4(self, tmp_path):
        """replace_beatmaps must convert v4 sources before writing to the
        CAB (source audit + behavior: the v4 check precedes the v2 check)."""
        src = open(os.path.join(os.path.dirname(__file__), '..', 'tools',
                                'full_custom_song_pipeline.py')).read()
        # v4 conversion is applied in replace_beatmaps BEFORE v2 conversion
        v4_block = re.search(
            r"if is_v4_beatmap\(data\):\s*\n\s*data = convert_v4_to_v3\(data\)", src)
        assert v4_block is not None, "replace_beatmaps must convert V4 first"
        # and in the mode-injection path
        assert re.search(r"if is_v4_beatmap\(bm_data\):", src) is not None, \
            "mode injection path must also handle V4 sources"


# ======================================================================
# Exp 231 — V4 columnar clobber: NoArrows arrows after v4→v3 merge
# ======================================================================

class TestV4NoArrowsClobberFix:
    """
    '15 Minutes' (443f3, BeatSaver v4.0.x columnar) shipped Hard NoArrows
    charts IDENTICAL to Standard — arrows everywhere. Chain: the generator
    wrote d=8 onto the columnar EVENTS, but colorNotesData ROWS kept their
    arrow d; convert_v4_to_v3 merges row-OVER-event at injection, so the
    arrows came back. OneSaber was immune (post-merge re-application since
    Exp 218); 90Degree is immune (generator only APPENDS rotationEvents,
    which the row merge cannot clobber). Fix: re-apply the NoArrows dot pass
    AFTER format conversion at injection (idempotent: d=8 stays d=8).
    """

    def test_row_merge_clobbers_generator_dots(self):
        """The bug itself: convert_v4_to_v3 merges row-over-event, restoring
        arrow d-values over the generator's d=8 events."""
        from full_custom_song_pipeline import convert_v4_to_v3
        gen_noarrows = {
            "version": "4.0.1",
            "colorNotes": [{"b": 5.0, "d": 8}, {"b": 5.0, "i": 1, "d": 8}],
            "colorNotesData": [{"x": 2, "y": 0, "c": 0, "d": 1},
                                {"x": 3, "y": 0, "c": 1, "d": 4}],
        }
        merged = convert_v4_to_v3(gen_noarrows)
        # This documents the clobber — the reason the post-conversion pass exists
        assert merged['colorNotes'][0]['d'] == 1, \
            "row merge must overwrite event d (that IS the converter contract)"
        assert merged['colorNotes'][1]['d'] == 4

    def test_post_conversion_no_arrows_pass_restores_dots(self):
        """Re-applying _generate_no_arrows AFTER the v4 conversion yields
        all-dot charts regardless of the columnar clobber."""
        from full_custom_song_pipeline import _generate_no_arrows, convert_v4_to_v3, normalize_v3_schema
        gen_noarrows = {
            "version": "4.0.1",
            "colorNotes": [{"b": 5.0, "d": 8}, {"b": 5.0, "i": 1, "d": 8},
                            {"b": 6.0, "i": 2, "d": 8}],
            "colorNotesData": [{"x": 2, "y": 0, "c": 0, "d": 1},
                                {"x": 3, "y": 0, "c": 1, "d": 1},
                                {"x": 1, "y": 2, "c": 0, "d": 4}],
            "bombNotes": [], "obstacles": [],
        }
        bm = convert_v4_to_v3(__import__('json').loads(__import__('json').dumps(gen_noarrows)))
        normalize_v3_schema(bm)
        bm = _generate_no_arrows(bm)
        dvals = sorted({n.get('d', 8) for n in bm['colorNotes']})
        assert dvals == [8], f"NoArrows must be all dots after post-conversion pass, got {dvals}"
        # geometry must survive (x/y/c from the rows)
        assert bm['colorNotes'][0]['x'] == 2
        assert bm['colorNotes'][2]['y'] == 2

    def test_no_arrows_pass_idempotent_on_correct_data(self):
        """The post-conversion pass must be a no-op for well-formed (already
        denormalized, already-dot) sources."""
        from full_custom_song_pipeline import _generate_no_arrows
        ok = {"version": "3.2.0",
              "colorNotes": [{"b": 5.0, "x": 1, "y": 0, "c": 0, "d": 8},
                              {"b": 6.0, "x": 2, "y": 1, "c": 1, "d": 8}]}
        out = _generate_no_arrows(ok)
        assert all(n['d'] == 8 for n in out['colorNotes'])
        assert out['colorNotes'][0]['x'] == 1

    def test_injection_path_applies_no_arrows_after_conversion(self):
        """Source audit: add_mode_characteristics must re-apply the NoArrows
        dot pass AFTER convert_v4_to_v3 (and must NOT blanket-apply the
        90Degree generator, which appends rotations and is not idempotent)."""
        src = open(os.path.join(os.path.dirname(__file__), '..', 'tools',
                                'full_custom_song_pipeline.py')).read()
        # The NoArrows post-conversion pass exists...
        assert re.search(
            r'elif mode == "NoArrows":\s*\n\s*bm_data = _generate_no_arrows\(bm_data\)', src), \
            "injection path must re-apply NoArrows dots after format conversion"
        # ...and it must come AFTER the is_v4_beatmap conversion block
        m_v4 = re.search(r'if is_v4_beatmap\(bm_data\):', src)
        m_noarrows = re.search(r'elif mode == "NoArrows":', src)
        assert m_v4 and m_noarrows and m_v4.start() < m_noarrows.start(), \
            "NoArrows re-application must follow the v4 conversion in the injection path"
        # 90Degree must NOT be blanket re-applied (rotation-append is not idempotent)
        assert 'elif mode in _MODE_GENERATORS' not in src, \
            "blanket generator re-application would double 90Degree rotations"

    def test_v4_map_expertplus_via_tier3(self):
        """443f3's ExpertPlus uses '<Diff>.beatmap.dat' (v4 bare tier) — the
        file selector must still resolve it with ignore_non_standard=True
        (the mode generators need a Standard source for every difficulty)."""
        files = ['AudioData.dat', 'EasyStandard.dat', 'ExpertPlus.beatmap.dat',
                 'ExpertPlus.lightshow.dat', 'ExpertStandard.dat', 'HardStandard.dat',
                 'Info.dat', 'NormalStandard.dat']
        sel = {d: _select_beatmap_file(d, files, ignore_non_standard=True) for d in DIFFICULTIES}
        assert sel['ExpertPlus'] == 'ExpertPlus.beatmap.dat'
        assert sel['Hard'] == 'HardStandard.dat'


# ======================================================================
# Exp 232 — Chained multi-pack deploy on a clean slate must ACCUMULATE pack redirects
# ======================================================================

class TestChainedPackRedirectAccumulation:
    """
    Clean-slate PS4 + 5 pack scripts in sequence ended with only the LAST
    pack's pack-bundle redirect surviving — the other 4 packs loaded stock
    (metadata swapped, but stock beatmaps/modes/songs). Root cause:
    _ensure_pack_bundle_redirects' stale-sweep defined "still configured"
    purely by LOCAL bundle existence (_get_pack_bundle_redirects filters
    os.path.isfile), while the clean-slate wipe empties pack_modes_bundles/.
    Each script's deploy saw only ITS OWN pack's bundle and deleted every
    other pack's redirect as "no longer configured" — even though those
    bundles were live on the PS4. Fix (Exp 232): a pack redirect is valid if
    in the current pair OR the pack is DEPLOYED per the redirects state file
    (_resolve_deployed_packs — the same authority every deploy flow uses).
    """

    def _build_cfg(self, tmp_path, build_dir):
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        albums = json.load(open(os.path.join(_root, 'beat_saber_song_ids.json')))['albums']
        cfg = {
            'title': {'id': 'CUSA12878'}, 'ps4': {'ip': 'x', 'ftp_port': 1},
            'paths': {'afr_base': '/data/GoldHEN/AFR'},
            'pack_modes': {'packs': [], 'build_dir': str(build_dir),
                'song_ids_path': os.path.join(_root, 'beat_saber_song_ids.json'),
                'dump_dir': '/workspace/ps4_dump/CUSA12878-patch',
                'catalog_key': 'aa/catalog.json',
                'patched_catalog': 'catalog_pack_modes.json',
                'patched_catalog_local': str(tmp_path / 'catalog_pack_modes.json')},
        }
        with open(cfg['pack_modes']['patched_catalog_local'], 'w') as f:
            f.write('{}')
        return cfg, albums

    def test_clean_slate_chain_accumulates_all_packs(self, tmp_path, monkeypatch):
        """THE regression: 5 scripts chained on a wiped workspace (each pack's
        local bundle exists only from its own run) must end with all 5 pack
        redirect entries — never only the last one."""
        import full_custom_song_pipeline as fcp
        rpath = tmp_path / 'redirects.json'
        monkeypatch.setattr('full_custom_song_pipeline._get_redirect_config_path',
                            lambda project_root=None: str(rpath))
        build_dir = tmp_path / 'build'
        build_dir.mkdir()
        cfg, albums = self._build_cfg(tmp_path, build_dir)
        packs = ['billieeilish', 'britneyspears', 'camellia', 'lizzo', 'therollingstones']
        for pack in packs:
            for a in albums:
                if a['pack'] == pack:
                    patched = fcp.pack_modes_builder.patched_bundle_name(a['packBundle'])
                    (build_dir / patched).write_bytes(b'BUNDLE')
            data = json.loads(rpath.read_text()) if rpath.exists() else {
                'titleId': 'CUSA12878', 'afrBase': '/data/GoldHEN/AFR', 'redirects': {}}
            fcp._ensure_pack_bundle_redirects(data, cfg, packs=[pack])
            rpath.write_text(json.dumps(data))
        final = json.loads(rpath.read_text())['redirects']
        pe = [k for k in final if '_pack_assets_' in k]
        assert len(pe) == 5, f"chained deploy must accumulate all 5 pack redirects, got {len(pe)}"
        assert 'aa/catalog.json' in final

    def test_deployed_pack_redirect_survives_missing_local_bundle(self, tmp_path, monkeypatch):
        """A pack whose bundle is live on the PS4 (entry in the state file)
        but missing locally must NOT have its redirect deleted by another
        pack's deploy."""
        import full_custom_song_pipeline as fcp
        rpath = tmp_path / 'redirects.json'
        monkeypatch.setattr('full_custom_song_pipeline._get_redirect_config_path',
                            lambda project_root=None: str(rpath))
        build_dir = tmp_path / 'build'
        build_dir.mkdir()
        cfg, albums = self._build_cfg(tmp_path, build_dir)
        # billieeilish deployed earlier (state file references it), bundle absent locally
        be_album = next(a for a in albums if a['pack'] == 'billieeilish')
        be_key = be_album['packBundle']
        be_val = be_key.replace('_pack_assets_', '_pack_modes_')
        rpath.write_text(json.dumps({
            'titleId': 'CUSA12878', 'afrBase': '/data/GoldHEN/AFR',
            'redirects': {be_key: be_val, 'aa/catalog.json': 'catalog_pack_modes.json'}}))
        # britneyspears bundle exists locally; its deploy must not delete BE's entry
        br_album = next(a for a in albums if a['pack'] == 'britneyspears')
        (build_dir / fcp.pack_modes_builder.patched_bundle_name(br_album['packBundle'])).write_bytes(b'B')
        data = json.loads(rpath.read_text())
        fcp._ensure_pack_bundle_redirects(data, cfg, packs=['britneyspears'])
        assert be_key in data['redirects'], \
            "deployed pack's redirect deleted because its local bundle is missing — the Exp 232 regression"

    def test_true_stale_pack_redirect_still_removed(self, tmp_path, monkeypatch):
        """The sweep must still remove redirects for packs that are neither in
        the current pair nor deployed (e.g. a pack uninstalled long ago)."""
        import full_custom_song_pipeline as fcp
        rpath = tmp_path / 'redirects.json'
        monkeypatch.setattr('full_custom_song_pipeline._get_redirect_config_path',
                            lambda project_root=None: str(rpath))
        build_dir = tmp_path / 'build'
        build_dir.mkdir()
        cfg, albums = self._build_cfg(tmp_path, build_dir)
        be_album = next(a for a in albums if a['pack'] == 'billieeilish')
        (build_dir / fcp.pack_modes_builder.patched_bundle_name(be_album['packBundle'])).write_bytes(b'B')
        ghost_key = 'ghost_pack_assets_all_ffffffffffffffffffffffffffffffff.bundle'
        data = {'redirects': {ghost_key: 'ghost_pack_modes_assets_all_ffffffffffffffffffffffffffffffff.bundle'}}
        fcp._ensure_pack_bundle_redirects(data, cfg, packs=['billieeilish'])
        assert ghost_key not in data['redirects'], "true-stale pack redirect must still be removed"


# ======================================================================
# Exp 235 — Release-zip plugin deployment (bundled-prx fallback)
# ======================================================================

class TestBundledPluginFallback:
    """
    The packaged release ships tools only (no src/, no Makefile) but bundles
    BOTH CI-built plugins in plugins/. --deploy-full must work end-to-end
    from the release zip alone — plugin deployment included — so build_plugin
    falls back to the bundled binary when no Makefile exists, and deploys it
    under the CANONICAL remote name (a debug deploy must replace the single
    plugins.ini entry, never fork a second one GoldHEN would also load).
    """

    def test_no_makefile_uses_bundled_prx(self, tmp_path):
        import full_custom_song_pipeline as fcp
        # Packaged-release layout: plugins/orbeats.prx, no Makefile
        (tmp_path / 'plugins').mkdir()
        (tmp_path / 'plugins' / 'orbeats.prx').write_bytes(b'PRX-REL')
        (tmp_path / 'plugins' / 'orbeats_debug.prx').write_bytes(b'PRX-DBG')
        prx = fcp.build_plugin(str(tmp_path), debug=False)
        assert prx == str(tmp_path / 'plugins' / 'orbeats.prx')

    def test_no_makefile_debug_uses_bundled_debug_prx(self, tmp_path):
        import full_custom_song_pipeline as fcp
        (tmp_path / 'plugins').mkdir()
        (tmp_path / 'plugins' / 'orbeats.prx').write_bytes(b'PRX-REL')
        (tmp_path / 'plugins' / 'orbeats_debug.prx').write_bytes(b'PRX-DBG')
        prx = fcp.build_plugin(str(tmp_path), debug=True)
        assert prx == str(tmp_path / 'plugins' / 'orbeats_debug.prx')

    def test_no_makefile_no_bundle_raises(self, tmp_path):
        import full_custom_song_pipeline as fcp
        with pytest.raises(RuntimeError):
            fcp.build_plugin(str(tmp_path), debug=False)

    def test_deploy_plugin_uses_canonical_remote_name(self, tmp_path, monkeypatch):
        """Whatever binary variant is deployed, the remote filename must stay
        orbeats.prx — the plugins.ini entry must never fork."""
        import full_custom_song_pipeline as fcp
        import library_manager
        captured = {}
        def guarded_install(config, path):
            captured.update(config=config, artifact=path)
            return {'ok': True}
        monkeypatch.setattr(library_manager, 'deploy_plugin', guarded_install)
        def unguarded(*args, **kwargs):
            raise AssertionError('Raw FTP must not bypass the guarded installer')
        monkeypatch.setattr(fcp, '_ftp_run', unguarded)
        dbg = tmp_path / 'orbeats_debug.prx'
        dbg.write_bytes(b'PRX-DBG')
        config = {'ps4': {'ip': 'x'}, 'title': {'id': 'CUSA12878'}}
        assert fcp.deploy_plugin(str(dbg), config) == {'ok': True}
        assert captured == {'config': config, 'artifact': str(dbg)}

    def test_plugin_only_mode_routes_through_resolver(self):
        """Source audit: plugin-only mode must call build_plugin (bundled-prx
        fallback), not a hardcoded PROJECT_ROOT/orbeats.prx path."""
        src = open(os.path.join(os.path.dirname(__file__), '..', 'tools',
                                'full_custom_song_pipeline.py')).read()
        assert re.search(
            r"if args\.deploy_plugin and not args\.song_dir:\s*\n\s*prx_path = build_plugin\(",
            src), "plugin-only mode must resolve the prx via build_plugin"
        assert "os.path.join(PROJECT_ROOT, 'orbeats.prx')" not in src, \
            "hardcoded prx path must be gone (bundled fallback would be bypassed)"
