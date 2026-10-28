#!/usr/bin/env bash
# Optional Linux x64, project-local analysis tools. No game/console access.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"
for tool in curl sha256sum sha512sum tar python3; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
[[ "$(uname -s)/$(uname -m)" == Linux/x86_64 ]] || { echo 'Requires Linux x64' >&2; exit 1; }
mkdir -p "$TOOLS/downloads" "$TOOLS/il2cpp-dumper" "$TOOLS/dotnet"
fetch() {
    local url="$1" file="$2" hash="$3" check="$4"
    if [[ ! -f "$file" ]]; then
        curl --fail --location --retry 2 --output "$file.part" "$url"
        mv -- "$file.part" "$file"
    fi
    printf '%s  %s\n' "$hash" "$file" | "$check" --check
}
# Official Microsoft 9.0 releases.json SHA512; tested runtime for net6 roll-forward.
fetch 'https://builds.dotnet.microsoft.com/dotnet/Runtime/9.0.15/dotnet-runtime-9.0.15-linux-x64.tar.gz' \
    "$TOOLS/downloads/dotnet-runtime-9.0.15-linux-x64.tar.gz" \
    e65b0993579e0afa709cdc28f6f5ae1252437c2cbd2fdcc4b436e85bbbce700203ff15563e2985f528f1759c43865ca94217139d36d6a62e1b5296bd9a2e4053 sha512sum
fetch 'https://github.com/Perfare/Il2CppDumper/releases/download/v6.7.46/Il2CppDumper-net6-v6.7.46.zip' \
    "$TOOLS/il2cpp-dumper/Il2CppDumper-net6-v6.7.46.zip" \
    db9bbbc538e33abfb057c7757ae5d6c1f16a05fdc0d13af8a5a67ea31faaba0c sha256sum
# Runtime archive is hash-pinned; install only in the ignored project tool directory.
tar -xzf "$TOOLS/downloads/dotnet-runtime-9.0.15-linux-x64.tar.gz" -C "$TOOLS/dotnet"
python3 - "$TOOLS/il2cpp-dumper" <<'PY'
import json
import sys
import zipfile
from pathlib import Path
root = Path(sys.argv[1])
with zipfile.ZipFile(root / 'Il2CppDumper-net6-v6.7.46.zip') as archive:
    for name in archive.namelist():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe Il2CppDumper archive member')
    archive.extractall(root / 'v6.7.46')
config_path = root / 'v6.7.46/config.json'
config = json.loads(config_path.read_text())
config['RequireAnyKey'] = False
config_path.write_text(json.dumps(config, indent=2) + '\n')
PY
"$TOOLS/dotnet/dotnet" --list-runtimes
printf '\nReady: project-local Il2CppDumper 6.7.46 + .NET 9.0.15.\n'
printf 'Use orbeats/development/scripts/run_il2cpp_dump.py --help.\n'
