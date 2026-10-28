"""Regression for the PS4 basic-light converter null-list crash; synthetic inputs."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "keyword_bundle_prepare", ROOT / "development/scripts/prepare_additive_bundle.py"
)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


@pytest.mark.parametrize("table", ["missing", {}, {"d": []}])
def test_supported_empty_keyword_tables_materialize_native_inner_list(table):
    data = {"version": "3.3.0", "basicBeatmapEvents": [{"b": 2, "et": 1, "i": 3, "f": 1.0}]}
    if table != "missing":
        data["basicEventTypesWithKeywords"] = copy.deepcopy(table)
    events = copy.deepcopy(data["basicBeatmapEvents"])
    prepare.complete_v3_keywords(data)
    assert data["basicEventTypesWithKeywords"] == {"d": []}
    assert data["basicBeatmapEvents"] == events
    before = copy.deepcopy(data)
    prepare.complete_v3_keywords(data)
    assert data == before


@pytest.mark.parametrize("table", [None, [], False, {"d": None}, {"d": [None]}, {"d": [], "unknown": []}, {"d": [{"k": "foo", "e": [1]}]}])
def test_keyword_completion_never_drops_authored_or_malformed_routing(table):
    data = {"version": "3.3.0", "basicEventTypesWithKeywords": table}
    before = copy.deepcopy(data)
    with pytest.raises(ValueError, match="unsupported light keywords"):
        prepare.complete_v3_keywords(data)
    assert data == before


@pytest.mark.parametrize("table", ["missing", {}, {"d": []}])
def test_real_preparer_completes_every_generated_difficulty(tmp_path, table):
    song = tmp_path / "song"
    prepare.generate_probe(song)
    original = {}
    for path in song.glob("*.dat"):
        if path.name == "Info.dat":
            continue
        data = json.loads(path.read_bytes())
        if table == "missing":
            data.pop("basicEventTypesWithKeywords", None)
        else:
            data["basicEventTypesWithKeywords"] = copy.deepcopy(table)
        data["basicBeatmapEvents"] = [{"b": 1, "et": 0, "i": 1, "f": 1.0}]
        original[path.stem] = copy.deepcopy(data)
        path.write_text(json.dumps(data))
    result = prepare.load_song(song)
    assert len(result["maps"]) == 5
    for difficulty, data in result["maps"].items():
        assert data["basicEventTypesWithKeywords"] == {"d": []}
        for key in ("colorNotes", "bombNotes", "obstacles", "basicBeatmapEvents"):
            assert data[key] == original[difficulty].get(key, [])
    assert prepare.load_song(song)["source_sha256"] == result["source_sha256"]


def test_same_native_completion_is_used_after_preserved_v3_validation():
    # Branch must first verify authored chart/lightshow equality, then complete
    # chart and regenerate its matching lightshow; V4 must remain untouched.
    source = (ROOT / "development/scripts/prepare_additive_bundle.py").read_text()
    assert "if native_light != lightshow_preserved(data): raise ValueError('native V3 lightshow mismatch')\n                    complete_v3_keywords(data)\n                    native_light = lightshow_preserved(data)" in source
