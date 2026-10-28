"""Prepare an isolated project-local Ubuntu22.04 root; no host package changes.

Fetch only the digest-pinned official Ubuntu OCI image, safely extract it under
.tools, then execute explicit commands using bubblewrap user namespaces. UID0
exists only inside that namespace. No Docker daemon, sudo, host root filesystem
writes or host home directory are needed. The root has no private console profile.

This is a build prerequisite prototype, not an AppImage compatibility claim.
"""

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
LOCK = Path(__file__).with_name("linux-baseline-lock.json")


def request(url, *, token=None, accept=None, limit=1000000):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if accept:
        headers["Accept"] = accept
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=headers), timeout=60
    ) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Download exceeds pinned size bound")
    return data


def checked(data, digest):
    if "sha256:" + hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("OCI content digest mismatch")
    return data


def extract_layer(archive, root):
    root = Path(root).resolve()
    total = 0
    with tarfile.open(archive, "r:gz") as stream:
        for entry in stream:
            name = PurePosixPath(entry.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or any(part.startswith(".wh.") for part in name.parts)
            ):
                raise ValueError("Unexpected OCI archive path or whiteout")
            if not (entry.isdir() or entry.isfile() or entry.issym() or entry.islnk()):
                raise ValueError("Special archive node refused")
            total += entry.size
            if total > 1000000000 or entry.size > 100000000:
                raise ValueError("OCI archive exceeds extraction bounds")
            if entry.issym() and entry.linkname.startswith("/"):
                # Keep rootfs links meaningful inside the namespace without ever
                # creating absolute links that could escape it on the host.
                target = root / entry.linkname.lstrip("/")
                if ".." in PurePosixPath(entry.linkname).parts:
                    raise ValueError("Escaping archive symlink")
                entry.linkname = os.path.relpath(target, root / name.parent)
            stream.extract(entry, root, filter="data")


def prepare(output):
    output = Path(output).absolute()
    if (
        output.exists()
        or output.is_symlink()
        or not output.resolve().is_relative_to(ROOT / ".tools")
    ):
        raise ValueError("Use fresh project-local .tools root")
    lock = json.loads(LOCK.read_text())
    token = json.loads(
        request(
            "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/ubuntu:pull"
        )
    )["token"]
    base = "https://registry-1.docker.io/v2/library/ubuntu"
    value = checked(
        request(
            base + "/manifests/" + lock["manifest_digest"],
            token=token,
            accept="application/vnd.oci.image.manifest.v1+json",
        ),
        lock["manifest_digest"],
    )
    manifest = json.loads(value)
    if (
        manifest["config"]["digest"] != lock["config_digest"]
        or [
            {"digest": row["digest"], "bytes": row["size"]}
            for row in manifest["layers"]
        ]
        != lock["layers"]
    ):
        raise ValueError("OCI manifest differs from reviewed lock")
    downloads = ROOT / ".tools/downloads/linux-baseline"
    downloads.mkdir(parents=True, exist_ok=True)
    archives = []
    for row in lock["layers"]:
        target = downloads / (row["digest"].removeprefix("sha256:") + ".tar.gz")
        if target.is_symlink():
            raise ValueError("Cached OCI symlink refused")
        if target.exists():
            value = target.read_bytes()
            if len(value) != row["bytes"]:
                raise ValueError("Cached OCI size mismatch")
            checked(value, row["digest"])
        else:
            value = checked(
                request(
                    base + "/blobs/" + row["digest"], token=token, limit=row["bytes"]
                ),
                row["digest"],
            )
            if len(value) != row["bytes"]:
                raise ValueError("OCI size mismatch")
            with target.open("xb") as stream:
                stream.write(value)
        archives.append(target)
    output.mkdir(parents=True)
    for archive in archives:
        extract_layer(archive, output)
    for name in ("dev", "proc", "tmp", "work"):
        (output / name).mkdir(exist_ok=True)
    (output / "tmp").chmod(0o1777)
    for name in ("resolv.conf", "hosts"):
        target = output / "etc" / name
        if target.is_symlink():
            raise ValueError("Unexpected root network config link")
        target.touch(exist_ok=True)
    (output / "orbeats-image-lock.json").write_bytes(LOCK.read_bytes())
    return {
        "root": str(output),
        "system_install": False,
        "docker_daemon": False,
        "build_started": False,
    }


def command(root, argv, *, work=None):
    root = Path(root).resolve()
    if (
        not root.is_relative_to(ROOT / ".tools")
        or (root / "orbeats-image-lock.json").read_bytes() != LOCK.read_bytes()
    ):
        raise ValueError("Expected pinned project-local root")
    if not argv or any(not isinstance(arg, str) for arg in argv):
        raise ValueError("Explicit command required")
    args = [
        "bwrap",
        "--unshare-user",
        "--uid",
        "0",
        "--gid",
        "0",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--die-with-parent",
        "--bind",
        str(root),
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
        "--ro-bind",
        "/etc/resolv.conf",
        "/etc/resolv.conf",
        "--ro-bind",
        "/etc/hosts",
        "/etc/hosts",
        "--clearenv",
        "--setenv",
        "HOME",
        "/root",
        "--setenv",
        "PATH",
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--setenv",
        "DEBIAN_FRONTEND",
        "noninteractive",
    ]
    if work:
        work = Path(work).resolve()
        if not work.is_dir() or not work.is_relative_to(ROOT / "temp"):
            raise ValueError("Expected project-local scratch work mount")
        args += ["--bind", str(work), "/work"]
    args += ["--chdir", "/work", "--", *argv]
    return args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    setup = sub.add_parser("prepare")
    setup.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--work", type=Path)
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(args.output), indent=2))
    else:
        argv = args.command
        if argv and argv[0] == "--":
            argv = argv[1:]
        subprocess.run(command(args.root, argv, work=args.work), check=True)


if __name__ == "__main__":
    main()
