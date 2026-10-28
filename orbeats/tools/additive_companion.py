"""Additive CLI backend used by the existing companion job runner.

Closed-title only. Immutable song files first, checked library.bin rename LAST.
Existing stock packs/catalog/redirects/flags/plugin are NEVER edited here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile
from ftplib import FTP, error_perm
from pathlib import Path

from additive_library import BASE, MAX_BYTES, decode, descriptor, encode, fnv, paths

ROOT = Path(__file__).resolve().parents[1]


def helper(name):
    p = ROOT / "development/scripts" / name
    spec = importlib.util.spec_from_file_location(name, p)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load additive preparation tool: " + str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(ftp, path, limit=200000001, missing=False):
    out = bytearray()

    def collect(b):
        out.extend(b)
        if len(out) > limit:
            raise ValueError("remote file exceeds bound: " + path)

    try:
        ftp.retrbinary("RETR " + path, collect)
    except error_perm as e:
        if missing and str(e).startswith("550"):
            # 550 can also mean denied. Require a successful parent listing and
            # absence of the exact name before treating a read failure as missing.
            name = Path(path).name
            parent = path.rsplit("/", 1)[0]
            if any(item.rstrip("/").rsplit("/", 1)[-1] == name for item in ftp.nlst(parent)):
                raise ValueError("Cannot read existing remote file; refusing to overwrite: " + path) from e
            return None
        raise
    return bytes(out)


def closed(ftp):
    # Successful sandbox listing is required; errors/permission failures are NOT closed.
    if any("CUSA12878" in p for p in ftp.nlst("/mnt/sandbox")):
        raise ValueError("Fully close Beat Saber before importing maps; keep FTP running.")


def checked_bundle(ftp, song):
    path = paths(song)[0]
    data = read(ftp, path, song["bytes"] + 1)
    if len(data) != song["bytes"] or fnv(data) != song["fnv"]:
        raise ValueError("library content verification failed: " + path)
    if hashlib.sha256(data).hexdigest() != song["sha256"]:
        raise ValueError("bundle SHA256 mismatch: " + path)
    return data


def checked(ftp, song):
    data = [checked_bundle(ftp, song)]
    for p, spec in zip(paths(song)[1:], (song["cover"], song["preview"])):
        b = read(ftp, p, spec["bytes"] + 1)
        if len(b) != spec["bytes"] or fnv(b) != spec["fnv"]:
            raise ValueError("library content verification failed: " + p)
        data.append(b)
    return data


def stage(ftp, path, content, run):
    closed(ftp)
    temporary = path + ".stage-" + run
    ftp.storbinary("STOR " + temporary, io.BytesIO(content))
    if read(ftp, temporary, len(content) + 1) != content:
        raise ValueError("staged full readback failed: " + path)
    return temporary


def load_library(ftp):
    raw = read(ftp, BASE + "/library.bin", MAX_BYTES + 1, missing=True)
    if raw is not None:
        return decode(raw), raw
    # Absent is only accepted for the known two-song migration. Every seed byte
    # is checked remotely before a new manifest can replace compiled defaults.
    if any("library.bin.backup-" in p or "library.bin.rollback-" in p for p in ftp.nlst(BASE)):
        raise ValueError("missing library with retained backup; recover it before importing")
    seed = json.loads((ROOT / "development/fixtures/additive-baseline-library.json").read_text())
    return decode(encode(seed)), None


def commit_library(ftp, songs, expected, run, backup_dir):
    from console_transaction import Transaction
    content = encode(songs)
    # Host storage is durable even when a caller uses a temporary report folder.
    transaction = Transaction(__import__(__name__), ftp, run)
    try:
        transaction.publish(BASE + '/library.bin', content, expected)
    except Exception:
        transaction.rollback()
        raise
    transaction.finish()
    return content


def download(map_id, destination):
    match = re.fullmatch(r"(?:https://beatsaver\.com/maps/)?([0-9a-fA-F]{1,12})/?", map_id)
    if not match:
        raise ValueError("BeatSaver map key or https://beatsaver.com/maps/<key> required")

    def fetch(url, limit):
        req = urllib.request.Request(url, headers={"User-Agent": "OrBeats/1"})
        with urllib.request.urlopen(req, timeout=45) as r:
            final = urllib.parse.urlparse(r.geturl())
            if final.scheme != "https" or not final.hostname or not final.hostname.endswith(".beatsaver.com"):
                raise ValueError("untrusted BeatSaver redirect")
            data = r.read(limit + 1)
            if len(data) > limit:
                raise ValueError("BeatSaver download exceeds bound")
            return data

    meta = json.loads(fetch("https://api.beatsaver.com/maps/id/" + match[1].lower(), 2000000))
    versions = meta.get("versions", [])
    if not versions:
        raise ValueError("BeatSaver map has no version")
    version = versions[0]
    for d in version.get("diffs", []):
        if d.get("ne") or d.get("me") or d.get("chroma"):
            raise ValueError("Map requires unsupported extensions: " + ", ".join(
                label for key, label in (("ne", "Noodle Extensions"), ("me", "Mapping Extensions"), ("chroma", "Chroma")) if d.get(key)
            ) + " in " + str(d.get("difficulty", "unknown difficulty")) + ". Mod-dependent maps cannot be installed safely.")
    url = version["downloadURL"]
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or not u.hostname or not u.hostname.endswith(".beatsaver.com"):
        raise ValueError("untrusted BeatSaver download host")
    data = fetch(url, 100000000)
    destination = Path(destination).resolve()
    destination.mkdir()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries = z.infolist()
        if len(entries) > 1000 or sum(i.file_size for i in entries) > 300000000:
            raise ValueError("oversized archive")
        seen = set()
        for i in entries:
            target = (destination / i.filename).resolve()
            if (
                "\\" in i.filename
                or not target.is_relative_to(destination.resolve())
                or (i.external_attr >> 16) & 0xF000 == 0xA000
            ):
                raise ValueError("unsafe archive entry")
            normalized = str(target).casefold()
            if normalized in seen:
                raise ValueError("duplicate archive entry")
            seen.add(normalized)
        z.extractall(destination)
    infos = [p.parent for p in destination.rglob("*") if p.name.lower() == "info.dat"]
    if len(infos) != 1:
        raise ValueError("one map folder required")
    # BeatSaver's hash is SHA1(Info.dat + referenced chart bytes in Info order),
    # NOT SHA1 of the ZIP container. Verify before any media conversion.
    folder = infos[0]
    info_path = next(p for p in folder.iterdir() if p.name.lower() == "info.dat")
    data = info_path.read_bytes()
    info = json.loads(data)
    prepare = helper("prepare_additive_bundle.py")
    for name in helper("import_v4_additive.py").references(info):
        data += prepare.local_file(folder, name).read_bytes()
    if hashlib.sha1(data).hexdigest().lower() != version["hash"].lower():
        raise ValueError("BeatSaver content hash mismatch")
    (folder / "beatsaver-metadata.json").write_text(json.dumps(meta), encoding="utf8")
    return folder


def install(config, map_id="", song_dir="", report_dir=None):
    if config.get("title", {}).get("id") != "CUSA12878":
        raise ValueError("only CUSA12878 2.04 supported")
    address = config["ps4"]
    report_dir = Path(report_dir or Path(tempfile.gettempdir()) / "orbis-beats-reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    run = uuid.uuid4().hex
    ftp = FTP()
    ftp.connect(address["ip"], int(address.get("ftp_port", 2121)), timeout=45)
    ftp.login(address.get("ftp_user", "anonymous"), address.get("ftp_password", ""))
    locked = False
    try:
        print("[additive] Checking closed title, plugin capability and library...", flush=True)
        closed(ftp)
        # Capability marker is deployed WITH a tested native binary; matching full
        # active ELF prevents installing a manifest an older plugin would ignore.
        cap = json.loads(read(ftp, BASE + "/companion-protocol.json", 4096))
        if cap.get("schema") != 1 or cap.get("title") != "CUSA12878":
            raise ValueError("install companion-capable plugin first")
        plugin = read(ftp, "/data/GoldHEN/plugins/orbeats.prx", 2000000)
        if hashlib.sha256(plugin).hexdigest() != cap.get("active_elf_sha256"):
            raise ValueError("plugin/capability mismatch; no files changed")
        flags = json.loads(read(ftp, "/data/GoldHEN/AFR/CUSA12878/features.json", 65536))
        if flags.get("enable_plugin") is not True or flags.get("enable_additive_song_packs") is not True:
            raise ValueError("enable additive plugin with game closed first")
        if any(
            flags.get(k)
            for k in [
                "enable_custom_song_replacements",
                "enable_song_metadata_modification",
                "enable_beatmap_mode_mapping",
                "enable_song_previews",
            ]
        ):
            raise ValueError("legacy replacement features must remain OFF")
        closed(ftp)
        try:
            ftp.mkd(BASE + "/.install-lock")
        except error_perm as e:
            raise ValueError("another import or interrupted import holds .install-lock; inspect before recovery") from e
        locked = True
        songs, old = load_library(ftp)
        print(f"[additive] Retaining {len(songs)} library entries; unrelated map files are not audited.", flush=True)
        template_seed = None
        if old is None:
            # Compiled legacy defaults are not proof of installation: verify once before migration.
            print("[additive] Verifying legacy files for one-time manifest migration...", flush=True)
            for i, s in enumerate(songs):
                content = checked(ftp, s)
                if i == 0:
                    template_seed = content[0]
                del content
        elif songs:
            print("[additive] Reading one verified conversion template...", flush=True)
            template_seed = checked_bundle(ftp, songs[0])
        with tempfile.TemporaryDirectory(prefix="bsd-additive-") as tmp:
            tmp = Path(tmp)
            source = Path(song_dir).resolve() if song_dir else download(map_id, tmp / "download")
            importer = helper("import_v3_additive.py")
            prepare = helper("prepare_additive_bundle.py")
            media = helper("prepare_additive_media.py")
            source_metadata = source / "beatsaver-metadata.json"
            infos = [p for p in source.iterdir() if p.name.lower() == "info.dat"]
            if len(infos) != 1:
                raise ValueError("one Info.dat required")
            info = json.loads(infos[0].read_text(encoding="utf-8-sig"))
            if not str(info.get("_version", "")).startswith("2."):
                print("[additive] Converting supported InfoV4/V4 charts to the PS4 format...", flush=True)
                v4_source = tmp / "v4-source"
                helper("import_v4_additive.py").normalize(source, v4_source, prepare.local_file)
                source = v4_source
            print("[additive] Validating and converting map/audio...", flush=True)
            normalized = tmp / "normalized"
            import_report = importer.import_song(source, normalized)
            for difficulty, count in import_report.get("ignored_v2_wall_placeholders", {}).items():
                print(f"[additive] Ignored {count} all-zero legacy wall placeholders in {difficulty}; playable walls retained.", flush=True)
            for difficulty, speed in import_report.get("default_njs", {}).items():
                print(f"[additive] Using native default note jump speed: {difficulty} {speed}.", flush=True)
            for skipped in import_report.get("skipped_difficulties", []):
                print("[additive] Not installed: " + skipped, flush=True)
            template = tmp / "template.bundle"
            seed = template_seed if songs else read(ftp, BASE + "/template.bundle", 200000001, missing=True)
            if seed is None:
                local = Path(config.get("additive_template", ""))
                if not local.is_file():
                    raise ValueError(
                        "Empty library needs a one-time legal conversion template; set its local path in Settings."
                    )
                seed = local.read_bytes()
                if len(seed) > 200000000:
                    raise ValueError("Conversion template exceeds size bound")
            template.write_bytes(seed)
            out = tmp / "prepared"
            source_info = next(p for p in source.iterdir() if p.name.lower() == "info.dat")
            original_audio = prepare.local_file(source, json.loads(source_info.read_text(encoding="utf-8-sig"))["_songFilename"])
            manifest = prepare.prepare(normalized, template, out, original_audio=original_audio)
            if manifest.get('characteristics') and cap.get('library_format',1)<4:
                raise ValueError('Update the OrBeats plugin in Settings for native characteristics.')
            if manifest.get('presentation') and cap.get('library_format', 1) < 3:
                raise ValueError('Update the OrBeats plugin in Settings for authored colors, loudness and offsets.')
            if (manifest.get('native_v4') or manifest.get('environment') not in (None, 'WeaveEnvironment')) and cap.get('native_maps') != 1:
                raise ValueError('This map requires the native-map plugin update in Settings before importing.')
            if manifest["audio_codec"] == "vorbis":
                print(f"[additive] Audio: original Vorbis packets at {manifest['audio_sample_rate']} Hz, without lossy re-encoding.", flush=True)
            else:
                print("[additive] Audio: PCM16 fallback (" + manifest["audio_fallback_reason"] + ").", flush=True)
            # A first import can later become its own conversion template.
            # Unity object allocation differs from the original stock template;
            # do not mistake that for changed source content. Independently
            # validate the installed immutable bundle against normalized maps,
            # sample/audio content and fresh manifest before retaining its bytes.
            installed = next((s for s in songs if s["id"] == manifest["level_id"]), None)
            if installed is not None:
                retained = checked_bundle(ftp, installed)
                validation = tmp / "retained"
                validation.mkdir()
                retained_manifest = dict(manifest)
                retained_manifest["bundle"] = dict(manifest["bundle"], bytes=len(retained), sha256=hashlib.sha256(retained).hexdigest())
                (validation / manifest["bundle"]["file"]).write_bytes(retained)
                (validation / "manifest.json").write_text(json.dumps(retained_manifest))
                prepare.validate(validation, prepare.load_song(normalized))
                manifest = retained_manifest
                (out / manifest["bundle"]["file"]).write_bytes(retained)
                (out / "manifest.json").write_text(json.dumps(manifest))
            menu = tmp / "media"
            m = media.prepare(source, out / "manifest.json", menu)
            blobs = [
                (out / manifest["bundle"]["file"]).read_bytes(),
                (menu / "song-cover.png").read_bytes(),
                (menu / "preview.wav").read_bytes(),
            ]
            song = descriptor(manifest, *blobs, m["preview_duration_seconds"])
            # Decode rounds floats exactly as the native reader; canonical equality.
            song = decode(encode([song]))[0]
            import score_source
            source_sha1 = score_source.original_hash(source, helper("import_v4_additive.py").references, prepare.local_file)
            # Compression has its own immutable ID; reimport must not create a
            # duplicate or replace an existing PCM entry for identical input.
            same = next((s for s in songs if s["id"] == song["id"]), None)
            if same is None and manifest.get("pcm_level_id"):
                same = next((s for s in songs if s["id"] == manifest["pcm_level_id"]), None)
            if same:
                if same["id"] == song["id"] and same != song:
                    raise ValueError("same level ID has different content; refusing overwrite")
                print(
                    "[additive] Song already listed; initializing library if needed, without duplication or repair.", flush=True
                )
                score_source.publish(ftp, __import__(__name__), same, source_sha1, run)
                if old is None:
                    commit_library(ftp, songs, old, run, report_dir)
                return {
                    "ok": True,
                    "already_present": True,
                    "title": song["title"],
                    "count": len(songs),
                    "restart_required": True,
                }
            candidate = songs + [song]
            if len(candidate) > cap.get("max_songs", 8):
                raise ValueError(f"Installed plugin permits {cap.get('max_songs', 8)} songs; this import would exceed that limit. Update the plugin in Settings for a higher-capacity profile.")
            library_format = cap.get('library_format', 1)
            if any(s.get('environment') for s in candidate) and (type(library_format) is not int or library_format < 2):
                raise ValueError('This lighting map requires the environment-aware plugin. Update the plugin in Settings before importing.')
            encode(candidate)  # cap/format BEFORE any upload
            print("[additive] Uploading immutable new-song files with full readback...", flush=True)
            for path, b in zip(paths(song), blobs):
                closed(ftp)
                # Optional reads prove absence using a successful parent listing.
                # New media folders must exist BEFORE checking their cover/preview;
                # otherwise both RETR and NLST return 550 on a legitimate first import.
                parent = path.rsplit("/", 1)[0]
                if parent != BASE:
                    try:
                        ftp.mkd(parent)
                    except error_perm as exc:
                        if not str(exc).startswith("550"):
                            raise
                        ftp.nlst(parent)  # prove it exists rather than hide a failed mkdir
                remote = read(ftp, path, len(b) + 1, missing=True)
                if remote is not None:
                    if remote != b:
                        raise ValueError("immutable song path collision: " + path)
                    continue
                staged = stage(ftp, path, b, run)
                closed(ftp)
                if read(ftp, path, len(b) + 1, missing=True) is not None:
                    raise ValueError("song appeared concurrently")
                ftp.rename(staged, path)
                if read(ftp, path, len(b) + 1) != b:
                    raise ValueError("final song readback mismatch")
            metadata = source_metadata
            if metadata.is_file():
                raw = metadata.read_bytes()
                if len(raw) > 2000000:
                    raise ValueError("Oversized map metadata")
                path = BASE + "/" + song["id"] + "-media/map-info.json"
                if read(ftp, path, 2000001, missing=True) is None:
                    staged = stage(ftp, path, raw, run)
                    closed(ftp)
                    ftp.rename(staged, path)
            score_source.publish(ftp, __import__(__name__), song, source_sha1, run)
            closed(ftp)
            # Existing immutable descriptors are retained; manifest CAS protects concurrent edits.
            # Only new files need full content verification during an append.
            print("[additive] Publishing library last; restart Beat Saber after completion.", flush=True)
            commit_library(ftp, candidate, old, run, report_dir)
            result = {
                "ok": True,
                "already_present": False,
                "id": song["id"],
                "title": song["title"],
                "count": len(candidate),
                "restart_required": True,
                "stock_changed": False,
                "plugin_changed": False,
                "limitations": "Validated vanilla V2/V3/V4, native arcs/chains/NJS and lighting, stock environments and supported characteristics; runtime extensions require OrBeats 0.8075. Mod-required effects are refused, not stripped.",
            }
            (report_dir / ("install-" + run + ".json")).write_text(json.dumps(result, indent=2) + "\n")
            return result
    finally:
        if locked:
            try:
                ftp.rmd(BASE + "/.install-lock")
            except Exception:
                pass  # Preserve failure, stale lock requires explicit recovery.
        ftp.close()
