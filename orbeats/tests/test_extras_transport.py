"""Exercise the actual blocking PS4 transport against fake imports, not live HTTPS."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXTRAS = ROOT / "orbeats_extras"


@pytest.fixture(scope="module")
def transport(tmp_path_factory):
    cc, cxx = shutil.which("clang"), shutil.which("clang++")
    if not cc or not cxx:
        pytest.skip("Native transport sanitizers need clang/clang++")
    out = tmp_path_factory.mktemp("extras-transport")
    flags = ["-g", "-O1", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    subprocess.run(
        [
            cc,
            *flags,
            "-DCJSON_NESTING_LIMIT=16",
            "-c",
            str(EXTRAS / "third_party/cjson/cJSON.c"),
            "-o",
            str(out / "json.o"),
        ],
        check=True,
    )
    subprocess.run(
        [
            cxx,
            *flags,
            "-std=c++11",
            "-I" + str(EXTRAS / "include"),
            str(ROOT / "orbeats/tests/native/extras_transport_test.cpp"),
            str(EXTRAS / "src/transport.cpp"),
            str(EXTRAS / "src/scoresaber.cpp"),
            str(out / "json.o"),
            "-o",
            str(out / "transport"),
        ],
        check=True,
    )
    return out / "transport"


@pytest.mark.parametrize(
    "scenario",
    [
        "normal",
        "modules-present",
        "send-error",
        "ssl-error",
        "diagnostic-error",
        "no-logger",
        "unsupported-retry",
        "tls-policy-error",
        "resolve-timeout-error",
        "fifty",
        "empty",
        "chunks",
        "faults",
        "identity",
        "cancel-before",
        "cancel-read",
        "cancel-second",
        "send-deadline",
        "read-deadline",
        "time-backwards",
        "404",
        "429",
        "redirect",
        "500",
        "oversize",
        "json",
        "changed",
        "invalid-count",
    ],
)
def test_native_transport_bounds_tls_policy_and_cleanup(transport, scenario):
    subprocess.run(
        [str(transport), scenario],
        timeout=15,
        check=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"},
    )
