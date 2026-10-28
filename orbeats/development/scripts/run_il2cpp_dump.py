#!/usr/bin/env python3
"""Run pinned local Il2CppDumper on owned inputs, preserving evidence; no FTP.

Requires optional .devcontainer/setup_additive_analysis.sh. Generated game-derived
files belong in ignored il2cpp_output/, never in source control or release assets.
This produces metadata declarations, NOT a verified callable ABI or runtime hook.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / ".tools/il2cpp-dumper/v6.7.46"


def digest(path: Path) -> dict:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha.hexdigest()}


def generate_dump(binary: Path, metadata: Path, output: Path, log: Path,
                  dotnet: Path, tool: Path = TOOL, timeout: int = 300) -> dict:
    """Generate into a NEW directory; refuse existing reports, logs and outputs."""
    binary, metadata, dotnet, tool = (p.resolve() for p in (binary, metadata, dotnet, tool))
    output, log = output.absolute(), log.absolute()
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    dll = tool / "Il2CppDumper.dll"
    config = tool / "config.json"
    for path in (binary, metadata, dotnet, dll, config):
        if not path.is_file():
            raise ValueError(f"Required local file missing: {path}")
    if not os.access(dotnet, os.X_OK):
        raise ValueError("dotnet must be executable")
    if json.loads(config.read_text()).get("RequireAnyKey") is not False:
        raise ValueError("RequireAnyKey must be false; run local analysis setup first")
    if output.exists() or output.is_symlink() or log.exists() or log.is_symlink():
        raise FileExistsError("Output directory and log must both be new")
    if not output.parent.is_dir() or not log.parent.is_dir():
        raise ValueError("Create output/log parent directories first")
    if log.resolve().is_relative_to(output.resolve()):
        raise ValueError("Log must be outside the new output directory")
    # Record originals before external analysis. Outputs/config remain local only.
    inputs = {"binary": digest(binary), "metadata": digest(metadata)}
    tool_inputs = {"dll": digest(dll), "config": digest(config)}
    with log.open("x") as stream:
        output.mkdir()  # exclusive; failures retain evidence, never clean user files
        command = [str(dotnet), str(dll), str(binary), str(metadata), str(output)]
        stream.write("Command: " + json.dumps(command) + "\n")
        stream.flush()
        env = {**os.environ, "DOTNET_ROLL_FORWARD": "Major",
               "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}
        subprocess.run(command, input="0\n", text=True, stdout=stream,
                       stderr=subprocess.STDOUT, env=env, check=True, timeout=timeout)
    for name, path in (("binary", binary), ("metadata", metadata)):
        if digest(path) != inputs[name]:
            raise ValueError("Input changed during analysis; do not trust output")
    artifacts = {}
    for name in ("dump.cs", "script.json", "il2cpp.h"):
        path = output / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Expected generated artifact missing or empty: {name}")
        artifacts[name] = digest(path)
    report = {"schema_version": 1, "tool_version": "6.7.46", "runtime_ready": False,
              "inputs": inputs, "tool_inputs": tool_inputs, "artifacts": artifacts,
              "log": digest(log), "command": command,
              "limitations": ["Metadata/addresses require independent binary and runtime verification",
                              "No pack registered, no console access or writes"]}
    with (output / "analysis-manifest.json").open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, default=ROOT / ".tools/dotnet/dotnet")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    report = generate_dump(args.binary, args.metadata, args.output, args.log,
                           args.dotnet, timeout=args.timeout)
    print(json.dumps({"runtime_ready": report["runtime_ready"],
                      "manifest": str(args.output / "analysis-manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
