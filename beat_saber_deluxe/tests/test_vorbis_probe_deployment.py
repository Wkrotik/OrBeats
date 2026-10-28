"""Developer-only codec deployment preserves production transaction safeguards."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest
from test_additive_companion import StrictFTP, synthetic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "development/scripts"))
import deploy_vorbis_probe as deploy

core, lib = deploy.core, deploy.lib


def state(songs=None):
    plugin = b"test-active-ELF"
    cap = {"schema": 1, "title": "CUSA12878", "active_elf_sha256": hashlib.sha256(plugin).hexdigest(), "max_songs": 64}
    return {
        lib.BASE + "/companion-protocol.json": json.dumps(cap).encode(),
        "/data/GoldHEN/plugins/orbeats.prx": plugin,
        "/data/GoldHEN/AFR/CUSA12878/features.json": json.dumps(
            {"enable_plugin": True, "enable_additive_song_packs": True}
        ).encode(),
        lib.BASE + "/library.bin": lib.encode(songs or []),
    }


def payload():
    song, files = synthetic(934)
    song["title"] += " [Vorbis test]"
    return lib.decode(lib.encode([song]))[0], [files[p] for p in lib.paths(song)]


def test_empty_library_stage_readback_publish_last_and_repeat_is_read_only(tmp_path):
    ftp = StrictFTP(state())
    song, blobs = payload()
    old = ftp.files[lib.BASE + "/library.bin"]
    result = deploy.deploy_payload(ftp, song, blobs, tmp_path)
    assert result["count"] == 1 and not result["hardware_playback_verified"]
    assert lib.decode(ftp.files[lib.BASE + "/library.bin"]) == [song]
    assert ftp.writes[-1][2] == lib.BASE + "/library.bin"
    import console_transaction
    assert not any('.backup-' in p or '.rollback-' in p for p in ftp.files)
    assert old in [p.read_bytes() for p in console_transaction.LOCAL_BACKUPS.rglob('*-before.bin')]
    assert lib.BASE + "/.install-lock" not in ftp.directories
    writes = list(ftp.writes)
    assert deploy.deploy_payload(ftp, song, blobs, tmp_path)["already_present"]
    assert ftp.writes == writes


def test_original_companion_marker_keeps_eight_song_limit_without_upgrading_plugin(tmp_path):
    ftp = StrictFTP(state())
    path = lib.BASE + "/companion-protocol.json"
    cap = json.loads(ftp.files[path])
    del cap["max_songs"]
    ftp.files[path] = json.dumps(cap).encode()
    before = ftp.files[path]
    assert deploy.deploy_payload(ftp, *payload(), tmp_path)["count"] == 1
    assert ftp.files[path] == before
    existing = [lib.decode(lib.encode([synthetic(i)[0]]))[0] for i in range(8)]
    ftp = StrictFTP(state(existing))
    ftp.files[path] = before
    old = ftp.files[lib.BASE + "/library.bin"]
    with pytest.raises(ValueError, match="capacity"):
        deploy.deploy_payload(ftp, *payload(), tmp_path)
    assert ftp.files[lib.BASE + "/library.bin"] == old
    assert not ftp.writes


def test_retains_other_library_entries_files_flags_and_plugin(tmp_path):
    existing, files = synthetic(17)
    existing = lib.decode(lib.encode([existing]))[0]
    ftp = StrictFTP(state([existing]) | files)
    originals = copy.deepcopy(ftp.files)
    song, blobs = payload()
    result = deploy.deploy_payload(ftp, song, blobs, tmp_path)
    assert result["existing_entries_preserved"] == 1
    assert lib.decode(ftp.files[lib.BASE + "/library.bin"])[0] == existing
    for path, data in originals.items():
        if not path.endswith("/library.bin"):
            assert ftp.files[path] == data


@pytest.mark.parametrize(
    "problem", ["active", "plugin", "capability", "flags", "lock", "missing_library", "capacity", "payload"]
)
def test_guard_failures_do_not_publish_or_replace_library(tmp_path, problem):
    ftp = StrictFTP(state())
    song, blobs = payload()
    if problem == "active":
        ftp.active = True
    elif problem == "plugin":
        ftp.files["/data/GoldHEN/plugins/orbeats.prx"] += b"changed"
    elif problem == "capability":
        ftp.files[lib.BASE + "/companion-protocol.json"] = b'{"schema":2}'
    elif problem == "flags":
        flags = {"enable_plugin": True, "enable_additive_song_packs": True, "enable_song_previews": True}
        ftp.files["/data/GoldHEN/AFR/CUSA12878/features.json"] = json.dumps(flags).encode()
    elif problem == "lock":
        ftp.mkd(lib.BASE + "/.install-lock")
    elif problem == "missing_library":
        del ftp.files[lib.BASE + "/library.bin"]
    elif problem == "capacity":
        cap = json.loads(ftp.files[lib.BASE + "/companion-protocol.json"])
        cap["max_songs"] = False
        ftp.files[lib.BASE + "/companion-protocol.json"] = json.dumps(cap).encode()
    elif problem == "payload":
        blobs[1] += b"bad"
    original = copy.deepcopy(ftp.files)
    with pytest.raises((ValueError, OSError)):
        deploy.deploy_payload(ftp, song, blobs, tmp_path)
    assert ftp.files == original
    assert not ftp.writes
    assert (lib.BASE + "/.install-lock" in ftp.directories) == (problem == "lock")


@pytest.mark.parametrize("problem", ["collision", "stage_readback", "publication"])
def test_collision_or_corrupt_upload_never_replaces_old_library(tmp_path, problem):
    ftp = StrictFTP(state())
    song, blobs = payload()
    if problem == "collision":
        ftp.files[lib.paths(song)[0]] = b"other"
    elif problem == "stage_readback":
        ftp.corrupt_stage = True
    elif problem == "publication":
        ftp.fail_publish = True
    old = ftp.files[lib.BASE + "/library.bin"]
    with pytest.raises((ValueError, OSError)):
        deploy.deploy_payload(ftp, song, blobs, tmp_path)
    assert ftp.files[lib.BASE + "/library.bin"] == old
    if problem == "collision":
        assert ftp.files[lib.paths(song)[0]] == b"other"
    assert lib.BASE + "/.install-lock" not in ftp.directories


def test_title_opening_mid_stage_keeps_manifest_and_interrupted_lock(tmp_path):
    class OpensDuringStage(StrictFTP):
        def storbinary(self, cmd, file):
            super().storbinary(cmd, file)
            self.active = True

    ftp = OpensDuringStage(state())
    old = ftp.files[lib.BASE + "/library.bin"]
    with pytest.raises(ValueError, match="Fully close Beat Saber"):
        deploy.deploy_payload(ftp, *payload(), tmp_path)
    assert ftp.files[lib.BASE + "/library.bin"] == old
    assert lib.BASE + "/.install-lock" in ftp.directories
    assert not any(action[0] == "rename" for action in ftp.writes)
