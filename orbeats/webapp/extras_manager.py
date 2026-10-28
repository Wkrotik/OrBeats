"""Separate, closed-title Extras installation; never mutate the song capability."""

import re
import uuid
from pathlib import Path

import additive_companion as core
import library_manager as library
from additive_library import BASE
from console_transaction import Transaction

TARGET = "/data/GoldHEN/plugins/orbeats_extras.prx"


def version(blob):
    if not isinstance(blob, bytes) or not blob.startswith(b"\x7fELF"):
        return None
    matches = set(re.findall(rb"OrBeats Extras ([0-9]+\.[0-9]{4}): [^\x00\r\n]{1,160}\x00", blob))
    return next(iter(matches)).decode() if len(matches) == 1 else None


def registration(original, enable=False):
    """Only exact Extras path in the supported title. Preserve all unrelated bytes."""
    if b"\0" in original:
        raise ValueError("Invalid plugins.ini")
    lines = original.splitlines(keepends=True)
    section, found, insert = "", [], None
    for i, raw in enumerate(lines):
        text = raw.decode("utf-8-sig").strip()
        if text.startswith("[") and text.endswith("]"):
            if section == "CUSA12878":
                insert = i
            section = text[1:-1]
        elif text.startswith(TARGET):
            if text not in (TARGET, TARGET + "=false", TARGET + "=true"):
                raise ValueError("Ambiguous Extras registration; review plugins.ini")
            if section != "CUSA12878":
                raise ValueError("Extras registered globally or for another title; review plugins.ini")
            found.append((i, text))
    if len(found) > 1:
        raise ValueError("Duplicate Extras registrations; review plugins.ini")
    if not enable:
        return "enabled" if found and found[0][1] != TARGET + "=false" else "disabled" if found else "missing"
    if found:
        i, text = found[0]
        lines[i] = lines[i].replace(text.encode(), TARGET.encode())
        return b"".join(lines)
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    if section == "CUSA12878":
        insert = len(lines)
    if insert is None:
        return (
            original
            + (newline if original and not original.endswith(b"\n") else b"")
            + b"[CUSA12878]"
            + newline
            + TARGET.encode()
            + newline
        )
    before = b"".join(lines[:insert])
    return (
        before
        + (newline if before and not before.endswith(b"\n") else b"")
        + TARGET.encode()
        + newline
        + b"".join(lines[insert:])
    )


def status(config, artifact):
    local = Path(artifact)
    candidate = library.elf_from_fself(local.read_bytes()) if local.is_file() else None
    with library.connection(config) as ftp:
        blob = core.read(ftp, TARGET, 2000000, missing=True)
        ini = core.read(ftp, "/data/GoldHEN/plugins.ini", 65536, missing=True) or b""
        if core.read(ftp, TARGET, 2000000, missing=True) != blob:
            raise ValueError("Extras changed during check; check again")
    return {
        "installed": blob is not None,
        "installed_version": version(blob),
        "available_version": version(candidate),
        "registration": registration(ini),
        "runtime_verified": False,
    }


def deploy(config, artifact):
    candidate = Path(artifact).read_bytes()
    canonical = library.elf_from_fself(candidate)
    if not version(canonical):
        raise ValueError("Unrecognized Extras artifact")
    if config.get("title", {}).get("id", "CUSA12878") != "CUSA12878":
        raise ValueError("Extras only supports CUSA12878 patch 2.04")
    with library.connection(config) as ftp:
        core.closed(ftp)
        main = core.read(ftp, "/data/GoldHEN/plugins/orbeats.prx", 2000000, missing=True)
        if not library.binary_version(main):
            raise ValueError("Install the main OrBeats plugin before Extras")
        ini_path = "/data/GoldHEN/plugins.ini"
        ini = core.read(ftp, ini_path, 65536, missing=True)
        merged = registration(ini or b"", enable=True)
        old = core.read(ftp, TARGET, 2000000, missing=True)
        if old is not None and not version(old):
            raise ValueError("Unknown existing Extras binary; refusing replacement")
        if old and tuple(map(int, version(old).split("."))) > tuple(map(int, version(canonical).split("."))):
            raise ValueError("Extras downgrade refused")
        library.acquire_install_lock(ftp)
        transaction = Transaction(core, ftp, uuid.uuid4().hex)
        releasable = False
        try:
            transaction.publish(TARGET, candidate, old, wanted=canonical)
            transaction.publish(ini_path, merged, ini)
            transaction.finish()
            releasable = True
        except Exception:
            transaction.rollback()
            releasable = True
            raise
        finally:
            if releasable:
                ftp.rmd(BASE + "/.install-lock")
    return {
        "ok": True,
        "restart_required": True,
        "message": "Extras installed and enabled. Restart Beat Saber. Health auto-dismiss is enabled by default; existing songs without score identity need reimport for leaderboards.",
    }
