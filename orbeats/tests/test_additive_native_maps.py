"""Native-map schemas and real UnityFS readback; no network/PS4 writes."""

import copy
import gzip
import json
from pathlib import Path

import additive_companion as app
import additive_v3_native as v3native
import additive_v4_native as native
import pytest
from test_additive_companion import decoder as native_decoder
from test_additive_v4_import import audio, chart, source

decoder = native_decoder

v4 = app.helper("import_v4_additive.py")
v3 = app.helper("import_v3_additive.py")
prepare = app.helper("prepare_additive_bundle.py")
ROOT = Path(__file__).resolve().parents[1]


def advanced():
    data = chart()
    data.update(
        arcs=[dict(hb=0.25, tb=1, hi=1, ti=1)],
        arcsData=[dict(m=1, tm=1)],
        chains=[dict(hb=0.25, tb=1, i=1)],
        chainsData=[dict(tx=2, ty=1, c=4, s=1)],
        njsEvents=[dict(b=0), dict(b=1, i=1)],
        njsEventData=[dict(d=2), dict(d=4, e=4)],
    )
    return data


def lights():
    result = dict(
        version="4.0.0",
        basicEvents=[dict(b=0.25)],
        basicEventsData=[dict(t=1, i=3, f=1)],
        colorBoostEvents=[dict(b=1)],
        colorBoostEventsData=[dict(b=1)],
        indexFilters=[dict(f=1, p=1)],
        eventBoxGroups=[],
    )
    for k, kind in enumerate(("Color", "Rotation", "Translation", "Fx"), 1):
        prefix = "fx" if kind == "Fx" else "light" + kind
        events = "floatFxEvents" if kind == "Fx" else "light" + kind + "Events"
        result[prefix + "EventBoxes"] = [dict(w=0.5, d=1)]
        result[events] = [dict(p=0, e=0)]
        result["eventBoxGroups"].append(dict(b=0.25, g=k, t=k, e=[dict(f=0, e=0, l=[dict(b=0.5)])]))
    return result


def test_native_chart_arcs_chains_njs_and_lights_validate_without_mutation():
    data, light = advanced(), lights()
    before = copy.deepcopy((data, light))
    assert native.chart(data, native.audio(audio()), 12) == 5
    assert native.lighting(light, 2)
    assert (data, light) == before


@pytest.mark.parametrize(
    "table,indexkey",
    [("arcs", "hi"), ("arcs", "ti"), ("arcs", "ai"), ("chains", "i"), ("chains", "ci"), ("njsEvents", "i")],
)
@pytest.mark.parametrize("bad", [-1, True, 0.5, 999, "0"])
def test_native_chart_references_are_checked(table, indexkey, bad):
    data = advanced()
    data[table][0][indexkey] = bad
    with pytest.raises(ValueError):
        native.chart(data, 2, 12)


@pytest.mark.parametrize("mutation", ["unknown", "ease", "beat", "group", "box", "filter", "event", "unused"])
def test_native_lighting_fails_closed(mutation):
    light = lights()
    if mutation == "unknown":
        light["eventBoxGroups"][0]["magic"] = 3
    if mutation == "ease":
        light["floatFxEvents"][0]["e"] = 50
    if mutation == "beat":
        light["eventBoxGroups"][0]["e"][0]["l"][0]["b"] = 3
    if mutation == "group":
        light["eventBoxGroups"][0]["g"] = 1024
    if mutation == "box":
        light["eventBoxGroups"][0]["e"][0]["e"] = 4
    if mutation == "filter":
        light["eventBoxGroups"][0]["e"][0]["f"] = 4
    if mutation == "event":
        light["eventBoxGroups"][0]["e"][0]["l"][0]["i"] = 4
    if mutation == "unused":
        light["floatFxEvents"].append(dict(e=50))
    with pytest.raises(ValueError):
        native.lighting(light, 2)


