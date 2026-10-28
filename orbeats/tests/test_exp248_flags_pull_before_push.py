"""
test_exp248_flags_pull_before_push.py — regression tests for the stale-flags push (Exp 248).

THE BUG (2026-10-02, live PS4): the user's console booted with "2/3 features"
and custom-song metadata vanished in-game. Cause: `apply_feature_flags`
(`--features-only --set-feature ...`) based its write on the LOCAL
features.json — which was stale (`enable_song_metadata_modification=false`
from the release-validation flag round-trips) — and pushed it wholesale over
the live PS4 state (which had the flag ON). Pull-before-push violated for
the flags path, exactly the Exp 246 redirects class.

THE FIX: apply_feature_flags now
1. parses the requested diffs first (bad syntax aborts before any I/O),
2. PULLS the live PS4 features.json (abort if the read FAILS; clean-slate
   when the file is absent),
3. materializes DEFAULT_FEATURES for keys the live file predates (Exp 221),
4. applies ONLY the requested diffs on top,
5. resyncs the local file from the result before deploying.

A webapp endpoint test amplified the bug by starting a REAL pipeline job —
also fixed: the suite now mocks the runner (test_webapp_tools::no_real_jobs)
and tests/conftest.py blocks lftp uploads suite-wide.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import full_custom_song_pipeline as pipeline  # noqa: E402
import pytest

CONFIG = {"ps4": {"ip": "10.0.0.1", "ftp_port": 2121,
                  "ftp_user": "anonymous", "ftp_password": ""},
          "title": {"id": "CUSA12878"},
          "paths": {"afr_base": "/data/GoldHEN/AFR"}}

LIVE_FLAGS = {"enable_plugin": True,
              "enable_custom_song_replacements": True,
              "enable_song_metadata_modification": True,   # the flag the bug turned off
              "enable_beatmap_mode_mapping": True}

STALE_LOCAL = {"enable_plugin": True,
               "enable_custom_song_replacements": True,
               "enable_song_metadata_modification": False,  # stale!
               "enable_beatmap_mode_mapping": True}


@pytest.fixture
def local_features_file(tmp_path, monkeypatch):
    path = tmp_path / "features.json"
    monkeypatch.setattr(pipeline, "_get_local_features_path",
                        lambda: str(path))
    return path


class TestPullBeforePush:
    def test_live_state_is_base_not_stale_local(self, local_features_file, monkeypatch):
        """THE Exp 248 scenario: local stale (metadata=false), PS4 live has
        it ON; a DIFFERENT flag is requested. The metadata flag must stay ON —
        the stale local value must never ride along."""
        local_features_file.write_text(json.dumps(STALE_LOCAL))
        monkeypatch.setattr(pipeline, "_download_features_from_ps4",
                            lambda config: json.loads(json.dumps(LIVE_FLAGS)))
        pushed = {}
        monkeypatch.setattr(pipeline, "_deploy_features_to_ps4",
                            lambda config: pushed.update(
                                json.loads(local_features_file.read_text())))
        pipeline.apply_feature_flags(["enable_beatmap_mode_mapping=false"], CONFIG)
        assert pushed["enable_song_metadata_modification"] is True   # preserved!
        assert pushed["enable_beatmap_mode_mapping"] is False         # the diff applied
        assert pushed["enable_plugin"] is True

    def test_requested_diff_applies_on_live(self, local_features_file, monkeypatch):
        monkeypatch.setattr(pipeline, "_download_features_from_ps4",
                            lambda config: dict(LIVE_FLAGS))
        pushed = {}
        monkeypatch.setattr(pipeline, "_deploy_features_to_ps4",
                            lambda config: pushed.update(
                                json.loads(local_features_file.read_text())))
        pipeline.apply_feature_flags(["enable_song_metadata_modification=false"], CONFIG)
        assert pushed["enable_song_metadata_modification"] is False

    def test_read_failure_aborts_never_blind(self, local_features_file, monkeypatch):
        """PS4 reachable-but-read-fails → SystemExit. Never push the local file."""
        local_features_file.write_text(json.dumps(STALE_LOCAL))

        def fail_read(config):
            raise RuntimeError("lftp rc=1 (connection reset)")

        monkeypatch.setattr(pipeline, "_download_features_from_ps4", fail_read)
        pushed = {}
        monkeypatch.setattr(pipeline, "_deploy_features_to_ps4",
                            lambda config: pushed.update({"called": True}))
        with pytest.raises(SystemExit):
            pipeline.apply_feature_flags(["enable_plugin=false"], CONFIG)
        assert pushed == {}, "no deploy may happen after a failed live read"

    def test_missing_remote_file_starts_from_defaults(self, local_features_file, monkeypatch):
        """Clean slate (no features.json on the PS4): defaults are the base."""
        monkeypatch.setattr(pipeline, "_download_features_from_ps4",
                            lambda config: None)
        pushed = {}
        monkeypatch.setattr(pipeline, "_deploy_features_to_ps4",
                            lambda config: pushed.update(
                                json.loads(local_features_file.read_text())))
        pipeline.apply_feature_flags(["enable_plugin=false"], CONFIG)
        # the diff applied, and every default materialized (DEFAULT_FEATURES
        # has all four flags ON — a clean slate deploys ON by design)
        assert pushed["enable_plugin"] is False
        assert pushed["enable_custom_song_replacements"] is True
        assert pushed["enable_song_metadata_modification"] is True
        assert pushed["enable_beatmap_mode_mapping"] is True

    def test_exp221_merge_still_materializes(self, local_features_file, monkeypatch):
        """A live file from BEFORE a flag existed gets the default materialized
        (Exp 221 rule preserved by the rewrite)."""
        old_live = {"enable_plugin": True,
                    "enable_custom_song_replacements": True,
                    "enable_song_metadata_modification": True}
        monkeypatch.setattr(pipeline, "_download_features_from_ps4",
                            lambda config: dict(old_live))
        pushed = {}
        monkeypatch.setattr(pipeline, "_deploy_features_to_ps4",
                            lambda config: pushed.update(
                                json.loads(local_features_file.read_text())))
        pipeline.apply_feature_flags(["enable_song_metadata_modification=false"], CONFIG)
        assert pushed["enable_beatmap_mode_mapping"] is True  # materialized default

    def test_bad_syntax_aborts_before_io(self, local_features_file, monkeypatch):
        """Malformed --set-feature aborts BEFORE any PS4 I/O."""
        calls = {"pull": 0, "push": 0}
        monkeypatch.setattr(pipeline, "_download_features_from_ps4",
                            lambda config: calls.__setitem__("pull", calls["pull"] + 1))
        monkeypatch.setattr(pipeline, "_deploy_features_to_ps4",
                            lambda config: calls.__setitem__("push", calls["push"] + 1))
        pipeline.apply_feature_flags(["enable_plugin=maybe"], CONFIG)
        assert calls == {"pull": 0, "push": 0}


class TestDownloadFeaturesTransport:
    """The new pull helper: banner-proof + abort-on-failure semantics."""

    def test_banner_survives_parse(self, tmp_path, monkeypatch):
        """Bannered content in the -o target parses (pitfall 1). We emulate
        lftp by intercepting the subprocess call at the module level — the
        helper imports subprocess inside the function, which resolves to the
        same module object, so patching subprocess.run works."""
        import subprocess

        raw = "156 bytes transferred\n" + json.dumps(
            {"enable_plugin": True}) + "}more banner"

        def fake_run(cmd, *a, **kw):
            # The helper passes lftp a single -e script:
            #   get "<remote>" -o "<local>"; quit
            # Both paths are _ftp_quote'd. Extract the -o target from it.
            if isinstance(cmd, list):
                script = next((t for t in cmd if isinstance(t, str) and "-o " in t), "")
                if " -o " in script:
                    target = script.split(" -o ", 1)[1].split(";")[0].strip().strip('"')
                    Path(target).write_text(raw)

            class R:
                returncode = 0
            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = pipeline._download_features_from_ps4(CONFIG)
        assert result["enable_plugin"] is True

    def test_absent_file_returns_none(self, monkeypatch):
        import subprocess as sp

        class R:
            returncode = 0
        monkeypatch.setattr(sp, "run", lambda *a, **k: R())
        assert pipeline._download_features_from_ps4(CONFIG) is None

    def test_read_failure_raises(self, monkeypatch):
        import subprocess as sp

        class R:
            returncode = 1
        monkeypatch.setattr(sp, "run", lambda *a, **k: R())
        with pytest.raises(RuntimeError, match="could not read"):
            pipeline._download_features_from_ps4(CONFIG)
