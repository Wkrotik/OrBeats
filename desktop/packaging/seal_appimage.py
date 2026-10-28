"""Finalize a development AppImage without rewriting the frozen backend.

linuxdeploy rewrites ELF RPATHs while assembling GTK/WebKit dependencies. That
must not modify the sealed backend or its native media resource hashes. Clone
its generated AppDir, replace ONLY the generated backend subtree from verified
frozen input, then invoke the pinned output-only compression plugin (no new ELF
rewrite pass). Never weaken resource verification or rewrite the manifest.

This is a local prototype, not a legal/ABI/clean-machine release approval.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop/backend"))
from media_profiles import LINUX_BASE, LINUX_CODECS
from resources import verify

BACKEND = Path("usr/lib/OrBeats/backend")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(root, *, generated=False):
    rows = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if generated and (
            relative == BACKEND
            or BACKEND in relative.parents
            or relative == Path(".DirIcon")
        ):
            continue
        if path.is_symlink():
            resolved = path.resolve()
            if (
                path.readlink().is_absolute()
                or not resolved.is_relative_to(root)
                or not resolved.is_file()
            ):
                raise ValueError("Unsafe AppDir/backend link: " + str(relative))
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("Non-file payload entry: " + str(relative))
        if path.name in ("ps4_config.json", "library.bin", "plugins.ini") or any(
            s in str(relative).lower()
            for s in ("libfmod", "global-metadata", "il2cppuserassemblies")
        ):
            raise ValueError("Private/proprietary input in payload")
        rows.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
        )
    if len(rows) > 10000 or sum(row["bytes"] for row in rows) > 3000000000:
        raise ValueError("Payload exceeds development packaging bounds")
    return rows


def copy_sealed_appdir(appdir, backend, output):
    appdir, backend = Path(appdir).resolve(), Path(backend).resolve()
    output = Path(output).absolute()
    if (
        output.exists()
        or output.is_symlink()
        or not output.resolve().is_relative_to(ROOT / "temp")
    ):
        raise ValueError("Use fresh project-local temp output")
    manifest = json.loads(
        (backend / "_internal/runtime/runtime-manifest.json").read_text()
    )
    verify(backend / "_internal/runtime")
    if {p for p in manifest if p.startswith("media/")} != set(
        LINUX_BASE + LINUX_CODECS
    ):
        raise ValueError("Complete Linux media and codecs required")
    for path in (backend / "orbeats-backend", appdir / "usr/bin/orbeats-desktop"):
        with path.open("rb") as stream:
            header = stream.read(64)
        if (
            len(header) < 20
            or header[:6] != b"\x7fELF\x02\x01"
            or int.from_bytes(header[18:20], "little") != 62
        ):
            raise ValueError("Expected Linux x64 executable")
    source_rows = inventory(backend)
    inventory(appdir, generated=True)
    if (
        not (appdir / "AppRun").is_file()
        or not (appdir / "orbeats-desktop.png").is_file()
    ):
        raise ValueError("Expected generated OrBeats AppDir")
    # Never follow a generated parent symlink when injecting the trusted subtree.
    if any(
        (appdir / p).is_symlink()
        for p in (Path("usr"), Path("usr/lib"), Path("usr/lib/OrBeats"))
    ):
        raise ValueError("Generated backend parent must be a real directory")

    def exclude(path, names):
        if Path(path) == appdir / "usr/lib/OrBeats":
            return ["backend"]
        return [".DirIcon"] if Path(path) == appdir else []

    shutil.copytree(appdir, output, symlinks=True, ignore=exclude)
    shutil.copytree(backend, output / BACKEND, symlinks=False)
    # Tauri's product-name .DirIcon can dangle; point at its actual bundled icon.
    (output / ".DirIcon").symlink_to("orbeats-desktop.png")
    verify(output / BACKEND / "_internal/runtime")
    if inventory(output / BACKEND) != source_rows:
        raise ValueError("Frozen backend changed during AppImage assembly")
    rows = inventory(output)
    return {
        "backend_files": len(source_rows),
        "appdir_files": len(rows),
        "backend_unchanged": True,
        "resource_hashes_valid": True,
        "files": rows,
    }


def assemble(appdir, backend, output, plugin):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Use fresh output")
    plugin = Path(plugin).resolve()
    lock = json.loads(
        (ROOT / "desktop/development/appimage-linux-tools.json").read_text()
    )
    expected = next(
        row
        for row in lock["assets"]
        if row["name"] == "linuxdeploy-plugin-appimage.AppImage"
    )
    if (
        plugin.stat().st_size != expected["bytes"]
        or digest(plugin) != expected["sha256"]
    ):
        raise ValueError("AppImage compression tool integrity failure")
    report = copy_sealed_appdir(appdir, backend, output / "OrBeats.AppDir")
    working_tool = output / "compression-tool.AppImage"
    shutil.copyfile(plugin, working_tool)
    working_tool.chmod(0o755)
    if digest(working_tool) != expected["sha256"]:
        raise ValueError("Working compression tool readback failed")
    version = json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text())[
        "version"
    ]
    image = output / f"OrBeats_{version}_amd64.AppImage"
    if image.exists():
        raise ValueError("Do not overwrite an existing AppImage")
    env = os.environ.copy()
    env.update(APPIMAGE_EXTRACT_AND_RUN="1", ARCH="x86_64", LDAI_OUTPUT=str(image))
    with (output / "compression.log").open("w") as log:
        subprocess.run(
            [
                str(working_tool),
                "--appimage-extract-and-run",
                "--appdir",
                str(output / "OrBeats.AppDir"),
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=180,
        )
    with image.open("rb") as stream:
        header = stream.read(11)
    if header[:4] != b"\x7fELF" or header[8:11] != b"AI\x02":
        raise ValueError("Expected type2 AppImage")
    report.update(
        candidate_only=True,
        published=False,
        legal_approval=False,
        baseline_compatibility=False,
        appimage=image.name,
        bytes=image.stat().st_size,
        sha256=digest(image),
        tool_sha256=expected["sha256"],
    )
    (output / "assembly-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "SHA256SUMS").write_text(report["sha256"] + "  " + image.name + "\n")
    return {k: v for k, v in report.items() if k != "files"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appdir", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plugin", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            assemble(args.appdir, args.backend, args.output, args.plugin), indent=2
        )
    )


if __name__ == "__main__":
    main()