def test_audio_regions_resample_exact_boundaries_and_lufs():
    data = audio()
    data["bpmData"] = [dict(si=0, ei=44100, sb=0, eb=1), dict(si=44100, ei=88200, sb=1, eb=3)]
    data["lufsData"] = [dict(si=0, ei=88200, l=-12)]
    result = native.resample_audio(data, 48000, 96000, "x")
    assert result["bpmData"] == [dict(si=0, ei=48000, sb=0, eb=1), dict(si=48000, ei=96000, sb=1, eb=3)]
    assert result["lufsData"] == [dict(si=0, ei=96000, l=-12)]
    with pytest.raises(ValueError, match="duration"):
        native.resample_audio(data, 48000, 96002, "x")


def test_native_import_and_complete_bundle_preserve_payloads(tmp_path):
    root, info = source(tmp_path)
    info["environmentNames"] = ["EDMEnvironment"]
    (root / "Info.dat").write_text(json.dumps(info))
    data, show = advanced(), lights()
    # Synthetic equivalents of Gaga's additional basic lighting channels must
    # survive real UnityFS/gzip readback, not merely pass a numeric range check.
    for event_type in (16, 17, 18, 19):
        show["basicEvents"].append(dict(b=0.5, i=len(show["basicEventsData"])))
        show["basicEventsData"].append(dict(t=event_type, i=4, f=1))
    (root / "ExpertPlus.dat").write_text(json.dumps(data))
    (root / "Lightshow.dat").write_text(json.dumps(show))
    normalized, converted = tmp_path / "v4", tmp_path / "v3"
    v4.normalize(root, normalized, prepare.local_file)
    report = v3.import_song(normalized, converted)
    song = prepare.load_song(converted)
    assert report["note_counts"] == {"ExpertPlus": 5}
    assert song["maps"]["ExpertPlus"] == data and song["native_lights"]["ExpertPlus"] == show
    assert song["environment"] == "EDMEnvironment"
    template = ROOT / "custom_songs/quick_test.bundle"
    if not template.exists():
        pytest.skip("legal local Unity template absent")
    output = tmp_path / "bundle"
    manifest = prepare.prepare(converted, template, output)
    prepare.validate(output, song)
    assert manifest["native_v4"] and manifest["note_counts"] == {"ExpertPlus": 5}
    import UnityPy

    env = UnityPy.load(str(output / manifest["bundle"]["file"]))
    objects = {o.path_id: o for o in env.objects}
    tree = next(o.read_typetree() for o in env.objects if o.class_id == 114)
    entry = tree["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"][0]

    def reopen(key):
        return json.loads(
            gzip.decompress(
                objects[entry[key]["m_PathID"]].read_typetree()["m_Script"].encode("utf8", errors="surrogateescape")
            )
        )

    assert reopen("_beatmapAsset") == data
    assert reopen("_lightshowAsset") == show


def test_v3_native_conversion_keeps_tempo_distributions_and_chains():
    tempo = v3.Tempo(60, [dict(b=1, m=120)])
    audio_data = v3native.audio_from_tempo(tempo, 88200)
    data = dict(
        version="3.3.0",
        colorNotes=[dict(b=0.25, x=1)],
        burstSliders=[dict(b=0.25, tb=1.5, c=0, x=1, y=0, d=1, tx=2, ty=1, sc=4, s=1)],
        lightTranslationEventBoxGroups=[
            dict(b=0.25, g=2, e=[dict(f=dict(f=1, p=1), w=1, d=1, s=2, t=1, l=[dict(b=1, t=2)])])
        ],
    )
    chart_data, light_data = v3native.convert(data, audio_data, 12)
    assert native.chart(chart_data, 3, 12) == 4
    assert audio_data["bpmData"] == [dict(si=0, ei=44100, sb=0, eb=1), dict(si=44100, ei=88200, sb=1, eb=3)]
    assert light_data["eventBoxGroups"][0]["b"] == 0.25
    assert light_data["lightTranslationEventBoxes"][0]["w"] == 1
    assert light_data["eventBoxGroups"][0]["e"][0]["l"][0]["b"] == 1


