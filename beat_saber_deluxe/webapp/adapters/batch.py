"""
batch.py — batch deployments: parse the example scripts, define the batch-file
format, save/load custom batches.

The example_*.sh scripts are the project's proven pack loadouts (34 packs,
~300 song replacements, QA'd on real hardware). Rather than re-declare that
data, the web app PARSES the scripts themselves — the scripts stay the single
source of truth and the Batch tab always shows exactly what the CLI runs.

Custom batches live as simple JSON files (format documented below AND in the
UI) in webapp/batches/ — user-editable anywhere (platform-agnostic: any text
editor on Windows/macOS/Linux works; the web app also imports/exports them
through the browser's file dialogs so nothing depends on server-side paths
in Pages mode).

Batch file format (v1):
    {
      "format": "bsd-batch",
      "version": 1,
      "name": "My 80s pack",
      "description": "optional",
      "songs": [
        {"map_id": "c213", "target": "Angry",
         "song_name": "Rhythm Is A Dancer", "artist": "Pegboard Nerds",
         "audio": "pcm16", "pad_fsb5": false, "convert_to_v3": true}
      ]
    }
Required per song: map_id, target. Everything else optional with the
pipeline's safe defaults applied. Unknown fields are preserved on load
(round-trip safe) and rejected loudly on schema errors.
"""

from __future__ import annotations

import json
import re

from . import paths

# The example scripts live at docs/example-scripts/ in BOTH the repo and the
# release zip (moved from .agent/docs/ so the layouts match — Exp 259). The
# parser checks the canonical path first, then the legacy .agent/docs/ layout
# (old checkouts) — first-match wins, no duplicates.
EXAMPLE_DIRS = [
    # Exp 270a: probe BOTH layout levels — the dev checkout keeps example
    # scripts at <root>/docs/example-scripts (RELEASE_ROOT), while the FLAT
    # release zip has them at the zip root (PROJECT_DIR). Missing this second
    # level made the Batch tab show 0 example packs from a clean zip
    # extraction (latent since the first M9 release; found validating the
    # 0.6.4 zip from a true clean extraction).
    paths.RELEASE_ROOT / "docs" / "example-scripts",
    paths.PROJECT_DIR / "docs" / "example-scripts",
    # legacy layout (pre-Exp 259 checkouts)
    paths.RELEASE_ROOT / ".agent" / "docs",
]
BATCH_DIR = paths.WEBAPP_DATA_DIR / "batches"
BATCH_FORMAT = "bsd-batch"
BATCH_VERSION = 1

# A live deploy line: python3 tools/full_custom_song_pipeline.py
#   --download-beat-saver-song <ID> --target <SLOT> ... --deploy-full
_DEPLOY_RE = re.compile(
    r"^python3\s+tools/full_custom_song_pipeline\.py\s+"
    r"--download-beat-saver-song\s+(?P<map_id>\S+)\s+"
    r"--target\s+(?P<target>\S+)\s+"
    r"(?P<rest>.*)--deploy-full",
    re.MULTILINE)
# The song comment immediately introducing a deploy command:
#   # Song 12: Angry → Rhythm Is A Dancer (Pegboard Nerds)
_SONG_COMMENT_RE = re.compile(
    r"^#\s*Song\s+\d+:\s*(?P<slot>.+?)\s*[→>]\s*(?P<custom>.+?)\s*$",
    re.MULTILINE)

_PACK_NAME_RE = re.compile(
    r"example_script_to_install_custom_songs_over_(?P<pack>.+?)_music_pack")


def _pack_display_name(stem: str) -> str:
    m = _PACK_NAME_RE.match(stem)
    raw = m.group("pack") if m else stem
    return raw.replace("_", " ").title()


def _unquote(raw: str) -> str:
    """
    Strip shell quoting from a parsed token.

    The example scripts quote shell metacharacters (e.g. --target
    "Scream&Shout" — the & would otherwise split the command). The quotes
    are SHELL syntax, not part of the slot name: the pipeline target is
    Scream&Shout. Leaving them in made the batch runner deploy to a slot
    literally named '"Scream&Shout"' (Exp 264: song 8 of the Britney pack
    would have failed even after the size-check fix).
    """
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    return raw


def parse_example_scripts() -> list[dict]:
    """
    Parse every example_*.sh into a batch definition.

    Returns a list of {"name", "description", "source", "songs": [...]}
    sorted by pack name. Only LIVE deploy lines are read (commented docs
    and template <MAP_ID> lines are skipped — they never match the regex
    because commented lines start with '#' and placeholders lack
    --deploy-full on the same live line).
    """
    packs = []
    seen = set()
    scripts = []
    for d in EXAMPLE_DIRS:
        if d.is_dir():
            for script in d.glob("example_script_*.sh"):
                if script.name not in seen:  # first layout wins (repo vs zip copy)
                    seen.add(script.name)
                    scripts.append(script)
    for script in sorted(scripts, key=lambda s: s.name):
        try:
            text = script.read_text(encoding="utf-8")
        except OSError:
            continue
        songs = []
        for m in _DEPLOY_RE.finditer(text):
            rest = m.group("rest")
            entry = {
                "map_id": m.group("map_id"),
                "target": _unquote(m.group("target")),
                "song_name": "",
                "artist": "",
                "audio": "vorbis" if "--vorbis" in rest else
                         ("hevag" if "--hevag" in rest else "pcm16"),
                "pad_fsb5": "--pad-fsb5" in rest,
                "convert_to_v3": "--no-convert-to-v3" not in rest,
            }
            songs.append(entry)
        # Attach the human hints (custom song name/artist) from the Song
        # comments by slot order — comment N precedes deploy command N.
        hints = _SONG_COMMENT_RE.findall(text)
        for entry, hint in zip(songs, hints):
            _slot, custom = hint
            if " / " in custom or "(" in custom:
                name_part = custom.rsplit("(", 1)[0].strip()
                artist_part = ""
                if "(" in custom and custom.endswith(")"):
                    artist_part = custom[custom.rfind("(") + 1:-1].strip()
                entry["song_name"] = name_part
                entry["artist"] = artist_part
        if songs:
            packs.append({
                "name": _pack_display_name(script.stem),
                "description": (f"{len(songs)} song replacements from "
                                f"{script.name} (the QA-proven example script)"),
                "source": script.name,
                "songs": songs,
            })
    return packs


