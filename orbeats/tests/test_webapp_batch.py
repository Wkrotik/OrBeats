"""
test_webapp_batch.py — Batch tab: example-script parser + custom-batch
files + endpoints (all local; no PS4, no real deploys — the batch job
route is validated for its guard logic only).
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

import server  # noqa: E402
from adapters import batch  # noqa: E402

client = TestClient(server.app)


class FakeJob:
    def __init__(self, argv, label=""):
        self.argv = list(argv)
        self.label = label
        self.id = 1
        self.exit_code = 0
        self.lines = ["(mocked)"]
        self.cancelled = False
        self.command_line = " ".join(argv)


@pytest.fixture(autouse=True)
def no_real_jobs(monkeypatch):
    started = []

    def fake_start(argv, label=""):
        started.append(("pipeline", list(argv), label))
        job = FakeJob(argv, label)
        server.RUNNER._job = job
        return job

    def fake_start_script(script, argv, label=""):
        started.append(("script", list(argv), label))
        job = FakeJob(argv, label)
        server.RUNNER._job = job
        return job

    monkeypatch.setattr(server.RUNNER, "start", fake_start)
    monkeypatch.setattr(server.RUNNER, "start_script", fake_start_script)
    server.RUNNER._job = None
    server.RUNNER.pending_flags = None
    yield started
    server.RUNNER._job = None
    server.RUNNER.pending_flags = None


@pytest.fixture
def started_jobs(no_real_jobs):
    return no_real_jobs


@pytest.fixture
def batches_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "BATCH_DIR", tmp_path)
    return tmp_path


class TestExampleParsing:
    def test_all_34_packs_parse(self):
        packs = batch.parse_example_scripts()
        assert len(packs) == 34
        names = [p["name"] for p in packs]
        assert any("Rolling Stones" in n for n in names)

    def test_rolling_stones_entries_shape(self):
        packs = batch.parse_example_scripts()
        rs = next(p for p in packs if "Rolling Stones" in p["name"])
        assert len(rs["songs"]) == 11
        s = rs["songs"][0]
        assert s["map_id"] and s["target"]
        assert s["convert_to_v3"] is True and s["pad_fsb5"] is False
        # human hints attached (the # Song N: comments)
        assert s["song_name"], "song comment hint not attached"
        assert s["artist"], "artist hint not attached"

    def test_commented_template_lines_skipped(self):
        """The docs' <MAP_ID> template lines (commented) must NOT parse."""
        packs = batch.parse_example_scripts()
        for p in packs:
            for s in p["songs"]:
                assert "<" not in s["map_id"], f"template placeholder parsed: {s}"

    def test_endpoint_matches_parser(self):
        j = client.get("/api/batch/examples").json()
        assert len(j["packs"]) == 34


class TestCustomBatchFiles:
    def test_save_and_load_roundtrip(self, batches_dir):
        doc = {"format": "bsd-batch", "version": 1, "name": "My Pack",
               "description": "test",
               "songs": [{"map_id": "c213", "target": "Angry",
                          "song_name": "Rhythm Is A Dancer",
                          "artist": "Pegboard Nerds"}]}
        saved = batch.save_custom_batch(doc)
        assert saved["file"].endswith(".json")
        loaded = batch.load_custom_batch(saved["file"])
        assert loaded["name"] == "My Pack"
        assert loaded["songs"][0]["map_id"] == "c213"
        assert loaded["songs"][0]["artist"] == "Pegboard Nerds"

    def test_defaults_normalized(self, batches_dir):
        doc = {"format": "bsd-batch", "version": 1, "name": "X",
               "songs": [{"map_id": "a", "target": "b"}]}
        saved = batch.save_custom_batch(doc)
        s = batch.load_custom_batch(saved["file"])["songs"][0]
        assert s["audio"] == "pcm16" and s["convert_to_v3"] is True \
            and s["pad_fsb5"] is False

    def test_unknown_fields_roundtrip(self, batches_dir):
        doc = {"format": "bsd-batch", "version": 1, "name": "X",
               "songs": [{"map_id": "a", "target": "b", "my_future_field": 42}]}
        saved = batch.save_custom_batch(doc)
        loaded = batch.load_custom_batch(saved["file"])
        assert loaded["songs"][0]["my_future_field"] == 42

    def test_validation_errors(self, batches_dir):
        with pytest.raises(ValueError, match="name"):
            batch.save_custom_batch({"songs": []})
        with pytest.raises(ValueError, match="map_id"):
            batch.save_custom_batch({"name": "X", "songs": [{"target": "b"}]})
        with pytest.raises(ValueError, match="format"):
            batch.save_custom_batch({"format": "other", "name": "X", "songs": []})
        with pytest.raises(ValueError, match="audio"):
            batch.save_custom_batch({"name": "X",
                                     "songs": [{"map_id": "a", "target": "b",
                                                "audio": "mp3"}]})

    def test_path_traversal_rejected(self, batches_dir):
        with pytest.raises(ValueError):
            batch.load_custom_batch("../evil.json")
        with pytest.raises(ValueError):
            batch.save_custom_batch({"name": "X", "songs": []},
                                    filename="a/b.json")

    def test_endpoint_save_list_delete(self, batches_dir):
        r = client.post("/api/batch/custom", json={
            "batch": {"format": "bsd-batch", "version": 1, "name": "API Pack",
                      "songs": [{"map_id": "c213", "target": "Angry"}]}})
        assert r.status_code == 200
        fname = r.json()["file"]
        lst = client.get("/api/batch/custom").json()["batches"]
        assert any(b["file"] == fname for b in lst)
        got = client.get(f"/api/batch/custom/{fname}").json()
        assert got["ok"] and got["batch"]["name"] == "API Pack"
        dele = client.delete(f"/api/batch/custom/{fname}")
        assert dele.status_code == 200
        assert client.get("/api/batch/custom/{fname}".replace("{fname}", fname)).status_code == 404


