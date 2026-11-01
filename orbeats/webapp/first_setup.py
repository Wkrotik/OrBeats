"""One owned stock schema, not a game dump. Explicit, closed-title request writes.

The existing native extractor owns its status/output. Collection is read-only on
PS4, even while the game runs. Only a validated synthetic conversion is cached
locally; it is never uploaded/shared. No credentials or game data are shipped.
"""

import base64
import faulthandler
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import library_manager as library
from adapters import config, paths
from console_transaction import Transaction, archive

core = library.core
AFR = "/data/GoldHEN/AFR/CUSA12878"
REQUEST = AFR + "/game_data_requests.txt"
STATUS = AFR + "/game_data_status.txt"
FLAGS = AFR + "/features.json"
# OST Vol.1: no DLC/entitlement bypass and no catalog or executable extraction.
ASSET = "Media/StreamingAssets/BeatmapLevelsData/100Bills"
MAX_TEMPLATE = 200000000
MAX_STOCK = 32000000
_lock = threading.Lock()
_activity_lock = threading.Lock()
_activity = {"busy": False, "phase": "", "started": None, "error": "", "log_file": ""}
_activity_log = None
_last_log = 0.0


def activity():
    with _activity_lock:
        return dict(_activity)


def phase(message, force=False):
    global _last_log
    with _activity_lock:
        if not _activity["busy"]:
            return
        _activity["phase"] = message
        if _activity_log and (force or time.monotonic() - _last_log >= 0.25):
            try:
                if _activity_log.tell() < 1000000:
                    _activity_log.write(message[:1024] + "\n")
                    _activity_log.flush()
                _last_log = time.monotonic()
            except OSError:
                pass


@contextmanager
def operation(name):
    """Never queue duplicate setup clicks behind a long FTP read or conversion."""
    global _activity_log, _last_log
    if not _lock.acquire(blocking=False):
        raise ValueError("Setup is already working; follow its progress instead of starting another check")
    watchdog = False
    try:
        with _activity_lock:
            _activity.update(busy=True, phase=name, started=time.time(), error="", log_file="")
        try:
            folder = paths.DATA_DIR / "logs"
            if folder.is_symlink():
                raise OSError("Log directory is a symlink")
            folder.mkdir(parents=True, exist_ok=True)
            for old in sorted(folder.glob("setup-*.log"))[:-19]:
                if old.is_file() and not old.is_symlink():
                    old.unlink()
            log = folder / ("setup-" + str(time.time_ns()) + ".log")
            _activity_log = log.open("x", encoding="utf-8")
            os.chmod(log, 0o600)
            with _activity_lock:
                _activity["log_file"] = str(log)
            faulthandler.dump_traceback_later(45, file=_activity_log)
            watchdog = True
        except (OSError, RuntimeError):
            pass  # Diagnostics must not turn a recoverable setup error into failure.
        _last_log = 0.0
        phase(name)
        yield
        phase("Setup operation completed", force=True)
    except Exception as exc:
        with _activity_lock:
            _activity["error"] = str(exc)[:1024]
        phase("Setup stopped: " + str(exc), force=True)
        raise
    finally:
        if watchdog:
            faulthandler.cancel_dump_traceback_later()
        with _activity_lock:
            if _activity_log:
                try:
                    _activity_log.close()
                except OSError:
                    pass
            _activity_log = None
            _activity["busy"] = False
        _lock.release()


