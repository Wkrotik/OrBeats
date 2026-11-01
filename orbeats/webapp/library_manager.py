"""Closed-title management of our manifest; never edit stock data or other plugins."""

import hashlib
import json
import re
import sys
import uuid
from contextlib import contextmanager
from ftplib import FTP, error_perm
from pathlib import Path
from threading import Lock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import additive_companion as core
from additive_library import BASE, MAX_BYTES, encode, paths
from goldhen_config import merge_ini
from console_transaction import Transaction

# GoldHEN can time out when a browser requests several covers simultaneously.
_ftp_lock = Lock()


def acquire_install_lock(f):
    return core.acquire_install_lock(f)

@contextmanager
def connection(config, write=False):
    with _ftp_lock:
        a = config["ps4"]
        f = FTP()
        locked = False
        try:
            f.connect(a["ip"], int(a.get("ftp_port", 2121)), timeout=15)
            f.login(a.get("ftp_user", "anonymous"), a.get("ftp_password", ""))
            if write:
                core.closed(f)
                acquire_install_lock(f)
                locked = True
            yield f
        finally:
            if locked:
                try:
                    f.rmd(BASE + "/.install-lock")
                except Exception:
                    pass
            f.close()


def recover_install_lock(config):
    """Explicit recovery ONLY: empty lock, stable manifest/names, no pending files.

    User must stop all writers on EVERY computer. FTP has no global process/owner
    query: these checks cannot establish remote writer inactivity by themselves.
    Never recursively remove anything or auto-resume an installation.
    """
    from console_transaction import LOCAL_BACKUPS, archive

    lock = BASE + "/.install-lock"

    def names(f, folder):
        rows = f.nlst(folder)  # Listing failure is not absence or an empty lock.
        if len(rows) > 4096:
            raise ValueError("Recovery listing exceeds safety bound; inspect manually")
        result = []
        for path in rows:
            if path.startswith("/") and not path.startswith(folder + "/"):
                raise ValueError("Unexpected recovery listing; inspect manually")
            name = path.rstrip("/").rsplit("/", 1)[-1]
            if name not in (".", ".."):
                result.append(name)
        return sorted(result)

    def snapshot(f):
        core.closed(f)
        root = names(f, BASE)
        if ".install-lock" not in root:
            raise ValueError("Installation lock changed during recovery; inspect before retrying")
        if names(f, lock):
            raise ValueError("Installation lock is not empty. Nothing was removed; inspect recovery data")
        manifest = core.read(f, BASE + "/library.bin", MAX_BYTES)
        songs = core.decode(manifest)
        listings = {BASE: root}
        media = [n for n in root if re.fullmatch(r"bsd_additive_[0-9a-f]{24}-media", n)]
        if len(media) > 256:
            raise ValueError("Too many recovery directories; inspect manually")
        for name in media:
            listings[BASE + "/" + name] = names(f, BASE + "/" + name)
        for folder, entries in listings.items():
            if any(any(t in n for t in (".stage-", ".rollback-", ".tmp-")) or n == "library.bin.bak" for n in entries):
                raise ValueError("Interrupted-install files need inspection. Nothing was removed")
        for song in songs:
            for path in paths(song):
                parent, name = path.rsplit("/", 1)
                if name not in listings.get(parent, []):
                    raise ValueError("Library files are missing; inspect recovery state before clearing its lock")
        return manifest, listings

    # Read-only connection avoids trying to acquire the lock being recovered;
    # _ftp_lock still serializes local management FTP access.
    with connection(config) as f:
        core.closed(f)
        if ".install-lock" not in names(f, BASE):
            return {"ok": True, "removed": False, "message": "No installation lock exists. Nothing changed."}
        before, listing = snapshot(f)
        directory = LOCAL_BACKUPS / ("lock-recovery-" + uuid.uuid4().hex)
        archive(directory, "library-before.bin", before)
        archive(directory, "inspection.json", json.dumps(listing, sort_keys=True).encode())
        if snapshot(f) != (before, listing):
            raise ValueError("Console state changed during recovery. Nothing was removed")
        core.closed(f)
        if names(f, lock):
            raise ValueError("Lock contents changed. Nothing was removed")
        # RMD cannot remove a nonempty directory. NO DELE, recursive traversal,
        # writes to song/plugin files, or implicit restart is permitted here.
        f.rmd(lock)
        archive(directory, "lock-removed.json", b'{"removed":true,"automatic_retry":false}')
        remaining = names(f, BASE)
        if ".install-lock" in remaining or core.read(f, BASE + "/library.bin", MAX_BYTES) != before:
            raise ValueError("Lock removal sent, but console state changed afterward. Do not retry; inspect recovery evidence")
        return {"ok": True, "removed": True, "message": "Empty installation lock removed. Library and backups were not changed. No installation was restarted."}


