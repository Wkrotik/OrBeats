"""Offline development inventory of a staged helper, not a legal approval/SBOM.

Records hashes, included distribution metadata/license texts and ELF needs.
No dependency execution, license guessing, private profiles or external fetches.
"""

import argparse
import email.parser
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def audit(root):
    root = Path(root).resolve()
    if (
        not root.is_relative_to(ROOT / "temp")
        or not (root / "orbeats-backend").is_file()
    ):
        raise ValueError("Audit an isolated project-local frozen payload")
    files, binaries, distributions = [], [], []
    for path in sorted(root.rglob("*")):
        link = None
        if path.is_symlink():
            target = path.resolve()
            if (
                path.readlink().is_absolute()
                or not target.is_relative_to(root)
                or not target.is_file()
            ):
                raise ValueError("Escaping/absolute/non-file link in staged payload")
            link = target.relative_to(root).as_posix()
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        if path.name in ("ps4_config.json", "library.bin", "plugins.ini") or re.search(
            r"libfmod|global-metadata|Il2cppUserAssemblies", name, re.IGNORECASE
        ):
            raise ValueError(
                "Private/proprietary or profile file in staged payload: " + name
            )
        value = path.read_bytes()
        files.append(
            {
                "path": name,
                "bytes": len(value),
                "sha256": hashlib.sha256(value).hexdigest(),
            }
        )
        if link is not None:
            files[-1]["link_target"] = link
        if value.startswith(b"\x7fELF"):
            dynamic = subprocess.check_output(
                ["readelf", "-d", str(path)], text=True, stderr=subprocess.DEVNULL
            )
            versions = subprocess.check_output(
                ["readelf", "--version-info", str(path)],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            binaries.append(
                {
                    "path": name,
                    "needed": sorted(
                        set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic))
                    ),
                    "runtime_paths": re.findall(
                        r"\((?:RUNPATH|RPATH)\).*?\[(.*?)\]", dynamic
                    ),
                    "glibc_versions": sorted(
                        set(re.findall(r"\bGLIBC_[0-9.]+", versions)),
                        key=lambda v: tuple(map(int, v[6:].split("."))),
                    ),
                }
            )
        if path.name == "METADATA" and path.parent.name.endswith(".dist-info"):
            data = email.parser.BytesParser().parsebytes(value)
            legal = [
                p.relative_to(root).as_posix()
                for p in sorted(path.parent.rglob("*"))
                if p.is_file() and re.search(r"license|copying|notice", p.name, re.IGNORECASE)
            ]
            distributions.append(
                {
                    "name": data.get("Name"),
                    "version": data.get("Version"),
                    "license_expression": data.get("License-Expression"),
                    "declared_license": data.get("License"),
                    "included_legal_files": legal,
                }
            )
    return {
        "schema": 1,
        "kind": "development-payload-audit",
        "legal_approval": False,
        "files": files,
        "elf_files": binaries,
        "python_distributions": distributions,
        "open_gates": [
            "Legal/source obligations review (including static glibc in FFmpeg)",
            "Audit Python stdlib/native libraries and Rust/WebKit separately",
            "Actual target OS clean-machine and installer/upgrade tests",
            "No assumption that included metadata identifies every transitive component",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.absolute()
    if out.exists() or not out.resolve().is_relative_to(ROOT / "temp"):
        raise ValueError("Choose fresh project-local output")
    result = audit(args.payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "files": len(result["files"]),
                "elf_files": len(result["elf_files"]),
                "python_distributions": len(result["python_distributions"]),
                "legal_approval": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
