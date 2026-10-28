#!/bin/bash
# Deploy all 11 Rolling Stones custom song bundles (except startmeup)
# Usage: ./deploy_all_songs.sh
# Requires ps4_config.json with correct IP settings

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE="$SCRIPT_DIR/tools/full_custom_song_pipeline.py"
OUTPUT="$SCRIPT_DIR/custom_songs"

# Read PS4 config for IP and port
CFG="$SCRIPT_DIR/ps4_config.json"
PS4_IP=$(python3 -c "import json; print(json.load(open('$CFG'))['ps4']['ip'])" 2>/dev/null || echo "192.168.100.117")
PS4_PORT=$(python3 -c "import json; print(json.load(open('$CFG'))['ps4']['ftp_port'])" 2>/dev/null || echo "2121")
TITLE_ID=$(python3 -c "import json; print(json.load(open('$CFG'))['title']['id'])" 2>/dev/null || echo "CUSA12878")
AFR_BASE=$(python3 -c "import json; print(json.load(open('$CFG'))['paths']['afr_base'])" 2>/dev/null || echo "/data/GoldHEN/AFR")

TARGETS=(
    "angry"
    "bitemyheadoff"
    "cantyouhearmeknocking"
    "deadmanwalking"
    "gimmeshelter"
    "icantgetnosatisfaction"
    "messitup"
    "paintitblack"
    "sugarsoaker"
    "sympathyforthedevil"
    "wholewideworld"
)

echo "Deploying to PS4 at $PS4_IP:$PS4_PORT..."
echo "Title ID: $TITLE_ID"
echo "========================================"

for TARGET in "${TARGETS[@]}"; do
    BUNDLE="$OUTPUT/${TARGET}_custom.bundle"
    if [ ! -f "$BUNDLE" ]; then
        echo "❌ Bundle not found: $BUNDLE"
        continue
    fi

    REMOTE_PATH="${AFR_BASE}/${TITLE_ID}/${TARGET}_v3"
    SIZE=$(stat --format=%s "$BUNDLE" 2>/dev/null || stat -f%z "$BUNDLE")
    SIZE_MB=$((SIZE / 1024 / 1024))

    echo "📤 Deploying $TARGET ($SIZE_MB MB)..."
    lftp -u anonymous, -p "$PS4_PORT" "$PS4_IP" \
        -e "put '$BUNDLE' -o '$REMOTE_PATH'; quit" 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "  ✅ $TARGET deployed"
    else
        echo "  ❌ $TARGET failed"
    fi
done

echo "========================================"
echo "All deployments complete!"
echo ""
echo "Next steps:"
echo "1. Restart Beat Saber on PS4"
echo "2. Play each Rolling Stones song and verify sync"
echo "3. Start Me Up (Espresso) was NOT redeployed - should still work as before"
