"""
paths.py — single source of location truth for the web app.

The web app is a THIN LAYER over the pipeline (plan §9.4 invariant 1): it must
spawn `tools/full_custom_song_pipeline.py` with CWD = the release/checkout root
(the pipeline derives PROJECT_ROOT from its own __file__, and its default config
paths are devcontainer-absolute — release finding #1). These helpers resolve
everything relative to THIS file so the webapp works from an extracted release
zip or a dev checkout unchanged.

LAYOUTS (Exp 270a): there are TWO real-world shapes, and they differ by one
level —
  dev checkout:  <root>/beat_saber_deluxe/webapp/   → PROJECT_DIR=beat_saber_deluxe,
                 RELEASE_ROOT=<root>; docs/, .agent/, ps4_dump/ live under <root>.
  release zip:   <extract>/webapp/  (flat — no beat_saber_deluxe/ wrapper)
                 → PROJECT_DIR=<extract> (the zip root), RELEASE_ROOT=<extract>'s
                 PARENT; docs/, requirements.txt live under <extract>.
Every RELEASE_ROOT-relative surface must therefore probe BOTH levels and use
whichever exists. The batch tab's example scripts were the live casualty: from
a clean zip extraction it found 0 example packs (latent since the first M9
release; caught by validating THIS release from a true clean extraction).
"""

from __future__ import annotations

import os
from pathlib import Path

# webapp/adapters/paths.py -> webapp -> beat_saber_deluxe -> release root
WEBAPP_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = WEBAPP_DIR.parent          # .../beat_saber_deluxe  (or the zip root when flat)
RELEASE_ROOT = PROJECT_DIR.parent        # the release/checkout root (or the extract dir's parent when flat)

PIPELINE = PROJECT_DIR / "tools" / "full_custom_song_pipeline.py"
# Desktop code/static resources are versioned; user state survives code upgrades.
DATA_DIR = Path(os.environ.get("ORBEATS_STATE_DIR", str(PROJECT_DIR))).resolve()
WEBAPP_DATA_DIR = DATA_DIR / "webapp" if "ORBEATS_STATE_DIR" in os.environ else WEBAPP_DIR
CONFIG_PATH = DATA_DIR / "ps4_config.json"
EXAMPLE_CONFIG_PATH = PROJECT_DIR / "ps4_config.example.json"
SONG_CATALOG = PROJECT_DIR / "beat_saber_song_ids.json"
FEATURES_LOCAL = DATA_DIR / "features.json"
DUMPER_CFG_REFERENCE = RELEASE_ROOT / "ps4_dump" / "dumper.cfg"
# Shipped inside the release zip at webapp/static/dumper.cfg (wizard download link)
DUMPER_CFG_BUNDLED = WEBAPP_DIR / "static" / "dumper.cfg"


def release_root_surname() -> Path:
    """The level that actually holds release-root content (docs/, ps4_dump/).

    In the dev checkout that's RELEASE_ROOT (…/<root>/beat_saber_deluxe/…);
    in the flat release zip it's PROJECT_DIR (the zip root itself). Probes
    for the marker dirs both ways; falls back to RELEASE_ROOT (dev shape)."""
    for cand in (RELEASE_ROOT, PROJECT_DIR):
        if (cand / "docs").exists() or (cand / "ps4_dump").exists():
            return cand
    return RELEASE_ROOT


def release_path(*parts: str) -> Path:
    """Resolve a release-root-relative path layout-agnostically (Exp 270a)."""
    return release_root_surname().joinpath(*parts)


# Layout-agnostic surfaces (were raw RELEASE_ROOT joins):
VALIDATOR = release_path("docs", "release-validation-test-procedure.sh")
if not VALIDATOR.exists():
    # dev checkout keeps it under .agent/docs (pre-Exp-259 location, still true in-repo)
    VALIDATOR = RELEASE_ROOT / ".agent" / "docs" / "release-validation-test-procedure.sh"


def release_default_dump_dir() -> Path:
    """Where the README tells users to put their dump: <release>/ps4_dump."""
    return release_path("ps4_dump")


def is_release_layout(path: Path | None = None) -> bool:
    """True when running from an extracted release zip (no .git, no .agent)."""
    root = path or release_root_surname()
    return not (root / ".git").exists()


def find_pipeline() -> Path:
    """Locate the pipeline script; raise with a useful message if absent."""
    if PIPELINE.exists():
        return PIPELINE
    raise FileNotFoundError(
        f"Pipeline not found at {PIPELINE}. The web app must run from a "
        "release/checkout containing beat_saber_deluxe/tools/."
    )
