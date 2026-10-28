"""Linux development smoke on private Xvfb and read-only WebKit overlay.

Requires setup_linux.py and a frozen backend. Never loads the checkout console
profile. No sandbox disabling, system installs or GUI on the user's display.
"""

import argparse
import ctypes as C
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
choice = parser.add_mutually_exclusive_group(required=True)
choice.add_argument("--backend", type=Path)
choice.add_argument(
    "--appimage",
    type=Path,
    help="Test actual project-local AppImage without WebKit overlay",
)
parser.add_argument(
    "--runtime-root",
    type=Path,
    help="Prepared Ubuntu root with only baseline graphics/runtime packages, no host /usr",
)
args = parser.parse_args()
if args.runtime_root and not args.appimage:
    parser.error("--runtime-root requires --appimage")
out = args.output.resolve()
if out.exists() or not out.is_relative_to(root / "temp"):
    raise ValueError("Use fresh project-local temp output")
out.mkdir(parents=True)
frozen = args.backend.resolve() if args.backend else args.appimage.resolve()
assert frozen.is_file() and frozen.is_relative_to(root / "temp"), (
    "Use the project-local frozen prototype"
)
usr = root / ".tools/tauri-linux/root/usr"
target = root / "desktop/src-tauri/target/debug"
backend = target / "backend"
if args.backend:
    if not backend.exists():
        backend.symlink_to(frozen.parent, target_is_directory=True)
    assert backend.resolve() == frozen.parent, (
        "Do not overwrite an existing different resource backend"
    )
number = next(n for n in range(90, 110) if not Path(f"/tmp/.X11-unix/X{n}").exists())
display = ":" + str(number)
auth = out / "xauth"
auth.touch(mode=0o600)
subprocess.run(
    ["xauth", "-f", str(auth), "add", display, ".", secrets.token_hex(16)], check=True
)
env = os.environ.copy()
env.update(
    DISPLAY=display,
    XAUTHORITY=str(auth),
    GDK_BACKEND="x11",
    DCONF_PROFILE="/dev/null",
    LD_LIBRARY_PATH=str(usr / "lib"),
    XDG_DATA_HOME=str(out / "native-data"),
    XDG_CONFIG_HOME=str(out / "native-config"),
    XDG_CACHE_HOME=str(out / "native-cache"),
)
env.pop("WAYLAND_DISPLAY", None)
xlog = (out / "xvfb.log").open("w")
xvfb = subprocess.Popen(
    [
        str(usr / "bin/Xvfb"),
        display,
        "-screen",
        "0",
        "1280x960x24",
        "-nolisten",
        "tcp",
        "-auth",
        str(auth),
    ],
    env=env,
    stdout=xlog,
    stderr=xlog,
)
lib = C.CDLL("libX11.so.6")
lib.XOpenDisplay.argtypes = [C.c_char_p]
lib.XOpenDisplay.restype = C.c_void_p
lib.XDefaultRootWindow.argtypes = [C.c_void_p]
lib.XDefaultRootWindow.restype = C.c_ulong
lib.XQueryTree.argtypes = [
    C.c_void_p,
    C.c_ulong,
    C.POINTER(C.c_ulong),
    C.POINTER(C.c_ulong),
    C.POINTER(C.POINTER(C.c_ulong)),
    C.POINTER(C.c_uint),
]
lib.XFetchName.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_char_p)]


class Attributes(C.Structure):
    _fields_ = [
        ("x", C.c_int),
        ("y", C.c_int),
        ("width", C.c_int),
        ("height", C.c_int),
        ("border_width", C.c_int),
        ("depth", C.c_int),
        ("visual", C.c_void_p),
        ("root", C.c_ulong),
        ("window_class", C.c_int),
        ("bit_gravity", C.c_int),
        ("win_gravity", C.c_int),
        ("backing_store", C.c_int),
        ("backing_planes", C.c_ulong),
        ("backing_pixel", C.c_ulong),
        ("save_under", C.c_int),
        ("colormap", C.c_ulong),
        ("map_installed", C.c_int),
        ("map_state", C.c_int),
        ("all_event_masks", C.c_long),
        ("your_event_mask", C.c_long),
        ("do_not_propagate_mask", C.c_long),
        ("override_redirect", C.c_int),
        ("screen", C.c_void_p),
    ]


