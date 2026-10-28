#!/usr/bin/env bash
# =============================================================================
# regen_il2cpp_dump.sh — Re-run Il2CppDumper on Beat Saber PS4
# =============================================================================
# Requires: dotnet SDK at /workspace/dotnet/, Il2CppDumper at /workspace/Il2CppDumper/
# Input: /workspace/ps4_dump/CUSA12878-patch/Media/Modules/Il2cppUserAssemblies.prx
#        /workspace/ps4_dump/CUSA12878-patch/Media/Metadata/global-metadata.dat
# Output: /workspace/il2cpp_output/dump.cs, il2cpp.h, script.json, stringliteral.json
# =============================================================================

set -e

DOTNET="/workspace/dotnet/dotnet"
DUMPER="/workspace/Il2CppDumper/Il2CppDumper.dll"
PRX="/workspace/ps4_dump/CUSA12878-patch/Media/Modules/Il2cppUserAssemblies.prx"
METADATA="/workspace/ps4_dump/CUSA12878-patch/Media/Metadata/global-metadata.dat"
OUTPUT="/workspace/il2cpp_output"

echo "=== Regenerating IL2CPP dump ==="

# Check prerequisites
if [ ! -f "$DOTNET" ]; then
    echo "ERROR: .NET not found at $DOTNET"
    echo "Run setup_devcontainer.sh or install .NET SDK first"
    exit 1
fi

if [ ! -f "$DUMPER" ]; then
    echo "ERROR: Il2CppDumper not found at $DUMPER"
    echo "Run setup_devcontainer.sh or download Il2CppDumper first"
    exit 1
fi

if [ ! -f "$PRX" ]; then
    echo "ERROR: Il2CppUserAssemblies.prx not found at $PRX"
    echo "Check that the PS4 dump exists at /workspace/ps4_dump/"
    exit 1
fi

if [ ! -f "$METADATA" ]; then
    echo "ERROR: global-metadata.dat not found at $METADATA"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT"

# Run Il2CppDumper (note: uses echo 0 to bypass console input prompt)
echo "   Dumping IL2CPP classes..."
cd /workspace/Il2CppDumper
echo "0" | "$DOTNET" "$DUMPER" "$PRX" "$METADATA" "$OUTPUT" 2>/dev/null

# Verify output
if [ -f "$OUTPUT/dump.cs" ]; then
    LINES=$(wc -l < "$OUTPUT/dump.cs")
    SIZE=$(du -h "$OUTPUT/dump.cs" | cut -f1)
    echo "   ✅ dump.cs generated ($LINES lines, $SIZE)"
    echo ""
    echo "=== Key findings ==="
    echo "BeatmapLevelSO class starts at line $(grep -n 'class BeatmapLevelSO : PersistentScriptableObject' "$OUTPUT/dump.cs" | cut -d: -f1)"
    echo "get_previewDifficultyBeatmapSets RVA: $(grep -B1 'get_previewDifficultyBeatmapSets' "$OUTPUT/dump.cs" | grep 'RVA' | head -1 | awk '{print $4}')"
else
    echo "❌ Failed to generate dump.cs"
    exit 1
fi

echo ""
echo "=== Done ==="
