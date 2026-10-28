"""Local-only rollback retention and exact owned-path migration; fake FTP only."""

import copy
import json
from pathlib import Path

import additive_companion as core
import console_transaction as recovery
import pytest
from goldhen_config import merge_ini
from test_companion_management import (
    BASE,
    CONFIG,
    INI,
    PLUGIN,
    Console,
    artifact,
    banner_blob,
    manager,
    seed,
)

LEGACY = "/data/GoldHEN/plugins/beat_saber_deluxe.prx"


def assert_clean(ftp):
    assert not any(".backup-" in p or ".rollback-" in p or ".stage-" in p for p in ftp.files)


def test_success_archives_before_replacing_and_cleans_temporary_state():
    ftp = Console({INI: b"old"})
    tx = recovery.Transaction(core, ftp, "success")
    tx.publish(INI, b"new", b"old")
    assert (tx.directory / "0-before.bin").read_bytes() == b"old"
    assert (tx.directory / "0-rollback.bin").read_bytes() == b"old"
    tx.finish()
    assert ftp.files == {INI: b"new"}
    assert json.loads((tx.directory / "journal.json").read_text())["complete"]
    assert_clean(ftp)


def test_local_archive_failure_never_replaces_active_file(monkeypatch):
    ftp = Console({INI: b"old"})

    def denied(*args):
        raise OSError("local disk unavailable")

    monkeypatch.setattr(recovery, "archive", denied)
    tx = recovery.Transaction(core, ftp, "disk-fail")
    with pytest.raises(OSError, match="local disk unavailable"):
        tx.publish(INI, b"new", b"old")
    assert ftp.files == {INI: b"old"} and not ftp.writes and not ftp.deletes


def test_failure_after_rename_restores_original_and_cleans_stage():
    ftp = Console({INI: b"old"})
    ftp.fail_target = INI
    tx = recovery.Transaction(core, ftp, "rename-fail")
    with pytest.raises(OSError, match="publication failure"):
        tx.publish(INI, b"new", b"old")
    tx.rollback()
    assert ftp.files == {INI: b"old"}
    assert_clean(ftp)


def test_cleanup_never_deletes_changed_recovery_data():
    ftp = Console({INI: b"old"})
    tx = recovery.Transaction(core, ftp, "changed-recovery")
    tx.publish(INI, b"new", b"old")
    held = INI + ".rollback-changed-recovery"
    ftp.files[held] = b"concurrent bytes"
    with pytest.raises(RuntimeError, match="Concurrent recovery data retained"):
        tx.finish()
    assert ftp.files[held] == b"concurrent bytes" and ftp.files[INI] == b"new"
    assert (tx.directory / "0-rollback.bin").read_bytes() == b"old"


def test_closed_title_is_rechecked_before_cleanup():
    ftp = Console({INI: b"old"})
    tx = recovery.Transaction(core, ftp, "live-title")
    tx.publish(INI, b"new", b"old")
    ftp.active = True
    with pytest.raises(ValueError, match="Fully close"):
        tx.finish()
    assert ftp.files[INI + ".rollback-live-title"] == b"old" and not ftp.deletes


@pytest.mark.parametrize("fail", [False, True])
def test_legacy_plugin_migration_and_rollback_preserve_raw_fself(monkeypatch, fail):
    ftp, songs = seed(monkeypatch)
    previous = artifact().read_bytes()
    ftp.files[LEGACY] = previous
    ftp.files[INI] = b"; keep\r\n[CUSA12878]\r\n  " + LEGACY.encode() + b" \r\n[OTHER]\r\n/other.prx\r\n"
    original = copy.deepcopy(ftp.files)
    if fail:
        # Fail the retirement AFTER candidate/INI/capability publication.
        rename = ftp.rename

        def broken(a, b):
            if a == LEGACY:
                raise OSError("retirement refused")
            return rename(a, b)

        monkeypatch.setattr(ftp, "rename", broken)
        with pytest.raises(OSError, match="retirement refused"):
            manager.deploy_plugin(CONFIG, artifact())
        assert ftp.files == original
    else:
        assert manager.deploy_plugin(CONFIG, artifact())["ok"]
        assert LEGACY not in ftp.files
        assert ftp.files[INI] == original[INI].replace(LEGACY.encode(), PLUGIN.encode())
        assert ftp.files[BASE + "/library.bin"] == original[BASE + "/library.bin"]
        archived = [p.read_bytes() for p in recovery.LOCAL_BACKUPS.rglob("*-rollback.bin")]
        assert previous in archived  # real FSELF retained, not just FTP's canonical view
    assert_clean(ftp)