def test_separate_v4_preview_uses_its_own_audio_at_zero(tmp_path):
    import wave

    root, info = source(tmp_path)
    info["songPreviewFilename"] = "preview.wav"
    with wave.open(str(root / "preview.wav"), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\x01\x00" * 44100 * 2)
    (root / "Info.dat").write_text(json.dumps(info))
    normalized = tmp_path / "normalized"
    v4.normalize(root, normalized, prepare.local_file)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(dict(level_id="bsd_additive_" + "a" * 24, song_name="Synthetic", duration_seconds=2))
    )
    result = app.helper("prepare_additive_media.py").prepare(normalized, manifest, tmp_path / "media")
    assert result["preview_start_seconds"] == 0 and result["preview_duration_seconds"] == 1
    with wave.open(str(tmp_path / "media/preview.wav")) as f:
        assert f.readframes(44100) == b"\x01\x00" * 44100 * 2


def test_v3_native_route_applies_to_every_difficulty_with_shared_bpm(tmp_path):
    root, info = source(tmp_path)
    native_source = dict(
        version="3.3.0",
        bpmEvents=[dict(b=1, m=120)],
        colorNotes=[dict(b=0.25, x=1)],
        burstSliders=[dict(b=0.25, tb=1.5, x=1, tx=2, sc=4, s=1)],
    )
    info2 = dict(
        _version="2.1.0",
        _songName="Synthetic",
        _songAuthorName="Fixture",
        _beatsPerMinute=60,
        _songFilename="song.wav",
        _difficultyBeatmapSets=[
            dict(
                _beatmapCharacteristicName="Standard",
                _difficultyBeatmaps=[
                    dict(
                        _difficulty="ExpertPlus",
                        _difficultyRank=9,
                        _beatmapFilename="ExpertPlus.dat",
                        _noteJumpMovementSpeed=12,
                    ),
                    dict(_difficulty="Easy", _difficultyRank=1, _beatmapFilename="Easy.dat", _noteJumpMovementSpeed=10),
                ],
            )
        ],
    )
    (root / "Info.dat").write_text(json.dumps(info2))
    (root / "ExpertPlus.dat").write_text(json.dumps(native_source))
    (root / "Easy.dat").write_text(json.dumps({k: v for k, v in native_source.items() if k != "burstSliders"}))
    output = tmp_path / "converted"
    v3.import_song(root, output)
    song = prepare.load_song(output)
    assert all(m["version"] == "4.1.0" for m in song["maps"].values())
    assert song["audio_data"]["bpmData"][-1]["eb"] == 3
    assert song["maps"]["Easy"]["colorNotes"][0]["b"] == 0.25


def test_authored_presentation_survives_both_normalizers_and_bundle(tmp_path):
    root, info = source(tmp_path)
    info["audio"]["lufs"] = -11
    info["colorSchemes"] = [
        dict(
            colorSchemeName="Authored",
            overrideNotes=True,
            overrideLights=True,
            saberAColor=dict(r=1, g=0, b=0),
            environmentColor0=dict(r=0, g=1, b=0),
        )
    ]
    (root / "Info.dat").write_text(json.dumps(info))
    v4.normalize(root, tmp_path / "v4", prepare.local_file)
    v3.import_song(tmp_path / "v4", tmp_path / "v3")
    song = prepare.load_song(tmp_path / "v3")
    profile = song["presentation"]
    assert profile["lufs"] == -11 and profile["offset"] == 0
    assert profile["colors"][4] == dict(saberAColor=[1, 0, 0, 1], environmentColor0=[0, 1, 0, 1])
    assert not any(profile["colors"][:4])
    template = ROOT / "custom_songs/quick_test.bundle"
    if not template.exists():
        pytest.skip("legal local Unity template absent")
    manifest = prepare.prepare(tmp_path / "v3", template, tmp_path / "bundle")
    assert manifest["presentation"] == profile
    prepare.validate(tmp_path / "bundle", song)


