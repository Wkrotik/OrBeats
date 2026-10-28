"""Prepare a fresh source-only export; never copy Git history or personal data.

The original checkout/index/history remain untouched. New repository initialization,
review, commit, private remote verification and push are separate explicit steps.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXTENSIONS = {
    ".py",
    ".rs",
    ".hpp",
    ".cfg",
    ".cpp",
    ".h",
    ".c",
    ".sh",
    ".mjs",
    ".js",
    ".css",
    ".html",
    ".md",
    ".toml",
    ".lock",
    ".json",
    ".svg",
    ".png",
    ".ico",
    ".yml",
    ".yaml",
    ".x",
}
ROOT_FILES = (
    "AGENTS.md",
    "README.md",
    "icon.svg",
    "LICENSE",
    ".gitignore",
    ".gitattributes",
    "requirements.txt",
    "backup-orbeats-files.py",
    "make_fself_fixed.py",
)
EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "target",
    "dist",
    "gen",
    "build",
    "obj",
    "obj-debug",
    "custom_songs",
    "legacy",
    "batches",
    "example-scripts",
    "staged_songs",
    "beatsage_uploads",
    "htmlcov",
    "afr_deploy",
}
SECRET = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|AKIA[0-9A-Z]{16})"
)


def eligible(relative):
    p = Path(relative)
    if any(x in EXCLUDED_PARTS or x.startswith(".") for x in p.parts[1:]):
        return False
    if p.parts[0] not in {
        "orbeats",
        "orbeats_extras",
        "desktop",
        "docs",
        ".github",
        ".devcontainer",
        "scripts",
    }:
        return str(p) in ROOT_FILES
    if p.parts[:3] in (("orbeats", "development", "docs"), ("orbeats", "development", "fixtures")):
        return False
    if p.parts[0] == ".devcontainer":
        return p.name in {"setup_additive_host.sh", "setup_additive_toolchain.sh", "setup_additive_analysis.sh"}
    if p.parts[0] == ".github":
        return p.name in {"private-build.yml"}
    if str(p) in {"docs/overnight-audit.md", "docs/installation-failure-audit.md"}:
        return False
    if p.name in {"ps4_config.json", "webapp_state.json", "queue.json", "runtime-state.json"} or p.name.startswith(
        ("catalog_", "redirects_", "experiment_log")
    ):
        return False
    if p.name in {
        "MEMORY_INJECTION_STATUS.md",
        "memory_scan_implementation.cpp",
        "memory_scan_implementation.md",
        "memory_inject_test.py",
        "memory_inject_plugin.cpp",
    }:
        return False
    if p.name == "beat_saber_song_ids.json":
        return False  # replaced with a source-only empty catalog, never copied
    if p.suffix.lower() == ".txt":
        return p.name.startswith("requirements") or p.name in {"fsb5-LICENSE.txt"}
    return p.suffix.lower() in EXTENSIONS or p.name in {"VERSION", "Makefile", "CMakeLists.txt"}


def prepare(output):
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT / ".publication"):
        raise ValueError("Choose a fresh .publication/ output; existing exports are never overwritten")
    inventory = {}
    candidates = [ROOT / name for name in ROOT_FILES]
    for name in ("orbeats", "orbeats_extras", "desktop", "docs", ".github", ".devcontainer", "scripts"):
        candidates.extend((ROOT / name).rglob("*"))
    for source in sorted(set(candidates)):
        if not source.is_file() or not eligible(source.relative_to(ROOT)):
            continue
        if source.is_symlink() or any(p.is_symlink() for p in source.parents if p.is_relative_to(ROOT)):
            raise ValueError("Source export refuses symlinks")
        relative = source.relative_to(ROOT).as_posix()
        value = source.read_bytes()
        if len(value) > 2000000 or SECRET.search(value):
            raise ValueError("Oversized source or credential-like content: " + relative)
        if source.suffix.lower() not in {".png", ".ico"}:
            text = value.decode("utf-8")
            text = text.replace("/path/to/OrBeats", "/path/to/OrBeats")
            value = text.encode("utf-8")
        inventory[relative] = value
    inventory["orbeats/beat_saber_song_ids.json"] = (
        json.dumps(
            {
                "meta": {
                    "game": "Beat Saber PS4",
                    "titleId": "CUSA12878",
                    "totalSongs": 0,
                    "totalPacks": 0,
                    "notes": "No game-derived catalog is distributed. Legacy replacement catalog extraction requires your own game.",
                },
                "albums": [],
            },
            indent=2,
        )
        + "\n"
    ).encode()
    # Default example only; never the user's actual FTP details.
    config = json.loads(inventory["orbeats/ps4_config.example.json"])
    config["ps4"]["ip"] = "127.0.0.1"
    inventory["orbeats/ps4_config.example.json"] = (json.dumps(config, indent=2) + "\n").encode()
    upstream = subprocess.check_output(["git", "rev-parse", "60ca3a4"], cwd=ROOT, text=True).strip()
    inventory["SOURCE_ORIGIN.md"] = f"""# Source origin and privacy boundary

OrBeats builds on Beat Saber Deluxe / BeatSaberPcCustomSongToPs4InstallConverter:
https://github.com/free5ty1e/BeatSaberPcCustomSongToPs4InstallConverter
Inherited baseline commit: `{upstream}`. GPL/upstream notices remain intact.

This repository starts with a reviewed source-only snapshot. Inherited Git history
contained game-derived assets and personal development evidence and was deliberately
not imported. The original local checkout/history remains intact.

No game bundles, metadata dumps, source songs, personal configuration, console
backups, agent conversations, tool caches or locally built binaries are included.
The stock-song catalog is empty: legacy replacement features requiring it need
user-owned extraction. Additive setup obtains its template from the user's console.
Tests needing owned inputs skip explicitly. Current CI artifacts are private testing
candidates, not public releases or proof of PS4 playback/installer readiness.
""".encode()
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in sorted(inventory.items())}
    output.mkdir(parents=True)
    for name, value in inventory.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        if name.endswith(".sh"):
            target.chmod(0o755)
    (output / "source-export-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {
        "files": len(inventory),
        "bytes": sum(map(len, inventory.values())),
        "git_history_copied": False,
        "published": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args().output), indent=2))
