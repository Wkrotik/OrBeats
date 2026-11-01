"""Source-safe synthetic FTP/state tests. No sockets, game assets or real PS4 writes."""

import copy
import hashlib
import json
import sys
from ftplib import error_perm
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "webapp")]
import additive_library as wire
import console_transaction
import first_setup as setup
from test_fresh_library import FTP

CFG = {"ps4": {"ip": "192.0.2.2"}, "additive_template": ""}


class Console(FTP):
    def __init__(self, files):
        super().__init__(files, dirs=("/", "/data", "/mnt", "/mnt/sandbox"))
        self.writes = []
        self.fail = ""

    def mkd(self, path):
        if path in self.dirs:
            raise error_perm("550 exists")
        self.writes.append(("mkdir", path))
        self.dirs.add(path)

    def rmd(self, path):
        self.writes.append(("rmdir", path))
        self.dirs.remove(path)

    def storbinary(self, command, stream, blocksize=8192):
        path = command.removeprefix("STOR ")
        self.writes.append(("store", path))
        self.files[path] = stream.read()

    def rename(self, old, new):
        if new == self.fail:
            self.fail = ""
            raise OSError("injected publish failure")
        self.writes.append(("rename", old, new))
        self.files[new] = self.files.pop(old)

    def delete(self, path):
        self.writes.append(("delete", path))
        del self.files[path]


@pytest.fixture
def environment(monkeypatch, tmp_path):
    plugin = b"\x7fELFsynthetic=== OrBeats v0.8079 started ===\x00"
    flags = b'{ "enable_plugin": true, "enable_additive_song_packs": true, "enable_game_data_extractor": false, "unrelated": 123 }'
    files = {
        setup.FLAGS: flags,
        setup.REQUEST: b"# retain user requests\r\nMedia/other\r\n",
        setup.STATUS: b"prior status evidence\n",
        setup.AFR + "/game_data/other": b"keep",
        wire.BASE + "/library.bin": wire.encode([]),
        wire.BASE + "/companion-protocol.json": json.dumps(
            {
                "schema": 1,
                "title": "CUSA12878",
                "plugin": "0.8079",
                "active_elf_sha256": hashlib.sha256(plugin).hexdigest(),
            }
        ).encode(),
        "/data/GoldHEN/plugins/orbeats.prx": plugin,
        "/data/GoldHEN/plugins.ini": b"[CUSA12878]\n/data/GoldHEN/plugins/orbeats.prx\n",
    }
    f = Console(files)
    cfg = copy.deepcopy(CFG)
    monkeypatch.setattr(setup.paths, "DATA_DIR", tmp_path)
    monkeypatch.setattr(console_transaction, "LOCAL_BACKUPS", tmp_path / "recovery")
    monkeypatch.setattr(setup.library, "FTP", lambda: f)
    monkeypatch.setattr(setup.config, "load_config", lambda: copy.deepcopy(cfg))

    def save(value):
        cfg.clear()
        cfg.update(copy.deepcopy(value))

    monkeypatch.setattr(setup.config, "save_config", save)
    monkeypatch.setattr(setup, "_validate_seed", lambda blob: b"independently validated synthetic test result")
    return f, cfg, copy.deepcopy(files)


def test_status_is_local_and_cannot_implicitly_connect_or_mark_ready(environment, monkeypatch):
    f, cfg, _ = environment
    monkeypatch.setattr(setup.library, "FTP", lambda: pytest.fail("Implicit FTP"))
    assert not setup.local_status(cfg)["complete"]
    assert not f.connections and not f.writes


