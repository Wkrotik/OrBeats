"""Curate release assets locally. Never publish or change repository visibility.

A partial stage is explicitly reported as incomplete, never release approval.
Checksums and plugin versions are derived from actual bytes; ZIPs, source-tree
copies, logs and profiles are not release assets. Legal/target lifecycle review
is separate from this file-integrity gate.
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orbeats/webapp"), str(ROOT / "orbeats/tools")]
import extras_manager
import library_manager
import release_updates


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stage(output, main, extras, appimage=None, windows=None):
    output = Path(output).absolute()
    if (
        output.exists()
        or output.is_symlink()
        or not output.resolve().is_relative_to(ROOT / "temp")
    ):
        raise ValueError("Use a fresh project-local temp output")
    version = json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text())[
        "version"
    ]
    if version != release_updates.APP_VERSION:
        raise ValueError("Desktop/feed version mismatch")
    records, files = {}, {}
    for kind, source, decoder in [
        ("main", main, library_manager.binary_version),
        ("extras", extras, extras_manager.version),
    ]:
        source = Path(source)
        if (
            source.is_symlink()
            or not source.is_file()
            or not 1 <= source.stat().st_size <= 2000000
        ):
            raise ValueError("Invalid plugin input")
        blob = source.read_bytes()
        plugin_version = decoder(library_manager.elf_from_fself(blob))
        if not plugin_version:
            raise ValueError("Unrecognized plugin")
        name = release_updates.NAMES[kind]
        records[kind] = {
            "asset": name,
            "version": plugin_version,
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }
        files[name] = (source, records[kind]["sha256"])
    for source, name, target in [
        (appimage, f"OrBeats_{version}_amd64.AppImage", "linux"),
        (windows, f"OrBeats_{version}_x64-setup.exe", "windows"),
    ]:
        if source is None:
            continue
        source = Path(source)
        if (
            source.is_symlink()
            or not source.is_file()
            or not 1000000 <= source.stat().st_size <= 500000000
        ):
            raise ValueError("Invalid desktop asset input")
        with source.open("rb") as stream:
            header = stream.read(4096)
        if target == "linux":
            valid = (
                header[:6] == b"\x7fELF\x02\x01"
                and header[8:11] == b"AI\x02"
                and int.from_bytes(header[18:20], "little") == 62
            )
        else:
            offset = int.from_bytes(header[60:64], "little")
            valid = (
                header[:2] == b"MZ"
                and offset <= len(header) - 6
                and header[offset : offset + 4] == b"PE\0\0"
            )
            # NSIS's installer stub may be PE32 even for an x64 application;
            # target-native CI, not this outer stub, verifies the bundled helper.
        if not valid:
            raise ValueError("Unexpected desktop asset format")
        files[name] = (source, digest(source))
    manifest = {"schema": 1, "app": version, "plugins": records}
    output.mkdir(parents=True)
    for name, (source, expected) in files.items():
        shutil.copyfile(source, output / name)
        if digest(output / name) != expected:
            raise ValueError("Release asset readback failure")
    (output / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    sums = []
    for path in sorted(output.iterdir()):
        with path.open("rb") as stream:
            sums.append(
                hashlib.file_digest(stream, "sha256").hexdigest() + "  " + path.name
            )
    (output / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    return {
        "version": version,
        "assets": sorted(p.name for p in output.iterdir()),
        "complete_platform_set": bool(appimage and windows),
        "published": False,
        "legal_or_lifecycle_approval": False,
        "no_zip": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--extras", type=Path, required=True)
    parser.add_argument("--appimage", type=Path)
    parser.add_argument("--windows", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            stage(args.output, args.main, args.extras, args.appimage, args.windows),
            indent=2,
        )
    )
