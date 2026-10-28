"""Exact native-media inventories. A target profile is all-or-nothing.

Inventories establish packaging integrity, not platform execution or legal
approval. Windows builds still require Windows-native smoke/installer evidence.
"""

import struct

LEGAL = (
    "COPYING.LGPLv2.1",
    "LICENSE.md",
    "source-lock.json",
    "build_media_linux.py",
    "build-command.json",
)
CODEC_LEGAL = (
    "libogg-COPYING",
    "libvorbis-COPYING",
    "codecs-source-lock.json",
    "build_codecs_linux.py",
    "codecs-build-command.json",
)
LINUX_NAMES = {
    "ogg": "libogg.so.0",
    "vorbis": "libvorbis.so.0",
    "vorbisenc": "libvorbisenc.so.2",
}
WINDOWS_NAMES = {
    "ogg": "libogg-0.dll",
    "vorbis": "libvorbis-0.dll",
    "vorbisenc": "libvorbisenc-2.dll",
}
LINUX_BASE = ("media/bin/ffmpeg", "media/bin/ffprobe") + tuple(
    "media/legal/" + p for p in LEGAL
)
LINUX_CODECS = tuple("media/lib/" + p for p in LINUX_NAMES.values()) + tuple(
    "media/legal/" + p for p in CODEC_LEGAL
)
WINDOWS_BASE = ("media/bin/ffmpeg.exe", "media/bin/ffprobe.exe") + tuple(
    "media/legal/" + p.replace("build_media_linux.py", "build_media_windows.sh")
    for p in LEGAL
)
WINDOWS_CODECS = tuple("media/lib/" + p for p in WINDOWS_NAMES.values()) + tuple(
    "media/legal/" + p for p in CODEC_LEGAL if p != "build_codecs_linux.py"
)
PROFILES = tuple(
    frozenset(p)
    for p in (
        LINUX_BASE,
        LINUX_BASE + LINUX_CODECS,
        WINDOWS_BASE,
        WINDOWS_BASE + WINDOWS_CODECS,
    )
)
EXECUTABLES = frozenset((*LINUX_BASE[:2], *WINDOWS_BASE[:2]))
ELF_FILES = frozenset(
    (*LINUX_BASE[:2], *(p for p in LINUX_CODECS if p.startswith("media/lib/")))
)
PE_FILES = frozenset(
    (*WINDOWS_BASE[:2], *(p for p in WINDOWS_CODECS if p.startswith("media/lib/")))
)


def validate_native(name, value):
    if name in ELF_FILES and not value.startswith(b"\x7fELF"):
        raise ValueError("Expected Linux ELF media tool")
    if name not in PE_FILES:
        return
    if len(value) < 64 or value[:2] != b"MZ":
        raise ValueError("Expected Windows x64 PE media tool")
    offset = struct.unpack_from("<I", value, 0x3C)[0]
    if (
        offset < 64
        or offset + 26 > len(value)
        or value[offset : offset + 4] != b"PE\0\0"
    ):
        raise ValueError("Invalid Windows PE header")
    machine, sections = struct.unpack_from("<HH", value, offset + 4)
    characteristics = struct.unpack_from("<H", value, offset + 22)[0]
    magic = struct.unpack_from("<H", value, offset + 24)[0]
    dll = name.startswith("media/lib/")
    if (
        machine != 0x8664
        or not sections
        or magic != 0x20B
        or not characteristics & 2
        or bool(characteristics & 0x2000) != dll
    ):
        raise ValueError("Expected correctly typed Windows x64 PE media file")


def validate_host_profile(manifest, platform):
    """Source resource validation is cross-target; execution/freezing is not."""
    media = frozenset(name for name in manifest if name.startswith("media/"))
    if not media:
        return
    allowed = {
        "linux": (frozenset(LINUX_BASE), frozenset(LINUX_BASE + LINUX_CODECS)),
        "win32": (frozenset(WINDOWS_BASE), frozenset(WINDOWS_BASE + WINDOWS_CODECS)),
    }
    if media not in allowed.get(platform, ()):
        raise ValueError(
            "Native media profile does not match this build/runtime platform"
        )
