"""
test_webapp_songs.py — M13: local song validation + zip intake + staging.

Hermetic (plan §6): synthetic map fixtures in tmp dirs; NO network, NO PS4.
The validator's contract mirrors the pipeline's own (adapters/songs.py
docstring) — these tests pin that mirror so the thin layer never drifts.
"""

import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

from adapters import songs  # noqa: E402


@pytest.fixture()
def staging(tmp_path, monkeypatch):
    """Point staging at a tmp dir so tests never touch the real one."""
    st = tmp_path / "staged_songs"
    monkeypatch.setattr(songs, "STAGING_DIR", st)
    monkeypatch.setattr(songs, "MANIFEST_PATH", st / "manifest.json")
    return st


def make_map(root: Path, *, schema="3.3.0", name="Test Song", artist="Tester",
             bpm=120.0, diffs=("Easy", "Normal", "Hard"),
             audio="song.ogg", extra=None) -> Path:
    """A minimal valid map folder (V2/V3 shape by default; V4 via schema=4)."""
    root.mkdir(parents=True, exist_ok=True)
    info = {
        "_version": schema,
        "_songName": name,
        "_songAuthorName": artist,
        "_beatsPerMinute": bpm,
        "_difficultyBeatmapSets": [{
            "_beatmapCharacteristicName": "Standard",
            "_difficultyBeatmaps": [
                {"_difficulty": d, "_beatmapFilename": f"{d}.dat"} for d in diffs
            ],
        }],
    }
    (root / "Info.dat").write_text(json.dumps(info))
    for d in diffs:
        (root / f"{d}.dat").write_text('{"_notes": []}')
    (root / audio).write_bytes(b"fake-ogg-data")
    for f in (extra or []):
        (root / f).write_bytes(b"x")
    return root


def make_v4_map(root: Path, name="V4 Song", artist="V4ist") -> Path:
    """A V4-shape map (nested song/audio objects, difficultyBeatmaps)."""
    root.mkdir(parents=True, exist_ok=True)
    info = {
        "_version": "4.0.0",
        "song": {"title": name, "author": artist},
        "audio": {"bpm": 111.0, "songFilename": "song.egg"},
        "difficultyBeatmaps": [
            {"characteristic": "Standard", "difficulty": "Expert",
             "beatmapFile": "Expert.beatmap.dat"},
        ],
    }
    (root / "Info.dat").write_text(json.dumps(info))
    (root / "Expert.beatmap.dat").write_text('{"colorNotes": []}')
    (root / "song.egg").write_bytes(b"fake-egg")
    return root


# ------------------------------------------------------------ validate_dir

def test_validate_happy_path(tmp_path):
    d = make_map(tmp_path / "map", name="Happy", artist="Camper")
    v = songs.validate_dir(str(d))
    assert v.ok, v.errors
    assert v.name == "Happy" and v.artist == "Camper"
    assert v.bpm == 120.0
    assert v.schema == "V3"
    assert v.difficulties == ["Easy", "Normal", "Hard"]
    assert v.audio_files == ["song.ogg"]
    # Easy present, Expert missing → exactly one warning (the auto-fill note)
    assert any("Expert" in w for w in v.warnings)


def test_validate_v2_schema():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = make_map(Path(td) / "m", schema="2.2.0")
        v = songs.validate_dir(str(d))
        assert v.ok and v.schema == "V2"


def test_validate_v4_nested_metadata(tmp_path):
    d = make_v4_map(tmp_path / "v4")
    v = songs.validate_dir(str(d))
    assert v.ok, v.errors
    assert v.name == "V4 Song" and v.artist == "V4ist"
    assert v.bpm == 111.0
    assert v.schema == "V4"
    assert v.difficulties == ["Expert"]


def test_validate_missing_dir():
    v = songs.validate_dir("/no/such/dir/anywhere")
    assert not v.ok
    assert "Folder not found" in v.errors[0]
    assert "To fix" in v.errors[0]


def test_validate_empty_path():
    v = songs.validate_dir("  ")
    assert not v.ok
    assert "No folder path" in v.errors[0]