def test_prepare_restore_preserve_exact_prior_files_and_plugin_owned_outputs(environment):
    f, cfg, before = environment
    assert setup.request(cfg)["ok"]
    values = json.loads(f.files[setup.FLAGS])
    assert values == dict(json.loads(before[setup.FLAGS]), enable_game_data_extractor=True)
    assert f.files[setup.REQUEST] == setup.ASSET.encode() + b"\n"
    assert before[setup.REQUEST] in [p.read_bytes() for p in (setup.paths.DATA_DIR / "recovery").rglob("*-before.bin")]
    assert f.files[setup.REQUEST].decode().splitlines().count(setup.ASSET) == 1
    assert setup.local_status(cfg)["cleanup_required"]
    with pytest.raises(ValueError, match="already requested"):
        setup.request(cfg)
    assert not setup.finish(cfg)["complete"]  # Restoration is not conversion proof.
    assert f.files == before
    assert not setup.local_status(cfg)["cleanup_required"]
    assert all(setup.STATUS not in mutation for mutation in f.writes)


def test_absent_request_is_retired_on_restore_not_replaced_with_empty_file(environment):
    f, cfg, _ = environment
    del f.files[setup.REQUEST]
    setup.request(cfg)
    setup.finish(cfg)
    assert setup.REQUEST not in f.files


@pytest.mark.parametrize("action", ["request", "finish"])
def test_writes_refused_while_title_open(environment, action):
    f, cfg, before = environment
    f.dirs.add("/mnt/sandbox/CUSA12878_000")
    with pytest.raises(ValueError, match="Fully close"):
        getattr(setup, action)(cfg)
    assert f.files == before and f.writes == []


def test_request_publication_failure_rolls_back_and_retains_recovery(environment):
    f, cfg, before = environment
    f.fail = setup.FLAGS
    with pytest.raises(OSError, match="injected"):
        setup.request(cfg)
    assert f.files == before
    assert setup.pending() and setup.local_status(cfg)["cleanup_required"]
    setup.finish(cfg)
    assert f.files == before


def test_finalize_refuses_independent_changes(environment):
    f, cfg, _ = environment
    setup.request(cfg)
    f.files[setup.REQUEST] += b"independent-new-request\n"
    before = dict(f.files)
    with pytest.raises(ValueError, match="changed independently"):
        setup.finish(cfg)
    assert f.files == before and not setup.pending()["restored"]


def test_switching_console_cannot_restore_or_collect_another_consoles_request(environment):
    f, cfg, _ = environment
    setup.request(cfg)
    cfg["ps4"]["ip"] = "192.0.2.99"
    for action in (setup.collect, setup.finish):
        with pytest.raises(ValueError, match="another PS4"):
            action(cfg)


@pytest.mark.parametrize(
    "status",
    [
        b"",
        b"Media/StreamingAssets/BeatmapLevelsData/100Bills-other\n",
        b"ERR Media/StreamingAssets/BeatmapLevelsData/100Bills not-found-on-mounts\n",
    ],
)
def test_missing_or_failed_extraction_cannot_complete(environment, status):
    f, cfg, _ = environment
    setup.request(cfg)
    f.files[setup.STATUS] = status
    before = dict(f.files)
    with pytest.raises(ValueError, match="not ready|Extraction failed"):
        setup.collect(cfg)
    assert f.files == before and not cfg["additive_template"]
    assert not setup.local_status(cfg)["ready"]


def test_collect_is_read_only_while_open_and_only_marks_ready_after_validation(environment):
    f, cfg, _ = environment
    setup.request(cfg)
    f.dirs.add("/mnt/sandbox/CUSA12878_000")
    f.files[setup.STATUS] += setup.ASSET.encode() + b"\n"
    f.files[setup.AFR + "/game_data/" + setup.ASSET] = b"synthetic stock fixture"
    before, writes = dict(f.files), list(f.writes)
    result = setup.collect(copy.deepcopy(cfg))
    assert result["ready"] and not result["complete"] and result["cleanup_required"]
    assert f.files == before and f.writes == writes
    assert Path(cfg["additive_template"]).read_bytes() == b"independently validated synthetic test result"
    f.dirs.remove("/mnt/sandbox/CUSA12878_000")
    assert setup.finish(cfg)["complete"]
    Path(cfg["additive_template"]).write_bytes(b"modified")
    assert not setup.local_status(cfg)["complete"]


