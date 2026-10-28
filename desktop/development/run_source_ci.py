"""Run the declared source-only subset, never pretending it is the full suite.

The complete local suite still exercises owned game-template/catalog fixtures.
No such inputs are uploaded. Exclusions and migration debt remain explicit.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    spec = json.loads(Path(__file__).with_name("source-ci-tests.json").read_text())
    tests = spec["tests"]
    if not tests or any(
        not p.startswith("tests/test_") or not p.endswith(".py") or ".." in p
        for p in tests
    ):
        raise ValueError("Invalid source-only test inventory")
    print(spec["scope"], flush=True)
    print("Explicit exclusions:", ", ".join(spec["excluded_modules"]), flush=True)
    (ROOT / "temp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="source-ci-", dir=ROOT / "temp") as tmp:
        guard = Path(tmp) / "lftp"
        guard.write_text(
            '#!/bin/sh\necho "Console access disabled for source-only CI" >&2\nexit 97\n'
        )
        guard.chmod(0o755)
        env = {
            **os.environ,
            "PATH": os.pathsep.join(
                [tmp, str(Path(sys.executable).parent), os.environ.get("PATH", "")]
            ),
        }
        return subprocess.run(
            [sys.executable, "-m", "pytest", *tests, "-q"],
            cwd=ROOT / "orbeats",
            env=env,
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
