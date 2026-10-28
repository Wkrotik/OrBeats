"""Regenerate OneSaber beatmaps with the corrected (RIGHT/blue) saber color.

Background: OneSaber mode is played with the RIGHT (blue) saber exclusively.
The mode generator (`_generate_one_saber`) previously forced notes to the LEFT
(red) saber, making generated OneSaber maps unplayable. After the generator
constant `_ONE_SABER_COLOR` was flipped to 1 (blue), every OneSaber beatmap
must be regenerated from its Standard source so the corrected color takes
effect in deployed bundles.

This script walks every custom song directory under
`beat-saber-ps4-custom-songs/songs/` and, for each `<Diff>OneSaber.dat` that
still contains LEFT/red (color 0) notes (i.e. the buggy generated set),
regenerates it from the song's Standard source via the now-fixed
`_generate_one_saber`. Files that are already RIGHT/blue (correct, including
mapper-authored OneSaber maps) are left untouched.

Usage:
    python3 development/scripts/regenerate_onesaber_blue.py
"""

import json
import os
import sys

# Allow importing the pipeline module from project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

import full_custom_song_pipeline as pipe  # noqa: E402

SONGS_ROOT = "/workspace/beat-saber-ps4-custom-songs/songs_repo"
DIFFS = ["Easy", "Normal", "Hard", "Expert", "ExpertPlus"]


def color_of(note):
    if "c" in note:
        return note["c"]
    return note.get("_type")


def set_color(note, val):
    if "c" in note:
        note["c"] = val
    if "_type" in note:
        note["_type"] = val


def has_red(notes):
    return any(color_of(n) == 0 for n in notes)


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def find_standard_source(song_dir, diff):
    base = os.path.basename(song_dir)
    for name in (f"{diff}Standard.dat", f"{diff}.dat"):
        p = os.path.join(song_dir, name)
        if os.path.isfile(p):
            return p
    return None


def main():
    regenerated = 0
    recolored = 0
    skipped = 0
    errors = 0

    for song_dir, _dirs, files in os.walk(SONGS_ROOT):
        # Only consider directories that actually contain beatmap .dat files.
        dat_files = [f for f in files if f.lower().endswith(".dat")]
        if not dat_files:
            continue
        for fn in sorted(dat_files):
            lower = fn.lower()
            if "onesaber" not in lower:
                continue
            # Derive difficulty by removing the "OneSaber" token.
            diff = fn.replace(".dat", "").replace("OneSaber", "").replace("onesaber", "")
            if diff not in DIFFS:
                print(f"  ! could not derive difficulty from {fn!r} (got {diff!r}) — skipping")
                errors += 1
                continue

            path = os.path.join(song_dir, fn)
            try:
                data = load(path)
            except Exception as e:
                print(f"  ! failed to read {path}: {e}")
                errors += 1
                continue

            notes = data.get("colorNotes") or data.get("_notes") or []
            if not has_red(notes):
                skipped += 1  # already RIGHT/blue (or bomb-only) — correct, leave alone
                continue

            src = find_standard_source(song_dir, diff)
            if src:
                try:
                    source = load(src)
                except Exception as e:
                    print(f"  ! failed to read standard source {src}: {e}")
                    errors += 1
                    continue
                new_data = pipe._generate_one_saber(source, min_gap=pipe._ONE_SABER_MIN_GAP)
                save(path, new_data)
                regenerated += 1
                print(f"  regenerated {os.path.relpath(path, SONGS_ROOT)} <- {os.path.basename(src)}")
            else:
                # No Standard source: just recolor existing notes to blue in place.
                for n in notes:
                    set_color(n, 1)
                save(path, data)
                recolored += 1
                print(f"  recolored-in-place {os.path.relpath(path, SONGS_ROOT)} (no standard source)")

    print(f"\nDone. regenerated={regenerated} recolored={recolored} "
          f"already-correct(skipped)={skipped} errors={errors}")


if __name__ == "__main__":
    main()
