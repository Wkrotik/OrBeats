"""Native and fallback checksums must remain identical to the PS4 wire codec."""
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import additive_library as lib
import native_hash


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if not compiler:
        pytest.skip("C compiler required for optional accelerator tests")
    path = tmp_path_factory.mktemp("native-hash") / native_hash.LIBRARY_NAME
    subprocess.run([sys.executable, str(ROOT / "development/scripts/build_native_hash.py"),
                    "--cc", compiler, "--output", str(path)], check=True, capture_output=True)
    return native_hash.load_native(path)


def test_known_vectors_and_fallback(monkeypatch):
    monkeypatch.setattr(native_hash, "_native", None)
    assert native_hash.fnv(b"") == 0xcbf29ce484222325
    assert native_hash.fnv(b"hello") == 0xa430d84680aabd0b
    assert native_hash.fnv(b"a\0b") != native_hash.fnv(b"a")
    assert native_hash.fnv(bytearray(range(256))) == native_hash.python_fnv(bytes(range(256)))


def test_native_matches_python_for_binary_buffers_and_wire_codec(native, monkeypatch):
    rng = random.Random(137)
    for size in (0, 1, 7, 8, 255, 256, 4096, 131072):
        data = rng.randbytes(size)
        assert native(data, len(data)) == native_hash.python_fnv(data)
    monkeypatch.setattr(native_hash, "_native", None)
    from test_additive_companion import baseline
    expected = lib.encode(baseline())
    monkeypatch.setattr(native_hash, "_native", native)
    assert lib.encode(baseline()) == expected
    assert lib.encode(lib.decode(expected)) == expected
    assert native_hash.fnv(memoryview(b"\0hello\xff")) == native_hash.python_fnv(b"\0hello\xff")
    with pytest.raises(ValueError):
        lib.decode(expected[:-1] + bytes([expected[-1] ^ 1]))


def test_missing_or_invalid_accelerator_is_not_accepted(tmp_path):
    path = tmp_path / native_hash.LIBRARY_NAME
    with pytest.raises(OSError):
        native_hash.load_native(path)
    path.write_bytes(b"not a library")
    with pytest.raises(OSError):
        native_hash.load_native(path)


def test_bad_native_function_is_rejected_by_startup_vectors(monkeypatch):
    class Wrong:
        def __call__(self, _data, _length):
            return 0
    class Library:
        orbeats_fnv1a64 = Wrong()
    monkeypatch.setattr(native_hash.ctypes, "CDLL", lambda _path: Library())
    with pytest.raises(ValueError, match="self-check"):
        native_hash.load_native("wrong-implementation")
