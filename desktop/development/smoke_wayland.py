"""Private nested-Wayland regression for the GTK zero/empty cursor crash.

Runs Weston X11/pixman on private authenticated Xvfb, never the user's display.
Needs project-local Ubuntu baseline Weston and setup_linux.py Xvfb. Each actual
AppImage receives a fresh keyfile settings backend with size=0/theme=''. Synthetic
pointer/key input stays on that private display. No console profile/FTP is used.
"""

import argparse
import ctypes as C
import json
import os
import secrets
import signal
import subprocess
import time
from pathlib import Path

from setup_linux_baseline import command

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appimage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-cursor-crash", action="store_true")
    args = parser.parse_args()
    image = args.appimage.resolve()
    out = args.output.absolute()
    if (
        out.exists()
        or out.is_symlink()
        or not out.resolve().is_relative_to(ROOT / "temp")
    ):
        raise ValueError("Use fresh project-local test output")
    if not image.is_relative_to(ROOT) or not image.is_file():
        raise ValueError("Use project-local candidate")
    out.mkdir(parents=True)
    runtime = out / "runtime"
    runtime.mkdir(mode=0o700)
    (out / "data").mkdir()
    (out / "cache").mkdir()
    config = out / "config/glib-2.0/settings"
    config.mkdir(parents=True)
    (config / "keyfile").write_text(
        "[org/gnome/desktop/interface]\ncursor-size=0\ncursor-theme=''\n"
    )
    keyfile_before = (config / "keyfile").read_bytes()
    number = next(
        n for n in range(90, 110) if not Path(f"/tmp/.X11-unix/X{n}").exists()
    )
    display = ":" + str(number)
    auth = out / "xauth"
    auth.touch(mode=0o600)
    subprocess.run(
        ["xauth", "-f", str(auth), "add", display, ".", secrets.token_hex(16)],
        check=True,
    )
    env = os.environ.copy()
    env.update(DISPLAY=display, XAUTHORITY=str(auth))
    xvfb_env = env | {"LD_LIBRARY_PATH": str(ROOT / ".tools/tauri-linux/root/usr/lib")}
    lib = C.CDLL("libX11.so.6")
    lib.XOpenDisplay.argtypes = [C.c_char_p]
    lib.XOpenDisplay.restype = C.c_void_p
    lib.XFlush.argtypes = [C.c_void_p]
    lib.XWarpPointer.argtypes = [
        C.c_void_p,
        C.c_ulong,
        C.c_ulong,
        C.c_int,
        C.c_int,
        C.c_uint,
        C.c_uint,
        C.c_int,
        C.c_int,
    ]
    lib.XDefaultRootWindow.argtypes = [C.c_void_p]
    lib.XDefaultRootWindow.restype = C.c_ulong
    lib.XStringToKeysym.argtypes = [C.c_char_p]
    lib.XStringToKeysym.restype = C.c_ulong
    lib.XKeysymToKeycode.argtypes = [C.c_void_p, C.c_ulong]
    lib.XKeysymToKeycode.restype = C.c_ubyte
    lib.XCloseDisplay.argtypes = [C.c_void_p]
    xtst = C.CDLL("libXtst.so.6")
    xtst.XTestFakeKeyEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
    xtst.XTestFakeMotionEvent.argtypes = [
        C.c_void_p,
        C.c_int,
        C.c_int,
        C.c_int,
        C.c_ulong,
    ]
    xtst.XTestFakeButtonEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
    xvfb = weston = app = None
    d = None
    try:
        with (out / "xvfb.log").open("w") as log:
            xvfb = subprocess.Popen(
                [
                    str(ROOT / ".tools/tauri-linux/root/usr/bin/Xvfb"),
                    display,
                    "-screen",
                    "0",
                    "1280x960x24",
                    "-nolisten",
                    "tcp",
                    "-auth",
                    str(auth),
                ],
                env=xvfb_env,
                stdout=log,
                stderr=log,
            )
        os.environ["XAUTHORITY"] = str(auth)
        for _ in range(100):
            if xvfb.poll() is not None:
                raise RuntimeError("Private Xvfb failed")
            d = lib.XOpenDisplay(display.encode())
            if d:
                break
            time.sleep(0.05)
        if not d:
            raise RuntimeError("Private X display unavailable")
        cmd = command(
            ROOT / ".tools/ubuntu2204-baseline-01",
            [
                "/usr/bin/env",
                "DISPLAY=" + display,
                "XAUTHORITY=/work/xauth",
                "XDG_RUNTIME_DIR=/work/runtime",
                "/usr/bin/weston",
                "--backend=x11-backend.so",
                "--use-pixman",
                "--width=1280",
                "--height=960",
                "--socket=wayland-test",
                "--idle-time=0",
                "--no-config",
                "--log=/work/weston.log",
            ],
            work=out,
        )
        # Weston pixman and the private X server must share IPC for XShm.
        cmd.remove("--unshare-ipc")
        offset = cmd.index("--")
        cmd[offset:offset] = ["--ro-bind", "/tmp/.X11-unix", "/tmp/.X11-unix"]
        with (out / "weston-stdout.log").open("w") as log:
            weston = subprocess.Popen(cmd, stdout=log, stderr=log)
        for _ in range(100):
            if weston.poll() is not None:
                raise RuntimeError("Private Weston failed")
            if (runtime / "wayland-test").exists():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("Private Wayland socket unavailable")
        env.update(
            XDG_RUNTIME_DIR=str(runtime),
            WAYLAND_DISPLAY="wayland-test",
            GDK_BACKEND="wayland",
            XDG_DATA_HOME=str(out / "data"),
            XDG_CONFIG_HOME=str(out / "config"),
            XDG_CACHE_HOME=str(out / "cache"),
            GSETTINGS_BACKEND="keyfile",
            WAYLAND_DEBUG="client",
            LIBGL_ALWAYS_SOFTWARE="1",
            XCURSOR_SIZE="24",
            XCURSOR_THEME="default",
        )
        env.pop("LD_LIBRARY_PATH", None)
        with (out / "app.log").open("w") as log:
            app = subprocess.Popen(
                [str(image), "--appimage-extract-and-run"],
                env=env,
                stdout=log,
                stderr=log,
            )
        main_seen = False
        for tick in range(200):
            if app.poll() is not None:
                break
            text = (out / "app.log").read_text(errors="replace")
            main_seen = main_seen or text.count('set_title("OrBeats")') >= 2
            x, y = [(400, 400), (600, 300), (800, 500), (500, 500)][tick % 4]
            xtst.XTestFakeMotionEvent(d, -1, x, y, 0)
            lib.XFlush(d)
            if main_seen and tick >= 80:
                break
            time.sleep(0.1)
        text = (out / "app.log").read_text(errors="replace")
        if args.expect_cursor_crash:
            assert (
                app.poll() is not None
                and "cursor_theme_name" in text
                and "assertion failed" in text
            ), "Original cursor crash was not reproduced"
            report = {
                "old_cursor_assertion_reproduced": True,
                "exit_code": app.returncode,
            }
        else:
            assert app.poll() is None and main_seen, (
                "Candidate did not survive native Wayland pointer input; inspect app.log"
            )
            assert "cursor_theme_name" not in text and "Gdk:ERROR" not in text
            assert "applied process-local fallback" in text
            assert "wl_pointer#" in text and ".motion(" in text
            from PIL import ImageGrab

            ImageGrab.grab(xdisplay=display).save(out / "native-wayland.png")
            # The nested pixman compositor does not reliably route a CSD-close
            # click. This regression tests pointer survival, not normal WM close.
            # Terminate ONLY this owned fresh synthetic parent; backend pipe EOF
            # must drain and release ownership. Never signal a user's app/backend.
            descendants = [app.pid]
            native = []
            for pid in descendants:
                proc = Path("/proc") / str(pid)
                try:
                    if (proc / "comm").read_text().strip() == "orbeats-desktop":
                        native.append(pid)
                    descendants.extend(
                        int(child)
                        for child in (proc / f"task/{pid}/children").read_text().split()
                    )
                except FileNotFoundError:
                    pass
            assert len(native) == 1, "Expected one owned synthetic native parent"
            os.kill(native[0], signal.SIGTERM)
            app.wait(timeout=20)
            import fcntl

            locks = list((out / "data").rglob("instance.lock"))
            assert len(locks) == 1
            released = False
            for _ in range(100):
                with locks[0].open("a+b") as owned:
                    try:
                        fcntl.flock(owned, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(owned, fcntl.LOCK_UN)
                        released = True
                    except BlockingIOError:
                        pass
                if released:
                    break
                time.sleep(0.05)
            assert released, "Owned backend did not drain after synthetic parent exit"
            queues = list((out / "data").rglob("queue.json"))
            assert len(queues) == 1
            q = json.loads(queues[0].read_text())
            assert q["paused"] and not q["pending"] and q["active"] is None
            report = {
                "native_wayland_main_window": True,
                "private_weston_and_xvfb": True,
                "zero_size_empty_theme": True,
                "pointer_input_survived": True,
                "initial_cursor_warnings": text.count("Failed to load cursor theme"),
                "synthetic_parent_eof_backend_drained": True,
                "normal_wayland_close_tested": False,
                "fresh_queue_paused": True,
            }
        assert (config / "keyfile").read_bytes() == keyfile_before, (
            "Test desktop preferences were modified"
        )
        report.update(settings_unchanged=True, ps4_writes=False, host_install=False)
        (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        if app is not None and app.poll() is None:
            # Only this fresh synthetic test process, never a user app/profile.
            # EOF drains its owned backend, which has no pending console work.
            app.terminate()
            app.wait(timeout=20)
        if weston is not None and weston.poll() is None:
            weston.terminate()
            weston.wait(timeout=10)
        if d:
            lib.XCloseDisplay(d)
        if xvfb is not None and xvfb.poll() is None:
            xvfb.terminate()
            xvfb.wait(timeout=10)


if __name__ == "__main__":
    main()
