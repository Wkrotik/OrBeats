#!/usr/bin/env python3
"""
ps4_state.py — Inspect the current OrBeats state on the PS4 AND local pipeline cache.

Lists every BSD-related file currently on the PS4 (plugins.ini + its contents,
AFR directory bundles/config json, plugin .prx) and prints a human-readable
summary conclusion: clean-slate, or "X custom songs, Y redirects, Z modified
music packs".

Also shows local pipeline cache files (song_metadata.json, redirects.json, catalog_pack_modes.json)
which affect what the pipeline thinks is deployed on PS4.

Uses lftp for a familiar, consistent interaction. Exits 0 on success.

Usage:
    python3 orbeats/development/scripts/ps4_state.py
"""

import subprocess
import sys
import json
import os

PS4_HOST = "192.168.100.117"
PS4_PORT = 2121
USER = "anonymous"
PASS = ""

GAME_DIR = "/user/app/CUSA12878"
AFR_DIR = "/data/GoldHEN/AFR/CUSA12878"
PLUGINS_INI = "/data/GoldHEN/plugins.ini"
PLUGINS_DIR = "/data/GoldHEN/plugins"


def run_lftp(*cmds):
    """Run one or more lftp -e commands and return combined stdout."""
    joined = "; ".join(cmds) + ("; quit" if cmds else "quit")
    result = subprocess.run(
        ["lftp", "-u", f"{USER},{PASS}", "-p", str(PS4_PORT), PS4_HOST,
         "-e", joined],
        capture_output=True, text=True, timeout=60)
    return result.stdout, result.returncode


def list_dir(path):
    out, _ = run_lftp(f"ls {path}")
    names = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 9:
            names.append((parts[0], parts[4], ' '.join(parts[8:])))
    return names


def cat_remote(path):
    out, rc = run_lftp(f"cat {path}")
    return out if rc == 0 else None


def is_custom_bundle(name):
    """A custom song/pack bundle or BSD config json we deploy."""
    n = name.lower()
    if name.startswith('.'):
        return False
    if n.endswith('.bundle'):
        # Include every *_v3.bundle, *_pack_modes_*.bundle, *_custom.bundle.
        return True
    if n in ('redirects.json', 'song_metadata.json', 'features.json',
             'catalog_pack_modes.json', 'catalog_startmeup_modes.json',
             'catalog_test.json', 'startmeup_pack_modes.bundle'):
        return True
    return False


