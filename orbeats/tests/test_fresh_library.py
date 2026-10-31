"""Fresh/source-only library and address regressions; no network or game inputs."""

import copy
import hashlib
import sys
from ftplib import error_perm
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "webapp")]
import additive_companion as core
import additive_legacy
import additive_library as wire
import companion_api
import library_manager as manager
from fastapi import HTTPException

CONFIG = {"ps4": {"ip": "192.0.2.2"}}


class FTP:
    def __init__(self, files=None, dirs=("/", "/data")):
        self.files = dict(files or {})
        self.dirs = set(dirs)
        for path in self.files:
            parent = path.rsplit("/", 1)[0]
            while parent:
                self.dirs.add(parent)
                parent = parent.rsplit("/", 1)[0]
        self.denied = set()
        self.list_denied = set()
        self.connections = []
        self.logins = []
        self.closed = False

    def connect(self, ip, port, timeout):
        self.connections.append((ip, port, timeout))

    def login(self, user, password):
        self.logins.append((user, password))

    def close(self):
        self.closed = True

    def nlst(self, path):
        if path not in self.dirs or path in self.list_denied:
            raise error_perm("550 denied or absent")
        prefix = path.rstrip("/") + "/"
        return sorted(
            {
                prefix + p[len(prefix) :].split("/")[0]
                for p in self.files.keys() | self.dirs
                if p.startswith(prefix) and p != path
            }
        )

    def retrbinary(self, cmd, callback):
        path = cmd.removeprefix("RETR ")
        if path not in self.files or path in self.denied:
            raise error_perm("550 denied or absent")
        callback(self.files[path])


def synthetic():
    song = additive_legacy.migration_songs()[0]
    blobs = [b"synthetic bundle", b"synthetic cover", b"synthetic preview" * 4]
    song.update(bytes=len(blobs[0]), fnv=wire.fnv(blobs[0]), sha256=hashlib.sha256(blobs[0]).hexdigest())
    for key, blob in zip(("cover", "preview"), blobs[1:]):
        song[key] = {"bytes": len(blob), "fnv": wire.fnv(blob)}
    return song, dict(zip(wire.paths(song), blobs))


@pytest.mark.parametrize("dirs", [("/", "/data"), ("/", "/data", wire.BASE)])
def test_fresh_catalog_has_no_phantom_songs_or_fixture_dependency(monkeypatch, tmp_path, dirs):
    monkeypatch.setattr(core, "ROOT", tmp_path)
    ftp = FTP(dirs=dirs)
    monkeypatch.setattr(manager, "FTP", lambda: ftp)
    assert manager.catalog(CONFIG) == []
    assert ftp.closed and ftp.files == {}
    assert not (tmp_path / "development/fixtures").exists()


def test_legacy_metadata_is_canonical_and_fresh_objects():
    songs = additive_legacy.migration_songs()
    assert wire.encode(wire.decode(wire.encode(songs))) == wire.encode(songs)
    songs[0]["stats"][0][0] = 1
    assert additive_legacy.migration_songs()[0]["stats"][0][0] == 312
    profile = (ROOT / "include/additive_library_profile.h").read_text()
    for song in songs:
        assert song["id"] in profile and song["sha256"] in profile


def test_existing_manifest_does_not_use_migration_defaults(monkeypatch):
    song, files = synthetic()
    raw = wire.encode([song])
    files[wire.BASE + "/library.bin"] = raw
    monkeypatch.setattr(additive_legacy, "migration_songs", lambda: pytest.fail("Unexpected migration"))
    assert core.load_library(FTP(files)) == (wire.decode(raw), raw)


@pytest.mark.parametrize("suffix", ["backup-previous", "rollback-previous"])
def test_retained_manifest_backup_never_becomes_fresh(suffix):
    ftp = FTP({wire.BASE + "/library.bin." + suffix: b"retained evidence"})
    before = copy.deepcopy(ftp.files)
    with pytest.raises(ValueError, match="retained backup"):
        core.load_library(ftp)
    assert ftp.files == before


