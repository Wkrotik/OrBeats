"""Cross-platform output and UI regressions. No console or external services."""

import ast
import copy
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import additive_presentation as presentation
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orbeats/webapp"))
from adapters.runner import SingleJobRunner


def test_empty_scheme_default_retains_difficulty_authored_colours():
    info = {
        "_colorSchemes": [],
        "_difficultyBeatmapSets": [
            {
                "_beatmapCharacteristicName": "Standard",
                "_difficultyBeatmaps": [
                    {
                        "_difficulty": "ExpertPlus",
                        "_beatmapColorSchemeIdx": 0,
                        "_customData": {"_envColorLeft": {"r": 0.2, "g": 0.3, "b": 0.4}},
                    }
                ],
            }
        ],
    }
    before = copy.deepcopy(info)
    palette = presentation.from_info(info)["colors"][4]
    assert palette["environmentColor0"] == [0.2, 0.3, 0.4, 1.0] and info == before


@pytest.mark.parametrize("index", [True, False, 1, -2, 0.0, "0"])
def test_empty_scheme_still_rejects_invalid_references(index):
    info = {
        "_colorSchemes": [],
        "_difficultyBeatmapSets": [
            {"_difficultyBeatmaps": [{"_difficulty": "Expert", "_beatmapColorSchemeIdx": index}]}
        ],
    }
    with pytest.raises(ValueError, match="scheme index"):
        presentation.from_info(info)


def test_worker_utf8_output_is_visible_before_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONIOENCODING", "ascii")
    marker = tmp_path / "finish"
    code = (
        "import time,pathlib;print('Installing → café 日本語',flush=True);p=pathlib.Path(%r);exec('while not p.exists(): time.sleep(.01)')"
        % str(marker)
    )
    runner = SingleJobRunner()
    job = runner._spawn([sys.executable, "-c", code], label="synthetic", command="synthetic")
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if any("café 日本語" in line for line in runner.snapshot()["lines"]):
                break
            time.sleep(0.02)
        assert runner.is_busy() and any("Installing → café 日本語" in line for line in runner.snapshot()["lines"])
        assert job.lines[0].startswith("[job] Worker started")
    finally:
        marker.touch()
        deadline = time.monotonic() + 5
        while runner.is_busy() and time.monotonic() < deadline:
            time.sleep(0.02)
    assert job.exit_code == 0 and job.ended_at


def test_frozen_tasks_explicitly_set_utf8_unbuffered_streams():
    tree = ast.parse((ROOT / "desktop/backend/entrypoint.py").read_text(encoding="utf-8"))
    task = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "task")
    loop = next(n for n in task.body if isinstance(n, ast.For))
    calls = []
    stream = SimpleNamespace(reconfigure=lambda **kwargs: calls.append(kwargs))
    exec(
        compile(ast.Module(body=[loop], type_ignores=[]), "<task-output-policy>", "exec"),
        {"sys": SimpleNamespace(stdout=stream, stderr=stream)},
    )
    assert calls == [dict(encoding="utf-8", errors="backslashreplace", line_buffering=True, write_through=True)] * 2


def test_owned_svg_and_ip_only_connection_form():
    static = ROOT / "orbeats/webapp/static"
    svg = ET.fromstring((static / "orbeats.svg").read_text(encoding="utf-8"))
    assert svg.tag == "{http://www.w3.org/2000/svg}svg"
    assert all(not n.tag.endswith("script") and not any("href" in k for k in n.attrib) for n in svg.iter())
    html = (static / "companion.html").read_text(encoding="utf-8")
    form = html.split('<form id="connection"', 1)[1].split("</form>", 1)[0]
    assert form.count("<input") == 1 and 'id="ip"' in form
    assert not any(f'id="{name}"' in html for name in ["port", "user", "password"])
    assert html.count('src="/static/orbeats.svg"') == 2 and ">♪<" not in html
    assert 'id="template-settings"' in html and "Not an FTP directory" in html
    assert "<progress " not in html and 'role="progressbar"' in html
    css = (static / "companion.css").read_text(encoding="utf-8")
    assert "@keyframes installation-activity" in css and "prefers-reduced-motion" in css
    js = (static / "companion.js").read_text(encoding="utf-8")
    assert 'addEventListener("wheel"' not in js and "onwheel" not in js
