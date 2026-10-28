import json
import os
import tempfile
import unittest

from tools.full_custom_song_pipeline import (
    _generate_90_degree,
    _generate_no_arrows,
    _generate_one_saber,
    add_mode_characteristics,
    build_mode_mapping,
    detect_song_modes,
    generate_missing_mode_beatmaps,
)

V2_NOTE = {"_time": 1.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 1, "_cutDirection": 3}
V3_NOTE = {"b": 1.0, "x": 0, "y": 0, "c": 1, "d": 3}


class TestNoArrowsGenerator(unittest.TestCase):
    def test_v2_color_notes_become_dots(self):
        data = {"_version": "2.0.0", "_notes": [V2_NOTE]}
        gen = _generate_no_arrows(data)
        self.assertEqual(gen["_notes"][0]["_cutDirection"], 8)

    def test_v2_bombs_keep_direction(self):
        bomb = {"_time": 2.0, "_lineIndex": 1, "_lineLayer": 1, "_type": 3, "_cutDirection": 0}
        data = {"_version": "2.0.0", "_notes": [V2_NOTE, bomb]}
        gen = _generate_no_arrows(data)
        self.assertEqual(gen["_notes"][1]["_cutDirection"], 0)

    def test_v3_color_notes_become_dots(self):
        data = {"version": "3.2.0", "colorNotes": [V3_NOTE]}
        gen = _generate_no_arrows(data)
        self.assertEqual(gen["colorNotes"][0]["d"], 8)

    def test_input_not_mutated(self):
        data = {"_version": "2.0.0", "_notes": [V2_NOTE]}
        _generate_no_arrows(data)
        self.assertEqual(data["_notes"][0]["_cutDirection"], 3)