class ProgressFTP:
    """Transparent read-only progress observation; no new console operations."""

    def __init__(self, ftp):
        self.ftp = ftp

    def __getattr__(self, name):
        return getattr(self.ftp, name)

    def retrbinary(self, command, callback, *args, **kwargs):
        name = command.rsplit("/", 1)[-1]
        count = 0
        phase("Reading " + name)

        def received(block):
            nonlocal count
            callback(block)
            count += len(block)
            phase("Reading " + name + ": " + str(count // 1024) + " KiB received")

        return self.ftp.retrbinary(command, received, *args, **kwargs)


def directory():
    result = paths.DATA_DIR / "setup"
    if result.is_symlink():
        raise ValueError("Setup directory must not be a symlink")
    return result


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    if path.is_symlink() or temporary.is_symlink() or path.parent.is_symlink():
        raise ValueError("Setup state must not be a symlink")
    with temporary.open("wb") as stream:
        os.chmod(temporary, 0o600)
        stream.write(json.dumps(value).encode())
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def pending():
    path = directory() / "pending.json"
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 500000:
        raise ValueError("Invalid setup recovery record; preserve it for inspection")
    value = json.loads(path.read_bytes())
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("ip"), str)
        or type(value.get("restored")) is not bool
        or not isinstance(value.get("changes"), list)
        or len(value["changes"]) != 2
        or any(not isinstance(row, dict) for row in value["changes"])
        or {row.get("path") for row in value["changes"]} != {REQUEST, FLAGS}
    ):
        raise ValueError("Invalid setup recovery record; preserve it for inspection")
    return value


def local_status(cfg):
    """No FTP, no implicit start and no completion from a user-supplied boolean."""
    record = pending()
    proof = directory() / "template.json"
    ready = False
    if proof.is_file() and not proof.is_symlink() and proof.stat().st_size < 4096:
        value = json.loads(proof.read_bytes())
        digest = value.get("sha256", "")
        if len(digest) == 64 and all(c in "0123456789abcdef" for c in digest):
            template = directory() / (digest + ".bundle")
            ready = (
                str(template) == cfg.get("additive_template")
                and template.is_file()
                and not template.is_symlink()
                and template.stat().st_size <= MAX_TEMPLATE
                and hashlib.sha256(template.read_bytes()).hexdigest() == digest
            )
    needs_cleanup = bool(record and not record.get("restored"))
    return {
        "ready": ready,
        "cleanup_required": needs_cleanup,
        "requested": needs_cleanup,
        "asset": ASSET,
        "complete": ready and not needs_cleanup,
        "activity": activity(),
    }


def _protocol(f):
    cap = json.loads(core.read(f, library.BASE + "/companion-protocol.json", 4096))
    plugin = core.read(f, "/data/GoldHEN/plugins/orbeats.prx", 2000000)
    if (
        cap.get("schema") != 1
        or cap.get("title") != "CUSA12878"
        or hashlib.sha256(plugin).hexdigest() != cap.get("active_elf_sha256")
    ):
        raise ValueError("Install/check the bundled main plugin before first setup")
    ini = core.read(f, "/data/GoldHEN/plugins.ini", 65536)
    if library.merge_ini(ini) != ini or library.binary_version(plugin) != cap.get("plugin"):
        raise ValueError("Main plugin registration/version needs review before setup")
    flags = core.read(f, FLAGS, 65536)
    values = json.loads(flags)
    if (
        values.get("enable_plugin") is not True
        or values.get("enable_additive_song_packs") is not True
        or any(
            values.get("enable_" + key)
            for key in (
                "custom_song_replacements",
                "song_metadata_modification",
                "beatmap_mode_mapping",
                "song_previews",
                "in_game_plugin_toggle",
            )
        )
    ):
        raise ValueError("Use the additive plugin profile; legacy replacement features must remain off")
    return flags, values


def _change(f, changes):
    tx = Transaction(core, f, uuid.uuid4().hex)
    try:
        for path, before, after in changes:
            if after is None:
                tx.retire(path, before)
            else:
                tx.publish(path, after, before)
        tx.finish()
    except Exception:
        tx.rollback()
        raise


def _same_console(record, cfg):
    if record["ip"] != cfg["ps4"]["ip"]:
        raise ValueError("Setup belongs to another PS4 address; restore that connection before continuing")


def request(cfg):
    """Never prepare extraction when a verified local template already suffices."""
    with operation("Checking whether first-time extraction is needed"):
        if local_status(cfg)["ready"]:
            raise ValueError("A verified local template is already ready; extraction is not needed")
        return _request(cfg)


