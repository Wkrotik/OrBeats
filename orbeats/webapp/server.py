#!/usr/bin/env python3
"""
server.py — OrBeats web app (local backend mode).

A THIN LAYER over the pipeline CLI: read-only queries hit small adapters;
every deploy is a subprocess argv call via the single-job runner
(plan: .agent/plans/web-app-song-conversion-pipeline-interface.md).

Run:
    python3 webapp/server.py            # binds 127.0.0.1:8765, opens browser
    python3 webapp/server.py --no-browser --port 9000

The static UI detects local-backend mode via GET /api/ping; the GitHub Pages
build of the same UI stubs /api/* and swaps Deploy for the command builder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
from pathlib import Path

from adapters import batch, beatsage, beatsaver, config, deploy, install_queue, loadout, paths, ps4, runner, songs
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="OrBeats")
from companion_api import router as companion_router
app.include_router(companion_router)
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost','127.0.0.1','[::1]','testserver'])
@app.middleware("http")
async def local_origin_guard(request, call_next):
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin:
        from urllib.parse import urlsplit
        parsed=urlsplit(origin)
        if parsed.scheme not in ('http','https') or parsed.netloc!=request.headers.get('host'):
            return JSONResponse({'detail':'Cross-origin console changes are refused'},status_code=403)
    if request.method in ('POST', 'DELETE', 'PUT', 'PATCH'):
        path = request.url.path
        management = (path in ('/api/orbis/settings', '/api/orbis/plugin', '/api/config/save')
                      or path.startswith('/api/orbis/library/')
                      or (path.startswith('/api/jobs/') and path != '/api/jobs/cancel'))
        if management and (RUNNER.is_busy() or INSTALL_QUEUE.has_work()):
            detail = ('A job is already running. Wait before starting another operation.'
                      if RUNNER.is_busy() and not INSTALL_QUEUE.has_work()
                      else 'Finish or clear the installation queue before changing the connection, plugin or library.')
            return JSONResponse({'detail': detail}, status_code=409)
    return await call_next(request)

RUNNER = runner.SingleJobRunner()
INSTALL_QUEUE = install_queue.InstallQueue(RUNNER)
STATIC_DIR = paths.WEBAPP_DIR / "static"


# --------------------------------------------------------------------------
# Mode detection + static UI
# --------------------------------------------------------------------------
# Code-version capture (Exp 280c — the round-3 stale-process lesson):
# the ping MUST report the versions of the RUNNING CODE, captured at import,
# NOT a fresh file read at request time. A stale server process (started before
# a pull) reading the files at request time reports the NEW version while
# serving OLD code — defeating the launcher's staleness check ("current" →
# reuse) and sending the user's clicks to 404s (the user's live report:
# Deploy Plugin → "❌ Not Found" while the ping proudly said 0.6.15).
_CODE_WEBAPP_VERSION = None
_CODE_PIPELINE_VERSION = None
_CODE_PLUGIN_VERSION = None


def _capture_code_versions():
    """Capture once at import: these are the versions THIS process runs."""
    global _CODE_WEBAPP_VERSION, _CODE_PIPELINE_VERSION, _CODE_PLUGIN_VERSION
    _CODE_WEBAPP_VERSION = _webapp_version()
    _CODE_PIPELINE_VERSION = _pipeline_version()
    _CODE_PLUGIN_VERSION = _plugin_version()


@app.get("/api/ping")
def ping():
    """Backend heartbeat — the UI's local-backend/Pages mode switch.
    Reports the import-time-captured versions of the RUNNING code (see the
    capture comment above — request-time file reads lie about staleness)."""
    return {"mode": "local-backend",
            "webapp_version": _CODE_WEBAPP_VERSION or _webapp_version(),
            "pipeline_version": _CODE_PIPELINE_VERSION or _pipeline_version(),
            "plugin_version": _CODE_PLUGIN_VERSION or _plugin_version(),
            "pipeline_present": paths.PIPELINE.exists()}


def _webapp_version() -> str:
    v = paths.WEBAPP_DIR / "VERSION"
    try:
        return v.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def _pipeline_version() -> str:
    v = paths.PROJECT_DIR / "VERSION"
    try:
        return v.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def _plugin_version() -> str:
    """Parse #define PLUGIN_VERSION from the plugin source; in a release
    extraction (no src/), read the version out of the BUNDLED PRX instead —
    the binary carries its boot-banner string ('=== OrBeats v0.8054
    started ==='), so release users still see a real version number (user
    request, Exp 280d — 'bundled' told them nothing)."""
    src = paths.PROJECT_DIR / "src" / "main.cpp"
    try:
        for line in src.read_text(encoding="utf-8").splitlines():
            if "PLUGIN_VERSION" in line and '"' in line:
                return line.split('"')[1]
    except OSError:
        pass
    prx = paths.PROJECT_DIR / "plugins" / "orbeats.prx"
    try:
        import re
        m = re.search(rb"(?:OrBeats|BS Deluxe) v(\d+\.\d+) started",
                      prx.read_bytes())
        if m:
            return "v" + m.group(1).decode()
    except OSError:
        pass
    return "bundled (no version found)"


# Capture at import (Exp 280c): after the last version-reader definition.
_capture_code_versions()


@app.get("/")
def index():
    # A fresh shell alone is insufficient: cached JS/CSS can still predate its
    # controls. Change each asset URL whenever its bytes change, independent of
    # timestamps/version bumps, while retaining ordinary static-file caching.
    html = (STATIC_DIR / "companion.html").read_text(encoding="utf-8")
    for asset in ("companion.css", "companion.js"):
        digest = hashlib.sha256((STATIC_DIR / asset).read_bytes()).hexdigest()[:20]
        html = html.replace(f'/static/{asset}"', f'/static/{asset}?v={digest}"')
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


# --------------------------------------------------------------------------
# Wizard: dump validation + config write
# --------------------------------------------------------------------------
@app.get("/api/dump/validate")
def dump_validate(path: str):
    """Live structural validation with per-missing-piece errors (plan §4.1b)."""
    if not path:
        raise HTTPException(400, "path parameter required")
    res = config.validate_dump(path)
    return {
        "ok": res.ok,
        "errors": res.errors,
        "warnings": res.warnings,
        "app_dir_present": res.app_dir_present,
        "patch_dir_present": res.patch_dir_present,
        "eboot_present": res.eboot_present,
        "origin_catalog_present": res.origin_catalog_present,
        "dlc_packs_found": res.dlc_packs_found,
    }


@app.get("/api/dump/default-location")
def dump_default_location():
    """Where this release expects the dump + whether it's already there."""
    default = paths.release_default_dump_dir()
    if default.exists():
        res = config.validate_dump(default)
        return {"default_path": str(default), "exists": True,
                "ok": res.ok, "errors": res.errors,
                "warnings": res.warnings,
                "dlc_packs_found": res.dlc_packs_found}
    return {"default_path": str(default), "exists": False}


