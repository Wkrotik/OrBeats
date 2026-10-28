"""
config.py — ps4_config.json read/validate/write adapter + wizard dump validation.

The wizard is UI-mandatory (plan §3 decision 4): the pipeline's built-in config
DEFAULTS are devcontainer-absolute, so the web app must write a fully-localized
ps4_config.json itself before any deploy. Everything derives from two answers:
the game-dump folder and the PS4's IP/port.

Dump validation (plan §4.1b functional level, §9.4 invariant 7) reports
per-missing-piece errors and a found-DLC confidence list — never a bare
"not found".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

TITLE_ID = "CUSA12878"
AAPattern = re.compile(r"^(?P<pack>[a-z0-9]+)_pack_assets_all_(?P<hash>[0-9a-f]{32})\.bundle$")

# The catalog key the pipeline's pack_modes config expects (aa/catalog.json —
# the origin catalog inside the dump; redirects point at the patched copy).
ORIGIN_CATALOG_REL = Path("Media/StreamingAssets/aa/catalog.json")
PATCH_MEDIA_DIR = Path("Media/StreamingAssets/aa/PS4")


@dataclass
class DumpValidation:
    """Result of validating a candidate ps4_dump folder (plan §4.1b)."""

    path: str
    ok: bool = False
    errors: list[str] = field(default_factory=list)      # per-missing-piece
    warnings: list[str] = field(default_factory=list)
    app_dir_present: bool = False
    patch_dir_present: bool = False
    eboot_present: bool = False
    origin_catalog_present: bool = False
    dlc_packs_found: list[str] = field(default_factory=list)  # confidence list


def validate_dump(dump_root: str | Path) -> DumpValidation:
    """
    Validate the structure of a decrypted game-dump folder.

    Expected (README prerequisites): dump_root contains CUSA12878-app/ (base
    game) and CUSA12878-patch/ (v2.04 patch, with unpacked files: eboot.bin +
    Media/...). DLC pack bundles live in the patch's
    Media/StreamingAssets/aa/PS4/<pack>_pack_assets_all_<hash>.bundle.
    """
    root = Path(dump_root).expanduser()
    res = DumpValidation(path=str(root))
    if not root.exists():
        res.errors.append(f"Folder does not exist: {root}")
        return res
    if not root.is_dir():
        res.errors.append(f"Not a folder: {root}")
        return res

    app_dir = root / f"{TITLE_ID}-app"
    patch_dir = root / f"{TITLE_ID}-patch"
    res.app_dir_present = app_dir.is_dir()
    res.patch_dir_present = patch_dir.is_dir()
    if not res.app_dir_present and not res.patch_dir_present:
        # Common case: user pointed AT CUSA12878-patch itself, or at the parent
        # that holds both -app/-patch but named differently.
        hint = (
            f"Neither {TITLE_ID}-app/ nor {TITLE_ID}-patch/ found inside "
            f"{root}. Point the picker at the folder that CONTAINS them "
            "(usually ps4_dump). The dumper creates both when split=3."
        )
        res.errors.append(hint)
        return res
    if not res.app_dir_present:
        res.errors.append(
            f"{TITLE_ID}-app/ missing (base game dump). Re-dump with a "
            "dumper.cfg that has split=3 so app and patch land in separate "
            "folders."
        )
    if not res.patch_dir_present:
        res.errors.append(
            f"{TITLE_ID}-patch/ missing (v2.04 patch dump). The patch dump is "
            "REQUIRED — pack bundles and templates live in it. Re-dump with "
            "split=3."
        )
        return res

    eboot = patch_dir / "eboot.bin"
    res.eboot_present = eboot.exists()
    if not res.eboot_present:
        res.errors.append(
            f"{eboot} missing — the patch dump must contain unpacked files. "
            "If your dumper produced only a single .pkg-like blob, it did not "
            "unpack; use GoldHEN's PS4 Dumper (the web app's Dump Guide has "
            "the recipe + dumper.cfg)."
        )

    origin_catalog = patch_dir / ORIGIN_CATALOG_REL
    res.origin_catalog_present = origin_catalog.exists()
    if not res.origin_catalog_present:
        res.errors.append(
            f"{ORIGIN_CATALOG_REL} missing from the patch dump — the pipeline "
            "reads this origin catalog to build the patched pack catalog."
        )

    # DLC confidence list: every <pack>_pack_assets_all_<hash>.bundle in aa/PS4
    packs: set[str] = set()
    aa_ps4 = patch_dir / PATCH_MEDIA_DIR
    if aa_ps4.is_dir():
        for entry in aa_ps4.iterdir():
            m = AAPattern.match(entry.name)
            if m:
                packs.add(m.group("pack"))
    res.dlc_packs_found = sorted(packs)
    if not res.dlc_packs_found:
        res.warnings.append(
            "No DLC pack bundles (_pack_assets_all_*.bundle) found in the "
            "dump. If you intend to replace songs in a music pack, that pack "
            "must be INSTALLED on the PS4 BEFORE dumping — its bundle lives in "
            "the patch dump. (This is the #1 setup symptom.)"
        )

    res.ok = not res.errors
    return res


def load_config() -> dict:
    """Read ps4_config.json; fall back to the shipped example's defaults."""
    if paths.CONFIG_PATH.exists():
        with open(paths.CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    if paths.EXAMPLE_CONFIG_PATH.exists():
        with open(paths.EXAMPLE_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg: dict) -> Path:
    """Write ps4_config.json (gitignored — per-machine paths/credentials)."""
    with open(paths.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    return paths.CONFIG_PATH


def build_wizard_config(dump_root: str | Path, ps4_ip: str, ftp_port: int = 2121,
                        ftp_user: str = "anonymous", ftp_password: str = "",
                        extra: dict | None = None) -> dict:
    """
    Build a fully-localized ps4_config.json from wizard answers.

    Every path is derived from THIS release's location (release finding #1:
    the pipeline's built-in defaults are devcontainer-absolute). The dump may
    live anywhere — `game_dump_dir`/`dump_dir` point at the user's chosen
    folder verbatim.
    """
    root = Path(dump_root).expanduser()
    patch = root / f"{TITLE_ID}-patch"
    cfg = {
        "ps4": {"ip": ps4_ip, "ftp_port": int(ftp_port),
                "ftp_user": ftp_user, "ftp_password": ftp_password},
        "title": {"id": TITLE_ID, "name": "Beat Saber"},
        "paths": {
            "afr_base": "/data/GoldHEN/AFR",
            "afr_target_suffix": "_v3.bundle",
            "game_dump_dir": str(patch),
            "template_dir": "Media/StreamingAssets/BeatmapLevelsData",
            "output_dir": str(paths.DATA_DIR / "custom_songs"),
        },
        "pack_modes": {
            "packs": [],  # AUTO-DISCOVER (Exp 224): scope = packs with local builds
            "build_dir": str(paths.DATA_DIR / "pack_modes_bundles"),
            "song_ids_path": str(paths.SONG_CATALOG),
            "dump_dir": str(patch),
            "catalog_key": "aa/catalog.json",
            "patched_catalog": "catalog_pack_modes.json",
            "patched_catalog_local": str(paths.DATA_DIR / "catalog_pack_modes.json"),
        },
        "mass_deploy": {
            "bundle_dir": str(paths.DATA_DIR / "mass_bundles"),
            "slots": [],
        },
    }
    if extra:
        for section, values in extra.items():
            cfg.setdefault(section, {}).update(values)
    return cfg
