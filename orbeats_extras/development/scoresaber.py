"""Anonymous, read-only ScoreSaber protocol probe. Not the console transport/UI.

Only original map content hashes are accepted; no generated IDs, auth or uploads.
"""

import argparse
import json
import re
import time
import unicodedata
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

DIFFICULTIES = {"Easy": 1, "Normal": 3, "Hard": 5, "Expert": 7, "ExpertPlus": 9}
MAX_RESPONSE = 512 * 1024


class Unavailable(ValueError):
    """Not an empty board: network, identity or protocol failed."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Unavailable("ScoreSaber redirected; service endpoint needs review")


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise Unavailable("Invalid ScoreSaber integer")
    return value


def identity(content_hash, difficulty, mode):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", content_hash or ""):
        raise ValueError("Original 40-character map content SHA1 required")
    if difficulty not in DIFFICULTIES or mode != "SoloStandard":
        raise ValueError(
            "First probe supports explicitly selected Standard charts only"
        )
    return content_hash.upper(), DIFFICULTIES[difficulty], mode


def plain_name(value):
    if not isinstance(value, str) or len(value) > 1024:
        raise Unavailable("Invalid ScoreSaber player name")
    # TMPro rich-text and control/BiDi characters must not become UI commands.
    value = "".join(c for c in value if not unicodedata.category(c).startswith("C"))
    return value.replace("<", "‹").replace(">", "›")[:64] or "Unknown player"


def request_page(url, timeout):
    request = Request(
        url,
        headers={
            "User-Agent": "OrBeats-Extras/0.0001-readonly",
            "Accept": "application/json",
        },
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise Unavailable("ScoreSaber returned a non-success status")
            raw = response.read(MAX_RESPONSE + 1)
    except HTTPError as exc:
        if exc.code == 429:
            raise Unavailable(
                "ScoreSaber rate limited; retry later (no automatic retry)"
            ) from exc
        raise Unavailable(f"ScoreSaber HTTP {exc.code}; board unavailable") from exc
    except OSError as exc:
        raise Unavailable("ScoreSaber network/TLS request failed") from exc
    if len(raw) > MAX_RESPONSE:
        raise Unavailable("ScoreSaber response too large")
    try:
        return json.loads(raw)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Unavailable("Invalid ScoreSaber JSON") from exc


def top_scores(
    content_hash,
    difficulty,
    *,
    count=100,
    mode="SoloStandard",
    fetch=request_page,
    cancelled=lambda: False,
    clock=time.monotonic,
):
    content_hash, rating, mode = identity(content_hash, difficulty, mode)
    integer(count, 1, 100)
    deadline = clock() + 30
    rows = []
    total = None
    for page in range(1, 10):
        if cancelled():
            raise Unavailable("Leaderboard selection cancelled")
        remaining = deadline - clock()
        if remaining <= 0:
            raise Unavailable("Leaderboard request deadline reached")
        query = urlencode({"difficulty": rating, "gameMode": mode, "page": page})
        url = f"https://scoresaber.com/api/leaderboard/by-hash/{content_hash}/scores?{query}"
        data = fetch(url, min(10, remaining))
        if cancelled() or clock() >= deadline:
            raise Unavailable("Leaderboard selection cancelled or timed out")
        if not isinstance(data, dict) or not isinstance(data.get("metadata"), dict):
            raise Unavailable("Invalid ScoreSaber page")
        meta = data["metadata"]
        found = integer(meta.get("total"), 0, 100000000)
        if (
            meta.get("page") != page
            or type(meta.get("page")) is not int
            or meta.get("itemsPerPage") != 12
        ):
            raise Unavailable("ScoreSaber pagination contract changed")
        if total is not None and found != total:
            raise Unavailable("Leaderboard changed during pagination; retry later")
        total = found
        scores = data.get("scores")
        expected = min(12, max(0, total - (page - 1) * 12))
        if not isinstance(scores, list) or len(scores) != expected:
            raise Unavailable("Incomplete ScoreSaber page")
        for index, entry in enumerate(scores):
            if not isinstance(entry, dict) or not isinstance(
                entry.get("leaderboardPlayerInfo"), dict
            ):
                raise Unavailable("Invalid ScoreSaber score")
            rank = integer(entry.get("rank"), 1, 100000000)
            if (
                rank != (page - 1) * 12 + index + 1
                or type(entry.get("fullCombo")) is not bool
            ):
                raise Unavailable("Unexpected score order or full-combo state")
            score = integer(entry.get("modifiedScore"), 0, 2147483647)
            rows.append(
                {
                    "rank": rank,
                    "score": score,
                    "player_name": plain_name(
                        entry["leaderboardPlayerInfo"].get("name")
                    ),
                    "full_combo": entry["fullCombo"],
                }
            )
        if len(rows) >= min(count, total):
            break
    return {
        "schema": 1,
        "source": "ScoreSaber",
        "read_only": True,
        "content_sha1": content_hash,
        "difficulty": difficulty,
        "game_mode": mode,
        "total": total,
        "rows": rows[:count],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_sha1")
    parser.add_argument("difficulty", choices=DIFFICULTIES)
    parser.add_argument("--count", type=int, default=100, choices=(50, 100))
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                top_scores(args.content_sha1, args.difficulty, count=args.count),
                ensure_ascii=False,
                indent=2,
            )
        )
    except (ValueError, Unavailable) as exc:
        parser.exit(2, f"Leaderboard unavailable: {exc}\n")


if __name__ == "__main__":
    main()