@app.post("/api/config/save")
def config_save(body: dict):
    """Wizard step 4: write the fully-localized ps4_config.json."""
    try:
        # Exp 281f: dump_root is OPTIONAL — the no-dump flow (game-data
        # extractor) is the default posture. When omitted, both dump paths
        # point at the local game_data cache; users who HAVE a dump can still
        # pass its root explicitly (developers/repair).
        cfg = config.build_wizard_config(
            dump_root=body.get("dump_root", str(paths.PROJECT_DIR / "game_data")),
            ps4_ip=body.get("ps4_ip", "192.168.100.117"),
            ftp_port=body.get("ftp_port", 2121),
            ftp_user=body.get("ftp_user", "anonymous"),
            ftp_password=body.get("ftp_password", ""),
        )
    except KeyError as e:
        raise HTTPException(400, f"missing field: {e}")
    written = config.save_config(cfg)
    return {"ok": True, "config_path": str(written), "config": cfg}


@app.get("/api/config")
def config_read():
    """Current ps4_config.json (or the example defaults) for the wizard."""
    return config.load_config()


@app.get("/api/catalog")
def catalog():
    """Slot/pack catalog from beat_saber_song_ids.json — drives the picker."""
    if not paths.SONG_CATALOG.exists():
        raise HTTPException(500, f"song catalog missing: {paths.SONG_CATALOG}")
    with open(paths.SONG_CATALOG, encoding="utf-8") as f:
        data = json.load(f)
    # Slim it for the UI: pack → slots (id, stock name/author, difficulties)
    albums = []
    for album in data.get("albums", []):
        albums.append({
            "pack": album.get("pack"),
            "packBundle": album.get("packBundle"),
            "songs": [
                {"songID": s.get("songID"),
                 "songName": s.get("songName"),
                 "songAuthorName": s.get("songAuthorName"),
                 "difficulties": s.get("difficulties")}
                for s in album.get("songs", [])
            ],
        })
    return {"albums": albums}


# --------------------------------------------------------------------------
# BeatSaver (server-side proxy for local-backend mode)
# --------------------------------------------------------------------------
@app.get("/api/beatsaver/search")
def beatsaver_search(q: str, page: int = 0, per_page: int = 20):
    try:
        return beatsaver.search(q, page=page, per_page=min(per_page, 50))
    except beatsaver.BeatSaverError as e:
        raise HTTPException(502, str(e))


@app.get("/api/beatsaver/map/{map_id}")
def beatsaver_map(map_id: str):
    try:
        return beatsaver.map_by_id(map_id)
    except beatsaver.BeatSaverError as e:
        if e.status == 404:
            raise HTTPException(404, f"Map {map_id} not found — it may have "
                                     "been deleted from BeatSaver.")
        raise HTTPException(502, str(e))


# --------------------------------------------------------------------------
# Songs: local-folder validation + zip intake + staging (M13, plan §5)
# Both new Pick-a-Song sections end here: a validated folder that flows into
# the Deploy tab unchanged (--song-dir). The adapter mirrors the pipeline's
# own contract (adapters/songs.py docstring) — the web app never converts.
# --------------------------------------------------------------------------
@app.get("/api/beatsage/guide")
def beatsage_guide():
    """The Beat Sage section's payload: the Tier-2 guided card (always)
    + the recommended options (pre-checks the Tier-1 form; also what the
    guided card tells the user to pick on beatsage.com) + the v1/v2 model
    descriptions + the density expectation note (KB: beatsage-charting-
    behavior — v2's Easy/Normal/Hard are ONE mellow band; density lives in
    Expert/Expert+; their AI offers no density slider)."""
    payload = beatsage.guidance_payload()
    payload["tier1_available"] = True  # the captured contract drives the form
    payload["systems"] = {
        "v2": {"label": "v2 — current model (recommended)",
                "description": "Beat Sage's current AI. Supports OneSaber/NoArrows/90° "
                               "modes. Charts a mellow Easy/Normal/Hard band — expect "
                               "the real density in Expert/Expert+ (measured: H ≈ 0.6, "
                               "E ≈ 2.1, E+ ≈ 3.3 notes/sec on a real song)."},
        "v1": {"label": "v1 — the original model",
                "description": "Marginally denser charts than v2 (measured on the same "
                               "audio: H 1.30 vs 1.19, E 2.40 vs 2.19 notes/sec) — NOT a "
                               "fix for the sparse Hard band. No OneSaber/90° support. "
                               "For completeness/comparison."},
    }
    payload["density_note"] = (
        "What to expect: Beat Sage's Easy/Normal/Hard are one flat mellow band — "
        "Hard will feel sparse next to a community map (that's their AI's design, "
        "not a conversion bug). The density lives in Expert/Expert+. There is no "
        "density slider on their service — the levers are difficulty choice and "
        "v1/v2. Per-difficulty note counts + notes/sec are shown on every staged song.")
    return payload


@app.get("/api/songs/test-song")
def songs_test_song(seconds: float = 48.0):
    """The original rights-clean test song, synthesized on demand (M13).
    100% math (adapters/testsong.py) — deterministic, so the 48s default is
    byte-identical to the already-deployed 'BSD Deluxe Theme (An Original)'.
    Use it to try Beat Sage without hunting for audio, or as a validation
    asset (the gated live-contract test uses the 8s variant)."""
    seconds = max(5.0, min(seconds, 120.0))
    from adapters import testsong
    data = testsong.generate_wav(seconds=seconds)
    from fastapi.responses import Response
    return Response(
        content=data, media_type="audio/wav",
        headers={"Content-Disposition":
                 f'attachment; filename="bsd_deluxe_theme_{int(seconds)}s.wav"'})


