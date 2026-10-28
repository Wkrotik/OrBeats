"""Build minimal static LGPL FFmpeg/ffprobe project-locally; no host installs.

Source/signature/key are vendor-HTTPS pinned; GPG fingerprint/signature checked.
No GPL/nonfree/external codec autodetection or network protocols are enabled.
This is a development tool payload, not a complete desktop release/license gate.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
FLAGS = [
    "--disable-everything",
    "--disable-autodetect",
    "--disable-network",
    "--disable-shared",
    "--enable-static",
    "--extra-ldflags=-static",
    "--disable-x86asm",
    "--disable-doc",
    "--disable-debug",
    "--disable-ffplay",
    "--disable-avdevice",
    "--disable-swscale",
    "--enable-ffmpeg",
    "--enable-ffprobe",
    "--enable-protocol=file,pipe",
    "--enable-decoder=vorbis,opus,flac,mp3,mp3float,aac,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le,adpcm_psx",
    "--enable-demuxer=ogg,flac,mp3,aac,wav,mov",
    "--enable-parser=vorbis,opus,flac,mpegaudio,aac",
    "--enable-encoder=pcm_s16le",
    "--enable-muxer=wav,s16le",
    "--enable-filter=aresample,atrim,asetpts,anull,aformat,volume",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    out = args.output.resolve()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("This development profile is Linux x86_64 only")
    if (
        out.exists()
        or not out.is_relative_to(ROOT / "temp")
        or not 1 <= args.jobs <= 16
    ):
        raise ValueError("Use fresh project-local temp output and jobs1..16")
    lock_path = Path(__file__).with_name("media-linux-lock.json")
    lock = json.loads(lock_path.read_text())["ffmpeg"]
    out.mkdir(parents=True)
    downloads = out / "downloads"
    downloads.mkdir()
    files = {}
    for key in ("source", "signature", "key"):
        target = downloads / key
        with urlopen(lock[key], timeout=60) as response:
            data = response.read(20000001)
        if (
            len(data) > 20000000
            or hashlib.sha256(data).hexdigest() != lock[key + "_sha256"]
        ):
            raise ValueError("Pinned download hash mismatch: " + key)
        target.write_bytes(data)
        files[key] = target
    home = out / "gnupg"
    home.mkdir(mode=0o700)
    gpg = ["gpg", "--homedir", str(home), "--batch", "--no-auto-key-retrieve"]
    subprocess.run(
        gpg + ["--import", str(files["key"])], check=True, capture_output=True
    )
    proof = subprocess.run(
        gpg
        + [
            "--status-fd",
            "1",
            "--verify",
            str(files["signature"]),
            str(files["source"]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if "[GNUPG:] VALIDSIG " + lock["fingerprint"] + " " not in proof.stdout:
        raise ValueError("Signature fingerprint mismatch")
    (out / "signature-proof.txt").write_text(proof.stdout + proof.stderr)
    with tarfile.open(files["source"], mode="r:xz") as archive:
        if any(
            not (
                p.name == "ffmpeg-" + lock["version"]
                or p.name.startswith("ffmpeg-" + lock["version"] + "/")
            )
            or p.issym()
            or p.islnk()
            for p in archive.getmembers()
        ):
            raise ValueError("Source archive outside expected root or contains links")
        archive.extractall(out, filter="data")
    src = out / ("ffmpeg-" + lock["version"])
    prefix = out / "payload"
    command = ["./configure", "--prefix=" + str(prefix)] + FLAGS
    (out / "build-command.json").write_text(json.dumps(command, indent=2) + "\n")
    environment = os.environ.copy()
    for key in (
        "LD_LIBRARY_PATH",
        "LIBRARY_PATH",
        "CFLAGS",
        "CPPFLAGS",
        "LDFLAGS",
        "PKG_CONFIG_PATH",
        "PKG_CONFIG_LIBDIR",
    ):
        environment.pop(key, None)
    with (out / "build.log").open("w") as log:
        subprocess.run(
            command, cwd=src, env=environment, stdout=log, stderr=log, check=True
        )
        subprocess.run(
            ["make", "-j" + str(args.jobs)],
            cwd=src,
            env=environment,
            stdout=log,
            stderr=log,
            check=True,
        )
    (prefix / "bin").mkdir(parents=True)
    for name in ("ffmpeg", "ffprobe"):
        target = prefix / "bin" / name
        shutil.copy2(src / name, target)
        header = subprocess.check_output(["readelf", "-l", str(target)], text=True)
        if "INTERP" in header or "DYNAMIC" in header:
            raise ValueError("Expected fully static tool: " + name)
        subprocess.run([str(target), "-version"], check=True, stdout=subprocess.DEVNULL)
    legal = prefix / "legal"
    legal.mkdir()
    for name in ("COPYING.LGPLv2.1", "LICENSE.md"):
        shutil.copy2(src / name, legal / name)
    shutil.copy2(lock_path, legal / "source-lock.json")
    shutil.copy2(Path(__file__), legal / "build_media_linux.py")
    shutil.copy2(out / "build-command.json", legal / "build-command.json")
    manifest = {
        p.relative_to(prefix).as_posix(): sha(p)
        for p in sorted(prefix.rglob("*"))
        if p.is_file()
    }
    (prefix / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "payload": str(prefix),
                "static": True,
                "ffmpeg": lock["version"],
                "files": len(manifest),
                "distribution_ready": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
