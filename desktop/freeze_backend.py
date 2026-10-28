"""Build a local frozen Python-helper prototype, not an installer/release.

Native media tools/licenses and platform shell builds remain separate gates.
Outputs only to the supplied project-local scratch directory.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from build_legal import legal_inputs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop/backend"))
from media_profiles import validate_host_profile
from resources import build


def omit_glibc_companion(output, platform=sys.platform):
    """A fresh generated helper must use the runtime's matching GLIBC libmvec.

    PyInstaller can collect libmvec via system libvorbis. Its GLIBC_PRIVATE
    dependency is not a portable interface. Omit only that known generated file,
    before candidate manifests/sealing; never mutate the source or prior builds.
    The runtime OS supplies libmvec as part of its GLIBC package.
    """
    if platform != "linux":
        return []
    path = Path(output) / "dist/orbeats-backend/_internal/libmvec.so.1"
    if path.is_symlink():
        raise ValueError("Unexpected generated libmvec symlink")
    if not path.exists():
        return []
    if not path.is_file() or not path.read_bytes().startswith(b"\x7fELF"):
        raise ValueError("Expected generated libmvec ELF")
    path.unlink()
    return ["libmvec.so.1"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--media",
        type=Path,
        help="Verified native media payload for this build platform",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT):
        raise ValueError("Choose a fresh project-local scratch output")
    output.mkdir(parents=True)
    notices = legal_inputs()
    manifest = build(
        ROOT / "beat_saber_deluxe",
        output / "runtime",
        ROOT / "LICENSE",
        media=args.media,
    )
    validate_host_profile(manifest, sys.platform)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "orbeats-backend",
        "--distpath",
        str(output / "dist"),
        "--workpath",
        str(output / "work"),
        "--specpath",
        str(output),
        "--paths",
        str(ROOT / "desktop/backend"),
        "--paths",
        str(ROOT / "beat_saber_deluxe/webapp"),
        "--paths",
        str(ROOT / "beat_saber_deluxe/tools"),
        "--paths",
        str(ROOT / "beat_saber_deluxe/development/scripts"),
        "--add-data",
        str(output / "runtime") + ":runtime",
    ]
    for notice in notices:
        command += ["--add-data", str(notice) + ":third-party-notices"]
    modules = [
        "server",
        "companion_api",
        "library_manager",
        "batch_runner",
        "beatsage_client",
        "runtime_dispatch",
        "full_custom_song_pipeline",
        "build_pack_mode_bundles",
        "song_previews",
        "hevag_encoder",
        "lapped_audio",
        "vorbis_audio",
        "native_hash",
        "goldhen_config",
        "console_transaction",
        "additive_companion",
        "additive_library",
        "additive_lighting",
        "additive_modes",
        "additive_presentation",
        "additive_v3_native",
        "additive_v4_native",
        "import_v2_additive",
        "import_v3_additive",
        "import_v4_additive",
        "prepare_additive_bundle",
        "prepare_additive_media",
        "download_beatsaver_songs",
    ]
    for module in modules:
        command += ["--hidden-import", module]
    for package in [
        "uvicorn",
        "fastapi",
        "starlette",
        "anyio",
        "httpx",
        "httpcore",
        "multipart",
        "pydantic",
        "PIL",
        "numpy",
        "soundfile",
        "UnityPy",
        "fsb5",
        "lz4",
    ]:
        command += ["--collect-all", package]
    command.append(str(ROOT / "desktop/backend/entrypoint.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    omitted = omit_glibc_companion(output)
    (output / "native-libraries-omitted.json").write_text(
        json.dumps({"runtime_glibc_companions": omitted}, indent=2) + "\n"
    )
    print(
        "Built frozen helper prototype; optional minimal FFmpeg payload included when requested. Complete dependency/license, platform-baseline, installer and release gates remain."
    )


if __name__ == "__main__":
    main()
