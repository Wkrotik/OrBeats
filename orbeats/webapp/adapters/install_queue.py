"""Explicit-start, in-memory install queue over the existing single-job runner.

Browser refresh/closure does not lose work. Service restart clears pending work;
never auto-resume console writes. Failed maps are skipped; cancellation pauses it.
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque

from . import deploy


class InstallQueue:
    MAX_PENDING = 64

    def __init__(self, runner):
        self.runner = runner
        self._lock = threading.RLock()
        self._pending = []
        self._active = None
        self._history = deque(maxlen=128)
        self._paused = True
        self._message = ""
        self._error = False
        self._thread = None

    def status(self):
        with self._lock:
            return {
                "pending": [dict(e) for e in self._pending],
                "active": dict(self._active) if self._active else None,
                "history": [dict(e) for e in self._history],
                "paused": self._paused,
                "message": self._message,
                "error": self._error,
            }

    def restore(self, snapshot):
        """Explicit operator-only startup handoff; always paused, never resume writes."""
        if not isinstance(snapshot, dict) or snapshot.get("active") is not None or snapshot.get("paused") is not True:
            raise ValueError("Only an idle paused queue can be restored")
        pending, history = snapshot.get("pending"), snapshot.get("history")
        if (
            not isinstance(pending, list)
            or len(pending) > self.MAX_PENDING
            or not isinstance(history, list)
            or len(history) > 128
        ):
            raise ValueError("Invalid queue snapshot bounds")

        def clean(entry, waiting):
            if (
                not isinstance(entry, dict)
                or not re.fullmatch(r"[0-9a-f]{1,12}", str(entry.get("map_id", "")))
                or not re.fullmatch(r"[0-9]{1,32}", str(entry.get("id", "")))
                or entry.get("status") not in ({"queued"} if waiting else {"failed", "complete", "cancelled"})
            ):
                raise ValueError("Invalid queue snapshot entry")
            result = {
                "id": str(entry["id"]),
                "map_id": entry["map_id"],
                "title": str(entry.get("title", ""))[:200],
                "status": entry["status"],
            }
            if not waiting:
                for key in ("job_id", "exit_code", "error"):
                    if key in entry:
                        result[key] = str(entry[key])[:512] if key != "exit_code" else entry[key]
            return result

        entries = [clean(e, True) for e in pending]
        results = [clean(e, False) for e in history]
        if len({e["map_id"] for e in entries}) != len(entries):
            raise ValueError("Duplicate pending maps in snapshot")
        with self._lock:
            if self._thread or self._active or self._pending or self._history:
                raise ValueError("Cannot restore over an existing queue")
            self._pending = entries
            self._history.extend(results)
            self._error = bool(snapshot.get("error"))
            self._message = "Queue preserved after service update. Review Downloads and resume manually."

    def has_work(self):
        with self._lock:
            return bool(self._pending or self._active)

    def add(self, map_id, title=""):
        key = str(map_id).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{1,12}", key):
            raise ValueError("A valid BeatSaver map key is required.")
        with self._lock:
            if any(e["map_id"] == key for e in self._pending + ([self._active] if self._active else [])):
                raise ValueError("This map is already queued or installing.")
            if len(self._pending) >= self.MAX_PENDING:
                raise ValueError("Queue is full (64 pending maps).")
            entry = {
                "id": str(time.time_ns()),
                "map_id": key,
                "title": str(title).strip()[:200] or "Map " + key,
                "status": "queued",
            }
            self._pending.append(entry)
            return dict(entry)

    def remove(self, entry_id):
        with self._lock:
            for i, entry in enumerate(self._pending):
                if entry["id"] == entry_id:
                    self._pending.pop(i)
                    return
            raise ValueError("Pending map not found; it may already be installing.")

    def clear(self):
        with self._lock:
            self._pending.clear()
            self._paused = True
            self._error = False
            self._message = "Pending maps cleared; an active installation finishes normally."

    def pause(self):
        with self._lock:
            self._paused = True
            self._message = "Paused. An active installation finishes before the queue stops."

    def start(self):
        with self._lock:
            if not self._pending and not self._active:
                raise ValueError("Add a map to the queue first.")
            self._paused = False
            self._error = False
            self._message = "Keep Beat Saber fully closed until the queue finishes."
            if self._thread is None:
                self._thread = threading.Thread(target=self._work, daemon=True)
                self._thread.start()

    def _work(self):
        while True:
            with self._lock:
                if self._paused or not self._pending:
                    if not self._paused:
                        self._paused = True
                        self._message = (
                            "Queue finished with unsuccessful maps. Use Retry beside a failed installation."
                            if self._error
                            else "Queue finished. You can launch Beat Saber manually."
                        )
                    self._thread = None
                    return
                entry = self._pending[0]
                try:
                    argv = deploy.DeployOptions(additive=True, map_id=entry["map_id"]).build_argv()
                    job = self.runner.start(argv, label="Install " + entry["title"])
                except Exception as exc:
                    self._error = True
                    if getattr(self.runner, "is_busy", lambda: False)():
                        self._paused = True
                        self._message = "Another job is running. Pending maps preserved; resume when it finishes."
                        self._thread = None
                        return
                    self._pending.pop(0)
                    entry.update(status="failed", exit_code=None, error=str(exc)[:512])
                    self._history.appendleft(dict(entry))
                    self._message = "Could not start " + entry["title"] + "; continuing with the next map."
                    continue
                self._pending.pop(0)
                entry.update(status="installing", job_id=str(job.id))
                self._active = entry
            # Wait for process exit and its fully drained output, not just PID exit.
            while job.exit_code is None:
                threading.Event().wait(0.05)
            with self._lock:
                entry.update(
                    status="cancelled" if job.cancelled else "complete" if job.exit_code == 0 else "failed",
                    exit_code=job.exit_code,
                )
                self._history.appendleft(dict(entry))
                self._active = None
                if job.cancelled or job.exit_code != 0:
                    # Keep a bounded reason per failed job before the runner replaces
                    # its log with the next installation. Never execute log content.
                    reason = next(
                        (line.strip() for line in reversed(job.lines)
                         if line.strip() and not (line.startswith("[PYI-") and "Failed to execute script" in line)),
                        "Cancelled" if job.cancelled else "Installation failed",
                    )
                    self._history[0]["error"] = re.sub(r"^\[additive\]\s*", "", reason)[:512]
                    self._error = True
                    if job.cancelled:
                        self._paused = True
                        self._message = "Installation cancelled. Remaining maps are paused."
                    elif not self._paused:
                        self._message = "Skipped " + entry["title"] + "; continuing with the next map."