lib.XGetWindowAttributes.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(Attributes)]
lib.XFree.argtypes = [C.c_void_p]
app = None
d = None
try:
    for _ in range(100):
        if xvfb.poll() is not None:
            raise RuntimeError("Private X server failed")
        if Path(f"/tmp/.X11-unix/X{number}").exists():
            break
        time.sleep(0.05)
    os.environ["XAUTHORITY"] = str(auth)
    d = lib.XOpenDisplay(display.encode())
    assert d
    log = (out / "native-window.log").open("w")
    command = [
        "bwrap",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
        "--overlay-src",
        "/usr/lib",
        "--overlay-src",
        str(usr / "lib"),
        "--ro-overlay",
        "/usr/lib",
        "--bind",
        str(out),
        str(out),
        "--tmpfs",
        "/tmp",
        "--ro-bind",
        "/tmp/.X11-unix",
        "/tmp/.X11-unix",
        str(target / "orbeats-desktop"),
    ]
    if args.appimage:
        env.pop("LD_LIBRARY_PATH", None)
        command = [
            "bwrap",
            "--ro-bind",
            "/",
            "/",
            "--dev-bind",
            "/dev",
            "/dev",
            "--proc",
            "/proc",
            "--bind",
            str(out),
            str(out),
            "--tmpfs",
            "/tmp",
            "--ro-bind",
            "/tmp/.X11-unix",
            "/tmp/.X11-unix",
            str(frozen),
            "--appimage-extract-and-run",
        ]
    if args.runtime_root:
        runtime = args.runtime_root.resolve()
        if (
            not runtime.is_relative_to(root / ".tools")
            or not (runtime / "orbeats-image-lock.json").is_file()
        ):
            raise ValueError("Use prepared project-local runtime root")
        image = out / "tested.AppImage"
        image.hardlink_to(frozen)
        for key in ("XAUTHORITY", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
            env[key] = env[key].replace(str(out), "/work")
        env["HOME"] = "/work"
        env["PATH"] = "/usr/bin:/bin"
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        command = [
            "bwrap",
            "--ro-bind",
            str(runtime),
            "/",
            # OCI layers omit runtime DNS configuration. Supply only normal
            # host network configuration, never host /usr or development libs.
            "--ro-bind",
            "/etc/resolv.conf",
            "/etc/resolv.conf",
            "--ro-bind",
            "/etc/hosts",
            "/etc/hosts",
            "--dev-bind",
            "/dev",
            "/dev",
            "--proc",
            "/proc",
            "--bind",
            str(out),
            "/work",
            "--tmpfs",
            "/tmp",
            "--ro-bind",
            "/tmp/.X11-unix",
            "/tmp/.X11-unix",
            "--chdir",
            "/work",
            "/work/tested.AppImage",
            "--appimage-extract-and-run",
        ]
    app = subprocess.Popen(command, env=env, stdout=log, stderr=log)

    def windows(*, visible_only=False):
        result = []
        rr = C.c_ulong()
        parent = C.c_ulong()
        count = C.c_uint()
        children = C.POINTER(C.c_ulong)()
        assert lib.XQueryTree(
            d,
            lib.XDefaultRootWindow(d),
            C.byref(rr),
            C.byref(parent),
            C.byref(children),
            C.byref(count),
        )
        for i in range(count.value):
            name = C.c_char_p()
            if lib.XFetchName(d, children[i], C.byref(name)) and name.value:
                text = name.value.decode(errors="replace")
                if text == "OrBeats":
                    attributes = Attributes()
                    if not visible_only or (
                        lib.XGetWindowAttributes(d, children[i], C.byref(attributes))
                        and attributes.map_state == 2
                    ):
                        result.append(children[i])
                lib.XFree(name)
        if children:
            lib.XFree(children)
        return result

    ready = False
    for _ in range(150):
        if app.poll() is not None:
            raise RuntimeError(
                "Native shell exited code "
                + str(app.returncode)
                + "; inspect native-window.log"
            )
        found = windows()
        visible = windows(visible_only=True)
        if len(found) >= 2 and visible == [max(found)]:
            ready = True
            break
        time.sleep(0.2)
    assert ready, "Main authenticated window did not appear"
    time.sleep(3)
    visible = windows(visible_only=True)
    assert len(visible) == 1 and visible == [max(windows())], (
        "Startup status resurfaced or main window stayed hidden"
    )
    from PIL import ImageGrab

    image = ImageGrab.grab(xdisplay=display)
    image.save(out / "native-window.png")

    class Client(C.Structure):
        _fields_ = [
            ("type", C.c_int),
            ("serial", C.c_ulong),
            ("send_event", C.c_int),
            ("display", C.c_void_p),
            ("window", C.c_ulong),
            ("message_type", C.c_ulong),
            ("format", C.c_int),
            ("data", C.c_long * 5),
        ]

    class Event(C.Union):
        _fields_ = [("client", Client), ("pad", C.c_long * 24)]

    lib.XInternAtom.argtypes = [C.c_void_p, C.c_char_p, C.c_int]
    lib.XInternAtom.restype = C.c_ulong
    lib.XSendEvent.argtypes = [
        C.c_void_p,
        C.c_ulong,
        C.c_int,
        C.c_long,
        C.POINTER(Event),
    ]
    lib.XFlush.argtypes = [C.c_void_p]
    event = Event()
    event.client.type = 33
    event.client.display = d
    event.client.window = visible[0]
    event.client.message_type = lib.XInternAtom(d, b"WM_PROTOCOLS", 0)
    event.client.format = 32
    event.client.data[0] = lib.XInternAtom(d, b"WM_DELETE_WINDOW", 0)
    assert lib.XSendEvent(d, visible[0], 0, 0, C.byref(event))
    lib.XFlush(d)
    hidden = False
    closing_visibility = []
    deadline = time.monotonic() + 20
    while app.poll() is None and time.monotonic() < deadline:
        current = windows(visible_only=True)
        closing_visibility.append(len(current))
        if not current:
            hidden = True
        elif hidden:
            raise AssertionError("An extra window resurfaced while the backend drained")
        time.sleep(0.01)
    assert app.wait(timeout=1) == 0, "Native shell did not close cleanly"
    assert not windows(visible_only=True), "Window survived clean close"
    states = list((out / "native-data").rglob("queue.json"))
    assert len(states) == 1
    state = json.loads(states[0].read_text())
    assert state["paused"] and state["active"] is None and not state["pending"]
    report = {
        "native_shell": True,
        "private_x_display": True,
        "authenticated_main_window_created": True,
        "screenshot": str((out / "native-window.png").relative_to(root)),
        "close_via_wm": True,
        "single_visible_authenticated_window": True,
        "no_resurfaced_close_window": True,
        "closing_visible_window_counts": closing_visibility,
        "backend_drained_and_exited": True,
        "fresh_state_queue_paused": True,
        "ps4_writes": False,
        "host_install": False,
        "actual_appimage": bool(args.appimage),
        "isolated_runtime_root": bool(args.runtime_root),
        "host_usr_mounted": not bool(args.runtime_root),
        "runtime_dns_configuration": bool(args.runtime_root),
        "webkit_overlay": not bool(args.appimage),
        "fuse_required": False if args.appimage else None,
    }
    (out / "native-smoke-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    if app is not None and app.poll() is None:
        print(
            "ERROR: native test still running; do not assume shutdown success, inspect owned process",
            app.pid,
        )
    if d:
        lib.XCloseDisplay.argtypes = [C.c_void_p]
        lib.XCloseDisplay(d)
    if app is None or app.poll() is not None:
        xvfb.terminate()
        xvfb.wait(timeout=10)
