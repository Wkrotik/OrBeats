"""Synthetic authored lighting/wire/managed ABI regressions; no console access."""

import copy
import gzip
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import additive_library as lib
import additive_lighting as lighting
from test_additive_companion import decoder, synthetic  # noqa: F401 -- pytest fixture

spec = importlib.util.spec_from_file_location("lighting_import", ROOT / "development/scripts/import_v3_additive.py")
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)


def chart():
    return {
        "version": "3.3.0",
        "colorNotes": [{"b": 2, "x": 1, "c": 1, "d": 3}],
        "colorBoostBeatmapEvents": [{"b": 2, "o": True}, {"b": 3}],
        "lightColorEventBoxGroups": [
            {
                "b": 1,
                "g": 2,
                "e": [
                    {
                        "f": {"f": 1, "p": 4, "n": 2, "s": 1090519040},
                        "w": 0.5,
                        "d": 2,
                        "r": 0.25,
                        "t": 1,
                        "i": 2,
                        "e": [{"b": 1, "c": 1, "s": 0.8, "i": 2}, {"c": -1}],
                    }
                ],
            }
        ],
        "lightRotationEventBoxGroups": [
            {"g": 3, "e": [{"a": 1, "s": -5, "t": 2, "d": 1, "w": 1, "l": [{"b": 0.5, "r": 90, "e": -1, "o": 2}]}]}
        ],
        "useNormalEventsAsCompatibleEvents": True,
    }


def test_constant_tempo_relative_distribution_and_native_zero_defaults():
    data = chart()
    data["bpmEvents"] = [{"m": 240}, {"b": 2, "m": 240}]
    before = copy.deepcopy(data)
    out = imp.convert_map(data, 120)
    assert data == before
    assert out["colorNotes"][0] == {"b": 1, "x": 1, "y": 0, "c": 1, "d": 3, "a": 0}
    assert out["colorBoostBeatmapEvents"] == [{"b": 1, "o": True}, {"b": 1.5, "o": False}]
    color = out["lightColorEventBoxGroups"][0]
    assert color["b"] == 0.5 and color["g"] == 2
    box = color["e"][0]
    assert box["w"] == 0.25 and box["r"] == 0.25 and box["f"] == before["lightColorEventBoxGroups"][0]["e"][0]["f"]
    assert box["e"][0]["b"] == 0.5 and box["e"][1]["b"] == 0
    assert out["lightRotationEventBoxGroups"][0]["e"][0]["l"][0]["b"] == 0.25
    assert lighting.lightshow(out)["useNormalEventsAsCompatibleEvents"] is True
    lighting.validate_boxes(out, 24)


def test_boost_piecewise_timing_but_distributed_boxes_still_refuse_real_bpm_changes():
    data = chart()
    data["bpmEvents"] = [{"m": 240}, {"b": 1, "m": 120}]
    with pytest.raises(ValueError, match="changing BPM"):
        imp.convert_map(data, 120)
    for key in lighting.BOX_KEYS:
        del data[key]
    out = imp.convert_map(data, 120)
    assert out["colorBoostBeatmapEvents"][0]["b"] == 1.5
    assert out["colorBoostBeatmapEvents"][1] == {"b": 2.5, "o": False}


@pytest.mark.parametrize(
    "case",
    [
        "group",
        "group-list",
        "box",
        "filter",
        "filter-extra",
        "seed-bool",
        "filter-type",
        "distribution",
        "axis",
        "ease-gap",
        "ease-bool",
        "event",
        "color",
        "brightness",
        "relative-negative",
        "relative-end",
        "nan",
        "events-list",
    ],
)
def test_malformed_boxes_fail_closed(case):
    data = chart()
    group = data["lightColorEventBoxGroups"][0]
    box = group["e"][0]
    event = box["e"][0]
    if case == "group":
        group["unknown"] = 0
    if case == "group-list":
        data["lightColorEventBoxGroups"] = {}
    if case == "box":
        box["unknown"] = 0
    if case == "filter":
        box["f"] = None
    if case == "filter-extra":
        box["f"]["unknown"] = 0
    if case == "seed-bool":
        box["f"]["s"] = True
    if case == "filter-type":
        box["f"]["f"] = 9
    if case == "distribution":
        box["d"] = 8
    if case == "axis":
        data["lightRotationEventBoxGroups"][0]["e"][0]["a"] = 4
    if case == "ease-gap":
        box["i"] = 99
    if case == "ease-bool":
        box["i"] = False
    if case == "event":
        event["customData"] = {"fake": 1}
    if case == "color":
        event["c"] = 3
    if case == "brightness":
        event["s"] = -1
    if case == "relative-negative":
        event["b"] = -1
    if case == "relative-end":
        event["b"] = 24
    if case == "nan":
        box["w"] = float("nan")
    if case == "events-list":
        box["e"] = None
    with pytest.raises(ValueError):
        lighting.validate_boxes(data, 24)


