#!/usr/bin/env python3
"""
batch_runner.py — execute a batch of pipeline deploys serially.

Invoked by the web app's Batch tab (never by users directly):
    python3 webapp/batch_runner.py --jobs '<json argv list>'

Runs each deploy as a subprocess with the pipeline's own argv, streaming
every line; STOPS at the first failure (exit != 0) so a broken song never
gets silently skipped — the same semantics as the chained example scripts
(script1 && script2). One deploy at a time is the runner's rule; this driver
IS the single job.

Exp 269c optimization: every --deploy-full rebuilds song-previews variants
for packs whose inputs changed. Across an N-song batch that means N-1
throwaway preview passes — only the LAST deploy's rebuild matters. The
runner appends --skip-song-preview-management to every batch command EXCEPT
the last, so previews regenerate exactly once, at the end. (A user-supplied
--skip-song-preview-management on the final command is respected as-is;
manual single deploys are never touched.)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tools"))
import sys
from pathlib import Path

WEBAPP = Path(__file__).resolve().parent
PROJECT = WEBAPP.parent
RELEASE_ROOT = PROJECT.parent
PIPELINE = PROJECT / "tools" / "full_custom_song_pipeline.py"

SKIP_PREVIEWS_FLAG = "--skip-song-preview-management"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True,
                        help="JSON list of pipeline argv lists")
    args = parser.parse_args()

    try:
        batch = json.loads(args.jobs)
    except json.JSONDecodeError as e:
        print(f"batch_runner: invalid --jobs payload: {e}", file=sys.stderr)
        return 2

    if not isinstance(batch, list) or not batch:
        print("batch_runner: empty batch", file=sys.stderr)
        return 2

    # Exp 269c: defer preview management to the LAST deploy only. The flag is
    # idempotent-safe: the pipeline ignores it when previews are OFF, and the
    # final command's full preview pass dirty-checks every pack (cheap when
    # clean). Skip when the batch is a single job — nothing to defer.
    if len(batch) > 1:
        for i, argv in enumerate(batch[:-1]):
            if (isinstance(argv, list) and "--deploy-full" in argv
                    and SKIP_PREVIEWS_FLAG not in argv):
                argv.append(SKIP_PREVIEWS_FLAG)
        if isinstance(batch[-1], list) and "--deploy-full" in batch[-1] \
                and SKIP_PREVIEWS_FLAG in batch[-1]:
            # user explicitly deferred previews even on the last command:
            # honor it (they may plan a manual --deploy-pack-modes follow-up)
            print("batch_runner: NOTE — last command carries "
                  "--skip-song-preview-management; previews were NOT rebuilt "
                  "this batch (run a deploy without the flag to refresh them)",
                  flush=True)

    print(f"=== Batch deploy: {len(batch)} songs ===")
    for i, argv in enumerate(batch, 1):
        label = " ".join(argv)
        print(f"\n--- [{i}/{len(batch)}] {' '.join(label.split())} ---", flush=True)
        result = subprocess.run(
            __import__("runtime_dispatch").command(PIPELINE, argv),
            cwd=str(RELEASE_ROOT),
            text=True, bufsize=1)
        if result.returncode != 0:
            print(f"\n❌ Batch STOPPED: song [{i}/{len(batch)}] failed "
                  f"(exit {result.returncode}). Fix it and re-run the batch; "
                  f"songs before this one are deployed.", flush=True)
            return result.returncode
    print(f"\n✅ Batch complete: {len(batch)}/{len(batch)} songs deployed.",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