@app.post("/api/songs/validate-dir")
def songs_validate_dir(body: dict):
    """Validate a local song folder (live, per plan §4) + stage it on success.
    Auto-staging is the point: a valid folder is instantly deployable and
    lands in the staged list (stable id per path — re-validating refreshes)."""
    path = str(body.get("path", "")).strip()
    if not path:
        raise HTTPException(400, "path required")
    v = songs.validate_dir(path)
    if not v.ok:
        return {"ok": False, "errors": v.errors, "warnings": v.warnings}
    entry = songs.stage_dir(path)
    return {"ok": True, "validation": {
                "name": v.name, "artist": v.artist, "bpm": v.bpm,
                "schema": v.schema, "difficulties": v.difficulties,
                "modes": v.modes, "beatmap_count": v.beatmap_count,
                "audio_files": v.audio_files, "warnings": v.warnings,
                "charts": v.charts, "environment": v.environment,
                "duration_s": v.duration_s, "cover_art": v.cover_art,
                "mode_notes": v.mode_notes},
            "staged": entry}


@app.post("/api/songs/stage-zip")
def songs_stage_zip(zip_file: UploadFile = File(...)):
    """Intake a map zip (drag-drop): extract → validate → stage. Shared by
    the local-folder section AND the Beat Sage guided flow (plan §3 Tier 2's
    return path) — any BeatSaver-format zip works."""
    if not (zip_file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "Expected a .zip map archive. To fix: drop the "
                                 "map zip itself (the file you downloaded).")
    data = zip_file.file.read()
    if not data:
        raise HTTPException(400, "The uploaded zip is empty. To fix: re-download "
                                 "the map and drop it again.")
    try:
        entry = songs.stage_zip_bytes(data, source="zip")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "staged": entry}


@app.get("/api/songs/staged")
def songs_staged():
    """The recent-songs list (survives restarts — plan §4). Entries whose
    folder vanished are pruned so the list never shows dead songs."""
    return {"songs": songs.list_staged()}


@app.delete("/api/songs/staged/{sid}")
def songs_staged_remove(sid: str):
    if not songs.remove_staged(sid):
        raise HTTPException(404, f"no such staged song: {sid}")
    return {"ok": True}


@app.post("/api/jobs/beatsage")
def jobs_beatsage(audio: UploadFile = File(...),
                  title: str = Form(""), artist: str = Form(""),
                  difficulties: str = Form(""), modes: str = Form(""),
                  events: str = Form(""), environment: str = Form(""),
                  system_tag: str = Form("")):
    """Tier 1: the web app drives beatsage.com for the user (plan §3).
    The audio lands in a temp file; the job script (webapp/beatsage_client.py)
    does the upload → poll → download → stage as THE single job (its lines
    stream through the shared live console; cancel kills the process group).
    The UI's rights/ToS checkboxes are enforced client-side AND the job
    script re-validates options — but the rights assertion is the user's."""
    upload_dir = paths.WEBAPP_DATA_DIR / "beatsage_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in (audio.filename or "audio") if c.isalnum() or c in ".-_")[:80]
    tmp = upload_dir / f"{int(time.time())}_{safe or 'audio'}"
    with open(tmp, "wb") as f:
        f.write(audio.file.read())
    spec = {
        "audio_path": str(tmp),
        "title": title, "artist": artist,
        "difficulties": [d for d in difficulties.split(",") if d],
        "modes": [m for m in modes.split(",") if m],
        "events": [e for e in events.split(",") if e],
        "environment": environment,
        "system_tag": system_tag,
    }
    client = paths.WEBAPP_DIR / "beatsage_client.py"
    if not client.exists():
        raise HTTPException(500, f"Beat Sage client missing: {client}")
    try:
        job = RUNNER.start_script(
            str(client), ["--job", json.dumps(spec)],
            label=f"Beat Sage: {title or safe}")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id,
            "command": f"Beat Sage generation for “{title or safe}” "
                       "(powered by beatsage.com)"}


# --------------------------------------------------------------------------
# PS4: test connection + read-only state
# --------------------------------------------------------------------------
@app.get("/api/ps4/test")
def ps4_test():
    res = ps4.test_connection()
    return {"ok": res.ok, **(res.data or {}), "error": res.error}


@app.get("/api/ps4/state")
def ps4_state():
    """Dashboard payload: redirects summary, features, metadata counts.
    Exp 280d: absent files (decisive 550) are the CLEAN-SLATE state — the
    payload marks each section absent and sets clean_slate=True when all
    three are, so the UI can say 'clean slate' instead of erroring."""
    payload: dict = {}
    red = ps4.read_redirects_summary()
    payload["redirects"] = {"ok": red.ok, "error": red.error,
                            "absent": bool(getattr(red, "absent", False)),
                            **(red.data or {})}
    feat = ps4.read_features()
    feat_absent = bool(getattr(feat, "absent", False))
    payload["features"] = {"ok": feat.ok, "error": feat.error,
                          "absent": feat_absent,
                          **({} if feat_absent else (feat.data or {}))}
    meta = ps4.read_song_metadata()
    if meta.ok and meta.data:
        names = (meta.data.get("song_names") or {})
        payload["song_metadata"] = {
            "ok": True, "absent": False,
            "custom_song_count": sum(
                1 for v in names.values()
                if isinstance(v, str) and v and " / " in v),
            "entries": names,
        }
    elif meta.ok:
        payload["song_metadata"] = {"ok": True, "absent": True,
                                    "custom_song_count": 0, "entries": {}}
    else:
        payload["song_metadata"] = {"ok": False, "absent": False,
                                    "error": meta.error}
    payload["clean_slate"] = all([
        payload["redirects"].get("absent", False),
        payload["features"].get("absent", False),
        payload["song_metadata"].get("absent", False),
    ]) and payload["redirects"]["ok"] and payload["features"]["ok"] \
        and payload["song_metadata"]["ok"]
    return payload


