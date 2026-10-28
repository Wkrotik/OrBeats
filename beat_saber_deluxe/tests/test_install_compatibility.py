"""Source-only installation regressions: synthetic maps, never PS4 or owned assets."""

import copy
import json
import shutil

import additive_v4_native as native
import pytest
from test_additive_v2_import import imp as legacy
from test_additive_v2_import import v2
from test_additive_v3_import import imp as primary
from test_additive_v4_import import chart


def test_constant_legacy_bpm_annotations_are_identity_not_silent_tempo_loss():
    source = v2()
    source["_BPMChanges"] = [{"_time": 2, "_BPM": 70}]
    before = copy.deepcopy(source)
    assert legacy.convert_map(source, base_bpm=70) == legacy.convert_map(v2())
    assert source == before
    for base in (None, 71, True):
        with pytest.raises(ValueError):
            legacy.convert_map(source, base_bpm=base)


def test_reviewed_legacy_atlas_scalar_never_changes_objects():
    source = v2()
    source["_customData"] = {"_atlasBeatsMap": 285278464}
    assert legacy.convert_map(source) == legacy.convert_map(v2())
    source["_customData"]["_atlasBeatsMap"] = {"_customEvents": []}
    with pytest.raises(ValueError):
        legacy.convert_map(source)


@pytest.mark.parametrize("environment", ["DefaultEnvironment", "BigMirrorEnvironment"])
def test_empty_environment_table_default_index_preserves_root(tmp_path, environment):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required for synthetic offline import")
    source = tmp_path / "source"
    primary.prepare.generate_probe(source)
    file = source / "Info.dat"
    info = json.loads(file.read_text())
    info.update(_environmentName=environment, _environmentNames=[])
    for diff in info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"]:
        diff["_environmentNameIdx"] = 0
    file.write_text(json.dumps(info))
    before = file.read_bytes()
    primary.import_song(source, tmp_path / "output")
    result = json.loads((tmp_path / "output/Info.dat").read_text())
    assert result["_environmentName"] == environment and file.read_bytes() == before


def test_zero_time_chain_keeps_all_authored_slices_and_times():
    source = chart()
    source.update(chains=[dict(hb=1, tb=1, i=1)], chainsData=[dict(tx=2, ty=1, c=5, s=1)])
    before = copy.deepcopy(source)
    native.chart(source, 2, 12)
    assert source == before
    source["chains"][0]["tb"] = 0.99
    with pytest.raises(ValueError, match="chains tail"):
        native.chart(source, 2, 12)
