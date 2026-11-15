"""Synthetic batch/geometry/menu regressions: no network, game inputs or console."""
import copy
import json
import re
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp"))

import additive_companion as core
import additive_library as wire
import additive_v3_native as v3native
import additive_v4_native as native
import companion_api
import console_transaction
import library_manager as manager
import pytest
from PIL import Image
from test_additive_v4_import import chart, source
from test_fresh_library import CONFIG, FTP, synthetic


@pytest.mark.parametrize("bpm", [2080, 100000])
def test_positive_fast_bpm_events_preserve_seconds_and_native_regions(bpm):
    importer = core.helper("import_v3_additive.py")
    tempo = importer.Tempo(130, [{"b": 1, "m": bpm}, {"b": 2, "m": 130}])
    assert tempo.time(2) == pytest.approx(60 / 130 + 60 / bpm)
    audio = v3native.audio_from_tempo(tempo, 441000)
    assert native.audio(audio) > 0
    assert audio["bpmData"][1]["eb"] == pytest.approx(2)
    for bad in (0, -1, float("nan"), float("inf"), 1000001, True):
        with pytest.raises(ValueError):
            importer.Tempo(130, [{"b": 1, "m": bad}])
    with pytest.raises(ValueError):
        importer.Tempo(100000, [])  # Base BPM guard was not widened.


@pytest.mark.parametrize("value", [-0.1, -0.2, -100, 100])
def test_native_signed_arc_tangents_preserved_but_geometry_not_widened(value):
    data = chart()
    data["arcsData"] = [{"m": value, "tm": value}]
    before = copy.deepcopy(data)
    native.chart(data, 2)
    assert data == before
    for bad in (-100.01, 100.01, float("nan"), True):
        data["arcsData"][0]["tm"] = bad
        with pytest.raises(ValueError, match="arcsData.tm"):
            native.chart(data, 2)


@pytest.mark.parametrize("start,duration,total,expected", [
    (0, 16, 8.881, (0, 8.881)), (0, 100, 150, (0, 30)),
    (200, 10, 12, (2, 10)), (9, 10, 12, (9, 3)), (1, 3, 12, (1, 3)),
])
def test_menu_preview_bounds_leave_gameplay_and_source_unchanged(tmp_path, monkeypatch, start, duration, total, expected):
    media = core.helper("prepare_additive_media.py")
    root = tmp_path / "song"
    root.mkdir()
    info = {"_songName": "Synthetic", "_previewStartTime": start, "_previewDuration": duration,
            "_songFilename": "audio.ogg", "_coverImageFilename": "cover.png"}
    (root / "Info.dat").write_text(json.dumps(info))
    (root / "audio.ogg").write_bytes(b"unchanged gameplay audio")
    Image.new("RGB", (4, 4)).save(root / "cover.png")
    level = tmp_path / "manifest.json"
    level.write_text(json.dumps({"level_id": "bsd_additive_" + "a" * 24, "song_name": "Synthetic", "duration_seconds": total}))
    def run(args, **kwargs):
        trim = args[args.index("-af") + 1]
        first, last = map(int, re.search(r"start_sample=(\d+):end_sample=(\d+)", trim).groups())
        with wave.open(args[-1], "wb") as audio:
            audio.setparams((2, 2, 44100, last - first, "NONE", "not compressed"))
            audio.writeframes(b"\0" * ((last - first) * 4))
    monkeypatch.setattr(media.subprocess, "run", run)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    result = media.prepare(root, level, tmp_path / "menu")
    assert (result["preview_start_seconds"], result["preview_duration_seconds"]) == expected
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before
    assert json.loads(level.read_text())["duration_seconds"] == total
    media.verify(tmp_path / "menu")


@pytest.mark.parametrize("layer", [0, 2, 3])
def test_wall_archive_check_uses_selected_revision_without_console(tmp_path, monkeypatch, layer):
    root, _ = source(tmp_path)
    data = chart()
    data["obstaclesData"][0]["y"] = layer
    (root / "ExpertPlus.dat").write_text(json.dumps(data))
    metadata = {"versions": [{"hash": "b" * 40}]}
    (root / "beatsaver-metadata.json").write_text(json.dumps(metadata))
    monkeypatch.setattr(core, "download", lambda *args: root)
    monkeypatch.setattr(core, "FTP", lambda: pytest.fail("No console contact for public archive check"))
    result = core.check_wall_layers("123ab")
    assert result["hash"] == "b" * 40
    assert bool(result["blockers"]) == (layer > 2)


class BatchFTP(FTP):
    def __init__(self, files):
        super().__init__(files, dirs=("/", "/data", "/mnt/sandbox"))
        self.deleted = []
        self.published = 0
        self.fail_publish = False
    def mkd(self, path):
        if path in self.dirs:
            raise core.error_perm("550 exists")
        self.dirs.add(path)
    def rmd(self, path):
        if self.nlst(path):
            raise core.error_perm("550 not empty")
        self.dirs.remove(path)
    def storbinary(self, command, stream):
        self.files[command.removeprefix("STOR ")] = stream.read()
    def rename(self, old, new):
        if new == wire.BASE + "/library.bin":
            if self.fail_publish:
                self.fail_publish = False
                raise OSError("publication failed")
            self.published += 1
        self.files[new] = self.files.pop(old)
    def delete(self, path):
        if path not in self.files or path in self.denied:
            raise core.error_perm("550 absent or denied")
        # Owned maps may be cleaned only after the single manifest update.
        if ".stage-" not in path and ".rollback-" not in path:
            assert self.published == 1
        self.deleted.append(path)
        del self.files[path]