class TestBatchJobEndpoint:
    def test_batch_requires_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server.paths, "CONFIG_PATH", tmp_path / "none.json")
        r = client.post("/api/jobs/batch", json={"songs": [{"map_id": "a", "target": "b"}]})
        assert r.status_code == 400

    def test_batch_validates_before_starting(self, monkeypatch, started_jobs):
        """A bad entry aborts with 400 and starts NOTHING."""
        monkeypatch.setattr(server.paths, "CONFIG_PATH", PROJECT / "ps4_config.json")
        r = client.post("/api/jobs/batch", json={
            "songs": [{"map_id": "a", "target": "b"},
                      {"map_id": "", "target": "x"}]})
        assert r.status_code == 400
        assert started_jobs == []

    def test_batch_starts_script_job(self, monkeypatch, started_jobs):
        monkeypatch.setattr(server.paths, "CONFIG_PATH", PROJECT / "ps4_config.json")
        r = client.post("/api/jobs/batch", json={
            "songs": [{"map_id": "c213", "target": "Angry"},
                      {"map_id": "6d63", "audio": "pcm16"}]})
        assert r.status_code == 200
        j = r.json()
        assert j["count"] == 2
        kind, argv, _ = started_jobs[0]
        assert kind == "script"
        payload = json.loads(argv[argv.index("--jobs") + 1])
        assert len(payload) == 2
        assert all("--additive-install" in row and "--target" not in row for row in payload)


class TestMultiPackBatch:
    """The multi-pack flow: the client merges selected example packs (in the
    order shown) into ONE /api/jobs/batch call. Server-side contract: the
    merged payload is a plain songs list — pinned here end-to-end."""

    def test_multi_pack_merge_and_run(self, monkeypatch, started_jobs):
        """Selecting the user's standard loadout (rolling stones, billie
        eilish, britney spears, lizzo, camellia) merges to the same songs
        the chained example scripts would deploy — in pack order."""
        monkeypatch.setattr(server.paths, "CONFIG_PATH", PROJECT / "ps4_config.json")
        packs = batch.parse_example_scripts()
        wanted = ["Rolling Stones", "Billie Eilish", "Britney Spears",
                  "Lizzo", "Camelia"]
        selected = [p for p in packs if any(w in p["name"] for w in wanted)]
        assert len(selected) == 5, f"expected 5 packs, got {[p['name'] for p in selected]}"
        songs = [dict(s) for p in selected for s in p["songs"]]
        total = sum(len(p["songs"]) for p in selected)
        assert len(songs) == total
        r = client.post("/api/jobs/batch", json={"songs": songs})
        # Legacy replacement presets exceed this bounded additive library;
        # refuse before starting any job, never overwrite the named DLC slots.
        assert r.status_code == 400
        assert started_jobs == []

    def test_multi_pack_counts_match_scripts(self):
        """The five-pack standard loadout's merged size == the sum of the
        scripts' deploy-line counts (no drops, no dupes from the merge)."""
        packs = batch.parse_example_scripts()
        wanted = ["Rolling Stones", "Billie Eilish", "Britney Spears",
                  "Lizzo", "Camelia"]
        selected = [p for p in packs if any(w in p["name"] for w in wanted)]
        merged = sum(len(p["songs"]) for p in selected)
        assert merged == 11 + 10 + 11 + 9 + 6  # RS, BE(10 — Lizzo-pack dupes removed), BS, Lizzo, Camelia


