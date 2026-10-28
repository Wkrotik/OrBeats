"""Bind fsb5's three Xiph codecs to reviewed app-owned files, never discovery.

Called only after runtime inventory verification, before any Vorbis consumer.
Do not globally monkeypatch ctypes discovery or fall back if bundled loading fails.
"""

import ctypes
import sys
from pathlib import Path

from media_profiles import LINUX_NAMES, WINDOWS_NAMES

NAMES = LINUX_NAMES  # Backwards-compatible Linux diagnostic fixture name.
_ACTIVE = None


def activate(root):
    global _ACTIVE
    directory = Path(root).resolve() / "media/lib"
    if not directory.exists():
        return {}
    names = (
        LINUX_NAMES
        if sys.platform == "linux"
        else WINDOWS_NAMES
        if sys.platform == "win32"
        else None
    )
    if names is None:
        raise RuntimeError("No codec profile for this platform")
    actual = {p.name for p in directory.iterdir()}
    if actual != set(names.values()):
        raise ValueError("Codec payload does not match native platform")
    paths = {key: directory / value for key, value in names.items()}
    if directory.is_symlink() or any(
        p.is_symlink() or not p.is_file() for p in paths.values()
    ):
        raise ValueError("Incomplete or linked bundled codec profile")
    if _ACTIVE is not None:
        if _ACTIVE["paths"] != paths:
            raise RuntimeError("Codec profile already activated from another runtime")
        return _ACTIVE["handles"]
    if "fsb5.vorbis" in sys.modules:
        raise RuntimeError("Vorbis imported before bundled codec activation")
    # SONAME dependencies bind to these exact files loaded first in order.
    handles = {
        name: ctypes.CDLL(str(path), winmode=0x00000900)
        if sys.platform == "win32"
        else ctypes.CDLL(str(path), mode=ctypes.RTLD_LOCAL)
        for name, path in paths.items()
    }
    import fsb5.utils

    original = fsb5.utils.load_lib

    def owned_load(*names):
        # The first requested name is authoritative. No fallback to the host or
        # another codec when one of our bundled libraries fails.
        if names and names[0] in handles:
            return handles[names[0]]
        return original(*names)

    fsb5.utils.load_lib = owned_load
    _ACTIVE = {"paths": paths, "handles": handles}
    return handles


def check(root, source):
    """Offline frozen-runtime proof; intentionally make host discovery unusable."""
    import ctypes.util
    import hashlib
    import json
    import re

    def deny_discovery(*args, **kwargs):
        raise RuntimeError("Host codec discovery forbidden in isolation check")

    ctypes.util.find_library = deny_discovery
    handles = activate(root)
    if set(handles) != set(NAMES):
        raise ValueError("Diagnostic requires complete bundled codec profile")
    import fsb5.vorbis
    import vorbis_audio

    for name, binding in [
        ("ogg", fsb5.vorbis.ogg),
        ("vorbis", fsb5.vorbis.vorbis),
        ("vorbisenc", fsb5.vorbis.vorbisenc),
    ]:
        if binding is not handles[name]:
            raise ValueError("Codec did not bind to owned library: " + name)
    with Path(source).open("rb") as stream:
        value = stream.read(20000001)
    if not value.startswith(b"OggS") or len(value) > 20000000:
        raise ValueError("Use a bounded original Vorbis Ogg fixture")
    # The identification packet declares its sample rate at28header+segment...
    rate = None
    for candidate in (44100, 48000):
        try:
            vorbis_audio.parse_ogg(value, sample_rate=candidate)
            rate = candidate
            break
        except ValueError:
            pass
    if rate is None:
        raise ValueError("Unsupported Vorbis fixture rate")
    fsb, frames, crc = vorbis_audio.build_fsb(value, sample_rate=rate)
    vorbis_audio.verify_fsb(fsb, frames, sample_rate=rate)
    # Linux diagnostic also rejects accidentally loaded host Xiph dependencies.
    if sys.platform == "win32":
        # Search restricted to DLL directory+System32, then independently inspect
        # the actual module filename. No DLL search on PATH/CWD.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        get_name = kernel.GetModuleFileNameW
        get_name.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_name.restype = ctypes.c_uint32
        for handle in handles.values():
            buffer = ctypes.create_unicode_buffer(32768)
            size = get_name(handle._handle, buffer, len(buffer))
            if (
                not 0 < size < len(buffer)
                or Path(buffer.value).resolve() != Path(handle._name).resolve()
            ):
                raise ValueError("Wrong Windows codec module loaded")
        maps = ""
    else:
        maps = Path("/proc/self/maps").read_text()
    loaded = {
        line.split()[-1]
        for line in maps.splitlines()
        if re.search(r"/lib(?:ogg|vorbis(?:enc)?)\.so", line)
    }
    expected = {str(Path(handle._name).resolve()) for handle in handles.values()}
    if sys.platform == "linux" and loaded != expected:
        raise ValueError("Unexpected Xiph mapping in process")
    print(
        json.dumps(
            {
                "bundled_codecs_only": True,
                "host_discovery_disabled": True,
                "rate": rate,
                "frames": frames,
                "fsb_bytes": len(fsb),
                "codebook_crc": crc,
                "source_sha256": hashlib.sha256(value).hexdigest(),
                "independent_decode": True,
                "console_writes": False,
            },
            indent=2,
        )
    )
