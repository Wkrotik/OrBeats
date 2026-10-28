#!/usr/bin/env bash
# Optional host-only environment, independent of the upstream /workspace container.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/orbeats/requirements-test.txt"
if command -v cc >/dev/null || command -v clang >/dev/null || command -v gcc >/dev/null || [[ -n "${CC:-}" ]]; then
    "$ROOT/.venv/bin/python" "$ROOT/orbeats/development/scripts/build_native_hash.py"
else
    printf '\nNo C compiler found; checksums will use the correct, slower Python fallback.\n'
fi
printf '\nRun tests: bash %q\n' "$ROOT/orbeats/development/scripts/run_additive_host_tests.sh"