# ---------------------------------------------------------------------------
# Custom batches (JSON files, user-editable)
# ---------------------------------------------------------------------------

def _validate_batch(data: dict, source: str) -> dict:
    """Validate + normalize a parsed batch document. Raises ValueError with
    a field-specific message the UI surfaces directly."""
    if not isinstance(data, dict):
        raise ValueError(f"{source}: batch file must be a JSON object")
    fmt = data.get("format", BATCH_FORMAT)
    if fmt != BATCH_FORMAT:
        raise ValueError(f"{source}: unknown format {fmt!r} (expected {BATCH_FORMAT!r})")
    version = data.get("version", BATCH_VERSION)
    if version != BATCH_VERSION:
        raise ValueError(f"{source}: unsupported batch version {version!r} (expected {BATCH_VERSION})")
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError(f"{source}: 'name' is required")
    songs = data.get("songs", [])
    if not isinstance(songs, list):
        raise ValueError(f"{source}: 'songs' must be a list")
    clean = []
    for i, s in enumerate(songs):
        if not isinstance(s, dict):
            raise ValueError(f"{source}: songs[{i}] must be an object")
        map_id = str(s.get("map_id", "")).strip()
        target = str(s.get("target", "")).strip()
        if not map_id:
            raise ValueError(f"{source}: songs[{i}].map_id is required")
        if not target:
            raise ValueError(f"{source}: songs[{i}].target is required")
        entry = {
            "map_id": map_id,
            "target": target,
            "song_name": str(s.get("song_name", "")).strip(),
            "artist": str(s.get("artist", "")).strip(),
            "audio": s.get("audio", "pcm16"),
            "pad_fsb5": bool(s.get("pad_fsb5", False)),
            "convert_to_v3": bool(s.get("convert_to_v3", True)),
        }
        if entry["audio"] not in ("pcm16", "vorbis", "hevag"):
            raise ValueError(f"{source}: songs[{i}].audio must be pcm16|vorbis|hevag")
        # preserve unknown keys for round-trip safety
        for k, v in s.items():
            if k not in entry:
                entry[k] = v
        clean.append(entry)
    return {"name": name,
            "description": str(data.get("description", "")).strip(),
            "songs": clean}


def list_custom_batches() -> list[dict]:
    """Saved custom batches (name, description, count, file) — read-only."""
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(BATCH_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append({"file": f.name,
                        "name": data.get("name", f.stem),
                        "description": data.get("description", ""),
                        "song_count": len(data.get("songs", []))})
        except (json.JSONDecodeError, OSError):
            out.append({"file": f.name, "name": f.stem,
                        "description": "(unreadable — not valid JSON)", "song_count": 0,
                        "error": True})
    return out


def load_custom_batch(filename: str) -> dict:
    """Load + validate one custom batch by filename (no paths — the batches
    dir is a jail, same rule as backup restores)."""
    if not filename or "/" in filename or ".." in filename or not filename.endswith(".json"):
        raise ValueError("invalid batch filename (name.json, no paths)")
    path = BATCH_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"no such batch: {filename}")
    data = json.loads(path.read_text(encoding="utf-8"))
    batch = _validate_batch(data, filename)
    batch["file"] = filename
    return batch


def save_custom_batch(data: dict, filename: str | None = None) -> dict:
    """Validate + persist a custom batch. Returns the saved doc."""
    batch = _validate_batch(data, "(from the web app)")
    name = batch["name"]
    if not filename:
        # Slugify the batch name into a safe filename
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_").lower() or "batch"
        filename = f"{slug}.json"
    if "/" in filename or ".." in filename or not filename.endswith(".json"):
        raise ValueError("invalid batch filename (name.json, no paths)")
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = {"format": BATCH_FORMAT, "version": BATCH_VERSION,
           "name": name, "description": batch["description"],
           "songs": batch["songs"]}
    path = BATCH_DIR / filename
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return {"file": path.name, **out}


def delete_custom_batch(filename: str) -> bool:
    """Delete a saved batch (only files inside the batches dir)."""
    if not filename or "/" in filename or ".." in filename or not filename.endswith(".json"):
        raise ValueError("invalid batch filename")
    path = BATCH_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"no such batch: {filename}")
    path.unlink()
    return True