def test_unknown_legacy_file_is_not_retired(monkeypatch):
    ftp, _ = seed(monkeypatch)
    ftp.files[LEGACY] = b"not our plugin"
    before = copy.deepcopy(ftp.files)
    with pytest.raises(ValueError, match="Unrecognized legacy plugin"):
        manager.deploy_plugin(CONFIG, artifact())
    assert ftp.files == before and not ftp.writes and not ftp.deletes


@pytest.mark.parametrize(
    "raw",
    [
        b"[CUSA12878]\n" + LEGACY.encode() + b"\n" + PLUGIN.encode() + b"\n",
        b"[default]\n" + LEGACY.encode() + b"\n",
        b"[OTHER]\n" + LEGACY.encode() + b"\n",
    ],
)
def test_ambiguous_registration_never_silently_migrates(raw):
    with pytest.raises(ValueError):
        merge_ini(raw)


def test_legacy_banner_is_readable_but_not_new_output_brand():
    assert manager.binary_version(banner_blob().replace(b"OrBeats", b"BS Deluxe")) == "0.8071"
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text()
    assert "TARGET := orbeats.prx" in makefile and "TARGET := orbeats_debug.prx" in makefile
    assert "TARGET := beat_saber_deluxe" not in makefile


def cleanup_module():
    import importlib.util

    file = Path(__file__).resolve().parents[1] / "development/scripts/cleanup_orbeats_backups.py"
    spec = importlib.util.spec_from_file_location("backup_cleanup", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cleanup_archives_only_identified_owned_backups(tmp_path):
    cleanup = cleanup_module()
    a = LEGACY + ".backup-" + "a" * 32
    b = LEGACY + ".exp311-backup"
    untouched = {
        LEGACY: banner_blob(),
        "/data/GoldHEN/plugins/other.prx.bak.123": b"other",
        LEGACY + ".rollback-interrupted": b"unknown",
        LEGACY + ".backup-not-a-uuid": b"unknown",
    }
    values = dict(untouched)
    values.update({a: artifact().read_bytes(), b: artifact().read_bytes()})
    ftp = Console(values)
    rows = cleanup.plan(ftp, tmp_path)
    assert {r["path"] for r in rows} == {a, b} and not ftp.deletes
    assert all(Path(r["archive"]).read_bytes() == values[r["path"]] for r in rows)
    assert set(cleanup.apply(ftp, rows, tmp_path)) == {a, b}
    assert ftp.files == untouched


@pytest.mark.parametrize("case", ["local", "remote", "title", "scope"])
def test_cleanup_rechecks_archives_remote_bytes_scope_and_closed_title(tmp_path, case):
    cleanup = cleanup_module()
    path = LEGACY + ".backup-" + "c" * 32
    ftp = Console({path: artifact().read_bytes()})
    rows = cleanup.plan(ftp, tmp_path)
    if case == "local":
        Path(rows[0]["archive"]).write_bytes(b"changed")
    if case == "remote":
        ftp.files[path] = b"changed"
    if case == "title":
        ftp.active = True
    if case == "scope":
        rows[0]["path"] = "/data/GoldHEN/plugins/other.prx"
    with pytest.raises(ValueError):
        cleanup.apply(ftp, rows, tmp_path)
    assert not ftp.deletes and path in ftp.files


def test_cleanup_unknown_backup_binary_fails_before_deletion(tmp_path):
    cleanup = cleanup_module()
    path = LEGACY + ".backup-" + "d" * 32
    ftp = Console({path: b"not an ELF"})
    with pytest.raises(ValueError):
        cleanup.plan(ftp, tmp_path)
    assert not ftp.deletes and not ftp.writes
