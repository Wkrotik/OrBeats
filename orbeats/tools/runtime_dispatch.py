"""Python child invocation shared by source and frozen desktop runtimes."""
import os
import sys
from pathlib import Path

TASKS = {
    "pipeline": "tools/full_custom_song_pipeline.py",
    "import-v3": "development/scripts/import_v3_additive.py",
    "prepare-additive": "development/scripts/prepare_additive_bundle.py",
    "batch": "webapp/batch_runner.py",
    "beatsage": "webapp/beatsage_client.py",
}


def command(script, argv):
    script = Path(script).resolve()
    if not getattr(sys, "frozen", False):
        return [sys.executable, str(script), *argv]
    root = Path(os.environ["ORBEATS_RUNTIME_ROOT"]).resolve()
    try:
        relative = script.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Script outside frozen runtime") from exc
    task = next((key for key, value in TASKS.items() if value == relative), None)
    if task is None:
        raise ValueError("This helper is not supported by the frozen desktop dispatcher")
    return [sys.executable, "--desktop-task", task, "--", *argv]