def test_connection(config):
    """Read-only FTP connect/login test, independent of library setup."""
    with connection(config):
        pass


def catalog(config):
    with connection(config) as f:
        songs, manifest = core.load_library(f)
        if manifest is None:
            # Compiled migration defaults are not proof that maps are installed.
            found = [
                core.read(f, path, spec["bytes"] + 1, missing=True) is not None
                for song in songs
                for path, spec in zip(paths(song), (song, song["cover"], song["preview"]))
            ]
            if not any(found):
                return []
            if not all(found):
                raise ValueError("Incomplete legacy library; recover its files before management")
            for song in songs:
                core.checked(f, song)
        for song in songs:
            raw = core.read(f, BASE + "/" + song["id"] + "-media/map-info.json", 2000001, missing=True)
            if raw:
                try:
                    song["info"] = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    song["info_warning"] = "Malformed optional metadata"
        return songs


def media(config, id, kind):
    if kind not in ("cover", "preview"):
        raise ValueError("Unknown media type")
    with connection(config) as f:
        songs, _ = core.load_library(f)
        s = next((s for s in songs if s["id"] == id), None)
        if not s:
            raise ValueError("Unknown installed map")
        b = core.read(f, paths(s)[1 if kind == "cover" else 2], s[kind]["bytes"] + 1)
        if len(b) != s[kind]["bytes"] or core.fnv(b) != s[kind]["fnv"]:
            raise ValueError(kind.title() + " checksum mismatch")
        return b


def remove(config, id):
    # Commit removal first. Only our exact immutable paths may be deleted afterwards.
    with connection(config, True) as f:
        songs, old = core.load_library(f)
        song = next((s for s in songs if s["id"] == id), None)
        if not song:
            raise ValueError("Unknown installed map")
        candidate = [s for s in songs if s["id"] != id]
        run = uuid.uuid4().hex
        # Retain a legal type-tree seed on the PS4, not a host-side song library.
        # Otherwise deleting the last entry makes the next conversion impossible.
        if not candidate and not any(p.rstrip("/").rsplit("/", 1)[-1] == "template.bundle" for p in f.nlst(BASE)):
            blob = core.checked_bundle(f, song)
            staged = core.stage(f, BASE + "/template.bundle", blob, run)
            core.closed(f)
            f.rename(staged, BASE + "/template.bundle")
        core.commit_library(f, candidate, old, run, None)
        leftovers = []
        for path in (*paths(song), BASE + "/" + id + "-media/map-info.json"):
            try:
                core.closed(f)
                f.delete(path)
            except error_perm as e:
                if not str(e).startswith("550"):
                    leftovers.append(path)
            except Exception:
                leftovers.append(path)
        try:
            core.closed(f)
            f.rmd(paths(song)[1].rsplit("/", 1)[0])
        except error_perm:
            pass
        return {"ok": True, "count": len(candidate), "cleanup_pending": leftovers, "restart_required": True}


def elf_from_fself(b):
    import struct

    if b[:4] != bytes.fromhex("4f153d1d") or len(b) > 2000000:
        raise ValueError("Not a bounded GoldHEN FSELF")
    n = struct.unpack_from("<H", b, 24)[0]
    e = 32 + n * 32
    if b[e : e + 4] != b"\x7fELF":
        raise ValueError("Missing embedded ELF")
    po = struct.unpack_from("<Q", b, e + 32)[0]
    pn = struct.unpack_from("<H", b, e + 56)[0]
    if not 0 < pn < 128:
        raise ValueError("Bad ELF program header count")
    ph = [struct.unpack_from("<IIQQQQQQ", b, e + po + i * 56) for i in range(pn)]
    size = max(x[2] + x[5] for x in ph)
    if size > 2000000:
        raise ValueError("Oversized ELF")
    out = bytearray(size)
    out[: po + pn * 56] = b[e : e + po + pn * 56]
    for i in range(n):
        flags, off, size, mem = struct.unpack_from("<QQQQ", b, 32 + i * 32)
        if flags & 0xFFFFF == 0x2804:
            j = flags >> 20
            if j >= pn or size != ph[j][5] or off + size > len(b):
                raise ValueError("Invalid FSELF segment")
            out[ph[j][2] : ph[j][2] + size] = b[off : off + size]
    out[40:48] = b"\0" * 8
    out[58:64] = b"\0" * 6
    return bytes(out)