def test_library_v3_presentation_is_native_decodable_and_legacy_reencodes(decoder):  # noqa: F811
    import additive_library as lib
    from test_additive_lighting import synthetic

    songs, _ = zip(synthetic(2), synthetic(3))
    songs = [dict(s) for s in songs]
    legacy = lib.encode(songs)
    profile = dict(lufs=-11, offset=0.125, colors=[{}, {}, {}, {}, dict(saberAColor=[1, 0, 0, 1])])
    songs[1]["presentation"] = profile
    blob = lib.encode(songs)
    assert blob.startswith(b"BSDALIB3")
    parsed = lib.decode(blob)
    assert parsed[1]["presentation"] == profile and "presentation" not in parsed[0]
    assert lib.encode(parsed) == blob
    decoder(blob, True)
    parsed[1].pop("presentation")
    assert lib.encode(parsed) == legacy


@pytest.mark.parametrize(
    "bad",
    [
        dict(lufs=float("nan"), offset=0, colors=[{}] * 5),
        dict(lufs=-14, offset=11, colors=[{}] * 5),
        dict(lufs=-14, offset=0, colors=[dict(saberAColor=[True, 0, 0, 1])] * 5),
    ],
)
def test_presentation_refuses_invalid_values(bad):
    from additive_presentation import validate

    with pytest.raises(ValueError):
        validate(bad)


@pytest.mark.parametrize("modes", [("Standard", "OneSaber", "NoArrows"), ("OneSaber",), ("90Degree", "360Degree")])
def test_multiple_characteristics_route_independent_maps_and_wire(tmp_path, decoder, modes):
    import additive_library as lib
    from test_additive_lighting import synthetic

    root, info = source(tmp_path)
    template_diff = copy.deepcopy(info["difficultyBeatmaps"][0])
    info["difficultyBeatmaps"] = [dict(template_diff, characteristic=k) for k in modes]
    (root / "Info.dat").write_text(json.dumps(info))
    normalized, converted = tmp_path / "modes-v4", tmp_path / "modes-v3"
    v4.normalize(root, normalized, prepare.local_file)
    v3.import_song(normalized, converted)
    song = prepare.load_song(converted)
    expected = {("ExpertPlus" if k == "Standard" else k + "/ExpertPlus") for k in modes}
    assert set(song["maps"]) == expected
    template = ROOT / "custom_songs/quick_test.bundle"
    if not template.exists():
        pytest.skip("legal template unavailable")
    output = tmp_path / "bundle"
    manifest = prepare.prepare(converted, template, output)
    prepare.validate(output, song)
    assert set(manifest["difficulty_stats"]) == expected
    bundle = (output / manifest["bundle"]["file"]).read_bytes()
    descriptor = lib.descriptor(manifest, bundle, b"c" * 128, b"p" * 128, 1)
    raw = lib.encode([descriptor])
    assert raw[:8] == b"BSDALIB4"
    decoded = lib.decode(raw)[0]
    assert decoded["mask"] == (16 if "Standard" in modes else 0)
    assert set(decoded["modes"]) == set(modes) - {"Standard"}
    assert all(v["mask"] == 16 for v in decoded["modes"].values())
    decoder(raw, True)
    legacy, _ = synthetic(17)
    assert lib.encode([lib.decode(lib.encode([legacy, descriptor]))[0]]) == lib.encode([legacy])


