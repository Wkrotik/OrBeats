"""Reject too-new GLIBC references in a complete generated AppDir.

Static version inspection complements, not replaces, isolated target-runtime
window/import tests. Does not approve licenses, installers or distro portability.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def references(text, maximum):
    if not re.fullmatch(r"[0-9]+\.[0-9]+", maximum):
        raise ValueError("Expected numeric major.minor GLIBC baseline")
    bound = tuple(map(int, maximum.split(".")))
    if re.search(r"\bGLIBC_PRIVATE\b", text):
        raise ValueError("Unsupported private GLIBC ABI requirement")
    versions = sorted(
        set(re.findall(r"\bGLIBC_[0-9]+(?:\.[0-9]+)+\b", text)),
        key=lambda value: tuple(map(int, value[6:].split("."))),
    )
    newer = [v for v in versions if tuple(map(int, v[6:].split("."))) > bound]
    if newer:
        raise ValueError("GLIBC baseline exceeded: " + ", ".join(newer))
    abi = sorted(set(re.findall(r"\bGLIBC_ABI_[A-Z0-9_]+\b", text)))
    # ABI marker DT_RELR was introduced in glibc2.36. Unknown symbolic ABI
    # requirements are never silently accepted by a numeric-version check.
    if any(tag != "GLIBC_ABI_DT_RELR" or bound < (2, 36) for tag in abi):
        raise ValueError(
            "Unsupported symbolic GLIBC ABI requirement: " + ", ".join(abi)
        )
    return versions


def audit(appdir, maximum="2.35"):
    root = Path(appdir).resolve()
    if (
        not root.is_relative_to(ROOT / "temp")
        or not (root / "usr/bin/orbeats-desktop").is_file()
    ):
        raise ValueError("Audit a complete project-local OrBeats AppDir")
    if not (root / "usr/lib/OrBeats/backend/orbeats-backend").is_file():
        raise ValueError("Frozen backend missing from AppDir")
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() and (
            path.readlink().is_absolute() or not path.resolve().is_relative_to(root)
        ):
            raise ValueError("Escaping distribution link")
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if path.name in (
            "libbaseline-ownership.so",
            "ps4_config.json",
            "library.bin",
            "plugins.ini",
        ):
            raise ValueError("Build-only/private file in distribution: " + name)
        value = path.read_bytes()
        if not value.startswith(b"\x7fELF"):
            continue
        text = subprocess.check_output(
            ["readelf", "--version-info", str(path)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        try:
            versions = references(text, maximum)
        except ValueError as exc:
            raise ValueError(name + ": " + str(exc)) from exc
        rows.append(
            {
                "path": name,
                "sha256": hashlib.sha256(value).hexdigest(),
                "glibc_versions": versions,
            }
        )
    if len(rows) < 2:
        raise ValueError("Expected native shell and frozen backend ELFs")
    return {
        "schema": 1,
        "kind": "development-AppDir-glibc-audit",
        "maximum_glibc": maximum,
        "static_abi_gate_passed": True,
        "clean_machine_approval": False,
        "legal_approval": False,
        "elf_files": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appdir", type=Path, required=True)
    parser.add_argument("--maximum-glibc", default="2.35")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.absolute()
    if (
        output.exists()
        or output.is_symlink()
        or not output.resolve().is_relative_to(ROOT / "temp")
    ):
        raise ValueError("Choose fresh project-local audit output")
    result = audit(args.appdir, args.maximum_glibc)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "elf_files"}
            | {"elf_count": len(result["elf_files"])},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
