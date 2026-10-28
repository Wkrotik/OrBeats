"""Extend a verified minimal-media payload with pinned source-built Xiph codecs.

Development staging only. Linux/glibc baseline, all other dependencies and release
legal review remain separate gates; no host library discovery or install steps.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop/backend"))
from resources import MEDIA_FILES, content, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    out, original = args.output.resolve(), args.media.resolve()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("Linux x86_64 profile only")
    if (
        out.exists()
        or not out.is_relative_to(ROOT / "temp")
        or not 1 <= args.jobs <= 16
    ):
        raise ValueError("Use fresh project-local temp output and jobs1..16")
    expected = {p.removeprefix("media/") for p in MEDIA_FILES}
    inventory = json.loads(content(original, "manifest.json"))
    actual = {
        p.relative_to(original).as_posix() for p in original.rglob("*") if p.is_file()
    }
    if set(inventory) != expected or actual != expected | {"manifest.json"}:
        raise ValueError("Expected reviewed base media profile")
    for name in expected:
        if digest(content(original, name)) != inventory[name]:
            raise ValueError("Base media changed: " + name)
    patch = ROOT / ".venv/bin/patchelf"
    if importlib.metadata.version("patchelf") != "0.17.2.4" or not patch.is_file():
        raise ValueError("Use project-local pinned patchelf0.17.2.4")
    out.mkdir(parents=True)
    prefix = out / "deps"
    commands = [{"patchelf_distribution": "0.17.2.4", "rpath_action": "--remove-rpath"}]
    environment = os.environ.copy()
    for key in (
        "LD_LIBRARY_PATH",
        "CFLAGS",
        "CPPFLAGS",
        "LDFLAGS",
        "LIBRARY_PATH",
        "PKG_CONFIG_PATH",
        "PKG_CONFIG_LIBDIR",
    ):
        environment.pop(key, None)
    lock_path = Path(__file__).with_name("codecs-linux-lock.json")
    lock = json.loads(lock_path.read_text())
    with (out / "build.log").open("w") as log:
        for source in lock["sources"]:
            with urlopen(source["url"], timeout=60) as response:
                value = response.read(10000001)
            if (
                len(value) > 10000000
                or hashlib.sha256(value).hexdigest() != source["sha256"]
            ):
                raise ValueError("Pinned source hash mismatch: " + source["name"])
            archive = out / (source["name"] + ".tar.xz")
            archive.write_bytes(value)
            stem = source["name"] + "-" + source["version"]
            with tarfile.open(archive, "r:xz") as tar:
                if any(
                    (p.name != stem and not p.name.startswith(stem + "/"))
                    or p.issym()
                    or p.islnk()
                    for p in tar.getmembers()
                ):
                    raise ValueError("Unexpected archive member")
                tar.extractall(out, filter="data")
            work = out / stem
            env = environment.copy()
            env["PKG_CONFIG_LIBDIR"] = str(prefix / "lib/pkgconfig")
            env["CPPFLAGS"] = "-I" + str(prefix / "include")
            env["LDFLAGS"] = "-L" + str(prefix / "lib")
            command = [
                "./configure",
                "--prefix=" + str(prefix),
                "--enable-shared",
                "--disable-static",
            ]
            commands.append(
                {
                    "source": stem,
                    "configure": command,
                    "environment_overrides": {
                        k: env[k] for k in ("PKG_CONFIG_LIBDIR", "CPPFLAGS", "LDFLAGS")
                    },
                }
            )
            for cmd in (
                command,
                ["make", "-j" + str(args.jobs)],
                ["make", "check"],
                ["make", "install"],
            ):
                subprocess.run(
                    cmd, cwd=work, env=env, stdout=log, stderr=log, check=True
                )
    payload = out / "payload"
    shutil.copytree(original, payload)
    (payload / "lib").mkdir()
    for name in ("libogg.so.0", "libvorbis.so.0", "libvorbisenc.so.2"):
        shutil.copy2(
            prefix / "lib" / name, payload / "lib" / name, follow_symlinks=True
        )
        subprocess.run(
            [str(patch), "--remove-rpath", str(payload / "lib" / name)], check=True
        )
        subprocess.run(
            ["strip", "--strip-unneeded", str(payload / "lib" / name)], check=True
        )
        header = subprocess.check_output(
            ["readelf", "-d", str(payload / "lib" / name)], text=True
        )
        if str(out) in header:
            raise ValueError("Absolute build path in library runtime metadata")
    for row in lock["sources"]:
        shutil.copy2(
            out / (row["name"] + "-" + row["version"]) / "COPYING",
            payload / "legal" / (row["name"] + "-COPYING"),
        )
    shutil.copy2(lock_path, payload / "legal/codecs-source-lock.json")
    shutil.copy2(Path(__file__), payload / "legal/build_codecs_linux.py")
    (payload / "legal/codecs-build-command.json").write_text(
        json.dumps(commands, indent=2).replace(str(out), "${BUILD_ROOT}") + "\n"
    )
    manifest = {
        p.relative_to(payload).as_posix(): digest(p.read_bytes())
        for p in sorted(payload.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    (payload / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "payload": str(payload),
                "files": len(manifest),
                "host_codec_copy": False,
                "distribution_ready": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
