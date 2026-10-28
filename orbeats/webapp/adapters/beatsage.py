"""
beatsage.py — Beat Sage (beatsage.com) client adapter (M13).

Beat Sage is a free third-party AI web service that generates Beat Saber
maps from any audio file. This module encodes the LIVE-CAPTURED contract of
their web app (M13.3 research, 2026-10-22 — captured from the site's own
page bundle: beatsage.com is a Nuxt app whose SERVER_HOST env constant is
the Google Cloud Run backend below; every route, field, and status value
was read verbatim from their client code):

  POST {host}/beatsaber_custom_level_create   multipart/form-data:
       audio_file (file), audio_metadata_title, audio_metadata_artist,
       difficulties (csv), modes (csv), events (csv), environment,
       system_tag ("v1"|"v2")            → {"id": <job-id>}
  GET  {host}/beatsaber_custom_level_heartbeat/<id>  → {"status": ...}
       status ∈ PENDING | LOADING_AUDIO | CREATING_LEVEL | FORMATTING_LEVEL
       | DONE (their UI polls every 3s, tolerating 3 consecutive failures)
  GET  {host}/beatsaber_custom_level_download/<id>  → the map zip

Their selectable values (the option surface): difficulties Normal/Hard/
Expert/ExpertPlus (Easy is NOT offered), modes Standard/NoArrows/OneSaber/
90Degree/360Degree, events Bombs/DotBlocks/Obstacles/Lights, ~16
environments, system_tag v1|v2. Their own defaults: difficulties
[Hard,Expert], modes [Standard,90Degree], events [DotBlocks,Obstacles].

RESPECT RULES (plan §2): it is a free service — we send ONE job at a time,
poll at their own UI's cadence, tolerate their failure budget, present
their branding explicitly ("powered by beatsage.com"), and degrade to the
guided flow (Tier 2) on ANY client-side failure. The user asserts rights to
the audio; using Beat Sage means accepting THEIR terms (linked in the UI).

The generated zip is a standard BeatSaver-format map (Info.dat +
per-difficulty .dat + .ogg audio) — exactly what the pipeline already
converts via --song-dir. The OUTPUT of this flow is a staged song folder
(adapters/songs.py); ZERO pipeline changes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

# Live-captured from the site's Nuxt bundle (env.SERVER_HOST) — 2026-10-22.
# If they ever move their backend, every call raises BeatSageError and the
# UI falls back to the guided flow (Tier 2) — the ladder makes this safe.
SERVER_HOST = "https://beatsage-v2-prod-http-f5hqh6gvya-uc.a.run.app"
SITE_URL = "https://beatsage.com/"
TOAST_UA = "BeatSaberDeluxe-WebApp (one job at a time; thanks Beat Sage!)"

DIFFICULTIES = ["Normal", "Hard", "Expert", "ExpertPlus"]  # v2 offers no Easy
MODES = ["Standard", "NoArrows", "OneSaber", "90Degree", "360Degree"]
# Their site's event checkboxes (the UI truth) — BUT their backend REJECTS
# "Lights" with HTTP 400 'Invalid events specified' in BOTH v1 and v2
# (live-probed 2026-10-22, Exp 283b: a broken/placeholder checkbox on their
# own site). We don't offer it — a checkbox that can never succeed is a trap.
EVENTS = ["Bombs", "DotBlocks", "Obstacles"]
_EVENT_UI_TRAP = "Lights"  # documented, never offered
ENVIRONMENTS = ["DefaultEnvironment", "Origins", "TriangleEnvironment",
                "NiceEnvironment", "BigMirrorEnvironment", "DragonsEnvironment",
                "KDAEnvironment", "MonstercatEnvironment", "CrabRaveEnvironment",
                "PanicEnvironment", "RocketEnvironment", "GreenDayEnvironment",
                "GreenDayGrenadeEnvironment", "TimbalandEnvironment",
                "FitBeatEnvironment", "LinkinParkEnvironment"]
SYSTEM_TAGS = ["v2", "v1"]

# OUR recommended defaults for PS4 deploys (shown in the guided card and
# pre-checked in the generate form): every difficulty Beat Sage offers, and
# Standard only — the pipeline itself auto-generates OneSaber/90Degree/etc.
# variants from Standard during the deploy (--enable-modes), so asking
# Beat Sage for extra modes would only spend their compute twice.
RECOMMENDED_DIFFICULTIES = ["Normal", "Hard", "Expert", "ExpertPlus"]
RECOMMENDED_MODES = ["Standard"]
RECOMMENDED_EVENTS = ["DotBlocks", "Obstacles"]   # their own defaults
RECOMMENDED_ENVIRONMENT = "DefaultEnvironment"
RECOMMENDED_SYSTEM_TAG = "v2"

HEARTBEAT_INTERVAL_SECONDS = 3.0   # their UI's own poll cadence
HEARTBEAT_MAX_FAILURES = 3         # their UI's own tolerance


class BeatSageError(RuntimeError):
    """Any Beat Sage client failure. The UI's response is ALWAYS the same:
    show the guided flow (Tier 2) with this message — never a dead end."""


def validate_options(options: dict) -> list[str]:
    """Reject unknown values BEFORE any upload (their UI silently filters;
    we fail fast so the user isn't surprised by a default we didn't show)."""
    errors: list[str] = []
    opts = options or {}
    for key, allowed in (("difficulties", DIFFICULTIES), ("modes", MODES),
                         ("events", EVENTS)):
        vals = opts.get(key) or []
        bad = [v for v in vals if v not in allowed]
        if bad:
            # their own site's broken checkbox gets a specific message
            if key == "events" and _EVENT_UI_TRAP in bad:
                errors.append(
                    "Beat Sage's 'Lights' event looks selectable on their site but "
                    "their API rejects it with HTTP 400 in both v1 and v2 (live-probed) — "
                    "leave it off. To fix: generate without Lights.")
                bad = [b for b in bad if b != _EVENT_UI_TRAP]
            if bad:
                errors.append(f"Unknown {key}: {', '.join(bad)} (allowed: {', '.join(allowed)}). To fix: pick from the offered checkboxes.")
        if not vals:
            errors.append(f"Pick at least one {key[:-1]}.")
    env = opts.get("environment", RECOMMENDED_ENVIRONMENT)
    if env not in ENVIRONMENTS:
        errors.append(f"Unknown environment: {env}. To fix: pick from the list.")
    system = opts.get("system_tag", RECOMMENDED_SYSTEM_TAG)
    if system not in SYSTEM_TAGS:
        errors.append(f"Unknown system: {system}. To fix: choose v1 or v2.")
    return errors


def guidance_payload() -> dict:
    """The Tier-2 guided-flow card (works with NO backend cooperation —
    the user drives beatsage.com themselves and drops the zip back)."""
    return {
        "site_url": SITE_URL,
        "tier": 2,
        "recommended": {
            "difficulties": RECOMMENDED_DIFFICULTIES,
            "modes": RECOMMENDED_MODES,
            "events": RECOMMENDED_EVENTS,
            "environment": RECOMMENDED_ENVIRONMENT,
            "system_tag": RECOMMENDED_SYSTEM_TAG,
        },
        "steps": [
            "Open beatsage.com (the button below).",
            "Upload your audio file (you must have the rights to it).",
            "Pick the recommended options shown on this card.",
            "Click Generate and wait a few minutes (they email nothing — the page polls).",
            "Download the generated zip when it completes.",
            "Drag the zip onto the drop zone below (section 3) — the web app validates and stages it, then you deploy as usual.",
        ],
    }


# ------------------------------------------------------------------ HTTP

def _request(route: str, data: bytes | None = None,
             content_type: str | None = None, timeout: int = 60) -> tuple[int, bytes]:
    """One HTTP call to the Beat Sage backend. Plain urllib — no session,
    no cookies, no retries (one job at a time, their budget respected)."""
    url = f"{SERVER_HOST}/{route.lstrip('/')}"
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("User-Agent", TOAST_UA)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()[:400]
        except Exception:
            pass
        raise BeatSageError(
            f"Beat Sage returned HTTP {e.code} ({body.decode('utf-8', 'replace')!r}). "
            "Beat Sage's service may be busy or changed — use the guided flow below "
            "(it always works), or try again later.") from e
    except Exception as e:  # network/DNS/timeout
        raise BeatSageError(
            f"Couldn't reach Beat Sage ({e}). To fix: check your internet connection — "
            "or use the guided flow below (open beatsage.com yourself and drop the zip back).") from e


def create_job(audio_path: str, title: str, artist: str,
               options: dict) -> str:
    """POST the audio + options → the job id. Multipart exactly as their
    web app builds it (field names verbatim from their bundle)."""
    fields = {
        "audio_metadata_title": title or Path(audio_path).stem,
        "audio_metadata_artist": artist or "Unknown Artist",
        "difficulties": ",".join(options.get("difficulties") or RECOMMENDED_DIFFICULTIES),
        "modes": ",".join(options.get("modes") or RECOMMENDED_MODES),
        "events": ",".join(options.get("events") or RECOMMENDED_EVENTS),
        "environment": options.get("environment") or RECOMMENDED_ENVIRONMENT,
        "system_tag": options.get("system_tag") or RECOMMENDED_SYSTEM_TAG,
    }
    boundary = "BeatSaberDeluxeBoundary7d1a2c9f"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    fname = Path(audio_path).name
    mime = "application/octet-stream"
    with open(audio_path, "rb") as f:
        audio = f.read()
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio_file\"; "
        f"filename=\"{fname}\"\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8"))
    parts.append(audio)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    _code, resp = _request(
        "beatsaber_custom_level_create", data=body,
        content_type=f"multipart/form-data; boundary={boundary}", timeout=300)
    try:
        doc = json.loads(resp.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise BeatSageError(
            f"Beat Sage's create response wasn't JSON ({e}). To fix: nothing on your side — "
            "use the guided flow below.") from e
    jid = doc.get("id") if isinstance(doc, dict) else None
    if not jid:
        raise BeatSageError(
            f"Beat Sage's create response carried no job id ({str(doc)[:200]}). "
            "To fix: use the guided flow below.")
    return str(jid)


def heartbeat(job_id: str) -> dict:
    """Poll a job → the status document ({"status": ...} plus whatever else
    they send — passed through untouched for the UI)."""
    _code, resp = _request(f"beatsaber_custom_level_heartbeat/{job_id}", timeout=30)
    try:
        doc = json.loads(resp.decode("utf-8"))
        if not isinstance(doc, dict):
            raise ValueError("not an object")
        return doc
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        raise BeatSageError(
            f"Beat Sage's heartbeat response wasn't JSON ({e}). To fix: nothing on your "
            "side — use the guided flow below.") from e


def download_zip(job_id: str) -> bytes:
    """Fetch the generated map zip."""
    _code, resp = _request(
        f"beatsaber_custom_level_download/{job_id}", timeout=300)
    if not resp[:2] == b"PK":
        raise BeatSageError(
            "Beat Sage's download wasn't a zip (their service may have errored mid-job). "
            "To fix: try generating again — or use the guided flow below.")
    return resp
