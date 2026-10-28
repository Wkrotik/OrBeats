"""OrBeats routes: local settings, public discovery, closed-title library writes."""

import datetime
import ipaddress
import urllib.parse

import library_manager as library
from adapters import beatsaver, config, paths
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter(prefix="/api/orbis")


def settings():
    return config.load_config()


def guarded(fn, *args):
    try:
        return fn(*args)
    except (ValueError, OSError, RuntimeError, EOFError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(503, "PS4 operation failed: " + str(e)) from e


@router.get("/settings")
def read_settings():
    cfg = settings()
    a = cfg.get("ps4", {})
    return {
        "name": "OrBeats",
        "ip": a.get("ip", ""),
        "port": a.get("ftp_port", 2121),
        "user": a.get("ftp_user", "anonymous"),
        "password_set": bool(a.get("ftp_password")),
        "template": cfg.get("additive_template", ""),
        "updates": {
            "state": "unconfigured",
            "message": "No official release feed configured; update checking is unavailable, not up to date.",
        },
    }


@router.post("/settings")
def save_settings(body: dict):
    try:
        ip = str(ipaddress.ip_address(body["ip"]))
        port = int(body.get("port", 2121))
        if not 1 <= port <= 65535:
            raise ValueError("Invalid FTP port")
        cfg = settings()
        a = cfg.setdefault("ps4", {})
        a.update(ip=ip, ftp_port=port, ftp_user=str(body.get("user", "anonymous")))
        if body.get("password") is not None:
            a["ftp_password"] = str(body["password"])
        cfg["additive_template"] = str(body.get("template", cfg.get("additive_template", "")))
        config.save_config(cfg)
        return {"ok": True}
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))


@router.get("/search")
def search(q: str = "", sort: str = "Latest", period: str = "all", page: int = 0):
    if (
        sort not in ["Latest", "Rating", "Relevance", "Curated"]
        or period not in ["all", "month", "week"]
        or not 0 <= page <= 100
    ):
        raise HTTPException(400, "Invalid search filter")
    args = {"q": q[:200], "sortOrder": sort}
    if period != "all":
        args["from"] = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30 if period == "month" else 7)
        ).isoformat()
    try:
        return beatsaver._get_json(
            "https://api.beatsaver.com/search/text/" + str(page) + "?" + urllib.parse.urlencode(args)
        )
    except beatsaver.BeatSaverError as e:
        raise HTTPException(502, str(e))


@router.get("/map/{key}")
def detail(key: str):
    import re

    if not re.fullmatch("[0-9a-fA-F]{1,12}", key):
        raise HTTPException(400, "Invalid BeatSaver key")
    try:
        return beatsaver._get_json("https://api.beatsaver.com/maps/id/" + key.lower())
    except beatsaver.BeatSaverError as e:
        raise HTTPException(e.status or 502, str(e))


@router.get("/library")
def installed():
    return {"songs": guarded(library.catalog, settings())}


@router.get("/library/{id}/cover")
def cover(id: str):
    return Response(
        guarded(library.media, settings(), id, "cover"),
        media_type="image/png", headers={"Cache-Control": "private, max-age=3600"}
    )


@router.get("/library/{id}/preview")
def preview(id: str):
    return Response(
        guarded(library.media, settings(), id, "preview"),
        media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"}
    )


@router.delete("/library/{id}")
def remove(id: str):
    return guarded(library.remove, settings(), id)


@router.get("/plugin")
def plugin_version():
    return guarded(library.plugin_status, settings(), paths.PROJECT_DIR / "orbeats.prx")


@router.post("/plugin")
def deploy_plugin():
    artifact = paths.PROJECT_DIR / "orbeats.prx"
    if not artifact.is_file():
        raise HTTPException(409, "Build the plugin first; no verified release artifact is bundled.")
    return guarded(library.deploy_plugin, settings(), artifact)