def main():
    print("=" * 62)
    print("OrBeats — PS4 State")
    print("=" * 62)

    # 1. Try to reach the PS4
    host = PS4_HOST
    out, rc = run_lftp("ls /")
    if rc != 0:
        print("❌  Could not reach the PS4 (is it on + jailbroken + FTP up?)")
        print("    lftp cmd example:")
        print(f'    lftp -u {USER}, -p {PS4_PORT} {host} -e "ls; quit"')
        return 2

    print(f"✅  PS4 reachable ({host}:{PS4_PORT})")
    print()

    # 2. plugins.ini + plugin .prx
    print("--- plugins.ini ---")
    ini = cat_remote(PLUGINS_INI)
    if ini is None:
        print("⚠️   plugins.ini not found / could not read")
        plug_entries = []
    else:
        print(ini.rstrip())
        plug_entries = [l.strip() for l in ini.splitlines()
                        if l.strip().startswith('/data/GoldHEN/plugins')
                        and not l.strip().startswith('#')]
    print()

    print("--- GoldHEN plugins dir ---")
    plist = list_dir(PLUGINS_DIR)
    has_plugin = False
    for perm, size, name in plist:
        if name in ('.', '..'):
            continue
        marker = "  ◄ BSD plugin" if name == 'orbeats.prx' else ""
        print(f"  {perm} {size:>10}  {name}{marker}")
        if name == 'orbeats.prx':
            has_plugin = True
    print()

    # Is the plugin registered in plugins.ini under [CUSA12878]?
    ini_registered = any('orbeats.prx' in e for e in plug_entries)

    # 3. AFR directory: custom bundles + config json (this is where the plugin reads from)
    print(f"--- {AFR_DIR} (AFR dir — plugin reads from here) ---")
    afr_list = list_dir(AFR_DIR)
    custom_bundles = []
    config_jsons = []
    for perm, size, name in afr_list:
        if name in ('.', '..'):
            continue
        is_custom = is_custom_bundle(name)
        tag = ""
        if is_custom:
            if name.endswith('.bundle'):
                custom_bundles.append(name)
                tag = "  ◄ custom bundle"
            else:
                config_jsons.append(name)
                tag = "  ◄ BSD config"
        print(f"  {perm} {size:>10}  {name}{tag}")
    print()

    # 4. Also check game dir for base game files (should be clean)
    print(f"--- {GAME_DIR} (game dir — base game only) ---")
    glist = list_dir(GAME_DIR)
    for perm, size, name in glist:
        if name in ('.', '..'):
            continue
        # Only show base game files, not custom content
        if name in ('app.pkg', 'app.pbm', 'app.pbm.backup', 'app.json', 'app.xml'):
            print(f"  {perm} {size:>10}  {name}")
        elif is_custom_bundle(name):
            print(f"  {perm} {size:>10}  {name}  ◄ STALE CUSTOM CONTENT (should be in AFR dir)")
        else:
            print(f"  {perm} {size:>10}  {name}")
    print()

    # 5. Summarize
    print("=" * 62)
    print("SUMMARY")
    print("=" * 62)

    # Parse redirects.json for song count if present
    redirect_count = None
    redirect_names = []
    if 'redirects.json' in config_jsons:
        red = cat_remote(f"{AFR_DIR}/redirects.json")
        if red is not None:
            try:
                # cat_remote output may carry lftp banner chatter around the
                # file bytes — decode exactly one JSON object (Exp 222).
                start = red.index('{')
                data, _ = json.JSONDecoder().raw_decode(red[start:])
                redirects = data.get('redirects', {})
                redirect_count = len(redirects)
                # song redirects = BeatmapLevelsData/* keys; other keys = pack/catalog
                redirect_names = sorted(
                    k.split('/', 1)[-1] for k in redirects
                    if k.startswith('BeatmapLevelsData/'))
            except Exception:
                pass

    # Separate custom song bundles from pack-mode bundles
    song_bundles = [b for b in custom_bundles
                    if b.endswith('_v3.bundle') or '_custom.bundle' in b]
    pack_bundles = [b for b in custom_bundles if '_pack_modes_assets_all_' in b]

    if not custom_bundles and not config_jsons and not has_plugin and not ini_registered:
        print("🧹  PS4 is in CLEAN SLATE state for OrBeats.")
        print("    No custom songs, no redirects, no modified music packs, no plugin.")
    else:
        msg = "🎵  OrBeats currently installed with"
        detail = []
        if song_bundles:
            detail.append(f"{len(song_bundles)} custom songs")
        else:
            detail.append("0 custom songs")
        detail.append(f"{redirect_count if redirect_count is not None else 0} redirects")
        if pack_bundles:
            detail.append(f"{len(pack_bundles)} modified music packs")
        else:
            detail.append("0 modified music packs")
        print(msg + ", ".join(detail) + ".")

        if song_bundles:
            print("\n  Custom songs:")
            for b in sorted(song_bundles):
                print(f"    - {b}")
        if redirect_names:
            print("\n  Redirects (BeatmapLevelsData/):")
            for r in sorted(redirect_names):
                print(f"    - {r}")
        if pack_bundles:
            print("\n  Modified music packs:")
            for b in sorted(pack_bundles):
                print(f"    - {b}")
        if has_plugin or ini_registered:
            print("\n  Plugin:")
            if ini_registered:
                print("    - orbeats.prx registered in plugins.ini [CUSA12878]")
            if has_plugin:
                print("    - orbeats.prx present in /data/GoldHEN/plugins/")
    print()
    print("=" * 62)

    # 5b. Feature flags (runtime plugin behavior — what the plugin will do on
    # next boot). Read from the PS4's features.json, not any local copy.
    # NOTE: cat_remote returns lftp's combined stdout, which can carry a
    # banner/preamble line (e.g. "open: GetPass() failed -- assume anonymous
    # login") before the file bytes — and trailing output after EOF. Parsing
    # the raw capture produced "Extra data: line N column M" errors (Exp 222),
    # so extract exactly the first JSON object via raw_decode and ignore any
    # surrounding chatter.
    print()
    print("--- Feature Flags (PS4 features.json — plugin behavior on next boot) ---")
    fx = cat_remote(f"{AFR_DIR}/features.json")
    if fx is None:
        print("  (features.json not found on PS4 — fresh-install defaults: ALL features ON — Exp 281)")
    else:
        try:
            decoder = json.JSONDecoder()
            # Find the first '{' and decode exactly one JSON object from there.
            start = fx.index('{')
            feats, _ = decoder.raw_decode(fx[start:])
        except Exception as e:
            print(f"  (failed to parse features.json: {e})")
            feats = None
        if feats is not None:
            # Absent keys default: enable_plugin=true (kill switch), others false.
            plugin_on = feats.get("enable_plugin", True)
            print(f"  Plugin (enable_plugin): {'ON — custom songs active' if plugin_on else 'OFF — official songs only'}")
            flag_names = ["enable_custom_song_replacements", "enable_song_metadata_modification",
                          "enable_beatmap_mode_mapping", "enable_song_previews"]
            for fn in flag_names:
                if fn not in feats:
                    print(f"  {fn}: MISSING (defaults false on the plugin)")
                else:
                    print(f"  {fn}: {'ON' if feats[fn] else 'OFF'}")
            n_on = sum(1 for fn in flag_names if feats.get(fn, False))
            print(f"  → Boot notification will show: "
                  f"\"OrBeats vX ({'ON' if plugin_on else 'OFF'}) ... ({n_on}/4 features "
                  f"{'ON' if plugin_on else '— plugin disabled'})\"")
    print()
    print("=" * 62)

    # 6. Local pipeline cache files (affect what pipeline thinks is deployed)
    print()
    print("--- Local Pipeline Cache (affects pipeline behavior) ---")
    local_cache_files = {
        "song_metadata.json": "/workspace/orbeats/song_metadata.json",
        "redirects.json": "/workspace/orbeats/redirects.json",
        "catalog_pack_modes.json": "/workspace/orbeats/catalog_pack_modes.json",
    }
    cache_present = []
    for name, path in local_cache_files.items():
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                if name == "redirects.json":
                    redirects = data.get('redirects', {})
                    print(f"  ✅ {name} ({len(data.get('redirects', {}))} redirects)")
                elif name == "song_metadata.json":
                    names = len(data.get('song_names', {}))
                    artists = len(data.get('song_artists', {}))
                    print(f"  ✅ {name} ({names} song names, {artists} artist entries)")
                elif name == "catalog_pack_modes.json":
                    # Count entries - catalog is an object with m_EntryDataString etc
                    print(f"  ✅ {name} (present)")
                cache_present.append(name)
            except Exception as e:
                print(f"  ⚠️  {name} (parse error: {e})")
        else:
            print(f"  ❌ {name} (missing)")

    if not cache_present:
        print("  (no local pipeline cache files)")

    print()
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())