# --------------------------------------------------------------------------
# Feature flags (read live; apply via --features-only job)
# --------------------------------------------------------------------------
FLAG_DESCRIPTIONS = {
    "enable_plugin": "Global kill switch. OFF = the plugin is fully inert and the game plays 100% official songs on the next boot — no uninstall needed. All flags default ON when features.json is absent (fresh installs work out of the box); this one stays as the master switch.",
    "enable_custom_song_replacements": "Gates all custom-song bundle redirects. OFF = every song loads its original stock audio and beatmaps (metadata labels stay).",
    "enable_song_metadata_modification": "Gates the in-game song-list name/artist swaps. OFF = songs show their official titles even when customs are deployed.",
    "enable_beatmap_mode_mapping": "Gates the extra game-mode buttons (OneSaber / NoArrows / 90Degree). OFF = the stock pack bundles + catalog are served (Standard only) — the safe posture while a pack is only partially deployed.",
    "enable_song_previews": "Gates the custom SONG PREVIEWS in the song menu (M10): highlighting a custom song plays its own ~10s audio instead of the stock song's clip. Previews ride inside the patched pack bundles — ON deploys the modes+previews bundle variant; OFF serves stock previews (the pack/mode redirects are shared with mode mapping: either flag ON keeps the patched pair live).",
    "enable_in_game_plugin_toggle": "In-game plugin toggle (M11, hardware-confirmed): arms the Move-controller hotkey — hold the Move button + trigger together for 2 full seconds (a combination used nowhere else in the game) to flip the global plugin state. You'll hear the PS4 notification sound (in VR the popup may not be visible); restart Beat Saber to apply the new state — the current session never changes mid-game. The hotkey keeps working even while the plugin itself is toggled OFF, so you can always flip it back on without a PC. Deliberately NOT affected by the kill switch — only this flag disables the hotkey. Full guide: docs/features/in-game-plugin-toggle.md.",
    "enable_additive_song_packs": "EXPERIMENTAL, OFF by default: add BSD Additive Proof as a normal pack referencing one owned stock song. Requires replacements, metadata modification, mode mapping and previews OFF; restart required. Does not import custom maps or clone level IDs. Console validation pending.",
    "enable_game_data_extractor": "M12: arms the in-console game-data extractor — the plugin copies the files the pipeline needs (per-slot templates ~13MB each, pack bundles, the catalog) out of the game's own data during a normal boot, so you never need to make or hold a decrypted dump on your PC. Use the Dump Guide tab's 'let the game extract it' flow: request the packs/songs you want, boot the game once, then pull the files into the local game_data cache. Idempotent (failures retry on the next boot); console-maintenance tooling like the M11 hotkey — deliberately NOT gated by the kill switch.",
}


@app.get("/api/flags")
def flags_read():
    """Live feature flags with descriptions + which are pending-apply."""
    res = ps4.read_features()
    pending = RUNNER.pending_flags if RUNNER.pending_flags else {}
    out = {
        "ok": res.ok,
        "error": res.error,
        "flags": [],
    }
    for name, value in (res.data or {}).items():
        out["flags"].append({
            "name": name,
            "value": value,
            "pending": pending.get(name, value) != value,
            "pendingValue": pending.get(name),
            "description": FLAG_DESCRIPTIONS.get(name, ""),
        })
    return out


@app.post("/api/jobs/flags-apply")
def jobs_flags_apply(body: dict):
    """Apply a whole flag loadout: one --features-only call per CHANGED flag
    would re-upload features.json repeatedly; instead build one argv with a
    --set-feature per flag (the pipeline accepts repeats)."""
    _require_config()
    wanted = body.get("flags", {})
    if not isinstance(wanted, dict) or not wanted:
        raise HTTPException(400, "flags map required")
    current_res = ps4.read_features()
    if not current_res.ok:
        raise HTTPException(502, f"Couldn't read live flags from the PS4 ({current_res.error}) "
                                 "— refusing to apply blind. Check the connection and retry.")
    current = current_res.data or {}
    argv = ["--features-only"]
    changed = 0
    for name, value in wanted.items():
        if name not in FLAG_DESCRIPTIONS:
            raise HTTPException(400, f"unknown feature flag: {name!r}")
        value = bool(value)
        if bool(current.get(name, name == "enable_plugin")) != value:
            argv += ["--set-feature", f"{name}={str(value).lower()}"]
            changed += 1
    if changed == 0:
        return {"ok": True, "job_id": None, "changed": 0,
                "message": "No changes — the PS4 flags already match this loadout."}
    RUNNER.pending_flags = {k: bool(v) for k, v in wanted.items()}
    try:
        job = RUNNER.start(argv, label=f"flags apply ({changed} changed)")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id, "changed": changed,
            "command": deploy.pipeline_command(argv)}


# --------------------------------------------------------------------------
# Backup / Restore (thin layer over backup-orbeats-files.py)
# --------------------------------------------------------------------------
BACKUP_SCRIPT = paths.release_path("backup-orbeats-files.py")
DEFAULT_BACKUP_DIR = paths.release_path("ps4_backups")


def _backup_dir() -> Path:
    """The effective backups dir: the user's persisted setting, else default."""
    from adapters import webapp_state
    return webapp_state.get_backup_dir()


@app.get("/api/backup/list")
def backup_list():
    """List available backups (name, size, when) — read-only."""
    backup_dir = _backup_dir()
    if not backup_dir.is_dir():
        return {"backups": [], "backup_dir": str(backup_dir)}
    out = []
    for entry in sorted(backup_dir.iterdir(), reverse=True):
        if entry.is_file() and entry.suffix == ".zip":
            out.append({"name": entry.name, "size": entry.stat().st_size,
                        "mtime": entry.stat().st_mtime})
    return {"backups": out, "backup_dir": str(backup_dir)}


@app.get("/api/backup/dir")
def backup_dir_get():
    """Where backups are read from/written to (the browse-button display)."""
    d = _backup_dir()
    return {"backup_dir": str(d), "default": str(DEFAULT_BACKUP_DIR),
            "is_default": d == DEFAULT_BACKUP_DIR, "exists": d.is_dir()}


@app.post("/api/backup/dir")
def backup_dir_set(body: dict):
    """Point the Backup/Restore tab at another backups folder. No paths are
    browsed arbitrarily: we accept any user-chosen path, list zips in it, and
    pass the resolved zip path to the restore job verbatim (the script
    handles its own validation)."""
    from adapters import webapp_state
    raw = str(body.get("path", "")).strip()
    if not raw:
        raise HTTPException(400, "path required")
    resolved = webapp_state.set_backup_dir(raw)
    # list immediately so the UI refreshes from the same call
    return {"ok": True, "backup_dir": str(resolved),
            **backup_list()}


