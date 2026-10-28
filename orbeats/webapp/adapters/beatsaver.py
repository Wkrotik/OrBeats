"""
beatsaver.py — BeatSaver public-API adapter (search + map-by-id).

The API is public, no key, CORS-enabled (verified 2026-09-29 — a GitHub Pages
origin gets 200s), so the Pages build queries it client-side; this adapter
serves the local-backend mode (search preview, badge data, 404 re-check at
deploy time — maps get deleted, plan §9.2).

Gotchas encoded here (plan §9.2):
- votes/score stats fields are UNRELIABLE (0/None often) — never sort on them;
  sort by downloads or recency.
- maps get DELETED — a picked map can 404 at deploy time; expose the lookup
  error so the UI can say "map was deleted", not "deploy failed".
- per-difficulty note counts (versions[0].diffs[].notes) are the real quality
  signal the pipeline relies on.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API_BASE = "https://api.beatsaver.com"
_UA = "BeatSaberDeluxe-WebApp/0.1"


class BeatSaverError(RuntimeError):
    """BeatSaver API failure (network, or map deleted/missing → 404)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _get_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise BeatSaverError(f"BeatSaver API {e.code} for {url}", status=e.code) from e
    except Exception as e:  # network/timeout/parse
        raise BeatSaverError(f"BeatSaver API request failed: {e}") from e


def _slim(doc: dict) -> dict:
    """Project a BeatSaver map doc down to the fields the picker UI needs."""
    meta = doc.get("metadata", {})
    versions = doc.get("versions") or []
    v0 = versions[0] if versions else {}
    diffs = [
        {
            "characteristic": d.get("characteristic"),
            "difficulty": d.get("difficulty"),
            "notes": d.get("notes"),
            "nps": d.get("nps"),
            "seconds": d.get("seconds"),
        }
        for d in v0.get("diffs", [])
    ]
    stats = doc.get("stats", {}) or {}
    return {
        "id": doc.get("id"),
        "name": doc.get("name"),
        "songAuthorName": meta.get("songAuthorName"),
        "levelAuthorName": meta.get("levelAuthorName"),
        "bpm": meta.get("bpm"),
        "duration": meta.get("duration"),
        "downloads": stats.get("downloads") or 0,
        "uploaded": doc.get("uploaded") or v0.get("createdAt"),
        "hash": v0.get("hash"),
        "downloadURL": v0.get("downloadURL"),
        "diffs": diffs,
        # The song-selection rule badge: native Easy/Normal/Hard present?
        # (Expert/E+ are auto-filled by the pipeline — informational only.)
        "nativeDifficulties": sorted({
            d.get("difficulty") for d in diffs
            if d.get("characteristic", "").lower() == "standard"
            and d.get("difficulty") in ("Easy", "Normal", "Hard")
        }),
    }


def search(query: str, page: int = 0, per_page: int = 20,
           api_base: str | None = None) -> dict:
    """Full-text search. Returns {'docs': [slim...], 'total': N}."""
    base = api_base or DEFAULT_API_BASE
    q = urllib.parse.quote(query)
    url = f"{base}/search/text/{page}?q={q}&per_page={per_page}"
    data = _get_json(url)
    docs = [_slim(d) for d in data.get("docs", [])]
    return {"docs": docs, "total": len(docs)}


def map_by_id(map_id: str, api_base: str | None = None) -> dict:
    """Fetch one map by key/hash/id. Raises BeatSaverError(404) if deleted."""
    base = api_base or DEFAULT_API_BASE
    doc = _get_json(f"{base}/maps/id/{urllib.parse.quote(map_id)}")
    return _slim(doc)
