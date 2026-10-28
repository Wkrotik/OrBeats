"""Durable desktop state; no PS4 operations or settings migration on import."""

import json
import os
from contextlib import contextmanager
from pathlib import Path


def atomic_json(path, value):
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if len(data) > 2000000:
        raise ValueError("Desktop state exceeds bound")
    temporary = path.with_name(path.name + ".tmp")
    # A parent holds the workspace lock. Refuse symlink state rather than follow it.
    if path.is_symlink() or temporary.is_symlink():
        raise ValueError("Desktop state must not be a symlink")
    with temporary.open("wb") as stream:
        os.chmod(temporary, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if os.name != "nt":
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


@contextmanager
def ownership(directory):
    """Kernel-held exclusive instance lock, automatically released on process exit."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink():
        raise ValueError("Desktop state directory must not be a symlink")
    path = directory / "instance.lock"
    if path.is_symlink():
        raise ValueError("Desktop lock must not be a symlink")
    with path.open("a+b") as stream:
        os.chmod(path, 0o600)
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            stream.write(b"\0")
            stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(
                    "Another OrBeats desktop owns this state directory"
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(
                    "Another OrBeats desktop owns this state directory"
                ) from exc
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
