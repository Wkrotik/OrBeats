"""Older working profiles and actionable import refusals; no console/network."""
import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from test_additive_v3_import import chart, imp

ROOT = Path(__file__).resolve().parents[1]


def test_initial_tab_uses_history_only_for_navigation_and_never_skips_restoration():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required")
    source = (ROOT / "webapp/static/companion.js").read_text()
    function = source[source.index("function initialTab("):source.index("async function initialize()")]
    subprocess.run([node, "-e", function + """
const assert=require('node:assert/strict');
for(const hash of ['', 'setup', 'discover', 'library', 'settings']) {
 const fresh={complete:false,cleanup_required:false},history={history:[{status:'complete'}]};
 assert.equal(initialTab(fresh,{history:[]},hash),'setup');
 for(const status of ['failed','cancelled','queued']) assert.equal(initialTab(fresh,{history:[{status}]},hash),'setup');
 assert.equal(initialTab(fresh,history,hash),['library','settings'].includes(hash)?hash:'discover');
 assert.equal(fresh.complete,false); // History is not setup validation.
 assert.equal(initialTab({...fresh,cleanup_required:true},history,hash),'setup');
 assert.equal(initialTab({...fresh,unavailable:true},history,hash),'setup');
 assert.equal(initialTab({complete:true,cleanup_required:true},history,hash),'setup');
 assert.equal(initialTab({complete:true},{history:[]},hash),['library','settings'].includes(hash)?hash:'discover');
}
"""], check=True)


@pytest.mark.parametrize("extra,valid", [({}, True), ({"time": 1}, False),
    ({"bookmarks": []}, False), ({"_time": True}, False),
    ({"_bookmarks": [{"_time": 1, "_name": "x", "track": "mod"}]}, False),
    ({"requirements": ["Noodle Extensions"]}, False)])
def test_v3_legacy_editor_aliases_are_validated_not_gameplay(tmp_path, extra, valid):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")
    source = tmp_path / "source"
    imp.prepare.generate_probe(source)
    file = source / "Easy.dat"
    data = chart()
    data["customData"] = {"_time": 23.211, "_bookmarks": [{"_time": 1, "_name": "Intro", "_color": [1, 0, 0, 1]}], **extra}
    file.write_text(json.dumps(data))
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    if not valid:
        with pytest.raises(ValueError):
            imp.import_song(source, tmp_path / "out")
    else:
        modern = copy.deepcopy(data)
        modern["customData"] = {"time": 23.211, "bookmarks": [{"b": 1, "n": "Intro", "c": [1, 0, 0, 1]}]}
        expected = imp.convert_map(modern, 120)
        imp.import_song(source, tmp_path / "out")
        assert json.loads((tmp_path / "out/Easy.dat").read_text()) == expected
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}


@pytest.mark.parametrize("kind,value,reason", [("duration", -.25, "wall duration"),
    ("width", -20, "wall geometry"), ("lighting", 40, "lighting event type"),
    ("beat", 689.25, "basicBeatmapEvents beat")])
def test_unsupported_authored_objects_explain_refusal_without_editing(tmp_path, kind, value, reason):
    source = tmp_path / "song"
    imp.prepare.generate_probe(source)
    file = source / "Easy.dat"
    data = json.loads(file.read_text())
    if kind in ("width", "duration"):
        data["obstacles"] = [{"b": 1, "x": 0, "y": 0, "d": value if kind == "duration" else 1, "w": value if kind == "width" else 1, "h": 1}]
    else:
        data["basicBeatmapEvents"] = [{"b": value if kind == "beat" else 0, "et": value if kind == "lighting" else 1, "i": 0, "f": 1}]
    file.write_text(json.dumps(data))
    before = file.read_bytes()
    with pytest.raises(ValueError, match="unsupported") as error:
        imp.prepare.load_song(source)
    assert reason in str(error.value) and file.read_bytes() == before


def test_mod_suggestion_refusal_names_the_unsupported_dependency():
    with pytest.raises(ValueError, match="mod-dependent maps are not supported.*ChromaGLS.*no effects were stripped"):
        imp.cosmetic_only({"_suggestions": ["ChromaGLS"]}, set())