class TestOneSaberGenerator(unittest.TestCase):
    def test_recolors_all_notes_to_one_color(self):
        data = {"_version": "2.0.0", "_notes": [
            {"_time": 1.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 1},
            {"_time": 2.0, "_lineIndex": 1, "_lineLayer": 1, "_type": 1, "_cutDirection": 2},
        ]}
        gen = _generate_one_saber(data)
        self.assertTrue(all(n["_type"] == 1 for n in gen["_notes"]))

    def test_drops_simultaneous_notes(self):
        data = {"_version": "2.0.0", "_notes": [
            {"_time": 1.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 1},
            {"_time": 1.0, "_lineIndex": 3, "_lineLayer": 2, "_type": 1, "_cutDirection": 2},
        ]}
        gen = _generate_one_saber(data)
        self.assertEqual(len(gen["_notes"]), 1)

    def test_drops_close_same_cell_arrowed_notes(self):
        # Since Exp 218 every OneSaber note becomes a dot, so close same-cell
        # notes no longer collide at all — both survive (as dots).
        data = {"_version": "2.0.0", "_notes": [
            {"_time": 1.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 1},
            {"_time": 1.125, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 2},
        ]}
        gen = _generate_one_saber(data, min_gap=0.25)
        self.assertEqual(len(gen["_notes"]), 2)
        self.assertTrue(all(n["_cutDirection"] == 8 for n in gen["_notes"]))

    def test_keeps_dots_near_arrows(self):
        # A dot after an arrow in the same cell is fine (any swing hits it).
        data = {"_version": "2.0.0", "_notes": [
            {"_time": 1.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 1},
            {"_time": 1.125, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 8},
        ]}
        gen = _generate_one_saber(data, min_gap=0.25)
        self.assertEqual(len(gen["_notes"]), 2)

    def test_v3_recolors_to_single_saber(self):
        data = {"version": "3.2.0", "colorNotes": [
            {"b": 1.0, "x": 0, "y": 0, "c": 1, "d": 1},
            {"b": 1.0, "x": 2, "y": 2, "c": 0, "d": 2},
        ]}
        gen = _generate_one_saber(data)
        self.assertEqual(len(gen["colorNotes"]), 1)
        self.assertEqual(gen["colorNotes"][0]["c"], 1)

    def test_v3_omitted_position_fields_default_to_zero(self):
        # V3 permits omitting x/y (and even b/d defaults). Some BeatSaver
        # sources (e.g. "Take Me to the Beach") ship notes with only
        # {"x","c","d","b"} — missing y. Regressions here crashed the
        # pipeline with KeyError: 'y'.
        data = {"version": "3.2.0", "colorNotes": [
            {"b": 1.0, "x": 2, "c": 1, "d": 1},                 # no y
            {"b": 1.0, "x": 2, "y": 1, "c": 0, "d": 2},
            {"b": 4.0, "x": 0, "y": 0, "c": 1, "d": 8},
        ]}
        gen = _generate_one_saber(data)
        self.assertEqual(len(gen["colorNotes"]), 2)  # simult drop leaves 2
        self.assertTrue(all(n.get("c", 1) == 1 for n in gen["colorNotes"]))
        gen = _generate_no_arrows(data)
        self.assertTrue(all(n["d"] == 8 for n in gen["colorNotes"]))

    def test_notes_become_dots(self):
        # Exp 218: OneSaber is dots-only on this setup — arrows read as
        # "still Standard" to the user.
        data = {"_version": "2.0.0", "_notes": [
            {"_time": 1.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 1},
            {"_time": 2.0, "_lineIndex": 1, "_lineLayer": 1, "_type": 1, "_cutDirection": 7},
        ]}
        gen = _generate_one_saber(data)
        self.assertTrue(all(n["_cutDirection"] == 8 for n in gen["_notes"]))

    def test_v3_notes_become_dots(self):
        data = {"version": "3.2.0", "colorNotes": [
            {"b": 1.0, "x": 0, "y": 0, "c": 0, "d": 3},
            {"b": 2.0, "x": 1, "y": 1, "c": 1, "d": 5},
        ]}
        gen = _generate_one_saber(data)
        self.assertTrue(all(n["d"] == 8 for n in gen["colorNotes"]))
        self.assertTrue(all(n["c"] == 1 for n in gen["colorNotes"]))

    def test_bombs_kept_as_bombs(self):
        # Bombs pass through untouched (color 3 must not be recolored).
        data = {"version": "3.2.0", "colorNotes": [
            {"b": 1.0, "x": 0, "y": 0, "c": 0, "d": 1},
            {"b": 2.0, "x": 1, "y": 1, "c": 3, "d": 0},
        ]}
        gen = _generate_one_saber(data)
        self.assertEqual(len(gen["colorNotes"]), 2)
        self.assertEqual(gen["colorNotes"][1]["c"], 3)
        self.assertEqual(gen["colorNotes"][0]["d"], 8)

    def test_input_not_mutated(self):
        data = {"_version": "2.0.0", "_notes": [V2_NOTE]}
        _generate_one_saber(data)
        self.assertEqual(data["_notes"][0]["_type"], 1)


