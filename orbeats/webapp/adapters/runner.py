"""
runner.py — single-job subprocess executor with a line-streamed log buffer.

Plan §3 decision 1: the pipeline runs as a SUBPROCESS with the exact argv the
CLI uses (never imported for deploys — it has sys.exit calls, module-level
config loading, and long FTP transfers). Plan §9.4 invariant 2: ONE job at a
time; PS4 state files are transaction records and concurrent writers corrupt
them (Exp 227/232/237 all trace to this class).

The runner owns the process; the SSE endpoint (server.py /api/stream) tails the
shared log buffer. Cancel terminates the whole process group.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import deploy, paths

MAX_BUFFER_LINES = 20000  # ring; a full deploy emits a few thousand lines


@dataclass
class Job:
    """One subprocess invocation (pipeline or helper script)."""

    id: int
    argv: list[str]
    cwd: str
    started_at: float
    pid: int | None = None
    ended_at: float | None = None
    exit_code: int | None = None
    cancelled: bool = False
    lines: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    label: str = ""
    command_line: str = ""
    log_path: str = ""


class SingleJobRunner:
    """Allows ONE job at a time; queues nothing (the UI says 'busy')."""

    def __init__(self):
        self._job: Job | None = None
        self._lock = threading.Lock()
        # Flags the UI has applied but the PS4 read hasn't confirmed yet —
        # purely informational for the Flags page's pending badges.
        self.pending_flags: dict | None = None

    # -- state queries -----------------------------------------------------
    @property
    def current(self) -> Job | None:
        with self._lock:
            return self._job

    def is_busy(self) -> bool:
        job = self.current
        return job is not None and job.exit_code is None

    def status(self) -> dict:
        job = self.current
        if job is None:
            return {"running": False, "job": None}
        with job.lock:
            return {
                "running": job.exit_code is None,
                "job": {
                    "id": job.id,
                    "label": job.label,
                    "command": f"python3 tools/full_custom_song_pipeline.py "
                               f"{' '.join(job.argv)}",
                    "started_at": job.started_at,
                    "ended_at": job.ended_at,
                    "exit_code": job.exit_code,
                    "cancelled": job.cancelled,
                    "line_count": len(job.lines),
                },
            }

    def lines_since(self, after_index: int = 0) -> tuple[int, list[str]]:
        """(new_index, lines) — SSE long-poll contract."""
        job = self.current
        if job is None:
            return 0, []
        with job.lock:
            new = job.lines[after_index:]
            return len(job.lines), new

    def snapshot(self, after: int = 0, job_id: str | None = None) -> dict:
        """Atomic polling snapshot; a queue transition resets the line cursor."""
        with self._lock:
            job = self._job
            if job is None:
                return {"running": False, "job": None, "index": 0, "lines": []}
            with job.lock:
                start = max(0, after) if str(job_id) == str(job.id) else 0
                return {"running": job.exit_code is None, "index": len(job.lines),
                        "lines": job.lines[start:], "job": {
                            "id": str(job.id), "label": job.label, "command": job.command_line,
                            "started_at": job.started_at, "ended_at": job.ended_at,
                            "exit_code": job.exit_code, "cancelled": job.cancelled,
                            "line_count": len(job.lines), "log_file": job.log_path}}

    # -- job lifecycle ------------------------------------------------------
    def start(self, argv: list[str], label: str = "") -> Job:
        """Run the PIPELINE with the given argv (the thin-layer deploy path)."""
        pipeline = paths.find_pipeline()
        from runtime_dispatch import command
        return self._spawn(command(pipeline, argv),
                            label=label, command=deploy.pipeline_command(argv))

    def start_script(self, script: str, argv: list[str], label: str = "") -> Job:
        """Run a helper script (e.g. backup-orbeats-files.py) with
        the same single-job + streaming guarantees. Thin layer: the script is
        the authority for its own behavior; the webapp only streams output."""
        rel = script
        try:
            rel = str(Path(script).relative_to(paths.RELEASE_ROOT))
        except ValueError:
            pass
        from runtime_dispatch import command
        return self._spawn(command(script, argv),
                           label=label, command=f"python3 {rel} {' '.join(argv)}")

    def _spawn(self, popen_argv: list[str], label: str, command: str) -> Job:
        with self._lock:
            if self._job is not None and self._job.exit_code is None:
                raise RuntimeError(
                    "A job is already running — one at a time (PS4 state files "
                    "are transaction records; concurrent writers corrupt them). "
                    "Wait for it to finish or cancel it first.")
            job = Job(
                id=time.time_ns(),
                argv=list(popen_argv[2:]),  # the script's own argv (after python3 + script)
                # CWD = the release/checkout root (same semantics as the
                # example scripts; the pipeline resolves the rest itself).
                # Exp 270a: layout-agnostic — in the flat release zip the
                # zip root IS PROJECT_DIR (RELEASE_ROOT points one level
                # above the extraction, where nothing lives).
                cwd=str(paths.release_root_surname()),
                started_at=time.time(),
                label=label,
                command_line=command,
            )
            # Reserve and spawn under the same lock: two simultaneous requests
            # must not both pass the busy check or observe a half-started job.
            previous=self._job
            self._job = job
            try:
                proc = subprocess.Popen(
                    popen_argv, cwd=job.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1,
                    encoding="utf-8", errors="replace",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "ORBEATS_JOB_DIAGNOSTICS": "1"},
                    start_new_session=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
                )
                job.pid = proc.pid
                job.lines.append("[job] Worker started; waiting for installation output…")
            except Exception:
                self._job=previous
                raise

        # Desktop jobs must not inherit the parent's private STOP/EOF pipe.
        # Persist diagnostics immediately, not only when a queue entry completes.
        # No bootstrap URL/cookie or config contents are written here.
        log = None
        if os.environ.get("ORBEATS_STATE_DIR"):
            try:
                folder = paths.DATA_DIR / "logs"
                if folder.is_symlink():
                    raise ValueError("Log directory must not be a symlink")
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / f"installation-{job.id}.log"
                log = target.open("x", encoding="utf-8")
                os.chmod(target, 0o600)
                job.log_path = str(target)
                for old in sorted(folder.glob("installation-[0-9]*.log"), reverse=True)[20:]:
                    if not old.is_symlink() and old.stem.removeprefix("installation-").isdigit():
                        old.unlink()  # Only this app's bounded diagnostic history.
                log.write(job.lines[0] + "\n")
                log.flush()
            except (OSError, ValueError) as e:
                if log:
                    log.close()
                log = None
                job.lines.append("[job] Could not save diagnostic log: " + str(e))
        log_bytes = 0
        first_output = threading.Event()

        def append(line):
            nonlocal log_bytes, log
            line = line.rstrip("\r\n")[:8192]
            with job.lock:
                if len(job.lines) < MAX_BUFFER_LINES:
                    job.lines.append(line)
                elif len(job.lines) == MAX_BUFFER_LINES:
                    job.lines.append("… log truncated (max lines reached)")
                if log:
                    try:
                        if log_bytes < 4 * 1024 * 1024:
                            log.write(line + "\n")
                            log.flush()
                            log_bytes += len(line.encode("utf-8")) + 1
                    except OSError:
                        log.close()
                        log = None
                        job.lines.append("[job] Diagnostic log write failed; live log remains available")

        def startup_warning():
            if not first_output.wait(20):
                append("[job] No child output after 20 seconds. Process creation is not proof of pipeline startup. Preserve this log; do not start a duplicate installation.")

        def _drain():
            nonlocal log
            assert proc.stdout is not None
            try:
                for line in proc.stdout:
                    first_output.set()
                    append(line)
            except (OSError, UnicodeError) as e:
                append("[job] Output stream failed: " + str(e))
            finally:
                first_output.set()
                proc.stdout.close()
                proc.wait()
                append(f"[job] Worker exited with code {proc.returncode}")
                with job.lock:
                    if log:
                        log.close()
                        log = None
                    job.ended_at = time.time()
                    job.exit_code = proc.returncode
                    if self.pending_flags and job.exit_code is not None:
                        self.pending_flags = None

        threading.Thread(target=startup_warning, daemon=True).start()
        threading.Thread(target=_drain, daemon=True).start()
        return job

    def cancel(self) -> bool:
        """Terminate the process group (lftp children die too)."""
        job = self.current
        if job is None or job.exit_code is not None:
            return False
        if job.pid:
            try:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(job.pid),'/T','/F'],
                                   capture_output=True,check=False)
                else:
                    os.killpg(os.getpgid(job.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        with job.lock:
            job.cancelled = True
        return True
