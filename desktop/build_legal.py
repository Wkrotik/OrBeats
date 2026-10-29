"""Specific recovered notices, not full distribution legal/source approval.

Validate the notice against the exact installed dependency source before passing
only an explicit file inventory to PyInstaller. No network or dependency import.
"""

import hashlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FSB5_MODULES = {"__init__.py", "pcm.py", "utils.py", "vorbis.py", "vorbis_headers.py"}


def legal_inputs():
    root = ROOT / "desktop/legal"
    files = [root / "fsb5-LICENSE.txt", root / "fsb5-provenance.json"]
    if any(p.is_symlink() or not p.is_file() for p in files):
        raise ValueError("Missing or symlinked recovered fsb5 notice/provenance")
    record = json.loads(files[1].read_text())
    if (
        record.get("package") != "fsb5"
        or record.get("version") != "1.0"
        or record.get("license") != "MIT"
        or set(record.get("module_sha256", {})) != FSB5_MODULES
        or hashlib.sha256(files[0].read_bytes()).hexdigest()
        != record.get("notice_sha256")
    ):
        raise ValueError("Recovered fsb5 notice/provenance mismatch")
    installed = importlib.metadata.distribution("fsb5")
    if installed.version != record["version"]:
        raise ValueError("Review fsb5 notices for the installed dependency version")
    for name, expected in record["module_sha256"].items():
        source = installed.locate_file("fsb5/" + name)
        if source.is_symlink() or not source.is_file():
            raise ValueError("Missing or symlinked installed fsb5 source")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(
                "Review fsb5 notices for altered dependency source: " + name
            )
    return files


def dependency_notices(output):
    """Preserve verbatim installed notices and a build-environment inventory.

    This is an explicit superset, not a claim that every installed distribution
    is linked into the helper. Native/stdlib notices and corresponding sources
    are supplied separately with the release. Never copy credential-bearing pip
    direct_url.json, RECORD paths, or arbitrary package metadata into this record.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for dist in sorted(
        importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()
    ):
        name, version = dist.metadata["Name"], dist.version
        if not all(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+!-]*", v) for v in (name, version)
        ):
            raise ValueError("Invalid distribution identity")
        files = []
        for relative in dist.files or []:
            path = Path(str(relative))
            if not path.name.lower().startswith(
                ("license", "copying", "copyright", "notice", "authors")
            ):
                continue
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Escaping installed notice path")
            source = Path(dist.locate_file(relative))
            if (
                source.is_symlink()
                or not source.is_file()
                or source.stat().st_size > 4000000
            ):
                raise ValueError("Invalid installed notice file")
            data = source.read_bytes()
            dest = output / (name + "-" + version) / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            files.append(
                {
                    "file": dest.relative_to(output).as_posix(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        rows.append(
            {
                "name": name,
                "version": version,
                "license_expression": dist.metadata.get("License-Expression"),
                "notices": files,
            }
        )
    record = {
        "schema": 1,
        "scope": "installed-build-environment-superset",
        "python": ".".join(map(str, sys.version_info[:3])),
        "platform": sys.platform,
        "distributions": rows,
        "complete_native_or_source_closure": False,
    }
    (output / "environment.json").write_text(json.dumps(record, indent=2) + "\n")
    return output