def test_bad_conversion_does_not_save_template_or_configuration(environment, monkeypatch):
    f, cfg, _ = environment
    f.files[wire.BASE + "/template.bundle"] = b"bad UnityFS"

    def refused(blob):
        raise ValueError("schema refused")

    monkeypatch.setattr(setup, "_validate_seed", refused)
    with pytest.raises(ValueError, match="schema refused"):
        setup.collect(cfg)
    assert not cfg["additive_template"] and not f.writes
    assert not setup.local_status(cfg)["complete"]


def test_existing_retained_seed_avoids_extraction_and_settings_race_is_refused(environment, monkeypatch):
    f, cfg, _ = environment
    f.files[wire.BASE + "/template.bundle"] = b"synthetic retained schema"
    old = copy.deepcopy(cfg)
    cfg["changed"] = True
    with pytest.raises(ValueError, match="Settings changed"):
        setup.collect(old)
    assert not cfg["additive_template"]
    result = setup.collect(copy.deepcopy(cfg))
    assert result["complete"] and not setup.pending() and not f.writes


def test_request_never_treats_denied_prior_data_as_absent(environment):
    f, cfg, before = environment
    f.denied.add(setup.REQUEST)
    with pytest.raises(ValueError, match="Cannot read existing"):
        setup.request(cfg)
    assert f.files == before
    assert not any(m[0] == "store" for m in f.writes)


def test_active_install_lock_is_not_cleared(environment):
    f, cfg, before = environment
    f.dirs.add(wire.BASE + "/.install-lock")
    with pytest.raises(ValueError, match="installation holds"):
        setup.request(cfg)
    assert f.files == before and f.writes == []


def test_setup_routes_keep_queue_busy_and_origin_guards(environment, monkeypatch):
    import server
    from fastapi.testclient import TestClient

    monkeypatch.setattr(server.RUNNER, "is_busy", lambda: True)
    client = TestClient(server.app)
    for action in ("request", "collect", "finish"):
        assert client.post("/api/orbis/setup/" + action, json={}).status_code == 409
        assert (
            client.post("/api/orbis/setup/" + action, json={}, headers={"origin": "https://evil.invalid"}).status_code
            == 403
        )
    assert client.get("/api/orbis/setup").status_code == 200


def test_queue_start_refused_until_extraction_settings_restored(environment, monkeypatch):
    import server
    from fastapi.testclient import TestClient

    f, cfg, _ = environment
    setup.request(cfg)
    monkeypatch.setattr(server, "_require_config", lambda: pytest.fail("Must block before installation config"))
    result = TestClient(server.app).post("/api/install-queue/start")
    assert result.status_code == 400 and "restore extraction settings" in result.json()["detail"]


def test_malformed_recovery_record_does_not_mark_restored(environment):
    f, cfg, _ = environment
    setup.request(cfg)
    p = setup.directory() / "pending.json"
    record = json.loads(p.read_bytes())
    record["changes"].pop()
    p.write_text(json.dumps(record))
    before = dict(f.files)
    with pytest.raises(ValueError, match="Invalid setup recovery"):
        setup.finish(cfg)
    assert f.files == before


def test_setup_directory_symlink_is_never_used(environment, tmp_path):
    f, cfg, before = environment
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "setup").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(ValueError, match="must not be a symlink"):
        setup.request(cfg)
    assert f.files == before and not list(elsewhere.iterdir())


def test_collected_stock_is_size_bounded_before_validation(environment, monkeypatch):
    f, cfg, _ = environment
    setup.request(cfg)
    f.files[setup.STATUS] = setup.ASSET.encode() + b"\n"
    monkeypatch.setattr(setup, "MAX_STOCK", 20)
    f.files[setup.AFR + "/game_data/" + setup.ASSET] = b"x" * 21
    monkeypatch.setattr(setup, "_validate_seed", lambda value: pytest.fail("Oversized asset reached validation"))
    with pytest.raises(ValueError, match="exceeds the setup size bound"):
        setup.collect(cfg)
    assert not cfg["additive_template"]
