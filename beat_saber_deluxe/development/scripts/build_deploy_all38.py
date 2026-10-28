"""Build + deploy all 38 custom-song bundles via the pipeline.

PHASE 1 (build): for each slot in mass_deploy.slots, resolve its source song
dir and run the per-song pipeline WITHOUT --deploy:
    full_custom_song_pipeline.py --song-dir <src> --target <slot> \
        --pcm16 --no-pad --output mass_bundles/<slot>_v3.bundle
(mode mapping + generators + V2->V3 conversion are v0.5314+ defaults).

PHASE 2 (deploy, one shot): run the pipeline once with
    --deploy-mass-bundles --deploy-pack-modes --deploy-config --verify-ps4
so bundles/catalog land on the PS4 BEFORE redirects.json references them
(Exp 180 crash rule), followed by full post-deploy validation.

Source resolution order:
  1. EXPLICIT_SOURCES below (slot -> absolute dir) - authoritative, no guessing.
  2. songs_repo/ or chromeo_backout/ match: Info.dat _songName ==
     song_metadata.json display name for that slot.
Slots whose source cannot be resolved abort the run (fail loud, deploy nothing).

Usage:
    python3 development/scripts/build_deploy_all38.py [--dry-run] [--build-only]
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = "/workspace/beat-saber-ps4-custom-songs/songs_repo"
CHROMEO_BACKOUT = "/workspace/beat-saber-ps4-custom-songs/songs/chromeo_backout"
PIPE = os.path.join(ROOT, "tools", "full_custom_song_pipeline.py")
BUNDLE_DIR = "/workspace/beat_saber_deluxe/mass_bundles"
CFG = os.path.join(ROOT, "ps4_config.json")
META = os.path.join(ROOT, "song_metadata.json")

# Authoritative slot -> source-dir mappings for slots whose names don't
# normalize-match a repo Info.dat _songName (Chromeo sources recovered from
# PS4 bundle extraction live in chromeo_backout/, not songs_repo/).
EXPLICIT_SOURCES = {
    "crystallized": os.path.join(CHROMEO_BACKOUT, "Crystallized"),
    "cyclehit": os.path.join(CHROMEO_BACKOUT, "CycleHit"),
    "exitthisearthsatomosphere": os.path.join(CHROMEO_BACKOUT, "ExitThisEarthsAtomosphere"),
    "ghost": os.path.join(CHROMEO_BACKOUT, "Ghost"),
    "lightitup": os.path.join(CHROMEO_BACKOUT, "LightItUp"),
    "whatthecat": os.path.join(CHROMEO_BACKOUT, "WhatTheCat"),
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_slots():
    src = open(os.path.join(ROOT, "tools", "full_custom_song_pipeline.py")).read()
    m = re.search(r'"slots":\s*\[(.*?)\]', src, re.S)
    return re.findall(r'"([^"]+)"', m.group(1))


def build_repo_index():
    idx = {}
    for base in (REPO, CHROMEO_BACKOUT):
        if not os.path.isdir(base):
            continue
        for h in os.listdir(base):
            info = os.path.join(base, h, "Info.dat")
            if os.path.isfile(info):
                try:
                    n = json.load(open(info)).get("_songName", "").strip()
                except Exception:
                    n = ""
                idx[os.path.join(base, h)] = n
    return idx


def resolve(slots, idx):
    meta = json.load(open(META))["song_names"]
    key_by_slot = {}
    for s in slots:
        for k in meta:
            if norm(k) == norm(s) or norm(k).startswith(norm(s)):
                key_by_slot[s] = k
                break
    out = {}
    for s in slots:
        if s in EXPLICIT_SOURCES and os.path.isdir(EXPLICIT_SOURCES[s]):
            out[s] = EXPLICIT_SOURCES[s]
            continue
        k = key_by_slot.get(s)
        disp = meta.get(k, "")
        key = disp.split("/")[0].strip().lower()
        cands = [d for d, n in idx.items() if n.strip().lower() == key]
        # Also fall back to normalized substring matching on song name.
        if not cands:
            cands = [d for d, n in idx.items()
                     if norm(n) and (norm(s) in norm(n) or norm(n) in norm(s))]
        if len(cands) >= 1:
            out[s] = sorted(cands)[0]
    return out


def main():
    dry = "--dry-run" in sys.argv
    build_only = "--build-only" in sys.argv
    slots = load_slots()
    idx = build_repo_index()
    resolved = resolve(slots, idx)
    unresolved = [s for s in slots if s not in resolved]
    print(f"total slots={len(slots)} resolved={len(resolved)} "
          f"unresolved={len(unresolved)}", flush=True)
    if unresolved:
        # Fail loud BEFORE building anything: a partial deploy is worse than
        # no deploy (the PS4 would keep serving stale bundles silently).
        print(f"ABORT: unresolved sources for slots {unresolved}", flush=True)
        sys.exit(1)

    os.makedirs(BUNDLE_DIR, exist_ok=True)

    # ---- PHASE 1: build every slot locally --------------------------------
    failures = []
    for s in slots:
        src = resolved[s]
        out = os.path.join(BUNDLE_DIR, f"{s}_v3.bundle")
        cmd = [
            sys.executable, PIPE,
            "--song-dir", src,
            "--target", s,
            "--pcm16", "--no-pad",
            "--output", out,
        ]
        # Chromeo backout dirs carry pre-extracted FSB5 audio (audio.fsb) instead
        # of a wav/ogg the pipeline can auto-discover — pass it explicitly.
        fsb = os.path.join(src, "audio.fsb")
        if os.path.isfile(fsb):
            cmd += ["--audio", fsb]
        print(f"=== BUILD {s} <- {src} ===", flush=True)
        if dry:
            print("  (dry-run) " + " ".join(cmd), flush=True)
            continue
        r = subprocess.run(cmd)
        print(f"  -> exit={r.returncode} ({out})", flush=True)
        if r.returncode != 0 or not os.path.isfile(out):
            failures.append(s)
    if failures:
        print(f"BUILD FAILED FOR SLOTS: {failures} — deploying nothing.", flush=True)
        sys.exit(1)
    if dry or build_only:
        print("Build phase complete (--build-only: stopping before deploy).", flush=True)
        return

    # ---- PHASE 2: one-shot deploy via pipeline flags ----------------------
    deploy_cmd = [
        sys.executable, PIPE,
        "--deploy-mass-bundles",
        "--deploy-pack-modes",
        "--deploy-config",
        "--verify-ps4",
    ]
    print("=== DEPLOY ALL (mass bundles + pack modes + redirects + verify) ===", flush=True)
    r = subprocess.run(deploy_cmd)
    print(f"deploy exit={r.returncode}", flush=True)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