@pytest.mark.parametrize("legacy", [False, True])
def test_v3_360_rotation_events_stay_native_and_beat_domain(tmp_path, legacy):
    root, _ = source(tmp_path)
    info = {
        "_version": "2.1.0",
        "_songName": "Rotation",
        "_songAuthorName": "Tester",
        "_beatsPerMinute": 60,
        "_songFilename": "song.wav",
        "_coverImageFilename": "cover.png",
        "_previewStartTime": 0,
        "_previewDuration": 1,
        "_difficultyBeatmapSets": [
            {
                "_beatmapCharacteristicName": "360Degree",
                "_difficultyBeatmaps": [
                    {
                        "_difficulty": "ExpertPlus",
                        "_difficultyRank": 9,
                        "_beatmapFilename": "ExpertPlus.dat",
                        "_noteJumpMovementSpeed": 12,
                    }
                ],
            }
        ],
    }
    raw = dict(
        version="3.3.0",
        colorNotes=[dict(b=0.25, x=1, y=0, c=0, d=1), dict(b=2, x=2, y=1, c=1, d=0)],
        bpmEvents=[dict(b=1, m=120)],
        rotationEvents=[dict(b=0.5, e=0, r=15), dict(b=0.5, e=1, r=-30)],
    )
    original = raw
    if legacy:
        original = {
            "_version": "2.0.0",
            "_notes": [{"_time": 0.25, "_lineIndex": 1, "_lineLayer": 0, "_type": 0, "_cutDirection": 1}],
            "_events": [{"_time": 0.5, "_type": 14, "_value": 4}, {"_time": 0.5, "_type": 15, "_value": 2}],
        }
        raw = app.helper("import_v2_additive.py").convert_map(original, allow_rotations=True)
    (root / "Info.dat").write_text(json.dumps(info))
    (root / "ExpertPlus.dat").write_text(json.dumps(original))
    converted = tmp_path / "native-rotation"
    v3.import_song(root, converted)
    song = prepare.load_song(converted)
    assert song["maps"]["360Degree/ExpertPlus"] == {**raw, "basicEventTypesWithKeywords": {"d": []}}
    assert song["audio_data"]["bpmData"][-1]["eb"] == (2 if legacy else 3)
    template = ROOT / "custom_songs/quick_test.bundle"
    if not template.exists():
        pytest.skip("legal template unavailable")
    out = tmp_path / "rotation-bundle"
    manifest = prepare.prepare(converted, template, out)
    prepare.validate(out, song)
    assert manifest["native_v3"] == ["360Degree/ExpertPlus"]
    assert manifest["characteristics"] == ["360Degree"]


@pytest.mark.parametrize("feature", ["modes", "native", "presentation"])
def test_native_capability_gate_and_no_legacy_publication(tmp_path, monkeypatch, feature):
    import hashlib

    import additive_library as lib
    from test_additive_companion import StrictFTP
    from test_additive_lighting import synthetic

    root, info = source(tmp_path)
    if feature == "modes":
        info["difficultyBeatmaps"][0]["characteristic"] = "OneSaber"
    elif feature == "native":
        data = chart()
        data.update(njsEvents=[{"b": 0.5, "i": 0}], njsEventData=[{"d": 1}])
        (root / info["difficultyBeatmaps"][0]["beatmapDataFilename"]).write_text(json.dumps(data))
    else:
        info["audio"]["lufs"] = -10
    (root / "Info.dat").write_text(json.dumps(info))
    # Cover schema fixture expects a valid PNG for complete preparation.
    from PIL import Image

    Image.new("RGB", (32, 32), "blue").save(root / "cover.png")
    stock, files = synthetic(31)
    blob = (ROOT / "custom_songs/quick_test.bundle").read_bytes()
    stock.update(bytes=len(blob), fnv=lib.fnv(blob), sha256=hashlib.sha256(blob).hexdigest())
    files[lib.paths(stock)[0]] = blob
    original = lib.encode([stock])
    files[lib.BASE + "/library.bin"] = original
    plugin = b"ELF fixture"
    files["/data/GoldHEN/plugins/orbeats.prx"] = plugin
    cap = {
        "schema": 1,
        "title": "CUSA12878",
        "max_songs": 64,
        "library_format": 3,
        "native_maps": 1,
        "active_elf_sha256": hashlib.sha256(plugin).hexdigest(),
    }
    if feature == "native":
        cap["library_format"] = 4
        cap["native_maps"] = 0
    if feature == "presentation":
        cap["library_format"] = 2
    files[lib.BASE + "/companion-protocol.json"] = json.dumps(cap).encode()
    files["/data/GoldHEN/AFR/CUSA12878/features.json"] = json.dumps(
        {"enable_plugin": True, "enable_additive_song_packs": True}
    ).encode()
    ftp = StrictFTP(files)
    monkeypatch.setattr(app, "FTP", lambda: ftp)
    cfg = {"title": {"id": "CUSA12878"}, "ps4": {"ip": "fake"}}
    with pytest.raises(
        ValueError,
        match={"modes": "native characteristics", "native": "native-map plugin", "presentation": "authored colors"}[
            feature
        ],
    ):
        app.install(cfg, song_dir=str(root), report_dir=tmp_path / "report")
    assert ftp.files[lib.BASE + "/library.bin"] == original and not ftp.writes