def binary_version(blob):
    """Read only the plugin's embedded startup banner, never a loose version string."""
    if not isinstance(blob, bytes) or not blob.startswith(b"\x7fELF") or len(blob) > 2000000:
        return None
    matches = set(re.findall(
        rb"=== (?:OrBeats|BS Deluxe|Beat Saber Deluxe) v([0-9]+\.[0-9]{4})(?: DEBUG)? started ===\x00", blob
    ))
    return next(iter(matches)).decode("ascii") if len(matches) == 1 else None


def plugin_status(config, artifact):
    """Read-only disk identity; does not claim the plugin is running in-game."""
    local = Path(artifact)
    candidate = elf_from_fself(local.read_bytes()) if local.is_file() else None
    with connection(config) as f:
        plugin = "/data/GoldHEN/plugins/orbeats.prx"
        blob = core.read(f, plugin, 2000000, missing=True)
        cap_raw = core.read(f, BASE + "/companion-protocol.json", 4096, missing=True)
        ini = core.read(f, "/data/GoldHEN/plugins.ini", 65536, missing=True)
        if core.read(f, plugin, 2000000, missing=True) != blob or core.read(f, BASE + "/companion-protocol.json", 4096, missing=True) != cap_raw:
            raise ValueError("Plugin changed during version check; wait for the update to finish and check again.")
    version = binary_version(blob)
    try:
        cap = json.loads(cap_raw) if cap_raw else {}
    except (ValueError, UnicodeDecodeError):
        cap = {}
    if not isinstance(cap, dict):
        cap = {}
    digest = hashlib.sha256(blob).hexdigest() if blob is not None else None
    capability_matches = bool(blob is not None and cap.get("schema") == 1 and cap.get("title") == "CUSA12878"
                              and cap.get("active_elf_sha256") == digest)
    declared = cap.get("plugin")
    version_matches = bool(version and (declared is None or declared == version))
    count = cap.get("max_songs", 8) if capability_matches and version_matches else None
    if type(count) is not int or not 1 <= count <= 64:
        count = None
    registration = "missing"
    try:
        if ini is not None:
            registration = "registered_once" if merge_ini(ini) == ini else "missing"
    except (ValueError, UnicodeDecodeError):
        registration = "needs_review"
    return {"installed": blob is not None, "installed_version": version,
            "available_version": binary_version(candidate), "version_source": "binary" if version else "unknown",
            "active_elf_sha256": digest, "capability_matches": capability_matches,
            "declared_version_matches": version_matches, "max_songs": count,
            "registration": registration, "runtime_verified": False}


