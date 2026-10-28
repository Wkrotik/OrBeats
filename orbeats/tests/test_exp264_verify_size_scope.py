"""Exp 264 — the post-deploy size check must only hard-fail for files THIS
SESSION uploaded (the batch-deploy false positive).

The user's exact scenario (Oct 7): a 22-song batch deploy (Britney + Rolling
Stones packs) stopped at song 1/22 because --deploy-full's post-deploy
validation reported `Size mismatches: ['Oxytocin_v3.bundle (local 36,706,086
vs PS4 36,706,075)']` — Oxytocin was NOT in the batch; its local bundle was
a stale artifact built by a different pipeline version during release
validation, while the live PS4 copy was a newer rebuild. 11 bytes of
irrelevance failed the deploy.

Fix: a module-level session ledger (_SESSION_UPLOADED_BUNDLES) that
deploy_to_ps4 and _deploy_file_to_ps4 record into; verify's check 6
hard-fails ONLY for ledger entries (and for EVERYTHING when no uploads
happened this session — standalone --verify-ps4 stays the deep audit).
"""

import importlib.util
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parent.parent / "tools" / "full_custom_song_pipeline.py"


@pytest.fixture()
def f():
    spec = importlib.util.spec_from_file_location("fcsp_exp264", PIPELINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CFG = {
    "ps4": {"ip": "192.168.100.117", "ftp_port": 2121,
            "ftp_user": "anonymous", "ftp_password": ""},
    "title": {"id": "CUSA12878"},
    "paths": {"afr_base": "/data/GoldHEN/AFR",
              "afr_target_suffix": "_v3.bundle"},
    "mass_deploy": {"bundle_dir": "/tmp/exp264-mass", "slots": []},
    "pack_modes": {"packs": []},
}


class TestSessionLedger:
    """deploy_to_ps4 / _deploy_file_to_ps4 record their uploads."""

    def test_song_upload_recorded(self, f, monkeypatch, tmp_path):
        f._SESSION_UPLOADED_BUNDLES.clear()
        bundle = tmp_path / "Oxytocin_custom.bundle"
        bundle.write_bytes(b"x" * 100)
        # GoldHEN `ls` single-file format the parser expects: 9 fields,
        # basename last (parts[-1] == remote basename), size at parts[4]
        listing = "-rwxrwxrwx 1 0 0 100 Oct 7 2026 Oxytocin_v3.bundle"
        monkeypatch.setattr("subprocess.run",
                            lambda *a, **k: type("R", (), {"returncode": 0, "stderr": "", "stdout": listing})())
        # _ftp_run (the verify-listing helper inside deploy_to_ps4):
        monkeypatch.setattr(f, "_ftp_run", lambda *a, **k: (0, listing, ""))
        f.deploy_to_ps4(str(bundle), "Oxytocin", CFG)
        assert "Oxytocin_v3.bundle" in f._SESSION_UPLOADED_BUNDLES

    def test_song_upload_failed_not_recorded(self, f, monkeypatch, tmp_path):
        f._SESSION_UPLOADED_BUNDLES.clear()
        bundle = tmp_path / "Angry_custom.bundle"
        bundle.write_bytes(b"x" * 10)
        # upload "succeeds" (rc 0) but listing shows nothing (the Exp 224
        # silent-failure signature) — must NOT be recorded.
        monkeypatch.setattr("subprocess.run",
                            lambda *a, **k: type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})())
        monkeypatch.setattr(f, "_ftp_run", lambda *a, **k: (0, "", ""))
        f.deploy_to_ps4(str(bundle), "Angry", CFG)
        assert "Angry_v3.bundle" not in f._SESSION_UPLOADED_BUNDLES

    def test_pack_file_upload_recorded(self, f, monkeypatch, tmp_path):
        f._SESSION_UPLOADED_BUNDLES.clear()
        local = tmp_path / "catalog_pack_modes.json"
        local.write_bytes(b"{}")
        monkeypatch.setattr("subprocess.run",
                            lambda *a, **k: type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})())
        assert f._deploy_file_to_ps4(CFG, str(local), "catalog_pack_modes.json") is True
        assert "catalog_pack_modes.json" in f._SESSION_UPLOADED_BUNDLES