@app.get("/api/backup/browse")
def backup_dir_browse(path: str = ""):
    """Lightweight folder listing for the browse UI: child dirs only (never
    files — the picker is for folders). Empty path = start at the current
    backup dir's parent (or home when unset)."""
    from adapters import webapp_state
    try:
        base = Path(path).expanduser() if path else webapp_state.get_backup_dir().parent
        if not base.is_dir():
            raise HTTPException(400, f"not a folder: {base}")
    except (OSError, ValueError) as e:
        raise HTTPException(400, f"invalid path: {e}")
    try:
        children = sorted(
            (d for d in base.iterdir() if d.is_dir()),
            key=lambda d: d.name.lower())
    except PermissionError:
        raise HTTPException(403, f"permission denied: {base}")
    return {"path": str(base), "parent": str(base.parent) if base.parent != base else None,
            "dirs": [{"name": d.name, "path": str(d)} for d in children]}


@app.post("/api/jobs/backup")
def jobs_backup(body: dict):
    """Run the backup script as a job. body: {"clean_ps4": bool}"""
    if not BACKUP_SCRIPT.exists():
        raise HTTPException(500, f"backup script missing: {BACKUP_SCRIPT}")
    clean = bool(body.get("clean_ps4", False))
    argv = ["backup"] + (["--clean-ps4"] if clean else [])
    # Custom backups folder → the script's --out flag (default dir needs no flag)
    backup_dir = _backup_dir()
    if backup_dir != DEFAULT_BACKUP_DIR:
        argv += ["--out", str(backup_dir)]
    try:
        job = RUNNER.start_script(str(BACKUP_SCRIPT), argv,
                                  label=f"backup{' + clean-ps4' if clean else ''}")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id,
            "command": f"python3 backup-orbeats-files.py {' '.join(argv)}"}


@app.post("/api/jobs/restore")
def jobs_restore(body: dict):
    """Restore a backup as a job. body: {"backup": name, "clean_ps4": bool}.
    DANGEROUS: overwrites the PS4's BSD state — confirm posture in the UI."""
    if not BACKUP_SCRIPT.exists():
        raise HTTPException(500, f"backup script missing: {BACKUP_SCRIPT}")
    name = str(body.get("backup", "")).strip()
    if not name or ".." in name or "/" in name:
        raise HTTPException(400, "backup name required (no paths)")
    path = _backup_dir() / name
    if not path.exists():
        raise HTTPException(404, f"no such backup: {name}")
    clean = bool(body.get("clean_ps4", False))
    argv = ["restore", str(path)] + (["--clean-ps4"] if clean else [])
    try:
        job = RUNNER.start_script(str(BACKUP_SCRIPT), argv,
                                  label=f"restore {name}{' + clean-ps4' if clean else ''}")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id,
            "command": f"python3 backup-orbeats-files.py {' '.join(argv)}"}


# --------------------------------------------------------------------------
# Batch deployments (example-script packs + custom batches)
# --------------------------------------------------------------------------
@app.get("/api/batch/examples")
def batch_examples():
    """The 34 example-script packs, parsed live from the scripts themselves
    (the scripts stay the single source of truth)."""
    return {"packs": batch.parse_example_scripts()}


@app.get("/api/batch/custom")
def batch_custom_list():
    """Saved custom batches (JSON files in webapp/batches/)."""
    return {"batches": batch.list_custom_batches()}


@app.get("/api/batch/custom/{filename}")
def batch_custom_load(filename: str):
    try:
        return {"ok": True, "batch": batch.load_custom_batch(filename)}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/batch/custom")
def batch_custom_save(body: dict):
    """Save (or overwrite) a custom batch. body: {"filename": optional,
    "batch": {format/version/name/description/songs}}."""
    try:
        saved = batch.save_custom_batch(
            body.get("batch", body),
            body.get("filename") or None)
        return {"ok": True, **saved}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/batch/custom/{filename}")
def batch_custom_delete(filename: str):
    try:
        batch.delete_custom_batch(filename)
        return {"ok": True}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/jobs/batch")
def jobs_batch(body: dict):
    """Run a batch as a sequence of --deploy-full jobs (one at a time — the
    runner's single-job rule; the client drives them serially and shows one
    live console). body: {"songs": [{map_id, target, ...}]}."""
    _require_config()
    songs = body.get("songs", [])
    if not isinstance(songs, list) or not songs:
        raise HTTPException(400, "songs list required")
    if len(songs)>64:
        raise HTTPException(400,"Batch exceeds the current 64-song resource budget.")
    # validate every entry BEFORE starting anything (fail fast, deploy nothing)
    for i, s in enumerate(songs):
        if not str(s.get("map_id", "")).strip():
            raise HTTPException(400, f"songs[{i}].map_id required")
    argv = []
    for s in songs:
        opts = deploy.DeployOptions(
            additive=True,
            map_id=str(s["map_id"]).strip(),
            target="",
            audio=s.get("audio", "pcm16"),
            pad_fsb5=bool(s.get("pad_fsb5", False)),
            convert_to_v3=bool(s.get("convert_to_v3", True)),
            deploy_full=True,
            skip_plugin=bool(s.get("skip_plugin", False)),
            song_name=str(s.get("song_name", "")).strip(),
            artist=str(s.get("artist", "")).strip(),
        )
        try:
            argv.append(opts.build_argv())
        except ValueError as e:
            raise HTTPException(400, f"songs[{i}]: {e}")
    # Run the batch as ONE shell-equivalent job: the runner gets a small
    # driver script that executes each argv in sequence, stopping at the
    # first failure (the exact semantics of the chained example scripts).
    driver = paths.WEBAPP_DIR / "batch_runner.py"
    if not driver.exists():
        raise HTTPException(500, f"batch driver missing: {driver}")
    payload = json.dumps(argv)
    try:
        job = RUNNER.start_script(
            str(driver), ["--jobs", payload],
            label=f"batch ({len(argv)} songs)")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id, "count": len(argv),
            "command": f"batch deploy: {len(argv)} songs"}


# --------------------------------------------------------------------------
# Feature requests (GitHub issue builder — client-side, works in Pages mode)
# --------------------------------------------------------------------------
@app.get("/api/feature-request/template")
def feature_request_template():
    """Repo coordinates for the issue-builder (client composes the URL; in
    Pages mode this is baked in — the endpoint exists for parity)."""
    return {
        "repo": "free5ty1e/BeatSaberPcCustomSongToPs4InstallConverter",
        "issue_url": "https://github.com/free5ty1e/BeatSaberPcCustomSongToPs4InstallConverter/issues/new",
        "labels": ["webapp feature request"],
    }