@pytest.fixture
def batch(tmp_path, monkeypatch):
    songs = []
    files = {}
    for i in range(3):
        song, blobs = synthetic()
        song["id"] = "bsd_additive_" + f"{i:024x}"
        songs.append(song)
        files.update(dict(zip(wire.paths(song), blobs.values())))
    files[wire.BASE + "/library.bin"] = wire.encode(songs)
    ftp = BatchFTP(files)
    monkeypatch.setattr(manager, "FTP", lambda: ftp)
    monkeypatch.setattr(console_transaction, "LOCAL_BACKUPS", tmp_path / "backups")
    return ftp, songs


def test_batch_removal_one_connection_one_manifest_commit_retains_unselected(batch):
    ftp, songs = batch
    before = {p: ftp.files[p] for p in wire.paths(songs[2])}
    result = manager.remove_many(CONFIG, [s["id"] for s in songs[:2]])
    assert result["count"] == 1 and not result["cleanup_pending"]
    assert wire.decode(ftp.files[wire.BASE + "/library.bin"]) == wire.decode(wire.encode([songs[2]]))
    assert ftp.published == 1 and len(ftp.connections) == 1
    assert all(ftp.files[p] == blob for p, blob in before.items())
    assert ftp.closed and wire.BASE + "/.install-lock" not in ftp.dirs


def test_last_batch_preserves_conversion_seed(batch):
    ftp, songs = batch
    blob = ftp.files[wire.paths(songs[0])[0]]
    manager.remove_many(CONFIG, [s["id"] for s in songs])
    assert ftp.files[wire.BASE + "/template.bundle"] == blob
    assert wire.decode(ftp.files[wire.BASE + "/library.bin"]) == []


@pytest.mark.parametrize("ids", [[], None, ["../../bad"], ["bsd_additive_" + "0" * 24] * 2,
                                  ["bsd_additive_" + "f" * 24]])
def test_invalid_or_stale_batch_changes_nothing(batch, ids):
    ftp, _ = batch
    before = dict(ftp.files)
    with pytest.raises(ValueError):
        manager.remove_many(CONFIG, ids)
    assert ftp.files == before and not ftp.deleted


def test_failed_batch_commit_does_not_delete_any_map(batch):
    ftp, songs = batch
    before = dict(ftp.files)
    ftp.fail_publish = True
    with pytest.raises(OSError, match="publication failed"):
        manager.remove_many(CONFIG, [songs[0]["id"], songs[1]["id"]])
    assert all(ftp.files[p] == blob for p, blob in before.items())
    assert not any(path in ftp.deleted for s in songs for path in wire.paths(s))


def test_denied_cleanup_is_reported_after_successful_batch(batch):
    ftp, songs = batch
    path = wire.paths(songs[0])[0]
    ftp.denied.add(path)
    result = manager.remove_many(CONFIG, [songs[0]["id"]])
    assert path in result["cleanup_pending"] and path in ftp.files
    assert result["count"] == 2


def test_independent_audio_endpoint_roundings_are_bounded():
    # Source metadata is one 48kHz sample short; resampling rounds the other endpoint.
    data = {"version": "4.0.0", "songFrequency": 48000, "songSampleCount": 95999,
            "bpmData": [{"si": 0, "ei": 95999, "sb": 0, "eb": 4}], "lufsData": []}
    assert native.audio_duration_matches(data, 44100, 88201)
    result = native.resample_audio(data, 44100, 88201, "test")
    assert result["bpmData"][0]["eb"] == 4 and data["songSampleCount"] == 95999
    for count in (88197, 88202):
        assert not native.audio_duration_matches(data, 44100, count)
    assert native.audio_duration_matches(data, 48000, 96000)
    assert not native.audio_duration_matches(data, 48000, 96001)


def test_empty_v2_reserved_fields_are_not_lost_gameplay():
    importer = core.helper("import_v2_additive.py")
    data = {"_version": "2.6.0", "_notes": [], "_obstacles": [], "_events": []}
    expected = importer.convert_map(data)
    for field, empty in (("_sliders", []), ("_specialEventsKeywordFilters", {})):
        assert importer.convert_map(dict(data, **{field: empty})) == expected
        for authored in ([{"_time": 1}], {"d": [1]}, None, False):
            with pytest.raises(ValueError, match="unsupported nonempty"):
                importer.convert_map(dict(data, **{field: authored}))


def test_stray_chart_presentation_defaults_are_not_real_selections():
    importer = core.helper("import_v3_additive.py")
    data = {"version": "3.3.0"}
    expected = importer.convert_map(data, 120)
    for field in ("_beatmapColorSchemeIdx", "_environmentNameIdx"):
        assert importer.convert_map(dict(data, **{field: 0}), 120) == expected
        for selection in (1, -1, True, "0"):
            with pytest.raises(ValueError, match="presentation index"):
                importer.convert_map(dict(data, **{field: selection}), 120)


def test_info_editor_alias_is_provenance_not_a_mod_bypass():
    importer = core.helper("import_v3_additive.py")
    importer.cosmetic_only({"editors": {"lastEditedBy": "Fixture"}}, {"editors"})
    for value in (None, "editor", []):
        with pytest.raises(ValueError, match="provenance"):
            importer.cosmetic_only({"editors": value}, {"editors"})
    with pytest.raises(ValueError, match="requirements"):
        importer.cosmetic_only({"editors": {}, "_requirements": ["Noodle Extensions"]}, {"editors"})


def test_bulk_api_uses_shared_transaction(batch, monkeypatch):
    ftp, songs = batch
    monkeypatch.setattr(companion_api, "settings", lambda: CONFIG)
    result = companion_api.remove_maps({"ids": [s["id"] for s in songs[:2]]})
    assert len(result["removed"]) == 2 and ftp.published == 1
