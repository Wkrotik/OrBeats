"""Fetch pinned Linux AppImage build tools project-locally, no system install.

Tauri's helper preparation changes its linuxdeploy copy in-place. Preserve
verified originals separately and create a fresh working XDG cache per build.
Checksums are pinned against upstream GitHub release asset metadata, not claimed
as independent signatures. No app/console operation or build is started here.
"""

import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = Path(__file__).with_name("appimage-linux-tools.json")
CLI_MEMBERS = frozenset(
    {"cargo-tauri", "README.md", "LICENSE-APACHE-2.0", "LICENSE-MIT"}
)


def matches(path, row):
    return (
        path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == row["bytes"]
        and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    )


def prepare(output):
    output = Path(output).absolute()
    if (
        output.exists()
        or output.is_symlink()
        or not output.resolve().is_relative_to(ROOT / ".tools")
    ):
        raise ValueError("Use fresh project-local .tools output")
    rows = json.loads(LOCK.read_text())["assets"]
    cache = ROOT / ".tools/downloads/appimage"
    cache.mkdir(parents=True, exist_ok=True)
    values = []
    for row in rows:
        path = cache / row["name"]
        if not matches(path, row):
            if path.exists() or path.is_symlink():
                raise ValueError("Cached tool integrity failure: " + row["name"])
            with urllib.request.urlopen(row["url"], timeout=60) as source:
                value = source.read(row["bytes"] + 1)
            if (
                len(value) != row["bytes"]
                or hashlib.sha256(value).hexdigest() != row["sha256"]
            ):
                raise ValueError("Downloaded tool integrity failure: " + row["name"])
            with path.open("xb") as dest:
                dest.write(value)
        values.append(path)
    output.mkdir(parents=True)
    tools = output / "cache/tauri"
    tools.mkdir(parents=True)
    cli = output / "bin"
    cli.mkdir()
    with tarfile.open(values[0], "r:gz") as archive:
        members = archive.getmembers()
        if (
            {p.name for p in members} != CLI_MEMBERS
            or len(members) != len(CLI_MEMBERS)
            or any(not p.isfile() or p.size > 100000000 for p in members)
        ):
            raise ValueError("Unexpected Tauri CLI archive members")
        for member in members:
            (cli / member.name).write_bytes(archive.extractfile(member).read())
    (cli / "cargo-tauri").chmod(0o755)
    for source in values[1:]:
        target = tools / source.name
        shutil.copyfile(source, target)
        target.chmod(0o755)
    shutil.copyfile(LOCK, output / "tools-lock.json")
    return {
        "cli": str(cli / "cargo-tauri"),
        "XDG_CACHE_HOME": str(output / "cache"),
        "verified_originals": str(cache),
        "build_started": False,
        "system_install": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))


if __name__ == "__main__":
    main()
