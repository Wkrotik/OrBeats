"""Generate reviewed source runtime resources; not a desktop release packager."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from resources import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--media",
        type=Path,
        help="Verified Linux media payload from build_media_linux.py",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = build(
        root / "beat_saber_deluxe", args.output, root / "LICENSE", media=args.media
    )
    print(
        f"Verified {len(manifest)} curated resources; no native tools or frozen helper bundled yet."
    )


if __name__ == "__main__":
    main()