@pytest.mark.parametrize("kind", [0, 1, 2])
def test_v3_native_fx_types_and_missing_reference(kind):
    raw = {
        "version": "3.3.0",
        "colorNotes": [dict(b=0.25, x=1, y=0, c=0, d=1)],
        "vfxEventBoxGroups": [{"b": 0.5, "g": 1, "t": kind, "e": [{"l": [0]}]}],
        "_fxEventsCollection": {"_il": [{"b": 0.25, "p": 0, "v": 1}], "_fl": [{"b": 0.25, "p": 0, "v": 0.8, "i": 0}]},
    }
    a = audio()
    assert v3native.validate_preserved(raw, a, 12) == (1, True)
    assert v3native.lightshow_preserved(raw)["vfxEventBoxGroups"] == raw["vfxEventBoxGroups"]
    bad = copy.deepcopy(raw)
    bad["vfxEventBoxGroups"][0]["e"][0]["l"] = [1]
    with pytest.raises(ValueError, match="index"):
        v3native.validate_preserved(bad, a, 12)
    if kind == 2:
        raw["_fxEventsCollection"]["_il"][0]["v"] = 2
        with pytest.raises(ValueError, match="boolean"):
            v3native.validate_preserved(raw, a, 12)


def test_future_native_chart_version_refused():
    data = chart()
    data["version"] = "4.9.0"
    with pytest.raises(ValueError, match="version"):
        native.chart(data, 2, 12)


@pytest.mark.parametrize("execution", [14, 15])
@pytest.mark.parametrize("value,degrees", list(enumerate([-60, -45, -30, -15, 15, 30, 45, 60])))
def test_legacy_rotation_enum_mapping_requires_explicit_mode(execution, value, degrees):
    convert = app.helper("import_v2_additive.py").convert_map
    raw = {"_version": "2.0.0", "_events": [{"_time": 1, "_type": execution, "_value": value}]}
    with pytest.raises(ValueError, match="rotation"):
        convert(raw)
    assert convert(raw, allow_rotations=True)["rotationEvents"] == [{"b": 1, "e": execution - 14, "r": degrees}]