# --------------------------------------------------------------------------
# Loadout tables (Manage Songs + Full Loadout tabs)
# --------------------------------------------------------------------------
@app.get("/api/loadout")
def loadout_state():
    """
    Full merge: every catalog pack/slot × live redirects × song metadata.

    Read failures are explicit (never "nothing deployed"): the payload always
    carries per-source read status the UI must surface when not ok.
    """
    res = ps4.read_deployment_state()
    merged = loadout.loadout_from_state(res.data or {})
    merged["readStatus"] = {
        "redirectsOk": not (res.data or {}).get("redirects_read_error"),
        "metadataOk": not (res.data or {}).get("metadata_read_error"),
        "afrOk": not (res.data or {}).get("afr_read_error"),
        "redirectsReadError": (res.data or {}).get("redirects_read_error"),
        "metadataReadError": (res.data or {}).get("metadata_read_error"),
        "afrReadError": (res.data or {}).get("afr_read_error"),
    }
    return merged


@app.get("/api/loadout/packs")
def loadout_packs():
    """Pack list for the Manage-Songs dropdown (from the local catalog —
    works even when the PS4 is offline)."""
    catalog = loadout.load_catalog()
    return {"packs": sorted(catalog.keys()),
            "songCounts": {p: len(s) for p, s in catalog.items()}}


# --------------------------------------------------------------------------
# Jobs: deploy + flags + clear + verify (ALL via the single-job runner)
# --------------------------------------------------------------------------
def _require_config() -> None:
    """Deploy pages refuse to run without a wizard-written config."""
    if not paths.CONFIG_PATH.exists():
        raise HTTPException(
            400, "No ps4_config.json yet — run the Setup Wizard first "
                 "(the pipeline's built-in defaults are devcontainer-absolute "
                 "and would misdirect the deploy).")


@app.post("/api/jobs/deploy")
def jobs_deploy(body: dict):
    _require_config()
    opts = deploy.DeployOptions(
        additive=True,
        map_id=str(body.get("map_id", "")).strip(),
        target=str(body.get("target", "")).strip(),
        # M13: a staged local folder rides along (the pipeline's own
        # precedence: song_dir overrides the BeatSaver download)
        song_dir=str(body.get("song_dir", "")).strip(),
        audio=body.get("audio", "pcm16"),
        pad_fsb5=bool(body.get("pad_fsb5", False)),
        convert_to_v3=bool(body.get("convert_to_v3", True)),
        deploy_full=bool(body.get("deploy_full", True)),
        skip_plugin=bool(body.get("skip_plugin", False)),
        song_name=str(body.get("song_name", "")).strip(),
        artist=str(body.get("artist", "")).strip(),
        enable_modes=str(body.get("enable_modes", "")).strip(),
    )
    try:
        argv = opts.build_argv()
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        job = RUNNER.start(argv, label=f"deploy {opts.describe()}")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id,
            "command": deploy.pipeline_command(argv)}


@app.post("/api/jobs/flags")
def jobs_flags(body: dict):
    _require_config()
    name = str(body.get("flag", "")).strip()
    value = bool(body.get("value", True))
    if not name or not name.startswith("enable_"):
        raise HTTPException(400, f"unknown feature flag: {name!r}")
    argv = deploy.flags_only_command(name, value)
    try:
        job = RUNNER.start(argv, label=f"flags {name}={value}")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id,
            "command": deploy.pipeline_command(argv)}


@app.post("/api/jobs/clear-target")
def jobs_clear_target(body: dict):
    _require_config()
    slot = str(body.get("slot", "")).strip()
    if not slot:
        raise HTTPException(400, "slot required")
    argv = deploy.clear_target_command(slot)
    try:
        job = RUNNER.start(argv, label=f"clear {slot}")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id,
            "command": deploy.pipeline_command(argv)}


@app.post("/api/jobs/verify")
def jobs_verify():
    _require_config()
    argv = deploy.verify_command()
    try:
        job = RUNNER.start(argv, label="verify-ps4")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id,
            "command": deploy.pipeline_command(argv)}


@app.get("/api/jobs/status")
def jobs_status():
    return RUNNER.status()


@app.post("/api/jobs/cancel")
def jobs_cancel():
    INSTALL_QUEUE.pause()
    return {"ok": RUNNER.cancel()}


@app.get("/api/install-queue")
def queue_status():
    return INSTALL_QUEUE.status()


@app.post("/api/install-queue")
def queue_add(body: dict):
    _require_config()
    try:
        return INSTALL_QUEUE.add(body.get("map_id", ""), body.get("title", ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/install-queue/{action}")
def queue_action(action: str):
    try:
        if action == "start":
            _require_config()
            INSTALL_QUEUE.start()
        elif action == "pause":
            INSTALL_QUEUE.pause()
        elif action == "clear":
            INSTALL_QUEUE.clear()
        else:
            raise HTTPException(404, "Unknown queue action")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return INSTALL_QUEUE.status()


@app.delete("/api/install-queue/{entry_id}")
def queue_remove(entry_id: str):
    try:
        INSTALL_QUEUE.remove(entry_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return INSTALL_QUEUE.status()


@app.get("/api/jobs/lines")
def jobs_lines(after: int = 0, job_id: str | None = None):
    """Legacy cursor contract; job-aware clients also handle queue transitions."""
    if job_id is not None:
        return RUNNER.snapshot(after, job_id)
    index, lines = RUNNER.lines_since(after)
    return {"index": index, "lines": lines, **RUNNER.status()}


# SSE variant (Phase 1 uses simple long-poll; kept for parity with the plan's
# architecture diagram — browsers with EventSource prefer this endpoint).
@app.get("/api/stream")
def stream():
    def event_gen():
        index = 0
        yield "data: {\"type\": \"start\"}\n\n"
        while True:
            index, lines = RUNNER.lines_since(index)
            if lines:
                payload = json.dumps({"type": "lines", "lines": lines})
                yield f"data: {payload}\n\n"
            status = RUNNER.status()
            if not status["running"] and status["job"] is not None:
                payload = json.dumps({"type": "end", "status": status["job"]})
                yield f"data: {payload}\n\n"
                return
            time.sleep(0.7)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# --------------------------------------------------------------------------
# Pages command-builder support (works in BOTH modes — pure function)
# --------------------------------------------------------------------------
@app.get("/api/command-preview")
def command_preview(map_id: str, target: str = "", audio: str = "pcm16",
                     pad_fsb5: bool = False, convert_to_v3: bool = True,
                     deploy_full: bool = True, skip_plugin: bool = False,
                     song_dir: str = ""):
    """The exact command the Deploy button would run (no config required).
    song_dir: the local-folder variant (M13) — matches adapters/deploy.py."""
    opts = deploy.DeployOptions(
        additive=True, map_id=map_id, target=target, audio=audio, pad_fsb5=pad_fsb5,
        convert_to_v3=convert_to_v3, deploy_full=deploy_full,
        skip_plugin=skip_plugin, song_dir=song_dir)
    try:
        argv = opts.build_argv()
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"command": deploy.pipeline_command(argv)}


# Static assets (must be mounted LAST so /api routes win)
if Path(STATIC_DIR).exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1",
                        help="local only by default — do not expose the PS4's "
                             "FTP credentials on the network")
    parser.add_argument("--no-browser", action="store_true",
                        help="don't auto-open the browser on start")
    parser.add_argument("--restore-queue", type=Path,
                        help="Restore an explicitly saved idle queue; stays paused until manual start")
    args = parser.parse_args()
    if args.restore_queue:
        if args.restore_queue.stat().st_size > 2000000:
            parser.error("Queue snapshot exceeds size bound")
        INSTALL_QUEUE.restore(json.loads(args.restore_queue.read_text()))

    port = _resolve_launch_port(args.host, args.port, open_browser=not args.no_browser)

    print(f"OrBeats web app — http://{args.host}:{port}")
    print(f"  release root: {paths.RELEASE_ROOT}")
    print(f"  pipeline:     {paths.find_pipeline()}")
    if not args.no_browser:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(
            f"http://{args.host}:{port}")).start()
    import uvicorn
    uvicorn.run(app, host=args.host, port=port, log_level="warning")