def test_validate_no_info_dat(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    v = songs.validate_dir(str(d))
    assert not v.ok
    assert "No Info.dat found" in v.errors[0]
    assert "To fix" in v.errors[0]


def test_validate_bad_json(tmp_path):
    d = tmp_path / "corrupt"
    d.mkdir()
    (d / "Info.dat").write_text("{not json")
    (d / "song.ogg").write_bytes(b"x")
    v = songs.validate_dir(str(d))
    assert not v.ok
    assert "not valid JSON" in v.errors[0]


def test_validate_no_audio(tmp_path):
    d = make_map(tmp_path / "noaudio")
    (d / "song.ogg").unlink()
    v = songs.validate_dir(str(d))
    assert not v.ok
    assert "No audio file found" in v.errors[0]
    assert "To fix" in v.errors[0]


def test_validate_no_beatmaps(tmp_path):
    d = make_map(tmp_path / "nobm")
    for f in d.glob("*.dat"):
        if f.name != "Info.dat":
            f.unlink()
    v = songs.validate_dir(str(d))
    assert not v.ok
    assert "No beatmap" in v.errors[0]


def test_validate_lowercase_info(tmp_path):
    d = tmp_path / "lower"
    d.mkdir()
    (d / "info.dat").write_text(json.dumps({
        "_version": "3.3.0", "_songName": "L", "_songAuthorName": "C",
        "_beatsPerMinute": 100, "_difficultyBeatmapSets": []}))
    (d / "Easy.dat").write_text("{}")
    (d / "s.wav").write_bytes(b"x")
    v = songs.validate_dir(str(d))
    assert v.ok and v.name == "L"


def test_validate_one_saber_filename(tmp_path):
    d = make_map(tmp_path / "modes")
    (d / "OneSaberExpert.dat").write_text("{}")
    (d / "ExpertPlusOneSaber.dat").write_text("{}")
    v = songs.validate_dir(str(d))
    assert v.ok
    assert "OneSaber" in v.modes
    assert "ExpertPlus" in v.difficulties


def test_validate_info_only_difficulties(tmp_path):
    """Info.dat declares Standard difficulties; filenames are V4-style —
    the declared set fills gaps the filename scan missed."""
    d = make_v4_map(tmp_path / "declared")
    info = json.loads((d / "Info.dat").read_text())
    info["difficultyBeatmaps"] = [
        {"characteristic": "Standard", "difficulty": d_, "beatmapFile": "x"}
        for d_ in ("Normal", "Expert")]
    (d / "Info.dat").write_text(json.dumps(info))
    (d / "Normal.beatmap.dat").write_text("{}")
    v = songs.validate_dir(str(d))
    assert v.ok
    assert set(v.difficulties) == {"Normal", "Expert"}


# ------------------------------------------------------------ zip intake

def _zip_bytes(files: dict[str, bytes]) -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _map_files(name="Zipped", artist="Zipper") -> dict[str, bytes]:
    info = {
        "_version": "3.3.0", "_songName": name, "_songAuthorName": artist,
        "_beatsPerMinute": 128,
        "_difficultyBeatmapSets": [{"_beatmapCharacteristicName": "Standard",
                                    "_difficultyBeatmaps": [
                                        {"_difficulty": "Hard", "_beatmapFilename": "Hard.dat"}]}],
    }
    return {"Info.dat": json.dumps(info).encode(),
            "Hard.dat": b"{}",
            "song.ogg": b"ogg-bytes"}


def test_stage_zip_root_layout(staging):
    entry = songs.stage_zip_bytes(_zip_bytes(_map_files()), source="zip")
    assert entry["name"] == "Zipped"
    assert entry["schema"] == "V3"
    assert entry["difficulties"] == ["Hard"]
    assert Path(entry["dir"]).is_dir()
    assert (Path(entry["dir"]) / "Info.dat").exists()
    # staged list reflects it
    listed = songs.list_staged()
    assert any(s["id"] == entry["id"] for s in listed)


def test_stage_zip_nested_folder(staging):
    """A zip that wraps everything in one folder descends to Info.dat."""
    files = {f"wrapper/{k}": v for k, v in _map_files().items()}
    entry = songs.stage_zip_bytes(_zip_bytes(files), source="zip")
    assert Path(entry["dir"]).name == "wrapper"
    assert (Path(entry["dir"]) / "Info.dat").exists()


def test_stage_zip_slip_guarded(staging):
    files = _map_files()
    files["../../evil.sh"] = b"#!/bin/sh\n"
    with pytest.raises(ValueError, match="unsafe zip entry"):
        songs.stage_zip_bytes(_zip_bytes(files))
    # and nothing escaped the staging dir
    assert not (staging.parent / "evil.sh").exists()


def test_stage_zip_absolute_path_guarded(staging):
    files = _map_files()
    files["/etc/pwned"] = b"x"
    with pytest.raises(ValueError, match="unsafe zip entry"):
        songs.stage_zip_bytes(_zip_bytes(files))


def test_stage_zip_bad_magic(staging):
    with pytest.raises(ValueError, match="Not a zip file"):
        songs.stage_zip_bytes(b"HTML-not-a-zip<html>")


def test_stage_zip_invalid_map_cleaned_up(staging):
    """A zip that extracts but doesn't validate leaves no staged residue."""
    files = {"Info.dat": b'{"_version": "3.0.0"}',  # no audio, no beatmaps
             }
    with pytest.raises(ValueError, match="No audio"):
        songs.stage_zip_bytes(_zip_bytes(files))
    assert list(staging.iterdir()) == []  # extraction dir cleaned


# ------------------------------------------------------------ staging lifecycle

def test_stage_dir_and_persistence(staging, tmp_path):
    d = make_map(tmp_path / "myfolder", name="Folder Song")
    e1 = songs.stage_dir(str(d))
    e2 = songs.stage_dir(str(d))  # same path → same id (refresh, not dupe)
    assert e1["id"] == e2["id"]
    assert len(songs.list_staged()) == 1


def test_stage_dir_invalid_raises(tmp_path):
    with pytest.raises(ValueError, match="No Info.dat"):
        songs.stage_dir(str(tmp_path))


def test_remove_staged_zip_deletes_extract(staging):
    entry = songs.stage_zip_bytes(_zip_bytes(_map_files()), source="beatsage")
    extracted = Path(entry["dir"])
    assert songs.remove_staged(entry["id"])
    assert not extracted.exists()
    assert songs.list_staged() == []


def test_remove_staged_path_keeps_folder(staging, tmp_path):
    d = make_map(tmp_path / "keepme")
    entry = songs.stage_dir(str(d))
    assert songs.remove_staged(entry["id"])
    assert d.exists()  # the user's folder was never ours
    assert songs.list_staged() == []


def test_list_staged_prunes_dead_paths(staging, tmp_path):
    d = make_map(tmp_path / "gone")
    songs.stage_dir(str(d))
    shutil.rmtree(d)  # folder vanished after staging
    assert songs.list_staged() == []  # pruned, not shown


def test_manifest_survives_restart(staging):
    songs.stage_zip_bytes(_zip_bytes(_map_files()), source="zip")
    # a "restart" = a fresh _load_manifest from the same file
    manifest = songs._load_manifest()
    assert manifest and manifest[list(manifest)[0]]["name"] == "Zipped"


# ------------------------------------------------------------ chart stats (Exp 283c)
class TestChartStats:
    """Per-difficulty notes/NPS/peak/bombs/obstacles + map facts — the
    'what to expect before you play' data (Beat Sage's flat E/N/H band
    is visible at staging time, not mid-song)."""

    def _map_with_charts(self, root: Path, notes_per_diff: dict, bombs=0,
                         obstacles=0, events=5) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        info = {"_version": "3.3.0", "_songName": "Stats", "_songAuthorName": "T",
                "_beatsPerMinute": 120, "_environmentName": "TriangleEnvironment",
                "_difficultyBeatmapSets": [{"_beatmapCharacteristicName": "Standard",
                                            "_difficultyBeatmaps": [
                                                {"_difficulty": d, "_beatmapFilename": f"{d}.dat"}
                                                for d in notes_per_diff]}]}
        (root / "Info.dat").write_text(json.dumps(info))
        (root / "cover.jpg").write_bytes(b"jpg")
        for diff, times in notes_per_diff.items():
            notes = []
            for i, t in enumerate(times):
                notes.append({"_time": t, "_lineIndex": 0, "cutDirection": 1})
            for b in range(bombs):
                notes.append({"_time": 1.0, "_type": 3})
            obstacle_rows = [{"_time": 2.0, "_lineIndex": 2, "_duration": 4}] * obstacles
            event_rows = [{"_time": float(i), "_type": 0, "_value": 1} for i in range(events)]
            (root / f"{diff}.dat").write_text(json.dumps(
                {"_notes": notes, "_obstacles": obstacle_rows, "_events": event_rows}))
        (root / "song.ogg").write_bytes(b"x")
        return root

    def test_stats_parsed_per_difficulty(self, tmp_path):
        # Hard: 60 notes spread over 60 beats (30s @120bpm) = 2 NPS
        d = self._map_with_charts(tmp_path / "m", {
            "Easy": [i * 4.0 for i in range(20)],        # 5s span, 20 notes → 4/s
            "Hard": [i * 1.0 for i in range(60)],        # 30s span, 60 notes → 2/s
        })
        v = songs.validate_dir(str(d))
        assert v.ok
        assert v.charts["Hard"]["notes"] == 60
        # Hard: 60 notes over beats 0..59 = 29.5s @120bpm → 60/29.5 = 2.03/s
        assert v.charts["Hard"]["nps"] == 2.03
        # Easy: 20 notes over beats 0..76 = 38s → 0.53/s
        assert v.charts["Easy"]["nps"] == 0.53
        assert v.charts["Hard"]["span_s"] == 29.5  # 59 beats × 0.5s
        # map-level facts (duration = the LONGEST chart span → Easy's 38s)
        assert v.environment == "TriangleEnvironment"
        assert v.cover_art == "cover.jpg"
        assert v.duration_s == 38.0

    def test_bombs_obstacles_events_counted(self, tmp_path):
        d = self._map_with_charts(tmp_path / "m", {"Hard": [1.0, 2.0]},
                                  bombs=3, obstacles=2, events=7)
        v = songs.validate_dir(str(d))
        c = v.charts["Hard"]
        assert c["bombs"] == 3          # V2: _type == 3 entries
        assert c["obstacles"] == 2
        assert c["events"] == 7

    def test_v3_color_notes_parsed(self, tmp_path):
        d = self._map_with_charts(tmp_path / "m", {})
        (d / "Hard.dat").write_text(json.dumps({
            "colorNotes": [{"b": i * 2.0} for i in range(30)],
            "bombNotes": [{"b": 1.0}] * 2,
            "obstacles": [{"b": 1.0}] * 4,
            "basicEvents": [{"b": 1.0}] * 9,
        }))
        v = songs.validate_dir(str(d))
        c = v.charts["Hard"]
        assert c["notes"] == 30
        assert c["bombs"] == 2
        assert c["obstacles"] == 4
        assert c["events"] == 9

    def test_peak_nps_math(self):
        # 95 notes packed into ~1 second of beat time at 120bpm → 95 notes
        # inside the 10s (20-beat) window → 9.5 NPS peak
        times = [1.0 + (i % 20) * 0.05 for i in range(95)]
        assert songs._peak_nps(times, bpm=120) >= 9.4
        # spread out: 1 note per 10 beats → 3 land in the 20-beat window → 0.3/s
        assert abs(songs._peak_nps([i * 10.0 for i in range(10)], bpm=120) - 0.3) < 0.01

    def test_sparse_warning_fires_for_mellow_hard(self, tmp_path):
        # Beat Sage's real-world shape: Hard at ~0.6 NPS over 170s+
        d = self._map_with_charts(tmp_path / "m", {
            "Hard": [i * 2.8 for i in range(108)],      # ~25s span... make it long:
        })
        # widen the span beyond the 30s threshold
        (d / "Hard.dat").write_text(json.dumps(
            {"_notes": [{"_time": i * 4.0} for i in range(108)],
             "_obstacles": [], "_events": []}))
        v = songs.validate_dir(str(d))
        assert v.ok
        assert any("Sparse charts" in w for w in v.warnings)
        assert any("Expert" in w for w in v.warnings)  # the guidance points there

    def test_no_sparse_warning_for_dense_charts(self, tmp_path):
        d = self._map_with_charts(tmp_path / "m", {
            "Hard": [i * 0.5 for i in range(120)],     # 2/s → no warning
        })
        v = songs.validate_dir(str(d))
        assert not any("Sparse" in w for w in v.warnings)

    def test_mode_variant_notes_totalled(self, tmp_path):
        d = self._map_with_charts(tmp_path / "m", {"Hard": [1.0, 2.0]})
        (d / "HardOneSaber.dat").write_text(json.dumps({"_notes": [{"_time": 1.0}] * 12}))
        (d / "Hard90Degree.dat").write_text(json.dumps({"_notes": []}))  # Beat Sage's 0-note 90s
        v = songs.validate_dir(str(d))
        assert v.mode_notes.get("OneSaber") == 12
        assert v.mode_notes.get("90Degree") == 0

    def test_generation_annotation(self, tmp_path, monkeypatch):
        st = tmp_path / "staged_songs"
        monkeypatch.setattr(songs, "STAGING_DIR", st)
        monkeypatch.setattr(songs, "MANIFEST_PATH", st / "manifest.json")
        d = self._map_with_charts(tmp_path / "m", {"Hard": [1.0, 2.0]})
        entry = songs.stage_dir(str(d))
        updated = songs.annotate_staged(entry["id"], {"generation": {
            "system_tag": "v1", "difficulties": ["Hard"]}})
        assert updated["generation"]["system_tag"] == "v1"
        assert songs._load_manifest()[entry["id"]]["generation"]["system_tag"] == "v1"
        assert songs.annotate_staged("nope", {}) is None

    def test_stats_in_validate_response(self, tmp_path, monkeypatch):
        import server as _server
        from fastapi.testclient import TestClient
        client = TestClient(_server.app)
        from adapters import songs as songs_adapter
        st = tmp_path / "staged_songs"
        monkeypatch.setattr(songs_adapter, "STAGING_DIR", st)
        monkeypatch.setattr(songs_adapter, "MANIFEST_PATH", st / "manifest.json")
        d = self._map_with_charts(tmp_path / "m", {"Hard": [i * 0.5 for i in range(40)]})
        r = client.post("/api/songs/validate-dir", json={"path": str(d)})
        j = r.json()
        assert j["ok"] is True
        assert j["validation"]["charts"]["Hard"]["notes"] == 40
        assert j["validation"]["environment"] == "TriangleEnvironment"
        assert j["validation"]["cover_art"] == "cover.jpg"
        # 40 notes over beats 0..19.5 = 9.75s → 4.1/s
        assert j["staged"]["charts"]["Hard"]["nps"] == 4.1

    def test_test_song_endpoint_deterministic(self):
        import hashlib

        import server as _server
        from fastapi.testclient import TestClient
        client = TestClient(_server.app)
        r = client.get("/api/songs/test-song", params={"seconds": 8})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("audio/wav")
        assert r.content[:4] == b"RIFF"
        r2 = client.get("/api/songs/test-song", params={"seconds": 8})
        assert hashlib.md5(r.content).hexdigest() == hashlib.md5(r2.content).hexdigest()
        # the 48s default reproduces the deployed theme song byte-for-byte
        r48 = client.get("/api/songs/test-song", params={"seconds": 48})
        assert hashlib.md5(r48.content).hexdigest() == "26d59c5d196b2be39c4aec6f5774b286"
