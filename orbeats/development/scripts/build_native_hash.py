#!/usr/bin/env python3
"""Build the optional host checksum library with an installed C compiler."""
import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
# Do not import the loader here: a loaded Windows DLL cannot be replaced.
LIBRARY_PATH = TOOLS / "native" / ("orbeats_hash" + (".dll" if sys.platform == "win32" else ".dylib" if sys.platform == "darwin" else ".so"))


def build(output=LIBRARY_PATH, cc=None):
    compiler = shlex.split(cc or os.environ.get("CC", ""))
    if not compiler:
        found = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if not found:
            raise RuntimeError("Install a C compiler to build acceleration, or use the Python fallback")
        compiler = [found]
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".hash-build-", dir=output.parent) as tmp:
        candidate = Path(tmp) / output.name
        flags = ["-std=c99", "-O3", "-Wall", "-Wextra", "-Werror"]
        flags += ["-dynamiclib"] if sys.platform == "darwin" else ["-shared"]
        if sys.platform != "win32":
            flags.append("-fPIC")
        subprocess.run([*compiler, *flags, str(TOOLS / "native/fnv.c"), "-o", str(candidate)], check=True)
        # Validation runs in a child so Windows can release the DLL before rename.
        subprocess.run([sys.executable, "-c", "import sys; from native_hash import load_native; load_native(sys.argv[1])",
                        str(candidate)], env={**os.environ, "PYTHONPATH": str(TOOLS)}, check=True)
        candidate.replace(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=LIBRARY_PATH)
    parser.add_argument("--cc", help="GCC/Clang-compatible C compiler command")
    args = parser.parse_args()
    print(build(args.output, args.cc))
