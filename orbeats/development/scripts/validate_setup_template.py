"""Isolated local setup conversion. No config, network or console operations.

Native audio imports run on this worker's main thread, never in the HTTP server.
The normal source/frozen dispatcher and runtime verification remain in force.
"""

import argparse
import faulthandler
import os
import sys
import tempfile
from pathlib import Path

# Source execution has no frozen entrypoint to install the owned tools path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
MAX_TEMPLATE = 200000000


def phase(message):
    print("[setup-worker] " + message, flush=True)


def validate(source, output):
    source, output = Path(source), Path(output)
    if source.is_symlink() or not source.is_file() or not 0 < source.stat().st_size <= MAX_TEMPLATE:
        raise ValueError("Invalid setup input size or path")
    if output.exists() or output.is_symlink() or output.parent.is_symlink():
        raise ValueError("Setup output must be a new owned file")
    phase("Loading conversion helpers in isolated worker")
    import prepare_additive_bundle as prepare

    with tempfile.TemporaryDirectory(prefix="conversion-", dir=output.parent) as tmp:
        root = Path(tmp)
        phase("Generating a small synthetic validation song")
        prepare.generate_probe(root / "synthetic")
        phase("Converting and independently reading back; native audio loading may take a minute")
        result = prepare.prepare(root / "synthetic", source, root / "validated")
        phase("Verifying the converted template")
        prepare.validate(root / "validated", prepare.load_song(root / "synthetic"))
        value = (root / "validated" / result["bundle"]["file"]).read_bytes()
        if not 0 < len(value) <= MAX_TEMPLATE:
            raise ValueError("Validated setup output exceeds size bound")
        # Publish only after all strict conversion/readback and temporary cleanup.
    with output.open("xb") as stream:
        os.chmod(output, 0o600)
        stream.write(value)
    phase("Synthetic template validation completed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    faulthandler.enable()
    faulthandler.dump_traceback_later(45)
    try:
        validate(args.input, args.output)
    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()
