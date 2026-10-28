"""Curated runtime resources. Never copy a checkout, user config, songs or dumps."""

import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath

# Deliberate source/data inventory, reviewed rather than recursive directory copy.
FILES = (
    "VERSION",
    "webapp/VERSION",
    "ps4_config.example.json",
    "beat_saber_song_ids.json",
    "src/main.cpp",
    "orbeats.prx",
    "webapp/server.py",
    "webapp/companion_api.py",
    "webapp/library_manager.py",
    "webapp/batch_runner.py",
    "webapp/beatsage_client.py",
    "webapp/adapters/__init__.py",
    "webapp/adapters/paths.py",
    "webapp/adapters/config.py",
    "webapp/adapters/batch.py",
    "webapp/adapters/beatsage.py",
    "webapp/adapters/beatsaver.py",
    "webapp/adapters/deploy.py",
    "webapp/adapters/install_queue.py",
    "webapp/adapters/loadout.py",
    "webapp/adapters/ps4.py",
    "webapp/adapters/runner.py",
    "webapp/adapters/songs.py",
    "webapp/adapters/testsong.py",
    "webapp/adapters/webapp_state.py",
    "webapp/static/companion.html",
    "webapp/static/companion.css",
    "webapp/static/companion.js",
    "webapp/static/index.html",
    "webapp/static/app.js",
    "webapp/static/style.css",
    "webapp/static/dumper.cfg",
    "webapp/static/map-placeholder.svg",
    "tools/full_custom_song_pipeline.py",
    "tools/runtime_dispatch.py",
    "tools/build_pack_mode_bundles.py",
    "tools/additive_companion.py",
    "tools/additive_library.py",
    "tools/additive_lighting.py",
    "tools/additive_modes.py",
    "tools/additive_presentation.py",
    "tools/additive_v3_native.py",
    "tools/additive_v4_native.py",
    "tools/console_transaction.py",
    "tools/native_hash.py",
    "tools/vorbis_audio.py",
    "tools/lapped_audio.py",
    "tools/goldhen_config.py",
    "tools/hevag_encoder.py",
    "tools/song_previews.py",
    "tools/download_beatsaver_songs.py",
    "development/scripts/import_v2_additive.py",
    "development/scripts/import_v3_additive.py",
    "development/scripts/import_v4_additive.py",
    "development/scripts/prepare_additive_bundle.py",
    "development/scripts/prepare_additive_media.py",
)


from media_profiles import (
    ELF_FILES as MEDIA_ELF_FILES,
)
from media_profiles import (
    EXECUTABLES as MEDIA_EXECUTABLES,
)
from media_profiles import (
    LINUX_BASE as MEDIA_FILES,
)
from media_profiles import (
    LINUX_CODECS as CODEC_FILES,
)
from media_profiles import (
    PROFILES as MEDIA_PROFILES,
)
from media_profiles import (
    validate_native,
)

__all__ = [
    "CODEC_FILES",
    "FILES",
    "MEDIA_ELF_FILES",
    "MEDIA_EXECUTABLES",
    "MEDIA_FILES",
    "MEDIA_PROFILES",
    "build",
    "content",
    "digest",
    "install",
    "safe_relative",
    "verify",
]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def safe_relative(name):
    if not isinstance(name, str) or "\\" in name or ":" in name:
        raise ValueError("Unsafe resource path")
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("..", ".") for part in path.parts)
        or str(path) != name
    ):
        raise ValueError("Unsafe resource path")
    return path


def content(root, name):
    path = root / safe_relative(name)
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError("Runtime resources must not be symlinks")
    value = path.read_bytes()
    if len(value) > 20000000:
        raise ValueError("Runtime resource exceeds size bound")
    return value


def build(source, output, license_path, media=None):
    source, output = Path(source).resolve(), Path(output)
    if output.exists():
        raise ValueError("Choose a new empty resource output directory")
    # Validate every source before creating an output tree.
    values = {name: content(source, name) for name in FILES}
    values["LICENSE"] = Path(license_path).read_bytes()
    if media is not None:
        media = Path(media).resolve()
        inventory = json.loads(content(media, "manifest.json"))
        expected = set(inventory) if isinstance(inventory, dict) else set()
        if not isinstance(inventory, dict) or expected not in tuple(
            {name.removeprefix("media/") for name in profile}
            for profile in MEDIA_PROFILES
        ):
            raise ValueError("Media payload does not match reviewed inventory")
        actual = {
            p.relative_to(media).as_posix() for p in media.rglob("*") if p.is_file()
        }
        if actual != expected | {"manifest.json"}:
            raise ValueError("Unexpected media payload files")
        for relative in sorted(expected):
            name = "media/" + relative
            value = content(media, relative)
            if inventory[relative] != digest(value):
                raise ValueError("Media payload integrity failure: " + relative)
            validate_native(name, value)
            values[name] = value
    output.mkdir(parents=True)
    manifest = {}
    for name, value in values.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        if name in MEDIA_EXECUTABLES:
            target.chmod(0o755)
        manifest[name] = {"bytes": len(value), "sha256": digest(value)}
    (output / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify(output)
    return manifest


def verify(root):
    root = Path(root).resolve()
    raw = (root / "runtime-manifest.json").read_bytes()
    if len(raw) > 65536:
        raise ValueError("Runtime manifest exceeds size bound")
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or set(manifest) not in (
        set(FILES) | {"LICENSE"},
        *(set(FILES) | {"LICENSE"} | set(profile) for profile in MEDIA_PROFILES),
    ):
        raise ValueError("Runtime manifest does not match curated inventory")
    for name, row in manifest.items():
        if (
            not isinstance(row, dict)
            or set(row) != {"bytes", "sha256"}
            or not re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"]))
        ):
            raise ValueError("Invalid runtime manifest record")
        value = content(root, name)
        validate_native(name, value)
        if len(value) != row["bytes"] or digest(value) != row["sha256"]:
            raise ValueError("Runtime resource integrity failure: " + name)
    actual = {
        str(p.relative_to(root).as_posix()) for p in root.rglob("*") if p.is_file()
    }
    if actual != set(manifest) | {"runtime-manifest.json"}:
        raise ValueError("Unexpected files in runtime resources")
    return digest(raw)


def install(root, state):
    """Copy verified code once to an isolated versioned workspace, never user data."""
    root, state = Path(root).resolve(), Path(state).resolve()
    version = verify(root)
    parent = state / "runtimes"
    if parent.is_symlink():
        raise ValueError("Desktop runtime directory must not be a symlink")
    parent.mkdir(exist_ok=True)
    target = parent / version
    if target.is_symlink():
        raise ValueError("Desktop runtime must not be a symlink")
    if target.exists():
        # Python is instructed not to generate pycache in the curated code tree.
        if verify(target) != version:
            raise ValueError("Desktop runtime changed")
        return target
    stage = parent / (version + ".stage")
    if stage.exists() or stage.is_symlink():
        raise ValueError("Interrupted runtime staging; inspect before explicit cleanup")
    shutil.copytree(root, stage, symlinks=False)
    verify(stage)
    stage.rename(target)
    return target
