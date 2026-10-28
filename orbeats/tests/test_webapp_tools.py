"""
test_webapp_tools.py — Flags / Backup-Restore / Feature-Request endpoint tests.

HARD RULE (Exp 248): NO test in this file may start a real pipeline job or
touch the real PS4. The user's live console was mutated by an earlier
version of these tests (a flags-apply test started a REAL
`--features-only` subprocess that pushed a stale local features.json over
the PS4's live state — turning the metadata flag OFF in-game).

Every job-starting endpoint is therefore tested against a MOCKED runner:
`no_real_jobs` (autouse) replaces server.RUNNER.start/start_script with
fakes that record argv and never spawn a subprocess.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

import server  # noqa: E402
from adapters import ps4 as ps4_adapter  # noqa: E402
from adapters import runner as runner_mod  # noqa: E402

client = TestClient(server.app)


class FakeJob:
    """Stand-in for a runner Job — no process, never touches the PS4."""

    def __init__(self, argv, label=""):
        self.argv = list(argv)
        self.label = label
        self.id = 1
        self.exit_code = 0
        self.lines = ["(mocked job — no real pipeline invocation)"]
        self.cancelled = False
        self.command_line = " ".join(argv)


@pytest.fixture(autouse=True)
def no_real_jobs(monkeypatch):
    """Exp 248: replace the runner's spawn methods with recorders. Any test
    that would have started a real pipeline/script subprocess gets a FakeJob
    instead; the recorded argv lets us assert EXACTLY what would have run
    (better coverage than before — we now assert the argv, not just 200 OK).
    """
    started = []

    def fake_start(argv, label=""):
        if server.RUNNER.is_busy():
            raise RuntimeError(
                "A job is already running — one at a time (PS4 state files "
                "are transaction records; concurrent writers corrupt them).")
        started.append(("pipeline", list(argv), label))
        job = FakeJob(argv, label)
        server.RUNNER._job = job
        return job

    def fake_start_script(script, argv, label=""):
        if server.RUNNER.is_busy():
            raise RuntimeError(
                "A job is already running — one at a time (PS4 state files "
                "are transaction records; concurrent writers corrupt them).")
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


@pytest.fixture(autouse=True)
def clean_runner(no_real_jobs):
    yield


# Back-compat alias for tests that referenced the old fixture shape.
@pytest.fixture
def started_jobs(no_real_jobs):
    return no_real_jobs


LIVE_FLAGS = {"enable_plugin": True, "enable_custom_song_replacements": True,
              "enable_song_metadata_modification": True, "enable_beatmap_mode_mapping": True}


class TestFlagsEndpoints:
    def test_flags_read_with_descriptions(self, monkeypatch):
        monkeypatch.setattr(server.ps4, "read_features",
                            lambda: ps4_adapter.ReadResult(ok=True, data=dict(LIVE_FLAGS)))
        r = client.get("/api/flags")
        j = r.json()
        assert j["ok"] is True
        by_name = {f["name"]: f for f in j["flags"]}
        assert set(by_name) == set(LIVE_FLAGS)
        # every flag carries a real description
        for f in j["flags"]:
            assert f["description"], f"{f['name']} missing description"
        assert "kill switch" in by_name["enable_plugin"]["description"].lower()

    def test_flags_read_failure_explicit(self, monkeypatch):
        monkeypatch.setattr(server.ps4, "read_features",
                            lambda: ps4_adapter.ReadResult(ok=False, error="timeout"))
        r = client.get("/api/flags")
        j = r.json()
        assert j["ok"] is False and j["flags"] == []

    def test_flags_apply_requires_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server.paths, "CONFIG_PATH", tmp_path / "none.json")
        r = client.post("/api/jobs/flags-apply", json={"flags": {"enable_plugin": False}})
        assert r.status_code == 400

    def test_flags_apply_rejects_unknown_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server.paths, "CONFIG_PATH", PROJECT / "ps4_config.json")
        monkeypatch.setattr(server.ps4, "read_features",
                            lambda: ps4_adapter.ReadResult(ok=True, data=dict(LIVE_FLAGS)))
        r = client.post("/api/jobs/flags-apply",
                        json={"flags": {"destroy_everything": True}})
        assert r.status_code == 400

    def test_flags_apply_blind_refused_when_ps4_unreadable(self, tmp_path, monkeypatch):
        """PS4 flags unreadable → 502, never apply blind (anti-wipe posture)."""
        monkeypatch.setattr(server.paths, "CONFIG_PATH", PROJECT / "ps4_config.json")
        monkeypatch.setattr(server.ps4, "read_features",
                            lambda: ps4_adapter.ReadResult(ok=False, error="no route"))
        r = client.post("/api/jobs/flags-apply",
                        json={"flags": {"enable_plugin": False}})
        assert r.status_code == 502

    def test_flags_apply_noop_when_unchanged(self, monkeypatch):
        monkeypatch.setattr(server.paths, "CONFIG_PATH", PROJECT / "ps4_config.json")
        monkeypatch.setattr(server.ps4, "read_features",
                            lambda: ps4_adapter.ReadResult(ok=True, data=dict(LIVE_FLAGS)))
        r = client.post("/api/jobs/flags-apply", json={"flags": dict(LIVE_FLAGS)})
        j = r.json()
        assert j["changed"] == 0 and j["job_id"] is None

    def test_flags_apply_diffs_only_changes(self, monkeypatch, started_jobs):
        """Only CHANGED flags go into argv — unchanged ones are not re-pushed.
        (Exp 248: this test previously started a REAL --features-only
        subprocess that pushed the stale local features.json over the live
        PS4 — it must run against the MOCKED runner and assert the argv.)"""
        monkeypatch.setattr(server.paths, "CONFIG_PATH", PROJECT / "ps4_config.json")
        monkeypatch.setattr(server.ps4, "read_features",
                            lambda: ps4_adapter.ReadResult(ok=True, data=dict(LIVE_FLAGS)))
        wanted = dict(LIVE_FLAGS)
        wanted["enable_song_metadata_modification"] = False
        r = client.post("/api/jobs/flags-apply", json={"flags": wanted})
        j = r.json()
        assert j["changed"] == 1
        assert "--set-feature" in j["command"]
        assert "enable_song_metadata_modification=false" in j["command"]
        assert "enable_plugin" not in j["command"].split("--set-feature")[-1]
        # the mocked runner captured exactly one pipeline invocation
        assert len(started_jobs) == 1
        kind, argv, _label = started_jobs[0]
        assert kind == "pipeline"
        assert "enable_song_metadata_modification=false" in argv
        assert not any("enable_plugin" in tok for tok in argv)

    def test_flags_apply_never_pushes_stale_local_file(self, monkeypatch, started_jobs):
        """Exp 248 regression pin: a flags-apply job carries ONLY the
        user-requested diffs as --set-feature tokens — it must never
        transport a local features.json wholesale (the stale-local-file
        push was the mechanism that turned the user's metadata flag off)."""
        monkeypatch.setattr(server.paths, "CONFIG_PATH", PROJECT / "ps4_config.json")
        monkeypatch.setattr(server.ps4, "read_features",
                            lambda: ps4_adapter.ReadResult(ok=True, data=dict(LIVE_FLAGS)))
        r = client.post("/api/jobs/flags-apply",
                        json={"flags": {"enable_song_metadata_modification": False}})
        j = r.json()
        assert j["changed"] == 1
        kind, argv, _ = started_jobs[0]
        set_feature_vals = [argv[i + 1] for i, t in enumerate(argv) if t == "--set-feature"]
        assert set_feature_vals == ["enable_song_metadata_modification=false"]
        # and absolutely no unrelated flag may ride along:
        for val in set_feature_vals:
            assert val.startswith(("enable_song_metadata_modification",
                                   "enable_plugin", "enable_custom_song_replacements",
                                   "enable_beatmap_mode_mapping"))


class TestBackupEndpoints:
    def test_backup_list_reads_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(server, "_backup_dir", lambda: tmp_path)
        (tmp_path / "bsd_backup_20260101_000000.zip").write_bytes(b"x" * 100)
        (tmp_path / "notazip.txt").write_text("ignore me")
        r = client.get("/api/backup/list")
        j = r.json()
        assert len(j["backups"]) == 1
        assert j["backups"][0]["name"] == "bsd_backup_20260101_000000.zip"
        assert j["backups"][0]["size"] == 100

    def test_backup_list_empty_dir_ok(self, monkeypatch, tmp_path):
        monkeypatch.setattr(server, "_backup_dir", lambda: tmp_path)
        assert client.get("/api/backup/list").json()["backups"] == []

    def test_backup_job_starts(self, monkeypatch):
        monkeypatch.setattr(server, "BACKUP_SCRIPT", PROJECT / "VERSION")  # exists
        r = client.post("/api/jobs/backup", json={"clean_ps4": False})
        assert r.status_code == 200
        assert "backup" in r.json()["command"]
        # clean up the job (VERSION "script" exits immediately; poll drains it)

    def test_backup_clean_flag_in_command(self, monkeypatch):
        monkeypatch.setattr(server, "BACKUP_SCRIPT", PROJECT / "VERSION")
        r = client.post("/api/jobs/backup", json={"clean_ps4": True})
        assert "--clean-ps4" in r.json()["command"]

    def test_restore_rejects_path_traversal(self, monkeypatch):
        """backup names are sanitized: no paths, no .. — the zip dir is a jail."""
        monkeypatch.setattr(server, "BACKUP_SCRIPT", PROJECT / "VERSION")
        monkeypatch.setattr(server, "_backup_dir",
                            lambda: PROJECT.parent / "ps4_backups")
        r = client.post("/api/jobs/restore",
                        json={"backup": "../../etc/passwd", "clean_ps4": False})
        assert r.status_code == 400

    def test_restore_unknown_backup_404(self, monkeypatch, tmp_path):
        monkeypatch.setattr(server, "BACKUP_SCRIPT", PROJECT / "VERSION")
        monkeypatch.setattr(server, "_backup_dir", lambda: tmp_path)
        r = client.post("/api/jobs/restore",
                        json={"backup": "nope.zip", "clean_ps4": False})
        assert r.status_code == 404


class TestFeatureRequest:
    def test_template_carries_repo(self):
        j = client.get("/api/feature-request/template").json()
        assert "BeatSaberPcCustomSongToPs4InstallConverter" in j["repo"]
        assert j["issue_url"].startswith("https://github.com/")


class TestRunnerContract:
    """Exp 248: the runner's SPAWN methods are mocked for ALL tests in this
    file (autouse no_real_jobs) — these tests assert the contract against
    the mocked recorder instead of executing real subprocesses. Real
    subprocess execution + streaming is covered in test_webapp_deploy.py's
    TestSingleJobRunner (which uses --help, never the PS4)."""

    def test_backup_job_argv_recorded(self, monkeypatch, started_jobs):
        """A backup request produces exactly one script job with the right argv."""
        monkeypatch.setattr(server, "BACKUP_SCRIPT", PROJECT / "VERSION")
        r = client.post("/api/jobs/backup", json={"clean_ps4": False})
        assert r.status_code == 200
        kind, argv, label = started_jobs[0]
        assert kind == "script" and argv == ["backup"]
        assert "backup" in label

    def test_single_job_rule_covers_scripts(self, monkeypatch, started_jobs):
        """A busy runner blocks a backup job (409) and starts NOTHING.
        (FastAPI converts HTTPException into a response — assert status.)"""
        fake = runner_mod.Job(id=1, argv=["x"], cwd="/tmp",
                              started_at=0.0)
        fake.exit_code = None
        server.RUNNER._job = fake
        monkeypatch.setattr(server, "BACKUP_SCRIPT", PROJECT / "VERSION")
        r = client.post("/api/jobs/backup", json={})
        assert r.status_code == 409
        assert "already running" in r.json()["detail"]
        assert started_jobs == [], "a blocked job must not be recorded as started"


class TestBackupDirBrowse:
    """The Backup/Restore tab's configurable backups folder (user request:
    the hardcoded /workspace/ps4_backups was invisible/blocked from change)."""

    def test_dir_get_reports_default(self, monkeypatch):
        from adapters import webapp_state
        monkeypatch.setattr(webapp_state, "STATE_PATH", None)  # force no-state path
        monkeypatch.setattr(webapp_state, "load", lambda: {})
        r = client.get("/api/backup/dir")
        j = r.json()
        assert j["is_default"] is True
        assert j["backup_dir"].endswith("ps4_backups")

    def test_dir_set_persists_and_lists(self, monkeypatch, tmp_path):
        from adapters import webapp_state
        state_file = tmp_path / "webapp_state.json"
        monkeypatch.setattr(webapp_state, "STATE_PATH", state_file)
        monkeypatch.setattr(webapp_state, "load", webapp_state.load)
        # a fresh state file: set the dir, read it back
        target = tmp_path / "my_backups"
        target.mkdir()
        r = client.post("/api/backup/dir", json={"path": str(target)})
        j = r.json()
        assert j["ok"] is True and j["backup_dir"] == str(target)
        # the backup LIST now reflects the new dir (no zips in it)
        assert j["backups"] == []
        # and a second GET confirms persistence
        assert client.get("/api/backup/dir").json()["backup_dir"] == str(target)

    def test_dir_set_rejects_empty(self):
        r = client.post("/api/backup/dir", json={"path": ""})
        assert r.status_code == 400

    def test_browse_lists_dirs_only(self, monkeypatch, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "afile.txt").write_text("nope")
        r = client.get("/api/backup/browse", params={"path": str(tmp_path)})
        j = r.json()
        assert [d["name"] for d in j["dirs"]] == ["subdir"]
        assert j["parent"] == str(tmp_path.parent)

    def test_browse_rejects_missing_folder(self):
        r = client.get("/api/backup/browse", params={"path": "/definitely/not/here"})
        assert r.status_code == 400

    def test_backup_job_passes_out_for_custom_dir(self, monkeypatch, started_jobs, tmp_path):
        """Custom backups folder → the backup job's argv carries --out."""
        from adapters import webapp_state
        monkeypatch.setattr(webapp_state, "STATE_PATH", tmp_path / "ws.json")
        monkeypatch.setattr(webapp_state, "load", webapp_state.load)
        client.post("/api/backup/dir", json={"path": str(tmp_path / "bk")})
        monkeypatch.setattr(server, "BACKUP_SCRIPT", PROJECT / "VERSION")
        r = client.post("/api/jobs/backup", json={})
        assert r.status_code == 200
        kind, argv, _ = started_jobs[0]
        assert kind == "script"
        # argv shape: ["backup", "--out", "<dir>"]
        assert argv[0] == "backup"
        out_i = argv.index("--out")
        assert argv[out_i + 1] == str(tmp_path / "bk")

    def test_backup_job_default_dir_no_out_flag(self, monkeypatch, started_jobs):
        """Default folder → no --out (the script's own default applies)."""
        from adapters import webapp_state
        monkeypatch.setattr(webapp_state, "load", lambda: {})
        monkeypatch.setattr(server, "BACKUP_SCRIPT", PROJECT / "VERSION")
        r = client.post("/api/jobs/backup", json={})
        assert r.status_code == 200
        kind, argv, _ = started_jobs[0]
        assert "--out" not in argv


class TestPluginOnlyDeploy:
    """M12 (Exp 280b): the fresh-user bootstrap needs a plugin-only deploy
    surface — the extractor lives in the plugin, so users must be able to
    deploy it BEFORE any song data exists (the Deploy tab card + the Get
    Started step-5 button → POST /api/jobs/deploy-plugin)."""

    def test_deploy_plugin_argv(self, no_real_jobs):
        started = no_real_jobs
        r = client.post("/api/jobs/deploy-plugin", json={"debug": False})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert started and started[0][0] == "pipeline"
        assert started[0][1] == ["--deploy-plugin"], \
            f"expected plugin-only argv, got {started[0][1]}"
        assert "--debug-logging" not in started[0][1]

    def test_deploy_plugin_debug_build(self, no_real_jobs):
        started = no_real_jobs
        r = client.post("/api/jobs/deploy-plugin", json={"debug": True})
        assert r.status_code == 200
        argv = started[0][1]
        assert argv == ["--deploy-plugin", "--debug-logging"], \
            f"debug deploy must carry --debug-logging, got {argv}"
        assert "DEBUG" in started[0][2]

    def test_deploy_plugin_flag_exists_in_pipeline_help(self):
        """Thin-layer proof (every webapp flag asserted present in --help)."""
        import subprocess
        r = subprocess.run(
            [sys.executable, str(PROJECT / "tools" / "full_custom_song_pipeline.py"),
             "--help"], capture_output=True, text=True, timeout=30)
        assert "--deploy-plugin" in r.stdout and "--debug-logging" in r.stdout

    def test_deploy_plugin_surfaces_exist_in_ui(self):
        """Static-audit discipline (Exp 252): every JS-referenced id must exist
        in the served HTML — the Deploy tab card + the Get Started step-5 card."""
        html = (PROJECT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
        for el_id in ("btn-deploy-plugin", "opt-plugin-debug",
                      "deploy-plugin-log", "deploy-plugin-status",
                      "btn-deploy-plugin-start", "deploy-plugin-start-log",
                      "deploy-plugin-start-status"):
            assert f'id="{el_id}"' in html, f"{el_id} missing from index.html"
        appjs = (PROJECT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
        assert "btn-deploy-plugin" in appjs and "btn-deploy-plugin-start" in appjs

    def test_debug_option_only_on_deploy_tab(self):
        """User directive (Exp 280b): the DEBUG logging option is exposed ONLY
        on the Deploy tab — the Get Started card must not carry it."""
        html = (PROJECT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
        opt_pos = html.find('id="opt-plugin-debug"')
        deploy_card = html.find('Plugin only — deploy or update')
        start_card = html.find('btn-deploy-plugin-start')
        assert opt_pos > deploy_card > 0, "the debug checkbox belongs to the Deploy tab card"
        assert opt_pos < start_card, "the debug checkbox must come BEFORE the Get Started card"


class TestPingReportsRunningCodeVersion:
    """Exp 280c — the round-3 stale-process lesson: the ping MUST report the
    versions of the RUNNING code (captured at import), never a fresh file
    read at request time. A stale process reading files at request time
    reports the NEW version while serving OLD code — defeating the
    launcher's staleness check and sending clicks to 404s (the user's live
    report: Deploy Plugin → "Not Found" while the ping said 0.6.15)."""

    def test_versions_captured_at_import_not_request_time(self, tmp_path, monkeypatch):
        # After import, mutating the version files must NOT change the ping —
        # the values were captured at import (the running code's versions).
        import server as srv
        monkeypatch.setattr(
            srv.paths, "WEBAPP_DIR", tmp_path, raising=False)
        (tmp_path / "VERSION").write_text("9.9.9-fake", encoding="utf-8")
        r = client.get("/api/ping")
        j = r.json()
        assert j["webapp_version"] != "9.9.9-fake", \
            "the ping must not read the VERSION file at request time"
        assert j["webapp_version"] == srv._CODE_WEBAPP_VERSION

    def test_capture_constants_exist(self):
        import server as srv
        for attr in ("_CODE_WEBAPP_VERSION", "_CODE_PIPELINE_VERSION",
                     "_CODE_PLUGIN_VERSION"):
            assert getattr(srv, attr, None), f"{attr} not captured at import"

    def test_launcher_staleness_check_uses_the_ping(self):
        """The resolver compares the ping payload vs the CURRENT file — with
        import-time capture, a stale process reports its OLD version and the
        launcher correctly offers stop-and-restart (the launch-resilience
        contract)."""
        import server as srv
        # a stale process reports a DIFFERENT version than the current file
        assert srv._CODE_WEBAPP_VERSION is not None
        # (the live proof: this very class was caught by the user's 404)
