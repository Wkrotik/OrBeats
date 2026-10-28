"""Stage a target-specific installer candidate; never execute CI or publish.

The emitted config is an input to a native Tauri build, not proof that an
installer runs. Legal review, supported-OS ABI and install/upgrade tests remain
explicit release gates. All outputs are isolated under this checkout's temp/.
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop/backend"))
from media_profiles import (
    LINUX_BASE,
    LINUX_CODECS,
    WINDOWS_BASE,
    WINDOWS_CODECS,
    validate_native,
)
from resources import verify

TARGETS = {
    "linux-x64": {
        "executable": "orbeats-backend",
        "profile": frozenset(LINUX_BASE + LINUX_CODECS),
        "magic": b"\x7fELF",
    },
    "windows-x64": {
        "executable": "orbeats-backend.exe",
        "profile": frozenset(WINDOWS_BASE + WINDOWS_CODECS),
        "magic": b"MZ",
    },
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stage(target, backend, output):
    if target not in TARGETS:
        raise ValueError("Unknown platform")
    backend, output = Path(backend).resolve(), Path(output).absolute()
    if (
        output.exists()
        or output.is_symlink()
        or not output.resolve().is_relative_to(ROOT / "temp")
    ):
        raise ValueError("Use fresh project-local temp output")
    spec = TARGETS[target]
    exe = backend / spec["executable"]
    runtime = backend / "_internal/runtime"
    if not exe.is_file():
        raise ValueError("Frozen helper does not match target platform")
    verify(runtime)
    with exe.open("rb") as stream:
        header = stream.read(4096)
    if not header.startswith(spec["magic"]):
        raise ValueError("Frozen helper does not match target platform")
    if target == "linux-x64" and (
        len(header) < 20
        or header[4:6] != b"\x02\x01"
        or int.from_bytes(header[18:20], "little") != 62
    ):
        raise ValueError("Expected Linux x86_64 frozen helper")
    if target == "windows-x64":
        validate_native("media/bin/ffmpeg.exe", header)
    manifest = json.loads((runtime / "runtime-manifest.json").read_text())
    if {p for p in manifest if p.startswith("media/")} != spec["profile"]:
        raise ValueError("Installer requires the complete native media+codec profile")
    files = []
    for path in sorted(backend.rglob("*")):
        if path.is_symlink() and (
            path.readlink().is_absolute()
            or not path.resolve().is_relative_to(backend)
            or not path.resolve().is_file()
        ):
            raise ValueError("Unsafe payload link")
        if not path.is_file():
            continue
        name = path.relative_to(backend).as_posix()
        if path.name in ("ps4_config.json", "library.bin", "plugins.ini") or any(
            p in name.lower()
            for p in ("libfmod", "global-metadata", "il2cppuserassemblies")
        ):
            raise ValueError("Private/proprietary input in payload")
        files.append(
            {
                "path": "backend/" + name,
                "bytes": path.stat().st_size,
                "sha256": sha(path),
            }
        )
    if len(files) > 10000 or sum(r["bytes"] for r in files) > 2000000000:
        raise ValueError("Payload exceeds staging bounds")
    config = json.loads(Path(__file__).with_name(target + ".json").read_text())
    config["bundle"]["resources"] = {str(output / "backend") + "/": "backend/"}
    output.mkdir(parents=True)
    # Flatten verified internal aliases; installers never receive escaping links.
    shutil.copytree(backend, output / "backend", symlinks=False)
    verify(output / "backend/_internal/runtime")
    for row in files:
        if sha(output / row["path"]) != row["sha256"]:
            raise ValueError("Staged helper readback failed")
    (output / "tauri-candidate.json").write_text(json.dumps(config, indent=2) + "\n")
    plan = {
        "schema": 1,
        "target": target,
        "candidate_only": True,
        "published": False,
        "native_build_required": True,
        "legal_review_complete": False,
        "files": files,
        "install_config": "tauri-candidate.json",
        "open_gates": [
            "native target build",
            "supported OS ABI",
            "dependency/source/license review",
            "install, upgrade, uninstall and recovery tests",
            "platform signing/reputation policy",
        ],
    }
    (output / "candidate-manifest.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = stage(args.target, args.backend, args.output)
    print(
        json.dumps(
            {
                "target": result["target"],
                "files": len(result["files"]),
                "candidate_only": True,
                "native_build_required": True,
                "published": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
