#!/usr/bin/env bash
# Optional, local-only Linux bootstrap. Does not install/deploy a PS4 plugin.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"
CACHE="$TOOLS/downloads"
SDK="$TOOLS/openorbis/OpenOrbis/PS4Toolchain"
GH_SRC="$TOOLS/goldhen-sdk"
OO_SHA=3c7cd5bb593ca74fa1c13fd59f3938dc0fc07985167f7275063019e63abe4526
GH_REV=bcea3c7ef01dac6d7f9f49ebf9e90fe66d86f5f7
GH_SHA=6257675780de53c5bface9821db92675cf0d908301efd3af8134603fda6dd957
for tool in curl sha256sum tar clang clang++ ld.lld llvm-ar make; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
mkdir -p "$CACHE"
fetch() {
    local url="$1" archive="$2" sha="$3"
    if [[ ! -f "$archive" ]]; then
        curl --fail --location --retry 2 --output "$archive.part" "$url"
        mv -- "$archive.part" "$archive"
    fi
    printf '%s  %s\n' "$sha" "$archive" | sha256sum --check
}
fetch 'https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain/releases/download/v0.5.4/toolchain-llvm-18.tar.gz' \
    "$CACHE/toolchain-llvm-18.tar.gz" "$OO_SHA"
fetch "https://codeload.github.com/GoldHEN/GoldHEN_Plugins_SDK/tar.gz/$GH_REV" \
    "$CACHE/goldhen-sdk.tar.gz" "$GH_SHA"
# Re-extract verified sources to make repeated setup independent of local edits.
mkdir -p "$TOOLS/openorbis" "$GH_SRC"
tar -xzf "$CACHE/toolchain-llvm-18.tar.gz" -C "$TOOLS/openorbis"
tar -xzf "$CACHE/goldhen-sdk.tar.gz" -C "$GH_SRC" --strip-components=1
export OO_PS4_TOOLCHAIN="$SDK"
make -C "$GH_SRC" clean
mkdir -p "$GH_SRC/build"
# Match the upstream Deluxe CI workaround for the SDK's crt/mkdir race.
clang -target x86_64-pc-linux-gnu -ffreestanding -nostdlib -fno-builtin -fPIC \
    -isysroot "$SDK" -isystem "$SDK/include" \
    -c "$GH_SRC/crt/crtprx.c" -o "$GH_SRC/build/crtprx.o"
make -C "$GH_SRC" libGoldHEN_Hook.a
mkdir -p "$SDK/include/GoldHEN"
cp "$GH_SRC"/include/* "$SDK/include/GoldHEN/"
cp "$GH_SRC/build/crtprx.o" "$GH_SRC/libGoldHEN_Hook.a" "$SDK/lib/"
printf '\nReady. Build locally with:\n  export OO_PS4_TOOLCHAIN=%q\n  make -C %q\n' "$SDK" "$ROOT/beat_saber_deluxe"