def _request(cfg):
    phase("Checking closed title and preparing extraction", force=True)
    with library.connection(cfg, True) as f:
        previous = pending()
        if previous and not previous.get("restored"):
            _same_console(previous, cfg)
            raise ValueError(
                "Extraction already requested. Launch Beat Saber, then fetch; do not rewrite recovery state"
            )
        flags, values = _protocol(f)
        old = core.read(f, REQUEST, 65536, missing=True)
        text = (old or b"").decode("utf-8")
        if "\x00" in text:
            raise ValueError("Malformed extraction requests; preserve the existing file")
        # Do not re-enable unrelated pending requests when the extractor starts.
        # Keep the exact original in recovery; temporarily request ONLY our asset.
        wanted = ASSET.encode() + b"\n"
        if len(wanted) > 65535:
            raise ValueError("Extraction request file is full; no changes made")
        values["enable_game_data_extractor"] = True
        new_flags = json.dumps(values).encode()

        def encoded(value):
            return None if value is None else base64.b64encode(value).decode("ascii")

        record = {
            "ip": cfg["ps4"]["ip"],
            "restored": False,
            "changes": [
                {"path": path, "before": encoded(before), "after": encoded(after)}
                for path, before, after in ((REQUEST, old, wanted), (FLAGS, flags, new_flags))
            ],
        }
        # Persist exact recovery intent before the first remote publication. An
        # interruption must never look like a clean first run.
        atomic(directory() / "pending.json", record)
        _change(f, [(REQUEST, old, wanted), (FLAGS, flags, new_flags)])
        return {
            "ok": True,
            "message": "Now launch Beat Saber yourself and wait at the main menu, then choose Fetch template. No song or stock file was changed.",
        }


def _validate_seed(blob):
    """Keep native conversion/imports out of the HTTP process, not just its loop."""
    from runtime_dispatch import command

    if not blob or len(blob) > MAX_TEMPLATE:
        raise ValueError("Conversion template is empty or exceeds the setup size bound")
    with tempfile.TemporaryDirectory(prefix="orbeats-setup-") as tmp:
        root = Path(tmp)
        template, output = root / "source.bundle", root / "validated.bundle"
        template.write_bytes(blob)
        os.chmod(template, 0o600)
        phase("Starting isolated template validation worker", force=True)
        argv = command(
            paths.PROJECT_DIR / "development/scripts/validate_setup_template.py",
            ["--input", str(template), "--output", str(output)],
        )
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        tail = []
        try:
            for line in iter(lambda: process.stdout.readline(8193), ""):
                line = line.rstrip()
                if line:
                    tail.append(line[:8192])
                    tail = tail[-12:]
                    if line.startswith("[setup-worker] "):
                        phase(line.removeprefix("[setup-worker] "), force=True)
                    else:
                        # Keep stack traces/warnings in diagnostics, not the UI's
                        # current progress label (which remains the actual stage).
                        with _activity_lock:
                            if _activity_log and _activity_log.tell() < 1000000:
                                _activity_log.write(line[:8192] + "\n")
                                _activity_log.flush()
            code = process.wait()
        except BaseException:
            # This child has NO console access or publication transaction. Reap it
            # before removing its private temporary inputs if the parent fails.
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
        finally:
            process.stdout.close()
        if code:
            raise ValueError("Template validation worker failed (exit " + str(code) + "): " + "\n".join(tail)[-4000:])
        if output.is_symlink() or not output.is_file() or not 0 < output.stat().st_size <= MAX_TEMPLATE:
            raise ValueError("Template worker did not produce a bounded validated result")
        return output.read_bytes()


def _existing_seed(f):
    songs, manifest = core.load_library(f)
    if manifest is None:
        found = [
            core.read(f, p, spec["bytes"] + 1, missing=True) is not None
            for s in songs
            for p, spec in zip(library.paths(s), (s, s["cover"], s["preview"]))
        ]
        if any(found) and not all(found):
            raise ValueError("Incomplete legacy library; recover it before first setup")
        if all(found) and songs:
            for s in songs:
                core.checked(f, s)
        else:
            songs = []
    if songs:
        return core.checked_bundle(f, songs[0])
    return core.read(f, library.BASE + "/template.bundle", MAX_TEMPLATE + 1, missing=True)


