"""Arch x86_64 development-only prerequisites, extracted project-locally.

Never invokes pacman install, sudo, a system service or Docker. Signatures use
only the host's read-only Arch public keyring; downloads also match pinned SHA256.
These packages are not part of an OrBeats release or its media-tool bundle.
"""

import base64
import hashlib
import json
import shlex
import subprocess
import tarfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
PREFIX = ROOT / ".tools/tauri-linux"


def main():
    cache = PREFIX / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    home = PREFIX / "gnupg"
    home.mkdir(mode=0o700, exist_ok=True)
    home.chmod(0o700)
    keyring = PREFIX / "keyring.gpg"
    subprocess.run(
        [
            "gpg",
            "--homedir",
            str(home),
            "--batch",
            "--yes",
            "--dearmor",
            "--output",
            str(keyring),
            "/usr/share/pacman/keyrings/archlinux.gpg",
        ],
        check=True,
    )
    rows = json.loads(Path(__file__).with_name("linux-build-lock.json").read_text())
    for row in rows:
        name = row["filename"]
        if Path(name).name != name or not name.endswith(".pkg.tar.zst"):
            raise ValueError("Unsafe package filename")
        package = cache / name
        if not package.exists():
            temporary = package.with_suffix(".download")
            with (
                urlopen(
                    "https://fastly.mirror.pkgbuild.com/extra/os/x86_64/" + name,
                    timeout=90,
                ) as source,
                temporary.open("xb") as output,
            ):
                while block := source.read(1024 * 1024):
                    output.write(block)
            temporary.replace(package)
        if hashlib.sha256(package.read_bytes()).hexdigest() != row["sha256sum"]:
            raise ValueError("Package checksum mismatch: " + name)
        signature = package.with_name(name + ".sig")
        signature.write_bytes(base64.b64decode(row["pgpsig"], validate=True))
        subprocess.run(
            [
                "gpgv",
                "--homedir",
                str(home),
                "--keyring",
                str(keyring),
                str(signature),
                str(package),
            ],
            check=True,
        )
        # Python3.14 tarfile supports Arch's zstd; data filter refuses path escape.
        with tarfile.open(package) as archive:
            archive.extractall(PREFIX / "root", filter="data")
    usr = PREFIX / "root/usr"
    for pc in (usr / "lib/pkgconfig").glob("*.pc"):
        text = pc.read_text()
        for field, suffix in [
            ("prefix", ""),
            ("exec_prefix", ""),
            ("libdir", "/lib"),
            ("includedir", "/include"),
        ]:
            text = text.replace(
                field + "=/usr" + suffix, field + "=" + str(usr) + suffix
            )
        pc.write_text(text)
    (PREFIX / "build-env.sh").write_text(
        "# Development-only, project-local GTK dependencies\n"
        + "export PKG_CONFIG_PATH="
        + shlex.quote(str(usr / "lib/pkgconfig"))
        + "${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}\n"
        + "export LIBRARY_PATH="
        + shlex.quote(str(usr / "lib"))
        + "${LIBRARY_PATH:+:$LIBRARY_PATH}\n"
        + "export LD_LIBRARY_PATH="
        + shlex.quote(str(usr / "lib"))
        + "${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\n"
    )
    print(
        "Verified and extracted local build dependencies; source .tools/tauri-linux/build-env.sh"
    )


if __name__ == "__main__":
    main()
