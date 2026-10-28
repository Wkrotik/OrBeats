"""
test_webapp_server.py — FastAPI endpoint tests (TestClient).

No network, no PS4: BeatSaver calls and ps4 adapter reads are monkeypatched.
Hardware-gate pattern: no test here may touch the real PS4 — the ps4
adapter's lftp path is never invoked.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

import server  # noqa: E402
from adapters import beatsaver as bs_adapter  # noqa: E402
from adapters import ps4 as ps4_adapter  # noqa: E402

client = TestClient(server.app)


class TestModeDetection:
    def test_ping_local_backend(self):
        r = client.get("/api/ping")
        assert r.status_code == 200
        j = r.json()
        assert j["mode"] == "local-backend"
        assert j["pipeline_present"] is True


class TestWizardEndpoints:
    def test_dump_validate_requires_path(self):
        r = client.get("/api/dump/validate")
        assert r.status_code == 422  # FastAPI: missing required query param

    def test_dump_validate_reports_missing(self, tmp_path):
        r = client.get("/api/dump/validate", params={"path": str(tmp_path / "nope")})
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is False
        assert any("does not exist" in e for e in j["errors"])

    def test_dump_validate_good(self, tmp_path):
        patch = tmp_path / "CUSA12878-patch"
        (patch / "Media/StreamingAssets/aa/PS4").mkdir(parents=True)
        (patch / "eboot.bin").write_bytes(b"x")
        (patch / "Media/StreamingAssets/aa/catalog.json").write_text("{}")
        (tmp_path / "CUSA12878-app").mkdir()
        r = client.get("/api/dump/validate", params={"path": str(tmp_path)})
        assert r.json()["ok"] is True

    def test_config_read_returns_something(self):
        r = client.get("/api/config")
        assert r.status_code == 200
        assert "ps4" in r.json()

    def test_config_save_and_roundtrip(self, tmp_path, monkeypatch):
        scratch = tmp_path / "ps4_config.json"
        monkeypatch.setattr(server.config.paths, "CONFIG_PATH", scratch)
        r = client.post("/api/config/save", json={
            "dump_root": str(tmp_path), "ps4_ip": "10.0.0.9"})
        assert r.status_code == 200
        assert r.json()["config_path"] == str(scratch)
        assert r.json()["config"]["ps4"]["ip"] == "10.0.0.9"


class TestCatalogEndpoint:
    def test_catalog_shape(self):
        r = client.get("/api/catalog")
        assert r.status_code == 200
        albums = r.json()["albums"]
        assert len(albums) > 30  # 36 packs in the real catalog
        pack_names = {a["pack"] for a in albums}
        assert "rollingstones" in pack_names or "therollingstones" in pack_names
        first_song = albums[0]["songs"][0]
        for key in ("songID", "songName", "songAuthorName"):
            assert key in first_song


class TestBeatSaverEndpoints:
    def test_search_proxies(self, monkeypatch):
        def fake_search(q, page=0, per_page=20, api_base=None):
            return {"docs": [{"id": "6d63", "name": "Take on Me - a-ha",
                             "nativeDifficulties": ["Easy", "Hard"]}], "total": 1}
        monkeypatch.setattr(server, "beatsaver", type("M", (), {"search": staticmethod(fake_search), "map_by_id": staticmethod(lambda i: {}), "BeatSaverError": bs_adapter.BeatSaverError}))
        r = client.get("/api/beatsaver/search", params={"q": "take on me"})
        assert r.status_code == 200
        assert r.json()["docs"][0]["id"] == "6d63"

    def test_map_404_maps_to_deleted_message(self, monkeypatch):
        def fake_map(map_id, api_base=None):
            raise bs_adapter.BeatSaverError("404", status=404)
        monkeypatch.setattr(server, "beatsaver", type("M", (), {"search": staticmethod(lambda *a, **k: {"docs": [], "total": 0}), "map_by_id": staticmethod(fake_map), "BeatSaverError": bs_adapter.BeatSaverError}))
        r = client.get("/api/beatsaver/map/deadmap")
        assert r.status_code == 404
        assert "deleted" in r.json()["detail"]


class TestPs4Endpoints:
    def test_ps4_test_unreachable_is_explicit(self, monkeypatch):
        """Failed read → explicit failure, never empty-truth (Exp 237/239/240)."""
        monkeypatch.setattr(server.ps4, "test_connection",
                            lambda: ps4_adapter.ReadResult(
                                ok=False, error="connection refused"))
        r = client.get("/api/ps4/test")
        j = r.json()
        assert j["ok"] is False
        # The endpoint spreads ReadResult.data OR {} — a failed read has
        # data=None, so 'status' comes only from the ok branch; the explicit
        # contract: ok=False + error present, never a fake success.
        assert j["error"] == "connection refused"

    def test_ps4_state_carries_read_errors(self, monkeypatch):
        monkeypatch.setattr(server.ps4, "read_redirects_summary",
                            lambda: ps4_adapter.ReadResult(ok=False, error="read failed"))
        monkeypatch.setattr(server.ps4, "read_features",
                            lambda: ps4_adapter.ReadResult(ok=False, error="read failed"))
        monkeypatch.setattr(server.ps4, "read_song_metadata",
                            lambda: ps4_adapter.ReadResult(ok=False, error="read failed"))
        r = client.get("/api/ps4/state")
        j = r.json()
        assert j["redirects"]["ok"] is False and "error" in j["redirects"]
        assert j["features"]["ok"] is False
        assert j["song_metadata"]["ok"] is False


class TestLoadoutEndpoints:
    def test_packs_list_offline_capable(self):
        """The Manage-Songs dropdown works without the PS4 (catalog only)."""
        r = client.get("/api/loadout/packs")
        assert r.status_code == 200
        j = r.json()
        assert len(j["packs"]) == 36
        assert j["songCounts"]["billieeilish"] > 0

    def test_loadout_carries_read_status(self, monkeypatch):
        """Read failures must surface as readStatus, never as clean-empty."""
        from adapters import ps4 as ps4_mod
        monkeypatch.setattr(
            server.ps4, "read_deployment_state",
            lambda: ps4_mod.ReadResult(ok=False, data={
                "redirects_read_error": "get: timeout"}, error="get: timeout"))
        r = client.get("/api/loadout")
        j = r.json()
        assert j["readStatus"]["redirectsOk"] is False
        assert j["readStatus"]["redirectsReadError"] == "get: timeout"
        # rows still render (catalog merge), but flagged unknown
        assert j["redirectedSlotCount"] == 0

    def test_loadout_happy_path_shape(self, monkeypatch):
        from adapters import ps4 as ps4_mod
        monkeypatch.setattr(
            server.ps4, "read_deployment_state",
            lambda: ps4_mod.ReadResult(ok=True, data={
                "redirects": {"BeatmapLevelsData/BadGuy": "BadGuy_v3.bundle"},
                "song_names": {"bad guy": "Odo / Ado"},
                "song_artists": {"Billie Eilish": " "}}))
        r = client.get("/api/loadout")
        j = r.json()
        assert j["readStatus"]["redirectsOk"] and j["readStatus"]["metadataOk"]
        billie = [p for p in j["packs"] if p["pack"] == "billieeilish"][0]
        badguy = [s for s in billie["songs"] if s["songID"] == "BadGuy"][0]
        assert badguy["customDeployed"] is True
        assert badguy["customName"] == "Odo"
        assert billie["deployedCount"] == 1


class TestJobGuards:
    def test_deploy_requires_config(self, monkeypatch, tmp_path):
        monkeypatch.setattr(server.paths, "CONFIG_PATH", tmp_path / "none.json")
        r = client.post("/api/jobs/deploy", json={"map_id": "x", "target": "y"})
        assert r.status_code == 400
        assert "Setup Wizard" in r.json()["detail"]

    def test_deploy_validates_options(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server.paths, "CONFIG_PATH", tmp_path / "none.json")
        monkeypatch.setattr(server.config.paths, "CONFIG_PATH", tmp_path / "none.json")
        r = client.post("/api/jobs/deploy", json={"map_id": "", "target": ""})
        assert r.status_code == 400

    def test_flags_rejects_unknown_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server.paths, "CONFIG_PATH", tmp_path / "none.json")
        monkeypatch.setattr(server.config.paths, "CONFIG_PATH", tmp_path / "none.json")
        r = client.post("/api/jobs/flags", json={"flag": "delete_everything", "value": True})
        assert r.status_code == 400

    def test_command_preview_no_longer_needs_replacement_slot(self):
        r = client.get("/api/command-preview", params={"map_id": "4ebb2", "target": ""})
        assert r.status_code == 200
        assert "--additive-install" in r.json()["command"]

    def test_command_preview_safe_default(self):
        r = client.get("/api/command-preview",
                       params={"map_id": "1d6c7c2", "target": "BadGuy"})
        j = r.json()
        assert "--additive-install --download-beat-saver-song 1d6c7c2 --config " in j["command"]
        assert "--target" not in j["command"] and "--deploy-full" not in j["command"]


class TestUiServed:
    def test_index_served(self):
        r = client.get("/")
        assert r.status_code == 200
        assert b"OrBeats" in r.content

    def test_index_assets_are_fingerprinted_and_fetchable(self):
        import hashlib
        import re
        response = client.get("/")
        assert response.headers["cache-control"] == "no-store"
        for name in ("companion.css", "companion.js"):
            url = re.search(r'/static/' + re.escape(name) + r'\?v=[0-9a-f]{20}', response.text).group()
            asset = client.get(url)
            assert asset.status_code == 200
            assert url.endswith(hashlib.sha256(asset.content).hexdigest()[:20])

    def test_changing_asset_bytes_changes_only_its_url(self, tmp_path, monkeypatch):
        import re
        (tmp_path / "companion.html").write_text('<link href="/static/companion.css"><script src="/static/companion.js"></script>')
        for name in ("companion.css", "companion.js"):
            (tmp_path / name).write_text("old")
        monkeypatch.setattr(server, "STATIC_DIR", tmp_path)
        before = client.get("/").text
        (tmp_path / "companion.js").write_text("new")
        after = client.get("/").text
        def url(html, asset):
            return re.search(r'/static/' + re.escape(asset) + r'\?v=[0-9a-f]{20}', html).group()
        assert url(before, "companion.js") != url(after, "companion.js")
        assert url(before, "companion.css") == url(after, "companion.css")

    def test_dumper_cfg_served(self):
        r = client.get("/static/dumper.cfg")
        assert r.status_code == 200
        assert b"split=3" in r.content


class TestVersionBadge:
    """The lower-corner version badge (user: 'so I can tell when your changes
    have taken effect'). Ping carries all three component versions."""

    def test_ping_carries_all_versions(self):
        j = client.get("/api/ping").json()
        assert j["webapp_version"] != "unknown" and j["webapp_version"] != "0.1.0"
        assert j["pipeline_version"] != "unknown"
        assert j["plugin_version"].startswith("v0.")

    def test_index_has_version_badge(self):
        html = client.get("/").text
        assert 'id="versions"' in html
        assert 'src="/static/companion.js?v=' in html


class TestDemosLink:
    """Exp 275: both web-app surfaces (local + Pages) carry a lower-left link
    to the project's demo-video/screenshot gallery (docs/demos.md on the MAIN
    branch — stable across releases; goes live when the PR merges)."""

    REPO_URL = "https://github.com/free5ty1e/BeatSaberPcCustomSongToPs4InstallConverter/blob/main/docs/demos.md"

    def test_link_in_index_html(self):
        html = (PROJECT / "webapp" / "static" / "index.html").read_text()
        assert 'id="demos-link"' in html
        assert self.REPO_URL in html
        assert 'target="_blank"' in html and 'rel="noopener"' in html

    def test_link_css_present(self):
        css = (PROJECT / "webapp" / "static" / "style.css").read_text()
        assert ".demos-link" in css
        assert "left: 0.6rem" in css          # lower-LEFT (badge is right)
        assert "print" in css                 # hidden when printing


class TestPluginVersionFromBundledPRX:
    """Exp 280d (user request): 'I still would want to see a version number
    for that bundled plugin'. In a release extraction there is no src/, but
    the bundled PRX carries its boot banner ('=== BS Deluxe v0.8054
    started ===') — extract the real version from it."""

    def test_bundled_prx_version_extracted(self, monkeypatch, tmp_path):
        import server as srv
        # a fake "release extraction": no src/, but a plugins/ PRX with the banner
        monkeypatch.setattr(srv.paths, "PROJECT_DIR", tmp_path, raising=False)
        (tmp_path / "plugins").mkdir()
        (tmp_path / "plugins" / "orbeats.prx").write_bytes(
            b"garbage\x00=== BS Deluxe v0.8054 started ===\x00more")
        assert srv._plugin_version() == "v0.8054"

    def test_version_falls_back_gracefully_with_neither(self, monkeypatch, tmp_path):
        import server as srv
        monkeypatch.setattr(srv.paths, "PROJECT_DIR", tmp_path, raising=False)
        assert "bundled" in srv._plugin_version()

    def test_ping_reports_the_bundled_prx_version(self, monkeypatch, tmp_path):
        import server as srv
        monkeypatch.setattr(srv.paths, "PROJECT_DIR", tmp_path, raising=False)
        (tmp_path / "plugins").mkdir()
        (tmp_path / "plugins" / "orbeats.prx").write_bytes(
            b"=== BS Deluxe v0.9999 started ===")
        srv._capture_code_versions()
        try:
            r = client.get("/api/ping")
            assert r.json()["plugin_version"] == "v0.9999"
        finally:
            # restore the real capture for other tests
            monkeypatch.undo()
            srv._capture_code_versions()


# ===================================================================== M13
class TestM13SongEndpoints:
    """Local-folder validation, zip intake, staging, Beat Sage guide —
    staging redirected to tmp; no PS4, no network."""

    def _make_map(self, root: Path) -> Path:
        import json as _json
        root.mkdir(parents=True, exist_ok=True)
        (root / "Info.dat").write_text(_json.dumps({
            "_version": "3.3.0", "_songName": "Srv", "_songAuthorName": "Test",
            "_beatsPerMinute": 100,
            "_difficultyBeatmapSets": [{"_beatmapCharacteristicName": "Standard",
                                        "_difficultyBeatmaps": [
                                            {"_difficulty": "Hard",
                                             "_beatmapFilename": "Hard.dat"}]}]}))
        (root / "Hard.dat").write_text("{}")
        (root / "song.ogg").write_bytes(b"ogg")
        return root

    def _staging(self, tmp_path, monkeypatch):
        from adapters import songs as songs_adapter
        st = tmp_path / "staged_songs"
        monkeypatch.setattr(songs_adapter, "STAGING_DIR", st)
        monkeypatch.setattr(songs_adapter, "MANIFEST_PATH", st / "manifest.json")
        return st

    def test_validate_dir_ok_stages(self, tmp_path, monkeypatch):
        self._staging(tmp_path, monkeypatch)
        d = self._make_map(tmp_path / "amap")
        r = client.post("/api/songs/validate-dir", json={"path": str(d)})
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is True
        assert j["staged"]["name"] == "Srv"
        # and it lands in the staged list
        r2 = client.get("/api/songs/staged")
        assert any(s["name"] == "Srv" for s in r2.json()["songs"])

    def test_validate_dir_problems_not_staged(self, tmp_path, monkeypatch):
        self._staging(tmp_path, monkeypatch)
        r = client.post("/api/songs/validate-dir",
                        json={"path": str(tmp_path / "missing")})
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is False
        assert j["errors"] and "To fix" in j["errors"][0]

    def test_validate_dir_requires_path(self):
        r = client.post("/api/songs/validate-dir", json={"path": "  "})
        assert r.status_code == 400

    def test_stage_zip_roundtrip(self, tmp_path, monkeypatch):
        import io
        import json as _json
        import zipfile
        self._staging(tmp_path, monkeypatch)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = {"_version": "3.3.0", "_songName": "Zipped",
                    "_songAuthorName": "Zip", "_beatsPerMinute": 90,
                    "_difficultyBeatmapSets": [
                        {"_beatmapCharacteristicName": "Standard",
                         "_difficultyBeatmaps": [{"_difficulty": "Expert",
                                                  "_beatmapFilename": "Expert.dat"}]}]}
            zf.writestr("Info.dat", _json.dumps(info))
            zf.writestr("Expert.dat", "{}")
            zf.writestr("song.wav", b"wav")
        r = client.post("/api/songs/stage-zip",
                        files={"zip_file": ("map.zip", buf.getvalue(), "application/zip")})
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is True and j["staged"]["name"] == "Zipped"

    def test_stage_zip_rejects_non_zip_name(self, tmp_path, monkeypatch):
        self._staging(tmp_path, monkeypatch)
        r = client.post("/api/songs/stage-zip",
                        files={"zip_file": ("map.exe", b"PK\x03\x04xx", "application/octet-stream")})
        assert r.status_code == 400
        assert ".zip" in r.json()["detail"]

    def test_stage_zip_rejects_empty_upload(self, tmp_path, monkeypatch):
        self._staging(tmp_path, monkeypatch)
        r = client.post("/api/songs/stage-zip",
                        files={"zip_file": ("map.zip", b"", "application/zip")})
        assert r.status_code == 400

    def test_staged_remove(self, tmp_path, monkeypatch):
        self._staging(tmp_path, monkeypatch)
        d = self._make_map(tmp_path / "rmme")
        j = client.post("/api/songs/validate-dir", json={"path": str(d)}).json()
        sid = j["staged"]["id"]
        r = client.delete(f"/api/songs/staged/{sid}")
        assert r.status_code == 200
        assert client.get("/api/songs/staged").json()["songs"] == []
        r404 = client.delete(f"/api/songs/staged/{sid}")
        assert r404.status_code == 404

    def test_beatsage_guide_payload(self):
        r = client.get("/api/beatsage/guide")
        assert r.status_code == 200
        j = r.json()
        assert j["tier"] == 2
        assert j["tier1_available"] is True
        assert j["recommended"]["modes"] == ["Standard"]
        assert j["site_url"].startswith("https://beatsage.com")

    def test_command_preview_song_dir(self, tmp_path):
        d = tmp_path / "m"
        d.mkdir()
        r = client.get("/api/command-preview",
                      params={"map_id": "", "target": "BadGuy",
                              "song_dir": str(d)})
        assert r.status_code == 200
        cmd = r.json()["command"]
        assert "--song-dir" in cmd
        assert "--download-beat-saver-song" not in cmd

    def test_deploy_endpoint_accepts_song_dir(self, tmp_path, monkeypatch):
        """The deploy POST with a song_dir builds the local argv (the job is
        never started: the runner is monkeypatched to refuse)."""
        d = tmp_path / "m"
        d.mkdir()
        class _FakeJob:
            id = 42
        def _no_start(argv, label=""):
            _no_start.called = True
            return _FakeJob()
        _no_start.called = False
        monkeypatch.setattr(server.RUNNER, "start", _no_start)
        # config gate: point CONFIG_PATH at a tmp file
        monkeypatch.setattr(server.paths, "CONFIG_PATH", tmp_path / "ps4_config.json")
        (tmp_path / "ps4_config.json").write_text("{}")
        r = client.post("/api/jobs/deploy",
                        json={"map_id": "", "song_dir": str(d), "target": "BadGuy"})
        assert r.status_code == 200, r.text
        assert _no_start.called is True
        assert "--song-dir" in r.json()["command"]
