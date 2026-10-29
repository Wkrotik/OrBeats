"""Owned desktop backend and frozen-task entry point. No external service reuse."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import runpy
import signal
import socket
import sys
import threading
from pathlib import Path

# Reserve stdout for the parent's single readiness record. All application output
# (including legacy pipeline banners) goes to stderr in server mode.
PRIVATE_STDOUT = sys.stdout
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from resources import install, verify
from session import Session
from storage import atomic_json, ownership


def runtime_path(root):
    from media_profiles import validate_host_profile

    validate_host_profile(
        json.loads((root / "runtime-manifest.json").read_text()), sys.platform
    )
    media = root / "media/bin"
    if media.is_dir():
        # Both server and frozen child tasks select reviewed bundled tools first.
        current = os.environ.get("PATH", "").split(os.pathsep)
        os.environ["PATH"] = os.pathsep.join(
            [str(media), *[p for p in current if p and p != str(media)]]
        )
    sys.path[:0] = [
        str(root / "webapp"),
        str(root / "tools"),
        str(root / "development/scripts"),
    ]
    os.environ["ORBEATS_RUNTIME_ROOT"] = str(root)
    from media_codecs import activate

    activate(root)


def task(args):
    # Frozen Python ignores -u; both ends of the job pipe use explicit UTF-8.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(
            encoding="utf-8",
            errors="backslashreplace",
            line_buffering=True,
            write_through=True,
        )
    root = Path(os.environ["ORBEATS_RUNTIME_ROOT"]).resolve()
    verify(root)
    runtime_path(root)
    from runtime_dispatch import TASKS

    if len(args) < 2 or args[0] not in TASKS or args[1] != "--":
        raise ValueError("Invalid desktop task invocation")
    script = root / TASKS[args[0]]
    sys.argv = [str(script), *args[2:]]
    runpy.run_path(str(script), run_name="__main__")


async def serve(root, state):
    import uvicorn

    runtime_path(root)
    import server as web
    from adapters import config, paths

    if not paths.CONFIG_PATH.exists():
        # New profile only. Never import checkout credentials or auto-target a PS4.
        cfg = config.build_wizard_config(state / "game_data", "127.0.0.1")
        cfg["paths"]["game_data_dir"] = str(state / "game_data")
        atomic_json(paths.CONFIG_PATH, cfg)
    snapshot = state / "queue.json"
    if snapshot.exists():
        if snapshot.is_symlink() or snapshot.stat().st_size > 2000000:
            raise ValueError("Invalid desktop queue snapshot")
        web.INSTALL_QUEUE.restore(json.loads(snapshot.read_bytes()))

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    origin = "http://127.0.0.1:" + str(listener.getsockname()[1])
    session = Session(origin)
    web.app.middleware("http")(session.guard)
    stopped = threading.Event()
    emitted = False

    def control():
        try:
            # STOP, malformed input or ordinary parent death (EOF) all mean stop.
            sys.stdin.buffer.readline(4097)
        finally:
            session.begin_shutdown()
            stopped.set()

    threading.Thread(target=control, daemon=True, name="desktop-parent-pipe").start()

    class OwnedServer(uvicorn.Server):
        @contextlib.contextmanager
        def capture_signals(self):
            previous = {}

            def graceful(*_):
                session.begin_shutdown()
                stopped.set()

            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, graceful)
            try:
                yield
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)

    config_uvicorn = uvicorn.Config(
        web.app, log_level="warning", access_log=False, timeout_graceful_shutdown=None
    )
    service = OwnedServer(config_uvicorn)

    async def lifecycle():
        nonlocal emitted
        while not service.should_exit:
            if stopped.is_set():
                # Re-pause until admitted requests have drained: an earlier
                # queue-start request might still be returning from its handler.
                web.INSTALL_QUEUE.pause()
                status = web.INSTALL_QUEUE.status()
                if session.drained(
                    runner_busy=web.RUNNER.is_busy(),
                    queue_active=status["active"] is not None,
                ):
                    if not status["paused"]:
                        raise RuntimeError("Queue not paused at shutdown")
                    atomic_json(snapshot, status)
                    service.should_exit = True
                    return
            elif service.started and not emitted:
                PRIVATE_STDOUT.write(json.dumps(session.readiness()) + "\n")
                PRIVATE_STDOUT.flush()
                emitted = True
            await asyncio.sleep(0.05)

    watcher = asyncio.create_task(lifecycle())
    try:
        await service.serve(sockets=[listener])
        # Signals must not bypass transactional draining. Disable uvicorn signal
        # handlers below; the owned parent controls ordinary STOP/EOF shutdown.
        if not stopped.is_set():
            raise RuntimeError(
                "Desktop backend stopped without graceful parent request"
            )
        await watcher
    finally:
        listener.close()
        if not watcher.done():
            watcher.cancel()


def main():
    if sys.argv[1:2] == ["--desktop-check-codecs"]:
        if len(sys.argv) != 3:
            raise ValueError("Use --desktop-check-codecs ORIGINAL_VORBIS_OGG")
        root = Path(os.environ["ORBEATS_RUNTIME_ROOT"]).resolve()
        verify(root)
        # Match production task setup, including the reviewed bundled FFmpeg
        # on PATH for the48kHz verification subprocess. No host tool fallback.
        runtime_path(root)
        from media_codecs import check

        check(root, Path(sys.argv[2]))
        return
    if sys.argv[1:2] == ["--desktop-task"]:
        task(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument(
        "--resources",
        type=Path,
        default=Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        / "runtime",
    )
    args = parser.parse_args()
    state = args.state_dir.absolute()
    os.environ["ORBEATS_STATE_DIR"] = str(state)
    with ownership(state), contextlib.redirect_stdout(sys.stderr):
        (state / "webapp").mkdir(exist_ok=True)
        root = install(args.resources, state)
        # Runtime code files remain immutable/inventory-verifiable. All writable
        # app state lives outside versioned runtime resources.
        os.chdir(state)
        asyncio.run(serve(root, state))


if __name__ == "__main__":
    main()