def deploy_plugin(config, artifact, release_version=None):
    candidate = Path(artifact).read_bytes()
    canonical = elf_from_fself(candidate)
    if len(candidate) > 2000000:
        raise ValueError("Oversized plugin")
    source = (Path(__file__).resolve().parents[1] / "src/main.cpp").read_text()
    match = re.search(r'#define PLUGIN_VERSION "(v[0-9.]+)"', source)
    if release_version is not None:
        if binary_version(canonical) != release_version:
            raise ValueError("Verified release version does not match binary")
    elif not match or match[1].encode() + b"\x00" not in canonical or b"OrBeats" not in canonical:
        raise ValueError("Build the current OrBeats plugin first; stale or unrelated artifact refused")
    run = uuid.uuid4().hex
    plugin = "/data/GoldHEN/plugins/orbeats.prx"
    with connection(config) as f:
        core.closed(f)
        for folder in ["/data/GoldHEN/plugins", "/data/GoldHEN/AFR", "/data/GoldHEN/AFR/CUSA12878", BASE]:
            try:
                f.mkd(folder)
            except error_perm:
                f.nlst(folder)
        acquire_install_lock(f)
        transaction = Transaction(core, f, run)
        committed = False
        recovered = False
        unchanged = object()

        def publish(path, value, expected=None, original_expected=unchanged):
            original = core.read(f, path, 2000000, missing=True)
            if original_expected is not unchanged and original != original_expected:
                raise ValueError('File changed concurrently: ' + path)
            transaction.publish(path, value, original, wanted=value if expected is None else expected)

        try:
            ini = "/data/GoldHEN/plugins.ini"
            original = core.read(f, ini, 65536, missing=True)
            merged = merge_ini(original or b"")  # Validate before replacing any active file.
            legacy = '/data/GoldHEN/plugins/beat_saber_deluxe.prx'
            legacy_blob = core.read(f, legacy, 2000000, missing=True)
            if legacy_blob is not None and binary_version(legacy_blob) is None:
                raise ValueError('Unrecognized legacy plugin; refusing automatic retirement')
            songs, manifest = core.load_library(f)
            format2 = tuple(map(int, binary_version(canonical).split("."))) >= (0, 8073)
            if any(s.get('environment') for s in songs) and not format2:
                raise ValueError('Existing environment-aware library requires plugin 0.8073 or newer; downgrade refused')
            required = 1 if manifest is None else int(chr(manifest[7]))
            supported = 4 if b'ORB_MODES_V1' in canonical else 3 if b'ORB_PRESENTATION_V1' in canonical else 2 if format2 else 1
            if required > supported:
                raise ValueError(f'Existing library format{required} requires a newer OrBeats plugin; downgrade refused')
            if manifest is None:
                found = [
                    core.read(f, path, spec["bytes"] + 1, missing=True) is not None
                    for song in songs
                    for path, spec in zip(paths(song), (song, song["cover"], song["preview"]))
                ]
                if any(found) and not all(found):
                    raise ValueError("Incomplete legacy library; recover its files before plugin setup")
                if all(found):
                    for song in songs:
                        core.checked(f, song)
                else:
                    songs = []  # A fresh console must not advertise two nonexistent maps.
            publish(plugin, candidate, canonical)
            if core.read(f, ini, 65536, missing=True) != original:
                raise ValueError("plugins.ini changed concurrently")
            publish(ini, merged, original_expected=original)
            if manifest is None:
                publish(BASE + "/library.bin", encode(songs), original_expected=None)
            flags = "/data/GoldHEN/AFR/CUSA12878/features.json"
            if core.read(f, flags, 65536, missing=True) is None:
                values = {"enable_plugin": True, "enable_additive_song_packs": True}
                for key in [
                    "custom_song_replacements",
                    "song_metadata_modification",
                    "beatmap_mode_mapping",
                    "song_previews",
                    "in_game_plugin_toggle",
                    "game_data_extractor",
                ]:
                    values["enable_" + key] = False
                publish(flags, json.dumps(values).encode(), original_expected=None)
            # Capability is last: interrupted setup cannot falsely approve new imports.
            publish(
                BASE + "/companion-protocol.json",
                json.dumps(
                    {
                        "schema": 1,
                        "title": "CUSA12878",
                        "plugin": binary_version(canonical),
                        "active_elf_sha256": hashlib.sha256(canonical).hexdigest(),
                        "max_songs": 64,
                        "native_maps": 1 if b"ORB_NATIVE_MAPS_V1" in canonical else 0,
                        "max_library_bytes": MAX_BYTES,
                        "library_format": 4 if b"ORB_MODES_V1" in canonical else 3 if b"ORB_PRESENTATION_V1" in canonical else 2 if tuple(map(int, binary_version(canonical).split("."))) >= (0, 8073) else 1,
                    }
                ).encode(),
            )
            # Registration now points only at OrBeats. Retire the legacy binary
            # in the SAME transaction so any earlier failure restores both paths.
            transaction.retire(legacy, legacy_blob)
            transaction.finish()
            committed = True
            return {
                "ok": True,
                "restart_required": True,
                "message": "Plugin installed; existing plugins.ini entries preserved. Restart the game. Empty libraries need a legal conversion template for their first import.",
            }
        except Exception:
            transaction.rollback()
            recovered = True
            raise
        finally:
            if committed or recovered:
                try:
                    f.rmd(BASE + "/.install-lock")
                except Exception:
                    pass
