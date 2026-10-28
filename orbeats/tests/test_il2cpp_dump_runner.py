"""Synthetic local runner tests; no real game files, .NET execution or network."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "development/scripts/run_il2cpp_dump.py"
spec = importlib.util.spec_from_file_location("il2cpp_runner", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture
def inputs(tmp_path):
    tool = tmp_path / "tool"
    tool.mkdir()
    (tool / "Il2CppDumper.dll").write_bytes(b"synthetic tool")
    (tool / "config.json").write_text('{"RequireAnyKey": false}')
    binary, metadata, dotnet = (tmp_path / n for n in ("binary", "metadata", "dotnet"))
    binary.write_bytes(b"synthetic binary")
    metadata.write_bytes(b"synthetic metadata")
    dotnet.write_text("synthetic executable; never executed")
    dotnet.chmod(0o700)
    return dict(binary=binary, metadata=metadata, output=tmp_path / "output",
                log=tmp_path / "analysis.log", dotnet=dotnet, tool=tool)


def fake_run(command, **kwargs):
    output = Path(command[-1])
    for name in ("dump.cs", "script.json", "il2cpp.h"):
        (output / name).write_text("synthetic generated evidence")
    kwargs["stdout"].write("Done!\n")
    assert kwargs["input"] == "0\n"
    assert kwargs["env"]["DOTNET_ROLL_FORWARD"] == "Major"
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 300
    return subprocess.CompletedProcess(command, 0)


def test_success_preserves_inputs_records_hashes_and_not_runtime_ready(inputs, monkeypatch):
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    before = inputs["binary"].read_bytes(), inputs["metadata"].read_bytes()
    result = runner.generate_dump(**inputs)
    assert result["runtime_ready"] is False
    assert result["inputs"]["binary"]["sha256"] == runner.digest(inputs["binary"])["sha256"]
    assert set(result["artifacts"]) == {"dump.cs", "script.json", "il2cpp.h"}
    assert json.loads((inputs["output"] / "analysis-manifest.json").read_text()) == result
    assert before == (inputs["binary"].read_bytes(), inputs["metadata"].read_bytes())


@pytest.mark.parametrize("name", ["output", "log"])
def test_refuses_existing_paths(inputs, name):
    inputs[name].write_text("preserve me")
    with pytest.raises(FileExistsError):
        runner.generate_dump(**inputs)
    assert inputs[name].read_text() == "preserve me"


def test_refuses_missing_input(inputs):
    inputs["metadata"] = inputs["metadata"].parent / "absent"
    with pytest.raises(ValueError, match="Required local file missing"):
        runner.generate_dump(**inputs)
    assert not inputs["output"].exists()


def test_refuses_interactive_tool_config(inputs):
    (inputs["tool"] / "config.json").write_text('{"RequireAnyKey": true}')
    with pytest.raises(ValueError, match="RequireAnyKey must be false"):
        runner.generate_dump(**inputs)


def test_nonzero_exit_preserves_log_but_no_success_manifest(inputs, monkeypatch):
    def fail(command, **kwargs):
        kwargs["stdout"].write("synthetic failure\n")
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(runner.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        runner.generate_dump(**inputs)
    assert "synthetic failure" in inputs["log"].read_text()
    assert not (inputs["output"] / "analysis-manifest.json").exists()


def test_zero_exit_without_artifacts_is_not_success(inputs, monkeypatch):
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: None)
    with pytest.raises(ValueError, match="Expected generated artifact"):
        runner.generate_dump(**inputs)
    assert not (inputs["output"] / "analysis-manifest.json").exists()


def test_changed_input_is_not_success(inputs, monkeypatch):
    def modify(command, **kwargs):
        fake_run(command, **kwargs)
        inputs["binary"].write_bytes(b"changed during analysis")
    monkeypatch.setattr(runner.subprocess, "run", modify)
    with pytest.raises(ValueError, match="Input changed during analysis"):
        runner.generate_dump(**inputs)
    assert not (inputs["output"] / "analysis-manifest.json").exists()


def test_bad_timeout(inputs):
    with pytest.raises(ValueError, match="timeout must be positive"):
        runner.generate_dump(**inputs, timeout=0)


def test_timeout_keeps_evidence(inputs, monkeypatch):
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
    monkeypatch.setattr(runner.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        runner.generate_dump(**inputs)
    assert inputs["log"].exists()
    assert not (inputs["output"] / "analysis-manifest.json").exists()


def test_log_cannot_live_inside_new_output(inputs):
    inputs["log"] = inputs["output"] / "analysis.log"
    with pytest.raises(ValueError):
        runner.generate_dump(**inputs)
    assert not inputs["output"].exists()
