"""Optional read-only leaderboard identity. Never derive SHA1 from converted IDs.

Sidecar is bound to the exact installed descriptor, not BeatSaver metadata.
It is published/read back before library.bin; existing imports can add it safely.
"""
import hashlib
import json
import re

MAGIC = b"ORBSSRC1"
SIZE = 158


def checksum(payload):
    value = 14695981039346656037
    for byte in payload:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return value.to_bytes(8, "little")


def original_hash(folder, references, local_file):
    infos = [p for p in folder.iterdir() if p.name.lower() == "info.dat"]
    if len(infos) != 1:
        raise ValueError("one original Info.dat required for score identity")
    raw = infos[0].read_bytes()
    info = json.loads(raw)
    digest = hashlib.sha1(raw)
    for name in references(info):
        digest.update(local_file(folder, name).read_bytes())
    return digest.hexdigest()


def encode(song, source_sha1):
    if not re.fullmatch(r"bsd_additive_[0-9a-f]{24}", song["id"]):
        raise ValueError("invalid score identity level")
    if not re.fullmatch(r"[0-9a-f]{64}", song["sha256"]):
        raise ValueError("invalid score identity bundle")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha1):
        raise ValueError("invalid original score hash")
    mask = song["mask"]
    if type(mask) is not int or not 0 <= mask <= 31:
        raise ValueError("invalid score identity chart mask")
    payload = MAGIC + song["id"].encode("ascii") + song["sha256"].encode("ascii") + source_sha1.encode("ascii") + bytes([mask])
    return payload + checksum(payload)


def publish(ftp, api, song, source_sha1, run):
    # Closed-title only, immutable stage/readback/rename. Never overwrite a
    # conflicting identity, and never alter a descriptor or library to repair it.
    content = encode(song, source_sha1)
    path = api.BASE + "/" + song["id"] + "-score-source.bin"
    api.closed(ftp)
    existing = api.read(ftp, path, SIZE + 1, missing=True)
    if existing is not None:
        if existing != content:
            raise ValueError("conflicting original score identity; refusing overwrite")
        return
    staged = api.stage(ftp, path, content, run)
    api.closed(ftp)
    if api.read(ftp, path, SIZE + 1, missing=True) is not None:
        raise ValueError("score identity appeared concurrently")
    ftp.rename(staged, path)
    if api.read(ftp, path, SIZE + 1) != content:
        raise ValueError("score identity final readback mismatch")
