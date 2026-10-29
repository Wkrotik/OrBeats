"""Source-only basic-light regressions: synthetic inputs, no game/song/PS4 access."""

import copy
import json

import additive_companion as app
import additive_v3_native as v3native
import additive_v4_native as native
import pytest

imp = app.helper("import_v3_additive.py")


def lights():
    return dict(version="4.0.0", basicEvents=[dict(b=0.25)], basicEventsData=[dict(t=1, i=3, f=1)])


def audio():
    return dict(
        version="4.0.0",
        songSampleCount=88200,
        songFrequency=44100,
        bpmData=[dict(si=0, ei=88200, sb=0, eb=2)],
        lufsData=[],
    )


@pytest.fixture
def source(tmp_path):
    folder = tmp_path / "source"
    imp.prepare.generate_probe(folder)
    return folder


@pytest.mark.parametrize("event_type", [*range(14), 16, 17, 18, 19])
def test_reviewed_basic_light_types_validate_without_mutation(event_type):
    light = lights()
    light["basicEventsData"][0]["t"] = event_type
    before = copy.deepcopy(light)
    native.lighting(light, 2)
    assert light == before


@pytest.mark.parametrize("unused", [False, True])
@pytest.mark.parametrize("bad", [-1, 14, 15, 20, 21, 40, 41, 42, 43, 100, 1000, True, False, 16.0, "16", None, [], {}])
def test_basic_light_types_reject_rotations_specials_unknowns_and_nonintegers(bad, unused):
    light = lights()
    if unused:
        light["basicEventsData"].append(dict(t=bad))
    else:
        light["basicEventsData"][0]["t"] = bad
    with pytest.raises(ValueError, match=r"basicEventsData\.t"):
        native.lighting(light, 2)


def test_v3_native_basic_light_types_are_preserved_in_order_and_unmodified():
    events = [dict(b=i / 20, et=t, i=4, f=1) for i, t in enumerate([*range(14), 16, 17, 18, 19])]
    data = dict(version="3.2.0", colorNotes=[dict(b=0.25, x=1)], basicBeatmapEvents=events)
    before = copy.deepcopy(data)
    _, light = v3native.convert(data, audio(), 12)
    reconstructed = []
    for event in light["basicEvents"]:
        row = light["basicEventsData"][event.get("i", 0)]
        reconstructed.append(dict(b=event.get("b", 0), et=row["t"], i=row["i"], f=row["f"]))
    assert reconstructed == events
    assert data == before


def test_ordinary_v3_bundle_input_preserves_reviewed_basic_light_types(source, tmp_path):
    events = [dict(b=i / 20, et=t, i=4, f=1) for i, t in enumerate([*range(14), 16, 17, 18, 19])]
    for path in source.glob("*.dat"):
        if path.name == "Info.dat":
            continue
        data = json.loads(path.read_bytes())
        data["basicBeatmapEvents"] = events
        path.write_text(json.dumps(data))
    normalized = tmp_path / "extended-lights"
    imp.import_song(source, normalized)
    song = imp.prepare.load_song(normalized)
    assert not song["native_lights"]  # Exercise ordinary V3, not native V4.
    assert all(chart["basicBeatmapEvents"] == events for chart in song["maps"].values())


@pytest.mark.parametrize("bad", [-1, 14, 15, 20, 21, 40, 100, 1000, True, 16.0, "16", None, [], {}])
def test_ordinary_v3_bundle_input_refuses_nonlight_basic_types(source, tmp_path, bad):
    normalized = tmp_path / "normalized"
    imp.import_song(source, normalized)
    info = json.loads((normalized / "Info.dat").read_bytes())
    filename = info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"][0]["_beatmapFilename"]
    path = normalized / filename
    data = json.loads(path.read_bytes())
    data["basicBeatmapEvents"] = [dict(b=1, et=bad, i=4, f=1)]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="invalid basic event"):
        imp.prepare.load_song(normalized)