@pytest.mark.parametrize(
    "name", ["bsd_additive_" + "a" * 24 + ".bundle", "bsd_additive_" + "b" * 24 + "-media/song-cover.png"]
)
def test_missing_manifest_with_other_owned_songs_requires_recovery(name):
    with pytest.raises(ValueError, match="unrecognized song files"):
        core.load_library(FTP({wire.BASE + "/" + name: b"do not orphan"}))


def test_visible_but_unreadable_manifest_is_not_missing():
    path = wire.BASE + "/library.bin"
    ftp = FTP({path: b"unreadable"})
    ftp.denied.add(path)
    with pytest.raises(ValueError, match="Cannot read existing"):
        core.load_library(ftp)


def test_visible_but_unlistable_directory_is_not_missing():
    ftp = FTP(dirs=("/", "/data", "/data/GoldHEN"))
    ftp.list_denied.add("/data/GoldHEN")
    with pytest.raises(ValueError, match="Cannot inspect existing"):
        core.load_library(ftp)


def test_root_listing_error_does_not_mean_fresh():
    ftp = FTP(dirs=())
    with pytest.raises(error_perm, match="550"):
        core.load_library(ftp)


def test_non_missing_ftp_error_propagates():
    class Broken(FTP):
        def nlst(self, path):
            raise error_perm("530 not logged in")

    with pytest.raises(error_perm, match="530"):
        core.load_library(Broken())


@pytest.mark.parametrize("partial", [True, False])
def test_legacy_migration_is_retained_and_checks_every_file(monkeypatch, partial):
    song, files = synthetic()
    monkeypatch.setattr(additive_legacy, "migration_songs", lambda: [copy.deepcopy(song)])
    if partial:
        files.pop(wire.paths(song)[2])
    ftp = FTP(files)
    monkeypatch.setattr(manager, "FTP", lambda: ftp)
    if partial:
        with pytest.raises(ValueError, match="Incomplete legacy"):
            manager.catalog(CONFIG)
    else:
        assert manager.catalog(CONFIG) == wire.decode(wire.encode([song]))
    assert ftp.files == files and ftp.closed


def test_corrupt_legacy_file_refuses_migration(monkeypatch):
    song, files = synthetic()
    files[wire.paths(song)[0]] = b"corrupt"
    monkeypatch.setattr(additive_legacy, "migration_songs", lambda: [song])
    monkeypatch.setattr(manager, "FTP", lambda: FTP(files))
    with pytest.raises(ValueError, match="verification"):
        manager.catalog(CONFIG)


@pytest.mark.parametrize("value", ["192.0.2.2:2121", "ftp://192.0.2.2", "", None, 123])
def test_invalid_address_never_connects_or_loads_old_settings(monkeypatch, value):
    monkeypatch.setattr(companion_api, "settings", lambda: pytest.fail("Old settings used"))
    monkeypatch.setattr(manager, "test_connection", lambda cfg: pytest.fail("Invalid connection attempted"))
    with pytest.raises(HTTPException) as error:
        companion_api.test_connection({"ip": value})
    assert error.value.status_code == 400 and "without :2121" in error.value.detail


def test_test_connection_uses_typed_address_without_library_or_save(monkeypatch):
    ftp = FTP()
    monkeypatch.setattr(manager, "FTP", lambda: ftp)
    monkeypatch.setattr(companion_api, "settings", lambda: pytest.fail("Saved address used"))
    monkeypatch.setattr(core, "load_library", lambda f: pytest.fail("Library read during FTP test"))
    monkeypatch.setattr(companion_api.config, "save_config", lambda cfg: pytest.fail("Test saved settings"))
    assert companion_api.test_connection({"ip": " 192.0.2.9 "}) == {"ok": True, "ip": "192.0.2.9", "port": 2121}
    assert ftp.connections == [("192.0.2.9", 2121, 15)] and ftp.logins == [("anonymous", "")]
    assert ftp.closed and ftp.files == {}


def test_failed_connection_closes_and_reports_failure(monkeypatch):
    ftp = FTP()

    def refused(*args, **kwargs):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(ftp, "connect", refused)
    monkeypatch.setattr(manager, "FTP", lambda: ftp)
    with pytest.raises(HTTPException) as error:
        companion_api.test_connection({"ip": "192.0.2.2"})
    assert error.value.status_code == 400 and ftp.closed