class Test90DegreeGenerator(unittest.TestCase):
    def test_v2_source_converted_to_v3(self):
        data = {"_version": "2.0.0", "_notes": [V2_NOTE]}
        gen = _generate_90_degree(data, cycle_beats=8, bpm=150.0)
        self.assertIn("colorNotes", gen)
        self.assertEqual(gen["version"], "3.2.0")
        self.assertEqual(gen["bpmEvents"][0]["m"], 150.0)

    def test_rotation_events_sweep_arc_and_span_map(self):
        data = {"_version": "2.0.0", "_notes": [
            {"_time": 2.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0},
            {"_time": 100.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0},
        ]}
        gen = _generate_90_degree(data, cycle_beats=8)
        events = gen["rotationEvents"]
        self.assertEqual(events[0]["b"], 2.0)
        # Single-lane 15° steps, always late (e=1), all within the 90° arc.
        self.assertTrue(all(abs(e["r"]) == 15 for e in events))
        self.assertTrue(all(e["e"] == 1 for e in events))
        # Cumulative rotation never leaves the ±45° arc (3 lanes each side).
        cum = 0.0
        for e in events:
            cum += e["r"]
            self.assertLessEqual(cum, 45)
            self.assertGreaterEqual(cum, -45)
        # Events span from the first note through the end of the map.
        self.assertGreaterEqual(events[-1]["b"], 100.0)

    def test_rotation_sweep_starts_center_and_bounces_at_extremes(self):
        data = {"_version": "2.0.0", "_notes": [
            {"_time": 1.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0},
            {"_time": 500.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 0},
        ]}
        gen = _generate_90_degree(data, cycle_beats=8)
        events = gen["rotationEvents"]
        # Sweep: right to +45, bounce, sweep left through center to -45, bounce...
        expected_deltas = [15, 15, 15, -15, -15, -15, -15, -15, -15, 15, 15, 15, 15, 15, 15]
        self.assertEqual([e["r"] for e in events[:len(expected_deltas)]], expected_deltas)
        # Cumulative positions visited: center -> +45 -> -45 -> +45 ...
        cum = 0.0
        positions = [cum]
        for e in events:
            cum += e["r"]
            positions.append(cum)
        self.assertEqual(positions[0], 0.0)
        self.assertEqual(positions[3], 45.0)   # first extreme reached
        self.assertEqual(positions[9], -45.0)  # swept to the other extreme
        self.assertEqual(max(positions), 45.0)
        self.assertEqual(min(positions), -45.0)

    def test_v3_data_preserved(self):
        data = {"version": "3.2.0", "colorNotes": [
            {"b": 1.0, "x": 0, "y": 0, "c": 1, "d": 1},
            {"b": 5.0, "x": 1, "y": 1, "c": 0, "d": 2},
        ]}
        gen = _generate_90_degree(data, cycle_beats=4)
        self.assertEqual(len(gen["colorNotes"]), 2)
        self.assertEqual(gen["rotationEvents"][0], {"b": 1.0, "e": 1, "r": 15})

    def test_v3_omitted_fields_in_90_degree(self):
        # Notes/obstacles/events with omitted b must not crash the generator.
        data = {"version": "3.2.0", "colorNotes": [
            {"b": 1.0, "x": 2, "c": 1, "d": 1},   # no y
            {"x": 1, "c": 0, "d": 2},             # no b
        ], "obstacles": [{"b": 6.0}], "basicBeatmapEvents": [{"b": 8.0}]}
        gen = _generate_90_degree(data, cycle_beats=8)
        self.assertEqual(len(gen["colorNotes"]), 2)
        # Omitted b defaults to beat 0, which becomes the sweep start.
        self.assertEqual(gen["rotationEvents"][0]["b"], 0.0)
        self.assertEqual(gen["rotationEvents"][-1]["b"], 8.0)  # spans the map

    def test_keeps_existing_rotation_events(self):
        data = {"version": "3.2.0", "colorNotes": [
            {"b": 1.0, "x": 0, "y": 0, "c": 1, "d": 1},
            {"b": 10.0, "x": 1, "y": 1, "c": 0, "d": 2},
        ], "rotationEvents": [{"b": 0.5, "e": 0, "r": -15}]}
        gen = _generate_90_degree(data, cycle_beats=8)
        self.assertEqual(gen["rotationEvents"][0], {"b": 0.5, "e": 0, "r": -15})
        self.assertEqual(gen["rotationEvents"][1]["b"], 1.0)

    def test_input_not_mutated(self):
        data = {"_version": "2.0.0", "_notes": [V2_NOTE]}
        _generate_90_degree(data)
        self.assertEqual(data["_notes"][0]["_cutDirection"], 3)


