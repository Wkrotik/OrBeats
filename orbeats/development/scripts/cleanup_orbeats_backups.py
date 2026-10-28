"""Explicit, closed-title cleanup of verified OrBeats plugin backups only.

No globs are sent to FTP. Unrelated plugins/backups and interrupted .rollback/
.stage state are out of scope. Plan/archives are local and deletion rechecks bytes.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "webapp")]
import additive_companion as core
import library_manager as manager
from console_transaction import archive

PLUGIN_DIR = "/data/GoldHEN/plugins"
OWNED_BACKUP = re.compile(
    r"(?:beat_saber_deluxe|orbeats)(?:_debug)?\.prx\."
    r"(?:backup-[0-9a-f]{32}|exp[0-9]+-backup(?:-[0-9]{8}T[0-9]{6}Z)?)"
)


def plan(ftp, directory):
    core.closed(ftp)
    rows = []
    for listed in ftp.nlst(PLUGIN_DIR):
        name = listed.rstrip("/").rsplit("/", 1)[-1]
        if not OWNED_BACKUP.fullmatch(name):
            continue
        path = PLUGIN_DIR + "/" + name
        raw = core.read(ftp, path, 2000000)
        canonical = manager.elf_from_fself(raw)
        version = manager.binary_version(canonical)
        if version is None:
            raise ValueError("Backup identity unknown; no deletion permitted: " + path)
        local = archive(directory, name, raw)
        rows.append(
            {
                "path": path,
                "archive": str(local.resolve()),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "version": version,
            }
        )
    archive(directory, "plan.json", json.dumps(rows, indent=2).encode())
    return rows


def apply(ftp, rows, directory):
    core.closed(ftp)
    # First verify ALL archives and remote bytes, then repeat CAS per deletion.
    values = []
    for row in rows:
        path = row["path"]
        if path.rsplit("/", 1)[0] != PLUGIN_DIR or not OWNED_BACKUP.fullmatch(path.rsplit("/", 1)[1]):
            raise ValueError("Path outside owned backup scope: " + path)
        value = Path(row["archive"]).read_bytes()
        if len(value) != row["bytes"] or hashlib.sha256(value).hexdigest() != row["sha256"]:
            raise ValueError("Local archive changed; refusing cleanup: " + path)
        if manager.binary_version(manager.elf_from_fself(value)) != row["version"]:
            raise ValueError("Archive identity changed: " + path)
        if core.read(ftp, path, 2000000) != value:
            raise ValueError("Remote backup changed; refusing cleanup: " + path)
        values.append(value)
    removed = []
    for row, value in zip(rows, values):
        core.closed(ftp)
        path = row["path"]
        if core.read(ftp, path, 2000000) != value:
            raise ValueError("Remote backup changed; refusing cleanup: " + path)
        ftp.delete(path)
        if core.read(ftp, path, 2000000, missing=True) is not None:
            raise ValueError("Backup deletion not confirmed: " + path)
        removed.append(path)
        archive(directory, f"deleted-{len(removed)}.json", json.dumps({"deleted": path}).encode())
    return removed
