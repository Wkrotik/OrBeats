"""Specific recovered notices, not full distribution legal/source approval.

Validate the notice against the exact installed dependency source before passing
only an explicit file inventory to PyInstaller. No network or dependency import.
"""

import hashlib
import importlib.metadata
import json
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
