"""Official GitHub release checks and explicitly requested, hash-verified plugins.

No automatic execution, console writes or self-update. Unavailable is never
reported as up to date. Trust is the project's HTTPS GitHub release, not a claim
that a checksum is an independent signature.
"""

import hashlib
import json
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

REPO = "Wkrotik/OrBeats"
APP_VERSION = "0.1.13"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"
NAMES = {"main": "orbeats.prx", "extras": "orbeats_extras.prx"}


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", value):
        raise ValueError("Invalid release version")
    return tuple(map(int, value.split(".")))


HOSTS = {"api.github.com", "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        target = urlsplit(url)
        if (
            target.scheme != "https"
            or target.hostname not in HOSTS
            or target.username
            or target.password
            or target.port not in (None, 443)
        ):
            raise ValueError("Unexpected release download redirect")
        return super().redirect_request(request, response, code, message, headers, url)


def read(url, limit):
    if url != API and not url.startswith(f"https://github.com/{REPO}/releases/download/"):
        raise ValueError("Only the official release feed is allowed")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "OrBeats/" + APP_VERSION,
            "Accept": "application/vnd.github+json" if url == API else "application/octet-stream",
        },
    )
    opener = urllib.request.build_opener(ReleaseRedirect())
    with opener.open(request, timeout=15) as response:
        if urlsplit(response.geturl()).scheme != "https" or urlsplit(response.geturl()).hostname not in HOSTS:
            raise ValueError("Unexpected release download host")
        value = response.read(limit + 1)
    if len(value) > limit:
        raise ValueError("Release response exceeds size limit")
    return value


def release():
    metadata = json.loads(read(API, 1000000))
    if not isinstance(metadata, dict) or metadata.get("draft") or metadata.get("prerelease"):
        raise ValueError("No stable release available")
    tag = metadata.get("tag_name", "")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Unexpected release tag")
    prefix = f"https://github.com/{REPO}/releases/download/{tag}/"
    assets = metadata.get("assets", [])
    if (
        not isinstance(assets, list)
        or len(assets) > 30
        or any(not isinstance(a, dict) or not isinstance(a.get("name"), str) for a in assets)
    ):
        raise ValueError("Invalid release assets")
    by_name = {a["name"]: a for a in assets}
    if len(by_name) != len(assets) or "release-manifest.json" not in by_name:
        raise ValueError("Release manifest unavailable")
    if by_name["release-manifest.json"].get("browser_download_url") != prefix + "release-manifest.json":
        raise ValueError("Manifest is not an official release asset")
    manifest = json.loads(read(prefix + "release-manifest.json", 16384))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != 1
        or manifest.get("app") != tag[1:]
        or not isinstance(manifest.get("plugins"), dict)
    ):
        raise ValueError("Release version mismatch")
    for kind, name in NAMES.items():
        row = manifest.get("plugins", {}).get(kind, {})
        if not isinstance(row, dict):
            raise ValueError("Invalid plugin release record")
        number(row.get("version"))
        if row.get("asset") != name or not re.fullmatch("[0-9a-f]{64}", str(row.get("sha256"))):
            raise ValueError("Invalid plugin release record")
        if type(row.get("bytes")) is not int or not 1 <= row["bytes"] <= 2000000:
            raise ValueError("Invalid plugin release size")
        if by_name.get(name, {}).get("browser_download_url") != prefix + name:
            raise ValueError("Plugin is not an official release asset")
    return manifest, prefix


def check(main_version=None, extras_version=None):
    try:
        manifest, _ = release()
        local = {"app": APP_VERSION, "main": main_version, "extras": extras_version}
        latest = {"app": manifest["app"], **{k: manifest["plugins"][k]["version"] for k in NAMES}}
        return {
            "state": "checked",
            "url": PAGE,
            "versions": {
                k: {"current": v, "latest": latest[k], "update_available": number(latest[k]) > number(v) if v else None}
                for k, v in local.items()
            },
            "message": "Official GitHub release checked. Plugin comparisons use bundled versions; check PS4 versions separately.",
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {
            "state": "unavailable",
            "url": PAGE,
            "message": "Update check unavailable. This does not mean up to date. " + str(exc),
        }


def install(config, kind):
    if kind not in NAMES:
        raise ValueError("Unknown plugin")
    manifest, prefix = release()
    row = manifest["plugins"][kind]
    blob = read(prefix + row["asset"], 2000000)
    if len(blob) != row["bytes"] or hashlib.sha256(blob).hexdigest() != row["sha256"]:
        raise ValueError("Plugin release integrity failure; nothing installed")
    import extras_manager as extras
    import library_manager as library

    canonical = library.elf_from_fself(blob)
    actual = library.binary_version(canonical) if kind == "main" else extras.version(canonical)
    if actual != row["version"]:
        raise ValueError("Plugin release binary/version mismatch")
    with tempfile.TemporaryDirectory(prefix="orbeats-plugin-") as tmp:
        artifact = Path(tmp) / NAMES[kind]
        artifact.write_bytes(blob)
        return (
            library.deploy_plugin(config, artifact, release_version=actual)
            if kind == "main"
            else extras.deploy(config, artifact)
        )
