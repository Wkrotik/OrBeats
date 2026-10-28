#!/usr/bin/env bash
# Run the full host suite with the venv inherited by child processes, FTP disabled.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    echo 'Create the host venv first: bash .devcontainer/setup_additive_host.sh' >&2
    exit 1
fi
mkdir -p "$ROOT/temp"
GUARD="$(mktemp -d "$ROOT/temp/no-console-tests.XXXXXX")"
trap 'rm -rf -- "$GUARD"' EXIT
cat > "$GUARD/lftp" <<'SH'
#!/bin/sh
echo 'Console access disabled for local-only tests' >&2
exit 97
SH
chmod +x "$GUARD/lftp"
# Tests launch `python3` subprocesses: sys.executable alone is not enough.
export PATH="$GUARD:$ROOT/.venv/bin:$PATH"
cd "$ROOT/orbeats"
exec_status=0
python -m pytest tests/ -v "$@" || exec_status=$?
exit "$exec_status"
