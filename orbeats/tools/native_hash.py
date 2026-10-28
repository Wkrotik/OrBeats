"""Optional portable C acceleration; identical wire format, no runtime compiler."""
import ctypes
import sys
import warnings
from pathlib import Path

LIBRARY_NAME = "orbeats_hash" + (".dll" if sys.platform == "win32" else ".dylib" if sys.platform == "darwin" else ".so")
LIBRARY_PATH = Path(__file__).resolve().parent / "native" / LIBRARY_NAME


def python_fnv(data):
    value = 14695981039346656037
    for b in data:
        value = ((value ^ b) * 1099511628211) & 0xffffffffffffffff
    return value


def load_native(path):
    library = ctypes.CDLL(str(path))
    function = library.orbeats_fnv1a64
    function.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    function.restype = ctypes.c_uint64
    for data in (b"", b"hello", bytes(range(256))):
        if function(data, len(data)) != python_fnv(data):
            raise ValueError("Native checksum self-check failed")
    return function


_native = None
if LIBRARY_PATH.is_file():
    try:
        _native = load_native(LIBRARY_PATH)
    except (OSError, AttributeError, ValueError) as error:
        warnings.warn(f"Native checksum unavailable; using Python: {error}", RuntimeWarning)

BACKEND = "native" if _native is not None else "python"


def fnv(data):
    if _native is None:
        return python_fnv(data)
    # bytes pass directly to C, including embedded NULs; only other buffers copy.
    if not isinstance(data, bytes):
        data = bytes(data)
    return _native(data, len(data))