class TestReleaseLayoutParsing:
    """Exp 258 (alpha01 release audit): a consumer running the web app from
    an EXTRACTED RELEASE ZIP gets the example scripts at
    docs/example-scripts/ (the zip layout), not .agent/docs/ (the repo
    layout). The parser must find them in both — the alpha01 zip's Batch
    tab shipped EMPTY."""

    def test_release_layout_finds_scripts(self, monkeypatch, tmp_path):
        """Simulate the extracted zip: only docs/example-scripts/ exists.
        (docs/example-scripts/ is now the CANONICAL layout — Exp 259 — but
        the parser must still find scripts wherever they live.)"""
        from adapters import batch as batch_mod
        ziproot = tmp_path / "release"
        scripts_dir = ziproot / "docs" / "example-scripts"
        scripts_dir.mkdir(parents=True)
        # copy three real scripts in (as the release zip does) — from the
        # REPO's canonical location, resolved relative to this test file
        # (NEVER absolute: /workspace/... exists only in the devcontainer —
        # CI runners check out elsewhere and the tests went red, Exp 259b)
        import shutil
        src = PROJECT.parent / "docs" / "example-scripts"
        assert src.is_dir(), f"example scripts not found at {src}"
        for name in ["example_script_to_install_custom_songs_over_rolling_stones_music_pack.sh",
                     "example_script_to_install_custom_songs_over_billie_eilish_music_pack.sh",
                     "example_script_to_install_custom_songs_over_lizzo_music_pack.sh"]:
            shutil.copy2(src / name, scripts_dir / name)
        monkeypatch.setattr(batch_mod, "EXAMPLE_DIRS", [scripts_dir])
        packs = batch_mod.parse_example_scripts()
        assert len(packs) == 3, f"release layout not parsed: {len(packs)} packs"
        names = sorted(p["name"] for p in packs)
        assert "Rolling Stones" in names and "Billie Eilish" in names

    def test_repo_layout_still_wins(self, monkeypatch):
        """The dev layout (docs/example-scripts) keeps working unchanged."""
        from adapters import batch as batch_mod
        packs = batch_mod.parse_example_scripts()
        assert len(packs) == 34

    def test_both_layouts_no_duplicates(self, monkeypatch, tmp_path):
        """When BOTH layouts exist (a repo checkout that also has a stray
        docs/example-scripts), each script parses exactly once."""
        import shutil

        from adapters import batch as batch_mod
        canonical = PROJECT.parent / "docs" / "example-scripts"
        stray = tmp_path / "docs" / "example-scripts"
        stray.mkdir(parents=True)
        shutil.copy2(canonical / "example_script_to_install_custom_songs_over_rolling_stones_music_pack.sh",
                     stray / "example_script_to_install_custom_songs_over_rolling_stones_music_pack.sh")
        monkeypatch.setattr(batch_mod, "EXAMPLE_DIRS", [canonical, stray])
        packs = batch_mod.parse_example_scripts()
        rs = [p for p in packs if "Rolling Stones" in p["name"]]
        assert len(rs) == 1, "duplicate pack from two layouts"
        assert len(packs) == 34


class TestExampleDirsBothLayouts:
    """Exp 270a: the batch adapter must find example scripts in BOTH shapes —
    the dev checkout (<root>/orbeats/webapp with docs at <root>) and
    the FLAT release zip (webapp at the zip root, docs beside it). The zip
    shape silently showed 0 example packs since the first M9 release."""

    def test_example_dirs_include_project_level(self):
        from adapters import batch, paths
        assert (paths.PROJECT_DIR / "docs" / "example-scripts") in batch.EXAMPLE_DIRS

    def test_at_least_one_dir_exists_in_repo(self):
        from adapters import batch
        assert any(d.is_dir() for d in batch.EXAMPLE_DIRS)

    def test_release_root_surname_prefers_existing_level(self, tmp_path):
        from adapters import paths
        # dev shape: docs under RELEASE_ROOT
        assert paths.release_root_surname() in (paths.RELEASE_ROOT, paths.PROJECT_DIR)
