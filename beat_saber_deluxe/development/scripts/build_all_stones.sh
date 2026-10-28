#!/bin/bash
# Build and deploy all 12 Rolling Stones replacements
set -e
REPO="/workspace/beat-saber-ps4-custom-songs/songs_repo"
TOOLS="/workspace/beat_saber_deluxe/tools"
PLUGIN_DIR="/workspace/beat_saber_deluxe"
OO_PS4_TOOLCHAIN=/opt/openorbis/OpenOrbis/PS4Toolchain
export OO_PS4_TOOLCHAIN

# Build & deploy plugin first
echo "=== Building & deploying plugin (debug) ==="
cd "$PLUGIN_DIR"
make clean && rm -rf obj && DEBUG=1 make -B

python3 -c "
import sys; sys.path.insert(0, '$TOOLS')
import json, os
from full_custom_song_pipeline import build_plugin, deploy_plugin, load_config
config = load_config('ps4_config.json')
prx = build_plugin('.', debug=True)
deploy_plugin(prx, config, debug=True)
"

# Auto-find song dirs by name
find_song_dir() {
    local name="$1"
    for d in "$REPO"/*/; do
        local info="${d}Info.dat"
        if [ -f "$info" ]; then
            local found=$(python3 -c "
import json
info = json.load(open('$info'))
if '$name'.lower() in info.get('_songName','').lower():
    print('$d')
" 2>/dev/null)
            if [ -n "$found" ]; then
                echo "$found"
                return 0
            fi
        fi
    done
    return 1
}

# Define mapping: Stones target -> song name (auto-find dir)
declare -A TARGETS
TARGETS["angry"]="We All Lift Together"
TARGETS["bitemyheadoff"]="Escaping the Ruins"
TARGETS["cantyouhearmeknocking"]="Spectre"
TARGETS["deadmanwalking"]="Finesse"
TARGETS["gimmeshelter"]="How You Like That"
TARGETS["icantgetnosatisfaction"]="Dreams Come True"
TARGETS["messitup"]="Powersnake"
TARGETS["paintitblack"]="Time Lapse"
TARGETS["sugarsoaker"]="Venom of Venus"
TARGETS["sympathyforthedevil"]="LIT"
TARGETS["wholewideworld"]="VOLUPTE"
# startmeup -> Espresso already deployed

for target in "${!TARGETS[@]}"; do
    songname="${TARGETS[$target]}"
    echo ""
    echo "=== Looking up: $songname..."
    songdir=$(find_song_dir "$songname")
    if [ -z "$songdir" ]; then
        echo "⚠️  Song not found: $songname — skipping $target"
        continue
    fi
    echo "=== Building: $target ← $songname ($(basename $songdir)) ==="
    
    # Strip trailing slash
    songdir="${songdir%/}"
    
    python3 "$TOOLS/full_custom_song_pipeline.py" \
        --song-dir "$songdir" \
        --target "$target" \
        --pcm16 --no-pad \
        --deploy
    
    if [ $? -eq 0 ]; then
        echo "  ✅ $target deployed"
    else
        echo "  ❌ $target FAILED"
    fi
done

echo ""
echo "=== ALL DONE ==="
