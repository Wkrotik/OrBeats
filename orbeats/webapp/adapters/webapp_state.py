"""
webapp_state.py — tiny persisted settings for the web app (per-machine).

Holds exactly the settings a user would want to survive a server restart and
that must NOT ship with the repo (machine-specific paths): the backup
directory for the Backup/Restore tab. Gitignored (webapp_state.json) — this
is the same treatment ps4_config.json gets.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import paths

STATE_PATH = paths.WEBAPP_DATA_DIR / "webapp_state.json"
DEFAULT_BACKUP_DIR = paths.release_path("ps4_backups")
VALID_KEYS = ("backup_dir",)


def load() -> dict:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k in VALID_KEYS}
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save(state: dict) -> Path:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    return STATE_PATH


def get_backup_dir() -> Path:
    """The Backup/Restore tab's directory: the user's setting or the default."""
    raw = load().get("backup_dir")
    if raw:
        return Path(raw).expanduser()
    return DEFAULT_BACKUP_DIR


def set_backup_dir(path: str | Path) -> Path:
    """Persist the user's chosen backups directory (validated to exist or
    creatable — restore can only browse what exists, but the user may point
    at a folder they'll create later for a fresh backup)."""
    resolved = Path(path).expanduser()
    state = load()
    state["backup_dir"] = str(resolved)
    save(state)
    return resolved