def collect(cfg):
    """Only RETR/NLST/login on console. Can run while extractor's title is open."""
    with operation("Waiting for FTP access; other PS4 reads may finish first"):
        record = pending()
        if record and not record.get("restored"):
            _same_console(record, cfg)
        status = local_status(cfg)
        if status["ready"]:
            return {
                "ok": True,
                **status,
                "message": "Using the already verified local template. "
                + (
                    "Close Beat Saber and restore extraction settings to finish setup."
                    if status["cleanup_required"]
                    else "No extraction or further template check is needed."
                ),
            }
        with library.connection(cfg) as connection:
            f = ProgressFTP(connection)
            phase("Checking installed plugin and supported settings")
            _protocol(f)
            phase("Checking the installed library for a conversion template")
            blob = _existing_seed(f)
            if blob is None and cfg.get("additive_template"):
                p = Path(cfg["additive_template"])
                if not p.is_file() or p.stat().st_size > MAX_TEMPLATE:
                    raise ValueError("Configured template is unavailable; review the advanced setting")
                blob = p.read_bytes()
            if blob is None:
                if not record or record.get("restored"):
                    raise ValueError(
                        "No existing template found. Close Beat Saber and choose Prepare first-time extraction"
                    )
                text = (core.read(f, STATUS, 65536, missing=True) or b"").decode("utf-8")
                if ASSET not in text.splitlines():
                    failures = [line for line in text.splitlines() if line.startswith("ERR " + ASSET + " ")]
                    raise ValueError(
                        "Extraction failed; fully close and relaunch Beat Saber to retry"
                        if failures
                        else "Template is not ready. Launch Beat Saber with the main plugin enabled and wait at its menu"
                    )
                blob = core.read(f, AFR + "/game_data/" + ASSET, MAX_STOCK + 1)
                if len(blob) > MAX_STOCK:
                    raise ValueError("Extracted stock asset exceeds the setup size bound")
        phase("Validating template with a synthetic conversion")
        checked = _validate_seed(blob)
        phase("Saving the validated template privately on this computer")
        digest = hashlib.sha256(checked).hexdigest()
        target = directory() / (digest + ".bundle")
        if target.exists():
            if target.is_symlink() or target.read_bytes() != checked:
                raise ValueError("Cached template changed; preserve it for inspection")
        else:
            archive(directory(), target.name, checked)
            os.chmod(target, 0o600)
        current = config.load_config()
        if current != cfg:
            raise ValueError("Settings changed during setup; no connection setting was overwritten")
        current["additive_template"] = str(target)
        config.save_config(current)
        atomic(directory() / "template.json", {"sha256": digest, "synthetic_conversion_verified": True})
        return {
            "ok": True,
            **local_status(current),
            "message": "Template fetched and independently validated; saved privately on this computer. Close Beat Saber before finalizing setup or installing songs.",
        }


def finish(cfg):
    """Restore only our exact request/flag bytes, while closed. Never erase output/status."""
    with operation("Checking closed title and restoring extraction settings"), library.connection(cfg, True) as f:
        record = pending()
        if not record or record.get("restored"):
            return {"ok": True, **local_status(cfg)}
        _same_console(record, cfg)
        _protocol(f)
        changes = []
        for row in record["changes"]:
            if row["path"] not in (REQUEST, FLAGS):
                raise ValueError("Invalid setup recovery path")

            def decoded(value):
                return None if value is None else base64.b64decode(value, validate=True)

            before, after = decoded(row["before"]), decoded(row["after"])
            actual = core.read(f, row["path"], 65536, missing=True)
            if actual not in (before, after):
                raise ValueError(
                    "Setup files changed independently; preserve recovery state rather than overwriting them"
                )
            changes.append((row["path"], actual, before))
        _change(f, changes)
        record["restored"] = True
        atomic(directory() / "pending.json", record)
        return {
            "ok": True,
            **local_status(cfg),
            "message": "Extraction settings restored. Setup is complete only when a validated template is present. Keep Beat Saber closed for installations.",
        }