class TestVerifySizeScope:
    """verify's check 6: hard-fail only what this session uploaded."""

    LIVE_REDIRECTS = {
        "titleId": "CUSA12878",
        "afrBase": "/data/GoldHEN/AFR",
        "redirects": {
            "BeatmapLevelsData/Oxytocin": "Oxytocin_v3.bundle",        # out of scope, stale local
            "BeatmapLevelsData/BabyOneMoreTime": "BabyOneMoreTime_v3.bundle",  # uploaded this session
        },
    }

    def _run_verify(self, f, monkeypatch, tmp_path, local_sizes, remote_sizes, ledger):
        """Drive verify_ps4_deployment with the network stubbed; return (ok, log lines)."""
        import logging
        records = []

        class Rec(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        h = Rec()
        f.log.addHandler(h)
        f.log.setLevel(logging.INFO)

        # local redirects.json = the live-matching state
        rpath = tmp_path / "redirects.json"
        import json
        rpath.write_text(json.dumps(self.LIVE_REDIRECTS))

        # local artifacts with the given sizes (name -> size); absent = no file
        custom_dir = tmp_path / "custom_songs"
        custom_dir.mkdir()
        for name, size in local_sizes.items():
            (custom_dir / name).write_bytes(b"x" * size)

        cfg = dict(CFG)
        cfg["paths"] = dict(CFG["paths"], output_dir=str(custom_dir))
        cfg["mass_deploy"] = dict(CFG["mass_deploy"], bundle_dir=str(tmp_path / "mass"))

        monkeypatch.setattr(f, "_get_redirect_config_path", lambda: str(rpath))
        monkeypatch.setattr(f, "_load_local_redirects",
                            lambda p: json.load(open(p)))
        # remote listing (name -> size)
        monkeypatch.setattr(f, "_list_remote_dir", lambda c: dict(remote_sizes))
        # PS4 redirects read == local (check 2 passes): the real flow
        # DOWNLOADS to a temp file via `lftp get -o <tmp>` then opens it —
        # the fake must write the payload to whatever -o target the command
        # names (not just print to stdout).
        def fake_run(cmd, *a, **k):
            # lftp -e script carries `get <remote> -o "<localtmp>"; quit` —
            # _ftp_quote wraps the target in double quotes. Mirror the real
            # transport: copy the local state file to the -o target.
            import re as _re
            joined = " ".join(cmd)
            m = _re.search(r'-o\s+"([^"]+)"', joined)
            if m and "redirects.json" in joined:
                import shutil as _sh
                _sh.copyfile(str(rpath), m.group(1))
            return type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})()
        monkeypatch.setattr("subprocess.run", fake_run)
        # check 7's catalog content: none configured
        monkeypatch.setattr(f, "_get_pack_modes_entries", lambda c, packs=None: [])
        monkeypatch.setattr(f, "_get_remote_pack_paths", lambda c, packs=None: [])
        monkeypatch.setattr(f, "_resolve_deployed_packs", lambda c: [])
        f._SESSION_UPLOADED_BUNDLES.clear()
        f._SESSION_UPLOADED_BUNDLES.update(ledger)
        try:
            ok = f.verify_ps4_deployment(cfg)
        finally:
            f.log.removeHandler(h)
        return ok, records

    def test_users_exact_scenario_passes(self, f, monkeypatch, tmp_path):
        """The Oct-7 batch scenario: Oxytocin stale-local mismatch (out of
        scope, NOT uploaded this session) + BabyOneMoreTime uploaded+intact
        → verify must PASS with an informational note, not fail."""
        ok, lines = self._run_verify(
            f, monkeypatch, tmp_path,
            local_sizes={"Oxytocin_custom.bundle": 36_706_086,
                         "BabyOneMoreTime_custom.bundle": 100},
            remote_sizes={"Oxytocin_v3.bundle": 36_706_075,
                          "BabyOneMoreTime_v3.bundle": 100},
            ledger={"BabyOneMoreTime_v3.bundle"})
        assert ok is True, [ln for ln in lines if "Size" in ln or "❌" in ln]
        assert any("informational" in ln for ln in lines), lines
        assert not any("❌ Size mismatches" in ln for ln in lines)

    def test_session_upload_corrupted_still_fails(self, f, monkeypatch, tmp_path):
        """The check's real purpose stays hard: a file THIS session uploaded
        whose remote size doesn't match the local build → deploy FAILS."""
        ok, lines = self._run_verify(
            f, monkeypatch, tmp_path,
            local_sizes={"BabyOneMoreTime_custom.bundle": 100},
            remote_sizes={"Oxytocin_v3.bundle": 36_706_075,
                          "BabyOneMoreTime_v3.bundle": 999},   # truncated upload!
            ledger={"BabyOneMoreTime_v3.bundle"})
        assert ok is False
        assert any("❌ Size mismatches" in ln and "BabyOneMoreTime" in ln for ln in lines)

    def test_standalone_verify_checks_everything(self, f, monkeypatch, tmp_path):
        """No uploads this session (standalone --verify-ps4): the stale-local
        Oxytocin mismatch IS a reportable failure — deep-audit mode keeps
        full-fleet checking."""
        ok, lines = self._run_verify(
            f, monkeypatch, tmp_path,
            local_sizes={"Oxytocin_custom.bundle": 36_706_086},
            remote_sizes={"Oxytocin_v3.bundle": 36_706_075,
                          "BabyOneMoreTime_v3.bundle": 100},
            ledger=set())
        assert ok is False
        assert any("❌ Size mismatches" in ln and "Oxytocin" in ln for ln in lines)