# ── Resilient launch (Exp 278h, user directives) ──────────────────────
# When the preferred port is busy, IDENTIFY the occupant and PRESENT OPTIONS
# instead of dying with uvicorn's raw "[Errno 98] address already in use".
# Non-interactive contexts (stdin not a TTY / EOF) take the smart default with
# a printed notice. EVERY error message carries a suggested course of action.
def _port_in_use(host: str, port: int) -> bool:
    """True when something is already listening on host:port (TCP connect probe)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def _who_is_on(host: str, port: int) -> tuple[str | None, dict | None]:
    """Identify a OrBeats web app instance already on the port.
    Returns (human description, ping payload) — (None, None) when the listener
    is not one of ours (or unreachable)."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://{host}:{port}/api/ping", timeout=1.5) as r:
            payload = json.loads(r.read())
        if isinstance(payload, dict) and payload.get("mode") == "local-backend":
            desc = (f"OrBeats web app {payload.get('webapp_version', '?')} "
                    f"(pipeline {payload.get('pipeline_version', '?')}, "
                    f"plugin {payload.get('plugin_version', '?')})")
            return desc, payload
    except Exception:
        pass
    return None, None


def _our_server_pids() -> list[int]:
    """PIDs of OUR OWN web app server processes (cmdline contains this
    server.py) — candidates for the stop-and-restart option. Linux/devcontainer."""
    import glob
    import os
    me = os.getpid()
    pids: list[int] = []
    for cmdline_file in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            raw = open(cmdline_file, "rb").read().decode("utf-8", "replace")
        except OSError:
            continue
        parts = [p for p in raw.split("\0") if p]
        if any("server.py" in p and "webapp" in p for p in parts):
            try:
                pid = int(cmdline_file.split("/")[2])
            except (IndexError, ValueError):
                continue
            if pid != me:
                pids.append(pid)
    return sorted(set(pids))


def _next_free_port(host: str, preferred: int, max_tries: int = 10) -> int:
    for p in range(preferred + 1, preferred + 1 + max_tries):
        if not _port_in_use(host, p):
            return p
    raise SystemExit(
        f"ERROR: ports {preferred}..{preferred + max_tries} are all in use.\n"
        f"To fix: stop the running web app instances (ps aux | grep '[s]erver.py', "
        f"then kill <PID>), or start on a port of your choice with --port <PORT>.")


def _resolve_launch_port(host: str, preferred: int, open_browser: bool = True) -> int:
    """Free port → use it. Occupied → identify the occupant, present options,
    and resolve. Never kills anything it cannot identify as its own web app."""
    if not _port_in_use(host, preferred):
        return preferred

    desc, ping = _who_is_on(host, preferred)
    stale = bool(ping) and ping.get("webapp_version") != _webapp_version()
    if desc:
        state = ("⚠️ STALE — it predates this checkout (it will keep serving old code "
                 "until restarted)") if stale else "current"
        print(f"\nPort {preferred} is already in use by: {desc} — {state}.")
    else:
        print(f"\nPort {preferred} is already in use by an unknown process "
              f"(not a OrBeats web app — it will NOT be touched).")

    pids = _our_server_pids()
    options: list[tuple[str, str]] = []  # (menu label, action)
    if desc:
        options.append((f"use the existing instance at http://{host}:{preferred} "
                        f"(open it in the browser; no new server started)", "use_existing"))
    options.append(("start a FRESH instance on the next free port "
                    "(the existing listener keeps running)", "next_port"))
    if desc and pids:
        options.append((f"STOP the running web app instance(s) (PID {', '.join(map(str, pids))}) "
                        f"and start fresh on {preferred}", "kill_and_take"))

    # Smart defaults: a CURRENT instance of ours → reuse it; a STALE one of ours
    # → stop + restart on the same port (the classic pain this resolver exists
    # for); an unknown occupant → never kill, take the next port.
    if desc and not stale:
        default_action = "use_existing"
    elif desc and stale and pids:
        default_action = "kill_and_take"
    else:
        default_action = "next_port"
    default = next((i for i, (_l, a) in enumerate(options, 1) if a == default_action), 1)

    print("How would you like to proceed?")
    for i, (label, _action) in enumerate(options, 1):
        marker = "   ← default" if i == default else ""
        print(f"  [{i}] {label}{marker}")

    choice = default
    interactive = False
    try:
        import sys as _sys
        interactive = _sys.stdin.isatty()
    except Exception:
        interactive = False
    if interactive:
        try:
            raw = input(f"Choose [1-{len(options)}] (Enter = {default}): ").strip()
            if raw:
                try:
                    picked = int(raw)
                except ValueError:
                    picked = -1
                if 1 <= picked <= len(options):
                    choice = picked
                else:
                    print(f"  ⚠️ '{raw}' is not one of the options — using the default ({default}).")
                    choice = default
        except EOFError:
            choice = default
    else:
        print(f"  (non-interactive context — taking option {default} automatically)")

    action = options[choice - 1][1]
    if action == "use_existing":
        if open_browser:
            import webbrowser
            webbrowser.open(f"http://{host}:{preferred}")
        print(f"Existing instance: http://{host}:{preferred} — nothing new started. "
              "(If it behaves oddly, it may be stale — re-run and choose the "
              "stop-and-restart option to replace it with this checkout's code.)")
        raise SystemExit(0)
    if action == "kill_and_take":
        import os
        import signal
        import time as _time
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError as e:
                print(f"  ⚠️ could not stop PID {pid} ({e}) — it may already be gone.")
        for _ in range(20):
            if not _port_in_use(host, preferred):
                print(f"Stopped the stale instance(s) — starting fresh on {preferred}.")
                return preferred
            _time.sleep(0.25)
        print("⚠️ the port did not free in time after stopping the instance(s). "
              "To fix: check what still holds it (ps aux | grep '[s]erver.py', "
              "kill the PID manually) — falling back to the next free port automatically.")
    return _next_free_port(host, preferred)


