#!/usr/bin/env python3
"""
verify_repair_ps4_assets.py — Isolate + repair corrupt custom-song assets on the PS4.

Context (Exp 193-194): a prior editing session (Gemini) deployed a bad per-song bundle
(e18921b "updated the custom bundle ... Start Me Up") that crashes Beat Saber at the menu
(CE-34878-0, post-VR, silent). The plugin (v0.8040 / a8a06f0), the 4 patched packs, and the
merged catalog were all verified GOOD. The crash is a per-song bundle loaded by the menu.

This script compares every deployed asset's md5 against the LOCAL good source, reports drift,
and (with --redeploy) re-uploads the good local copy over any corrupted remote file.

Local good sources:
  per-song : beat_saber_deluxe/custom_songs/<slot>_custom.bundle   -> <slot>_v3.bundle
  packs    : beat_saber_deluxe/pack_modes_bundles/<pack>_pack_modes_assets_all_<hash>.bundle
  catalog  : beat_saber_deluxe/catalog_pack_modes.json            -> catalog_pack_modes.json
Deployed root: /data/GoldHEN/AFR/CUSA12878/

Usage:
  python3 verify_repair_ps4_assets.py            # verify only, report drift
  python3 verify_repair_ps4_assets.py --redeploy # verify, then re-upload drifted/missing
  python3 verify_repair_ps4_assets.py --redeploy --all  # re-upload every local asset
"""
import json, hashlib, os, sys, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BS = ROOT  # ROOT is already .../beat_saber_deluxe
CFG = json.load(open(os.path.join(BS, "ps4_config.json")))
PS4_IP = CFG["ps4"]["ip"]
PS4_PORT = CFG["ps4"]["ftp_port"]
AFR = "/data/GoldHEN/AFR/CUSA12878"

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def get_remote_md5(remote):
    # download to temp and hash
    tmp = "/tmp/opencode/_vr_%s" % os.path.basename(remote)
    try:
        subprocess.run(["lftp", "-u", "anonymous,", "-p", str(PS4_PORT), PS4_IP,
                        "-e", "get %s -o %s; quit" % (remote, tmp)],
                       check=True, capture_output=True, timeout=120)
        return md5(tmp)
    except Exception:
        return None

def remote_exists(remote):
    r = subprocess.run(["lftp", "-u", "anonymous,", "-p", str(PS4_PORT), PS4_IP,
                        "-e", "ls %s; quit" % remote],
                       capture_output=True, text=True, timeout=30)
    return "not found" not in r.stderr.lower() and r.returncode == 0

def put(local, remote):
    subprocess.run(["lftp", "-u", "anonymous,", "-p", str(PS4_PORT), PS4_IP,
                    "-e", "put %s -o %s; quit" % (local, remote)],
                   check=True, capture_output=True, timeout=300)

def main():
    redeploy = "--redeploy" in sys.argv
    allmode = "--all" in sys.argv
    redir = json.load(open(os.path.join(BS, "redirects.json")))
    entries = redir["redirects"]

    plan = []  # (kind, local, remote)
    for key, val in entries.items():
        if key == "aa/catalog.json":
            plan.append(("catalog", os.path.join(BS, "catalog_pack_modes.json"),
                         "%s/catalog_pack_modes.json" % AFR))
        elif key.endswith("_pack_assets_all_.bundle") or "_pack_assets_all_" in key:
            # pack redirect: key = original pack name, val = patched pack name
            local = os.path.join(BS, "pack_modes_bundles", val)
            plan.append(("pack", local, "%s/%s" % (AFR, val)))
        elif key.startswith("BeatmapLevelsData/"):
            slot = key.split("/", 1)[1]
            local = os.path.join(BS, "custom_songs", "%s_custom.bundle" % slot)
            plan.append(("song", local, "%s/%s" % (AFR, val)))

    drift = []
    for kind, local, remote in plan:
        if not os.path.exists(local):
            print("[SKIP] %-7s no local source: %s" % (kind, local))
            continue
        local_md5 = md5(local)
        remote_md5 = get_remote_md5(remote) if not allmode else None
        if allmode:
            print("[ALL ] %-7s %s" % (kind, os.path.basename(remote)))
            drift.append((kind, local, remote, "forced"))
            continue
        if remote_md5 is None:
            print("[MISS] %-7s %s (remote missing/unreachable)" % (kind, os.path.basename(remote)))
            drift.append((kind, local, remote, "missing"))
        elif remote_md5 != local_md5:
            print("[DRIFT] %-7s %s  local=%s remote=%s" % (kind, os.path.basename(remote), local_md5[:10], remote_md5[:10]))
            drift.append((kind, local, remote, "drift"))
        else:
            print("[OK  ] %-7s %s" % (kind, os.path.basename(remote)))

    print("\n=== %d drift/missing of %d assets ===" % (len(drift), len(plan)))
    if not redeploy:
        print("Run with --redeploy to re-upload good local copies over drifted/missing remotes.")
        return
    for kind, local, remote, why in drift:
        print("REDEPLOY %s -> %s" % (kind, remote))
        put(local, remote)
    print("Done. Clear bs_log.txt and reboot Beat Saber to confirm stable boot.")

if __name__ == "__main__":
    main()