def test_all_twenty_five_characteristic_difficulty_routes(tmp_path, decoder):
    prep = app.helper("prepare_additive_bundle.py")
    import copy

    from additive_modes import DIFFS
    from additive_modes import MODES as NAMES
    from PIL import Image

    root, info = source(tmp_path)
    original = info["difficultyBeatmaps"][0]
    info["difficultyBeatmaps"] = []
    for mode in NAMES:
        for difficulty in DIFFS:
            row = copy.deepcopy(original)
            row.update(characteristic=mode, difficulty=difficulty)
            info["difficultyBeatmaps"].append(row)
    (root / "Info.dat").write_text(json.dumps(info))
    Image.new("RGB", (32, 32)).save(root / "cover.png")
    normalized = tmp_path / "normalized-all"
    v4.normalize(root, tmp_path / "v4-all", prep.local_file)
    v3.import_song(tmp_path / "v4-all", normalized)
    song = prep.load_song(normalized)
    assert len(song["maps"]) == 25
    target = tmp_path / "prepared-all"
    manifest = prep.prepare(normalized, ROOT / "custom_songs/quick_test.bundle", target)
    assert prep.validate(target, song) == manifest
    assert set(manifest["characteristics"]) == set(NAMES)
    assert len(manifest["difficulties"]) == 25

    import additive_library as lib

    descriptor = lib.descriptor(manifest, (target / manifest["bundle"]["file"]).read_bytes(), b"c" * 128, b"p" * 128, 1)
    raw = lib.encode([descriptor])
    decoded = lib.decode(raw)[0]
    assert decoded["mask"] == 31 and all(decoded["modes"][mode]["mask"] == 31 for mode in NAMES[1:])
    decoder(raw, True)


def test_v4_difficulty_palette_is_preserved_over_scheme_through_bundle_and_wire(tmp_path, decoder):
    import additive_library as lib
    from additive_presentation import COLORS, LEGACY, color

    root, info = source(tmp_path)
    info["environmentNames"] = ["WeaveEnvironment"]
    # All nine known fields, including alpha; per-difficulty values override the scheme.
    custom = {key[1:]: dict(r=(i + 1) / 10, g=0.2, b=0.3, a=0.9) for i, key in enumerate(LEGACY)}
    custom["difficultyLabel"] = "Authored label"
    info["difficultyBeatmaps"][0]["customData"] = custom
    info["colorSchemes"] = [dict(overrideNotes=True, saberAColor=dict(r=0, g=1, b=0))]
    (root / "Info.dat").write_text(json.dumps(info))
    before = copy.deepcopy(info)
    nativechart = advanced()
    (root / "ExpertPlus.dat").write_text(json.dumps(nativechart))
    show = lights()
    (root / "Lightshow.dat").write_text(json.dumps(show))
    normalized = v4.normalize(root, tmp_path / "v4", prepare.local_file)
    assert json.loads((root / "Info.dat").read_text()) == before
    mapped = normalized["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"][0]["_customData"]
    assert mapped["_difficultyLabel"] == "Authored label"
    assert all(mapped[old] == custom[old[1:]] for old in LEGACY)
    v3.import_song(tmp_path / "v4", tmp_path / "v3")
    song = prepare.load_song(tmp_path / "v3")
    expected = {key: color(custom[old[1:]]) for old, key in zip(LEGACY, COLORS)}
    assert song["presentation"]["colors"] == [{}, {}, {}, {}, expected]
    assert song["maps"]["ExpertPlus"] == nativechart and song["native_lights"]["ExpertPlus"] == show
    template = ROOT / "custom_songs/quick_test.bundle"
    if not template.exists():
        pytest.skip("legal local Unity template absent")
    manifest = prepare.prepare(tmp_path / "v3", template, tmp_path / "bundle")
    assert prepare.validate(tmp_path / "bundle", song) == manifest
    assert manifest["presentation"]["colors"][4] == expected
    entry = lib.descriptor(
        manifest, (tmp_path / "bundle" / manifest["bundle"]["file"]).read_bytes(), b"c" * 128, b"p" * 128, 1
    )
    raw = lib.encode([entry])
    decoded = lib.decode(raw)[0]
    for field, rgba in expected.items():
        assert decoded["presentation"]["colors"][4][field] == pytest.approx(rgba)
    decoder(raw, True)


