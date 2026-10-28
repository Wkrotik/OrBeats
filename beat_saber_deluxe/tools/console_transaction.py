"""Verified publication with local recovery archives, no permanent console backups.

Remote rollback names are temporary transaction state, not a retention policy.
Unknown/concurrent bytes or interrupted transactions are never auto-deleted.
"""

import hashlib
import json
import os
from pathlib import Path

LOCAL_BACKUPS = (Path(os.environ["ORBEATS_STATE_DIR"]) if "ORBEATS_STATE_DIR" in os.environ
                 else Path(__file__).resolve().parents[2]) / "ps4_backups" / "transactions"


def sync_directory(directory):
    if os.name != "nt":
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def archive(directory, name, content):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(directory)
    if path.read_bytes() != content:
        raise ValueError("Local recovery archive readback failed: " + str(path))
    return path


class Transaction:
    def __init__(self, core, ftp, run, directory=None):
        self.core, self.ftp, self.run = core, ftp, run
        self.directory = Path(directory or LOCAL_BACKUPS) / run
        self.entries = []
        self.done = False

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        value = {
            "complete": self.done,
            "entries": [
                {k: v for k, v in e.items() if k not in ("old", "wanted", "held", "upload")} for e in self.entries
            ],
        }
        target = self.directory / "journal.json"
        temporary = target.with_suffix(".tmp")
        with temporary.open("w") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        sync_directory(self.directory)

    def publish(self, path, value, expected, wanted=None):
        return self._change(path, value, expected, value if wanted is None else wanted)

    def retire(self, path, expected):
        if expected is not None:
            self._change(path, None, expected, None)

    def _change(self, path, value, expected, wanted):
        c, f = self.core, self.ftp
        c.closed(f)
        if c.read(f, path, 2000000, missing=True) != expected:
            raise ValueError("File changed concurrently: " + path)
        if expected == wanted:
            return
        index = len(self.entries)
        if expected is not None:
            archive(self.directory, f"{index}-before.bin", expected)
        staged = c.stage(f, path, value, self.run) if value is not None else None
        entry = {
            "path": path,
            "old": expected,
            "wanted": wanted,
            "rollback": path + ".rollback-" + self.run,
            "stage": staged,
            "moved": False,
            "published": False,
            "held": None,
            "upload": value,
        }
        self.entries.append(entry)
        self.save()
        c.closed(f)
        if c.read(f, path, 2000000, missing=True) != expected:
            raise ValueError("File changed concurrently: " + path)
        if expected is not None:
            if c.read(f, entry["rollback"], 2000000, missing=True) is not None:
                raise ValueError("Transaction recovery path already exists")
            f.rename(path, entry["rollback"])
            entry["moved"] = True
            # GoldHEN RETR .prx yields canonical ELF; after rename it yields FSELF.
            # Archive BOTH forms before permitting any recovery-file deletion.
            entry["held"] = c.read(f, entry["rollback"], 2000000)
            archive(self.directory, f"{index}-rollback.bin", entry["held"])
            entry["rollback_sha256"] = hashlib.sha256(entry["held"]).hexdigest()
            self.save()
        if staged is not None:
            c.closed(f)
            f.rename(staged, path)
            entry["published"] = True
            self.save()
            if c.read(f, path, 2000000) != wanted:
                raise ValueError("Published readback failed: " + path)

    def _delete_exact(self, path, content):
        c, f = self.core, self.ftp
        c.closed(f)
        current = c.read(f, path, 2000000, missing=True)
        if current is None:
            return
        if current != content:
            raise RuntimeError("Concurrent recovery data retained: " + path)
        f.delete(path)

    def finish(self):
        # Verify the entire transaction BEFORE removing any recovery state.
        for e in self.entries:
            if self.core.read(self.ftp, e["path"], 2000000, missing=True) != e["wanted"]:
                raise RuntimeError("Published transaction changed: " + e["path"])
        self.done = True
        self.save()
        for e in self.entries:
            if e["moved"]:
                self._delete_exact(e["rollback"], e["held"])

    def rollback(self):
        if self.done:
            raise RuntimeError("Transaction committed; cleanup needs review: " + str(self.directory))
        c, f = self.core, self.ftp
        for e in reversed(self.entries):
            c.closed(f)
            current = c.read(f, e["path"], 2000000, missing=True)
            if e["published"]:
                if current != e["wanted"]:
                    raise RuntimeError("Concurrent data during rollback; retained local journal: " + e["path"])
                # Preserve the rejected new file locally as well.
                archive(self.directory, f"rejected-{len(list(self.directory.glob('rejected-*')))}.bin", current)
                self._delete_exact(e["path"], current)
            elif e["moved"] and current is not None:
                raise RuntimeError("Concurrent data during rollback; retained local journal: " + e["path"])
            if e["moved"]:
                if c.read(f, e["rollback"], 2000000) != e["held"]:
                    raise RuntimeError("Recovery file changed: " + e["rollback"])
                c.closed(f)
                f.rename(e["rollback"], e["path"])
                if c.read(f, e["path"], 2000000) != e["old"]:
                    raise RuntimeError("Restored readback failed: " + e["path"])
            if e["stage"]:
                staged = c.read(f, e["stage"], 2000000, missing=True)
                if staged is not None:
                    # Only a stage owned by this journal can be removed.
                    self._delete_exact(e["stage"], e["upload"])
        self.save()