# --------------------------------------------------------------------------
# Game-data extraction (M12, Exp 280) — the "no dump required" flow.
# The pipeline owns both operations (--request-game-data / --pull-game-data
# as job subprocesses — thin layer); these endpoints read state + start jobs.
# --------------------------------------------------------------------------

def _local_game_data_summary() -> dict:
    """Local cache summary (paths.game_data_dir)."""
    cfg = config.load_config()
    gd = cfg.get("paths", {}).get("game_data_dir", "game_data")
    gd_path = paths.PROJECT_DIR / gd if not str(gd).startswith("/") else Path(gd)
    files = 0
    total = 0
    if gd_path.is_dir():
        for dp, _, fs in os.walk(gd_path):
            for f in fs:
                files += 1
                try:
                    total += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
    current_dump_dir = cfg.get("paths", {}).get("game_dump_dir", "")
    return {
        "dir": str(gd_path),
        "exists": gd_path.is_dir(),
        "files": files,
        "bytes": total,
        "game_dump_dir_current": current_dump_dir,
        "cache_is_active": str(current_dump_dir).endswith("game_data"),
    }


@app.get("/api/game-data/state")
def game_data_state():
    """Live extraction state: requested (requests.txt), extracted/failed
    (status.txt), and the local cache summary."""
    requests_res = ps4.read_game_data_requests()
    status_res = ps4.read_game_data_status()
    out = {
        "ok": requests_res.ok and status_res.ok,
        "error": requests_res.error if not requests_res.ok else status_res.error,
        "requests": requests_res.data or [],
        "extracted": (status_res.data or {}).get("done", []) if status_res.ok else [],
        "errors": (status_res.data or {}).get("errors", []) if status_res.ok else [],
        "cache": _local_game_data_summary(),
    }
    if out["ok"]:
        req = set(out["requests"])
        done = set(out["extracted"])
        out["pending"] = sorted(req - done)
        out["missing_from_requests"] = sorted(done - req)
    return out


@app.post("/api/jobs/game-data-request")
def jobs_game_data_request(body: dict):
    """Write the extraction manifest to the PS4 (one pipeline subprocess)."""
    _require_config()
    packs = body.get("packs") or None
    slots = body.get("slots") or None
    if not packs and not slots:
        raise HTTPException(400, "packs or slots required (comma-separated)")
    if isinstance(packs, list):
        packs = [str(p).strip() for p in packs if str(p).strip()]
    if isinstance(slots, list):
        slots = [str(s).strip() for s in slots if str(s).strip()]
    argv = deploy.game_data_request_command(packs, slots)
    label = "request game data " + (f"packs={','.join(packs)}" if packs else
                                    f"slots={','.join(slots)}")
    try:
        job = RUNNER.start(argv, label=label)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id, "command": deploy.pipeline_command(argv)}


@app.post("/api/jobs/game-data-pull")
def jobs_game_data_pull():
    """Mirror the console's game_data/ into the local cache (resumable)."""
    _require_config()
    argv = deploy.game_data_pull_command()
    try:
        job = RUNNER.start(argv, label="pull game data")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id, "command": deploy.pipeline_command(argv)}


@app.post("/api/jobs/deploy-plugin")
def jobs_deploy_plugin(body: dict):
    """Plugin-only deploy (M12, Exp 280b — the fresh-user bootstrap): builds
    (or falls back to the bundled binary) + deploys orbeats.prx and
    ensures the plugins.ini entry. body.debug deploys the DEBUG build."""
    _require_config()
    debug = bool((body or {}).get("debug", False))
    argv = deploy.plugin_deploy_command(debug=debug)
    try:
        job = RUNNER.start(argv, label=f"deploy plugin{' (DEBUG)' if debug else ''}")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "job_id": job.id, "command": deploy.pipeline_command(argv)}


@app.post("/api/game-data/use-cache")
def game_data_use_cache():
    """Point paths.game_dump_dir at the local game_data cache (after a pull)."""
    cfg = config.load_config()
    summary = _local_game_data_summary()
    if not summary["exists"] or summary["files"] == 0:
        raise HTTPException(400, "the local cache is empty — run the pull first "
                                  "(Boot the game once with the extractor armed, then "
                                  "Pull extracted files. To fix: nothing is broken — "
                                  "the cache just has no files yet.)")
    cfg.setdefault("paths", {})["game_dump_dir"] = summary["dir"]
    # Exp 281f: repoint EVERY dump consumer — pack_modes.dump_dir too. The
    # user's proof run exposed the hybrid: the Setup Wizard pins
    # pack_modes.dump_dir at the wizard's dump_root (their REAL dump), the
    # song template build followed the cache while the pack-patch step
    # silently read the real dump's pack bundle + catalog. The button now
    # switches the whole pipeline: remove any pin so the pipeline's
    # follow-game_dump_dir rule resolves the cache (and set it explicitly
    # for tooling that reads the raw file).
    pm = cfg.setdefault("pack_modes", {})
    pm["dump_dir"] = summary["dir"]
    written = config.save_config(cfg)
    return {"ok": True, "config_path": str(written),
            "game_dump_dir": summary["dir"],
            "pack_modes_dump_dir": summary["dir"]}


if __name__ == "__main__":
    main()