@pytest.mark.parametrize(
    "custom",
    [
        None,
        [],
        "colors",
        {"requirements": ["Chroma"]},
        {"suggestions": ["Noodle Extensions"]},
        {"colorLeft": dict(r=0.2, g=0.3, b=0.4), "arbitrary": True},
        {"colorLeft": dict(r=True, g=0, b=0)},
        {"colorLeft": dict(r=2, g=0, b=0)},
        {"colorLeft": dict(r=float("nan"), g=0, b=0)},
        {"colorLeft": dict(r=0, g=0)},
        {"colorLeft": dict(r=0, g=0, b=0, a=-1)},
        {"difficultyLabel": 5},
        {"difficultyLabel": "x" * 201},
    ],
)
def test_v4_difficulty_custom_metadata_fails_closed(tmp_path, custom):
    root, info = source(tmp_path)
    info["difficultyBeatmaps"][0]["customData"] = custom
    (root / "Info.dat").write_text(json.dumps(info))
    before = (root / "Info.dat").read_bytes()
    with pytest.raises(ValueError, match="metadata|color|scalar|label"):
        v4.normalize(root, tmp_path / "bad", prepare.local_file)
    assert (root / "Info.dat").read_bytes() == before


def test_arc_color_comes_from_head_not_unused_tail_metadata_color():
    data = advanced()
    arc = data["arcs"][0]
    head = data["colorNotesData"][arc.get("hi", 0)]
    tail = dict(head, c=1 - head.get("c", 0), x=3)
    data["colorNotesData"].append(tail)
    arc["ti"] = len(data["colorNotesData"]) - 1
    before = copy.deepcopy(data)
    assert native.chart(data, 2, 12) == 5
    assert data == before
    arc["ti"] = len(data["colorNotesData"])
    with pytest.raises(ValueError, match="arc tail index"):
        native.chart(data, 2, 12)


@pytest.mark.parametrize("difference,accepted", [(-2, False), (-1, True), (0, True), (1, True), (2, False)])
def test_native_audio_sample_tolerance_is_exact_at_boundary(difference, accepted):
    data = dict(
        version="4.0.0",
        songSampleCount=6868222,
        songFrequency=44100,
        bpmData=[dict(si=0, ei=6868222, sb=0, eb=360.802277)],
        lufsData=[],
    )
    assert native.audio_duration_matches(data, 44100, 6868222 + difference) is accepted
    if accepted:
        value = native.resample_audio(data, 44100, 6868222 + difference, "test")
        assert value["bpmData"][0]["ei"] == 6868222 + difference
    else:
        with pytest.raises(ValueError, match="durations disagree"):
            native.resample_audio(data, 44100, 6868222 + difference, "test")


def test_zero_duration_chains_keep_slice_count_geometry_and_exact_timing():
    data = advanced(); data['chains'][0]['tb'] = data['chains'][0]['hb']
    before = copy.deepcopy(data)
    assert native.chart(data, 2, 12) == 5
    assert data == before
    data['chains'][0]['tb'] = data['chains'][0]['hb'] - 0.001
    with pytest.raises(ValueError, match='chains tail'): native.chart(data, 2, 12)
    data = advanced(); data['arcs'][0]['tb'] = data['arcs'][0]['hb']
    with pytest.raises(ValueError, match='arcs tail'): native.chart(data, 2, 12)


def test_zero_duration_v3_chains_convert_losslessly_without_epsilon_or_dropped_slices():
    data = {'version': '3.3.0', 'colorNotes': [{'b': 1, 'x': 1, 'y': 0, 'c': 0, 'd': 1}],
            'burstSliders': [{'b': 1, 'tb': 1, 'c': 0, 'x': 1, 'y': 0, 'd': 1,
                              'tx': 1, 'ty': 1, 'sc': 5, 's': 1}]}
    before = copy.deepcopy(data)
    out, _ = v3native.convert(data, audio(), 12)
    assert out['chains'][0]['hb'] == out['chains'][0]['tb'] == 1
    assert out['chainsData'][0] == dict(tx=1, ty=1, c=5, s=1)
    assert native.chart(out, 2, 12) == 5 and data == before
