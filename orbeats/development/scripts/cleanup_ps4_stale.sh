#!/bin/bash
# Clean stale files out of the AFR dir on the PS4 (Exp 186).
#
# The Aug-13 redeploy uploaded the fresh builds as <slot>_v3.bundle, but the PS4
# still holds a pile of stale artifacts from earlier naming schemes that confuse
# deploys and waste space:
#   - <slot>_v3                      (no .bundle)  old Jul-12 builds
#   - <slot>_v3 dirs                               old Camellia dirs
#   - Crystallized_v3 / CycleHit_v3 / ...          old titlecase Aug-2 builds
#   - rollingstones_pack_patched.bundle etc.       stale pack variants
#   - catalog_test.json, 100bills*, startmeup_*    ancient test artifacts
#
# This script removes ONLY files/dirs that are NOT redirect targets and NOT
# current config/plugin assets. Run with --dry-run first to see what it will do.
#
# Usage:
#   development/scripts/cleanup_ps4_stale.sh [--dry-run] [--yes]
set -eu

cd "$(dirname "$0")/../.."
HOST=192.168.100.117
PORT=2121
AFR=/data/GoldHEN/AFR/CUSA12878

DRY=1
YES=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --yes)     DRY=0; YES=1 ;;
    *) echo "unknown arg: $a"; exit 2 ;;
  esac
done

# Build the keep-set from the current redirects.json values + infra files.
KEEP="$(python3 - <<'EOF'
import json
d = json.load(open('redirects.json'))
vals = set(d.get('redirects', {}).values())
# infra/config files that must survive a cleanup
vals |= {'redirects.json', 'features.json', 'song_metadata.json', 'bs_log.txt'}
for v in sorted(vals):
    print(v)
EOF
)"

KEEP_FILE=$(mktemp)
printf '%s\n' "$KEEP" > "$KEEP_FILE"

list_remote() {
  lftp -u anonymous, -p "$PORT" "$HOST" -e "ls $AFR; quit" 2>/dev/null \
    | awk '{if ($1 ~ /^d/) {print $NF "/"} else {print $NF}}'
}

stale_list() {
  # A name is stale if it is NOT in the keep set AND is not one of the
  # always-keep containers (Media/, Plugins/) or a redirect-target-looking file.
  while IFS= read -r name; do
    [ -z "$name" ] && continue
    case "$name" in
      Media/|Plugins/|'./'|'../') continue ;;
    esac
    if ! grep -qxF "$name" "$KEEP_FILE"; then
      # Never remove files that end in _v3.bundle (fresh builds) even if not
      # currently referenced — they are candidates, not stale junk.
      case "$name" in
        *_v3.bundle) continue ;;
      esac
      echo "$name"
    fi
  done
}

echo "== Computing stale files on PS4 (dry-run=$DRY) =="
stale=$(list_remote | stale_list || true)

if [ -z "$stale" ]; then
  echo "No stale files found — PS4 is clean."
  rm -f "$KEEP_FILE"
  exit 0
fi

echo "$stale" | while IFS= read -r name; do
  [ -z "$name" ] && continue
  if [ "$DRY" = "1" ]; then
    echo "  would rm: $name"
  else
    echo "  rm: $name"
  fi
done

if [ "$DRY" = "1" ]; then
  echo ""
  echo "Dry run — nothing deleted. Re-run with --yes to actually remove."
  rm -f "$KEEP_FILE"
  exit 0
fi

echo ""
if [ "$YES" = "0" ]; then
  read -rp "Delete ${#stale} files? [y/N] " ans
  [ "$ans" = "y" ] || [ "$ans" = "Y" ] || { echo "aborted"; rm -f "$KEEP_FILE"; exit 1; }
fi

echo "$stale" | while IFS= read -r name; do
  [ -z "$name" ] && continue
  lftp -u anonymous, -p "$PORT" "$HOST" -e "rm -rf $AFR/$name; quit" 2>/dev/null \
    && echo "  deleted: $name" \
    || echo "  FAILED: $name"
done

rm -f "$KEEP_FILE"
echo "Cleanup complete. Run: python3 tools/full_custom_song_pipeline.py --deploy-config --verify-ps4"