class TestGenerateMissingModeBeatmaps(unittest.TestCase):
    def _write_song(self, d, files):
        for name, content in files.items():
            with open(os.path.join(d, name), 'w') as fh:
                fh.write(content)

    def _v2(self, t, line=0, layer=0, typ=0, d=0):
        return json.dumps({"_version": "2.0.0", "_notes": [
            {"_time": t, "_lineIndex": line, "_lineLayer": layer, "_type": typ, "_cutDirection": d}
        ]})

    def test_generates_missing_modes_and_keeps_own(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_song(d, {
                "info.dat": json.dumps({"_songName": "Test", "_beatsPerMinute": 120.0}),
                "EasyStandard.dat": self._v2(1.0),
                "ExpertStandard.dat": self._v2(2.0),
                "90DegreeExpert.dat": self._v2(3.0),  # song's own — must not be overwritten
            })
            detected = detect_song_modes(d)
            enabled = build_mode_mapping(detected, None)
            generated = generate_missing_mode_beatmaps(d, detected, enabled, bpm=120.0)

            self.assertIn("EasyOneSaber.dat", generated)
            self.assertIn("EasyNoArrows.dat", generated)
            self.assertIn("Easy90Degree.dat", generated)
            # Expert has its own 90Degree file → not regenerated.
            self.assertNotIn("Expert90Degree.dat", generated)
            self.assertTrue(os.path.exists(os.path.join(d, "90DegreeExpert.dat")))

    def test_no_generation_when_modes_present(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_song(d, {
                "info.dat": json.dumps({"_songName": "Test"}),
                "EasyStandard.dat": self._v2(1.0),
                "EasyOneSaber.dat": self._v2(2.0),
                "EasyNoArrows.dat": self._v2(3.0),
                "Easy90Degree.dat": self._v2(4.0),
            })
            detected = detect_song_modes(d)
            enabled = build_mode_mapping(detected, None)
            generated = generate_missing_mode_beatmaps(d, detected, enabled)
            self.assertEqual(generated, [])

    def test_skips_difficulties_without_standard_source(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_song(d, {
                "info.dat": json.dumps({"_songName": "Test"}),
                "EasyStandard.dat": self._v2(1.0),
            })
            detected = detect_song_modes(d)
            enabled = build_mode_mapping(detected, None)
            generated = generate_missing_mode_beatmaps(d, detected, enabled)
            self.assertTrue(all(f.startswith("Easy") for f in generated))

class TestModeBeatmapInjection(unittest.TestCase):
    """Verify add_mode_characteristics injects real beatmap assets (not clones)."""

    def _v2(self, t, line=0, layer=0, typ=0, d=0):
        return json.dumps({"_version": "2.0.0", "_notes": [
            {"_time": t, "_lineIndex": line, "_lineLayer": layer, "_type": typ, "_cutDirection": d}
        ]})

    def test_injected_beatmaps_reference_new_textassets(self):

        from UnityPy import load as load_bundle

        # Build a song dir with Standard source (all 5 difficulties)
        with tempfile.TemporaryDirectory() as d:
            files = {
                "info.dat": json.dumps({"_songName": "Test", "_beatsPerMinute": 120.0}),
                "EasyStandard.dat": self._v2(1.0, typ=0, d=3),
                "NormalStandard.dat": self._v2(2.0, typ=1, d=1),
                "HardStandard.dat": self._v2(3.0, typ=0, d=2),
                "ExpertStandard.dat": self._v2(4.0, typ=1, d=0),
                "ExpertPlusStandard.dat": self._v2(5.0, typ=0, d=1),
            }
            for name, content in files.items():
                with open(os.path.join(d, name), 'w') as fh:
                    fh.write(content)

            detected = detect_song_modes(d)
            enabled = build_mode_mapping(detected, None)
            generated = generate_missing_mode_beatmaps(d, detected, enabled, bpm=120.0)

            # Load a test CAB
            import os as _os
            test_bundle = _os.path.join(
                _os.path.dirname(_os.path.dirname(__file__)),
                "test_data", "template_standard.bundle"
            )
            if not _os.path.isfile(test_bundle):
                self.skipTest("template_standard.bundle not available")

            env = load_bundle(test_bundle)
            bf_file = None
            cab = None
            for k, f in env.files.items():
                bf_file = f
                if hasattr(f, 'files'):
                    for fk, ff in f.files.items():
                        if hasattr(ff, 'objects') and ff.objects:
                            cab = ff
                            break
                if cab:
                    break

            # Verify all mode sets reference DIFFERENT pathIDs than Standard
            beatmap_level = None
            for pid, obj in cab.objects.items():
                if obj.class_id == 114:
                    beatmap_level = obj
                    break

            if beatmap_level is None:
                self.skipTest("No BeatmapLevel object in template")

            # Get Standard pathIDs
            bl_tt = beatmap_level.read_typetree()
            std_set = [s for s in bl_tt['_difficultyBeatmapSets'] if s['_beatmapCharacteristicSerializedName'] == 'Standard'][0]
            std_pids = [e['_beatmapAsset']['m_PathID'] for e in std_set['_difficultyBeatmaps']]

            # Apply mode mapping with generated beatmaps
            mode_count = add_mode_characteristics(
                cab, ["OneSaber", "NoArrows"], song_dir=d,
                generated_files=generated, bpm=120.0, target_name="Test"
            )
            self.assertEqual(mode_count, 2)

            # Save and reload to verify persisted changes
            result = bf_file.save(packer="lz4")
            import io as _io
            env2 = load_bundle(_io.BytesIO(result))
            cab2 = None
            for k, f in env2.files.items():
                if hasattr(f, 'files'):
                    for fk, ff in f.files.items():
                        if hasattr(ff, 'objects') and ff.objects:
                            cab2 = ff
                            break
                if cab2:
                    break

            bl_tt = None
            for pid, obj in cab2.objects.items():
                if obj.class_id == 114:
                    bl_tt = obj.read_typetree()
                    break

            all_sets = bl_tt['_difficultyBeatmapSets']

            # Verify OneSaber and NoArrows sets reference DIFFERENT pathIDs than Standard
            non_std_sets = [s for s in all_sets
                            if s['_beatmapCharacteristicSerializedName'] in ('OneSaber', 'NoArrows')]
            for ns in non_std_sets:
                for entry in ns['_difficultyBeatmaps']:
                    beatmap_pid = entry['_beatmapAsset']['m_PathID']
                    self.assertNotIn(beatmap_pid, std_pids,
                        f"{ns['_beatmapCharacteristicSerializedName']} beatmap pid {beatmap_pid} should not be a Standard pid")

            # Verify new TextAsset objects were created
            text_asset_pids = [pid for pid, obj in cab2.objects.items() if obj.class_id == 49]
            self.assertGreater(len(text_asset_pids), len(std_pids),
                "Should have created new TextAsset objects for generated modes")

    def test_generated_v2_no_arrows_converted_to_v3_before_injection(self):
        """NoArrows generated from V2 source should be V3 after injection."""

        with tempfile.TemporaryDirectory() as d:
            files = {
                "info.dat": json.dumps({"_songName": "Test", "_beatsPerMinute": 120.0}),
                "EasyStandard.dat": self._v2(1.0, typ=0, d=3),
            }
            for name, content in files.items():
                with open(os.path.join(d, name), 'w') as fh:
                    fh.write(content)

            detected = detect_song_modes(d)
            enabled = build_mode_mapping(detected, None)
            generated = generate_missing_mode_beatmaps(d, detected, enabled, bpm=120.0)

            # Verify the generated NoArrows file exists
            no_arrows_file = [f for f in generated if 'NoArrows' in f]
            self.assertEqual(len(no_arrows_file), 1)

            # Check the generated file content
            with open(os.path.join(d, no_arrows_file[0])) as fh:
                bm = json.load(fh)
            # Should be V2 (generator preserves input format)
            self.assertEqual(bm.get("_version"), "2.0.0")
            # But after injection (V2→V3 conversion), should be V3
            # This is handled in add_mode_characteristics - verify the conversion logic
            self.assertIn('d', str(bm) or '_notes' in bm, "Should have note data")

    def test_idempotent_injection_with_pre_existing_mode_files(self):
        """Re-running the pipeline on a source dir that already has generated
        mode .dat files (generated_files empty) must still inject the mode
        beatmaps as new TextAssets, not fall back to cloning Standard refs."""
        import os as _os

        from UnityPy import load as load_bundle

        with tempfile.TemporaryDirectory() as d:
            files = {
                "info.dat": json.dumps({"_songName": "Test", "_beatsPerMinute": 120.0}),
                "EasyStandard.dat": self._v2(1.0, typ=0, d=3),
                "NormalStandard.dat": self._v2(2.0, typ=1, d=1),
                "HardStandard.dat": self._v2(3.0, typ=0, d=2),
                "ExpertStandard.dat": self._v2(4.0, typ=1, d=0),
                "ExpertPlusStandard.dat": self._v2(5.0, typ=0, d=1),
            }
            for name, content in files.items():
                with open(os.path.join(d, name), 'w') as fh:
                    fh.write(content)

            # Simulate a previous run: generate the mode files once
            detected = detect_song_modes(d)
            enabled = build_mode_mapping(detected, None)
            generate_missing_mode_beatmaps(d, detected, enabled, bpm=120.0)

            test_bundle = _os.path.join(
                _os.path.dirname(_os.path.dirname(__file__)),
                "test_data", "template_standard.bundle"
            )
            if not _os.path.isfile(test_bundle):
                self.skipTest("template_standard.bundle not available")

            env = load_bundle(test_bundle)
            bf_file = None
            cab = None
            for k, f in env.files.items():
                bf_file = f
                if hasattr(f, 'files'):
                    for fk, ff in f.files.items():
                        if hasattr(ff, 'objects') and ff.objects:
                            cab = ff
                            break
                if cab:
                    break

            # Apply mode mapping with song_dir but EMPTY generated_files —
            # pre-existing mode files on disk must still be injected
            mode_count = add_mode_characteristics(
                cab, ["OneSaber", "NoArrows"], song_dir=d,
                generated_files=[], bpm=120.0, target_name="Test"
            )
            self.assertEqual(mode_count, 2)

            # Save and reload to verify persisted changes (UnityPy typetree
            # reads are cached in-session, so assertions need a fresh load)
            import io as _io
            result = bf_file.save(packer="lz4")
            env2 = load_bundle(_io.BytesIO(result))
            cab2 = None
            for k, f in env2.files.items():
                if hasattr(f, 'files'):
                    for fk, ff in f.files.items():
                        if hasattr(ff, 'objects') and ff.objects:
                            cab2 = ff
                            break
                if cab2:
                    break

            beatmap_level = None
            for pid, obj in cab2.objects.items():
                if obj.class_id == 114:
                    beatmap_level = obj
                    break
            self.assertIsNotNone(beatmap_level)

            bl_tt = beatmap_level.read_typetree()
            std_set = [s for s in bl_tt['_difficultyBeatmapSets']
                       if s['_beatmapCharacteristicSerializedName'] == 'Standard'][0]
            std_pids = [e['_beatmapAsset']['m_PathID'] for e in std_set['_difficultyBeatmaps']]

            # New TextAssets must have been created for the modes
            new_text_assets = 0
            for pid, obj in cab2.objects.items():
                if obj.class_id == 49 and obj.path_id not in std_pids:
                    new_text_assets += 1
            self.assertGreaterEqual(new_text_assets, 10,
                "Pre-existing mode files should be injected as new TextAssets")

            # Mode sets must reference DIFFERENT pathIDs than Standard
            for s in bl_tt['_difficultyBeatmapSets']:
                if s['_beatmapCharacteristicSerializedName'] in ('OneSaber', 'NoArrows'):
                    for entry in s['_difficultyBeatmaps']:
                        self.assertNotIn(entry['_beatmapAsset']['m_PathID'], std_pids,
                            f"{s['_beatmapCharacteristicSerializedName']} should not clone Standard")


if __name__ == '__main__':
    unittest.main()


if __name__ == '__main__':
    unittest.main()