@pytest.mark.parametrize("value", [None, {}, [{"b": True}], [{"b": -1}], [{"b": 1, "o": 1}], [{"b": 1, "x": 1}]])
def test_boosts_are_bounded_boolean_events(value):
    with pytest.raises(ValueError):
        lighting.boosts(value, 24)


def test_library_v2_mixed_stock_roundtrip_and_native_reader(decoder):  # noqa: F811 -- pytest fixture
    songs = [synthetic(1)[0], synthetic(2)[0]]
    legacy = lib.encode(songs)
    assert legacy.startswith(b"BSDALIB1")
    songs[1]["environment"] = lighting.REVIEWED_ENVIRONMENT
    raw = lib.encode(songs)
    assert raw.startswith(b"BSDALIB2") and lib.encode(lib.decode(raw)) == raw
    assert "environment" not in lib.decode(raw)[0]
    assert lib.decode(raw)[1]["environment"] == lighting.REVIEWED_ENVIRONMENT
    assert "environment=WeaveEnvironment" in decoder(raw, True)
    for corrupt in [raw[:-1], raw + b"x", raw[:8] + bytes(12) + raw[20:]]:
        decoder(corrupt, False)
    # Repaired checksum is not permission to route an arbitrary environment.
    payload = raw[20:].replace(b"WeaveEnvironment", b"OtherEnvironment")
    corrupt = b"BSDALIB2" + struct.pack("<IQ", len(payload), lib.fnv(payload)) + payload
    with pytest.raises(ValueError):
        lib.decode(corrupt)
    decoder(corrupt, False)
    songs[1].pop("environment")
    assert lib.encode(songs) == legacy


@pytest.fixture
def source(tmp_path):
    folder = tmp_path / "source"
    imp.prepare.generate_probe(folder)
    info = json.loads((folder / "Info.dat").read_bytes())
    info["_environmentName"] = lighting.REVIEWED_ENVIRONMENT
    for diff in info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"]:
        (folder / diff["_beatmapFilename"]).write_text(json.dumps(chart()))
    (folder / "Info.dat").write_text(json.dumps(info))
    return folder


def test_full_bundle_preserves_difficulty_lighting_environment_and_corruption_refusal(source, tmp_path):
    pytest.importorskip("UnityPy")
    import UnityPy

    normal = tmp_path / "normalized"
    imp.import_song(source, normal)
    out = tmp_path / "prepared"
    song = imp.prepare.load_song(normal)
    manifest = imp.prepare.prepare(normal, ROOT / "custom_songs/quick_test.bundle", out)
    assert manifest["environment"] == lighting.REVIEWED_ENVIRONMENT
    imp.prepare.validate(out, song)
    bundle = out / manifest["bundle"]["file"]
    env = UnityPy.load(str(bundle))
    level = next(o.read_typetree() for o in env.objects if o.class_id == 114)
    ids = {e["_lightshowAsset"]["m_PathID"] for e in level["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"]}
    texts = [o for o in env.objects if o.class_id == 49 and o.path_id in ids]
    found = 0
    for obj in texts:
        tree = obj.read_typetree()
        if ".lightshow.gz" not in tree["m_Name"]:
            continue
        found += 1
        data = json.loads(gzip.decompress(tree["m_Script"].encode("utf-8", errors="surrogateescape")))
        assert len(data["colorBoostBeatmapEvents"]) == 2
        assert data["lightColorEventBoxGroups"][0]["g"] == 2
        assert data["useNormalEventsAsCompatibleEvents"] is True
    assert found == 5
    altered = json.loads((out / "manifest.json").read_bytes())
    altered.pop("environment")
    (out / "manifest.json").write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="environment"):
        imp.prepare.validate(out, song)
    (out / "manifest.json").write_text(json.dumps(manifest))
    # Mutate only the serialized lightshow; update SHA so actual readback catches it.
    obj = next(o for o in texts if ".lightshow.gz" in o.read_typetree()["m_Name"])
    tree = obj.read_typetree()
    data = json.loads(gzip.decompress(tree["m_Script"].encode("utf-8", errors="surrogateescape")))
    data["lightColorEventBoxGroups"][0]["g"] = 5
    tree["m_Script"] = gzip.compress(json.dumps(data).encode(), mtime=0).decode("utf-8", errors="surrogateescape")
    obj.save_typetree(tree)
    b = next(iter(env.files.values())).save()
    bundle.write_bytes(b)
    manifest["bundle"].update(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="lightshow"):
        imp.prepare.validate(out, song)


@pytest.mark.parametrize("mode", ["unreviewed", "bad-index", "index-routing"])
def test_environment_routing_is_explicit(source, tmp_path, mode):
    info_path = source / "Info.dat"
    info = json.loads(info_path.read_bytes())
    if mode == "unreviewed":
        info["_environmentName"] = "InventedEnvironment"
    if mode == "bad-index":
        info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"][0]["_environmentNameIdx"] = 3
    if mode == "index-routing":
        info["_environmentName"] = "InventedEnvironment"
        info["_environmentNames"] = [lighting.REVIEWED_ENVIRONMENT]
        for d in info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"]:
            d["_environmentNameIdx"] = 0
    info_path.write_text(json.dumps(info))
    if mode == "index-routing":
        imp.import_song(source, tmp_path / "normal")
        assert imp.prepare.load_song(tmp_path / "normal")["environment"] == lighting.REVIEWED_ENVIRONMENT
    else:
        with pytest.raises(ValueError, match="environment"):
            imp.import_song(source, tmp_path / "normal")


@pytest.mark.parametrize("format2", [False, True])
def test_normal_installer_requires_capability_then_preserves_legacy_entries(source, tmp_path, monkeypatch, format2):
    import additive_companion as app
    from PIL import Image
    from test_additive_companion import StrictFTP

    info = json.loads((source / "Info.dat").read_bytes())
    info.update(_coverImageFilename="cover.png", _previewStartTime=1, _previewDuration=1)
    (source / "Info.dat").write_text(json.dumps(info))
    Image.new("RGB", (32, 32), "green").save(source / "cover.png")
    stock, files = synthetic(5)
    blob = (ROOT / "custom_songs/quick_test.bundle").read_bytes()
    stock.update(bytes=len(blob), fnv=lib.fnv(blob), sha256=hashlib.sha256(blob).hexdigest())
    files[lib.paths(stock)[0]] = blob
    original = lib.encode([stock])
    files[lib.BASE + "/library.bin"] = original
    plugin = b"ELF fixture"
    files["/data/GoldHEN/plugins/orbeats.prx"] = plugin
    cap = {"schema": 1, "title": "CUSA12878", "max_songs": 64, "active_elf_sha256": hashlib.sha256(plugin).hexdigest()}
    if format2:
        cap["library_format"] = 2
    files[lib.BASE + "/companion-protocol.json"] = json.dumps(cap).encode()
    files["/data/GoldHEN/AFR/CUSA12878/features.json"] = json.dumps(
        {"enable_plugin": True, "enable_additive_song_packs": True}
    ).encode()
    ftp = StrictFTP(files)
    monkeypatch.setattr(app, "FTP", lambda: ftp)
    cfg = {"title": {"id": "CUSA12878"}, "ps4": {"ip": "fake"}}
    if not format2:
        with pytest.raises(ValueError, match="environment-aware plugin"):
            app.install(cfg, song_dir=str(source), report_dir=tmp_path / "reports")
        assert ftp.files[lib.BASE + "/library.bin"] == original
        assert not ftp.writes
    else:
        result = app.install(cfg, song_dir=str(source), report_dir=tmp_path / "reports")
        assert result["ok"] and result["count"] == 2
        raw = ftp.files[lib.BASE + "/library.bin"]
        assert raw.startswith(b"BSDALIB2")
        songs = lib.decode(raw)
        assert lib.encode([songs[0]]) == original
        assert songs[1]["environment"] == lighting.REVIEWED_ENVIRONMENT
        again = app.install(cfg, song_dir=str(source), report_dir=tmp_path / "reports")
        assert again["already_present"] and ftp.files[lib.BASE + "/library.bin"] == raw
    assert lib.BASE + "/.install-lock" not in ftp.directories


def test_conflicting_difficulty_environment_is_not_silently_collapsed(source, tmp_path):
    path = source / "Info.dat"
    info = json.loads(path.read_bytes())
    info["_environmentNames"] = ["DefaultEnvironment"]
    diff = info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"][0]
    diff["_environmentNameIdx"] = 0
    chart_path = source / diff["_beatmapFilename"]
    data = chart()
    for key in lighting.BOX_KEYS:
        data.pop(key)
    chart_path.write_text(json.dumps(data))
    path.write_text(json.dumps(info))
    with pytest.raises(ValueError, match="mixed per-difficulty environments"):
        imp.import_song(source, tmp_path / "normal")
