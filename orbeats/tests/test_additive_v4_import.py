"""Synthetic V4 schemas; no game inputs, source songs, network or console writes."""

import hashlib
import io
import json
import wave
import zipfile

import additive_companion as app
import pytest
from PIL import Image

v4 = app.helper("import_v4_additive.py")
prepare = app.helper("prepare_additive_bundle.py")


def empty_lights():
    return {"version": "4.0.0", "basicEvents": [], "basicEventTypesWithKeywords": {"d": []}}


def chart():
    return {
        "version": "4.1.0",
        "colorNotes": [{"b": 0.25, "i": 1}, {"b": 1}],
        "colorNotesData": [{"x": 2, "c": 1, "d": 3}, {"x": 1}],
        "bombNotes": [{"b": 0.5}],
        "bombNotesData": [{"x": 3, "y": 2}],
        "obstacles": [{"b": 0.75}],
        "obstaclesData": [{"x": 0, "d": 0.25, "w": 1, "h": 5}],
    }


def audio():
    return {
        "version": "4.0.0",
        "songSampleCount": 88200,
        "songFrequency": 44100,
        "bpmData": [{"si": 0, "ei": 88200, "sb": 0, "eb": 2}],
        "lufsData": [],
    }


def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    info = {
        "version": "4.0.1",
        "song": {"title": "Synthetic", "author": "Fixture"},
        "audio": {
            "songFilename": "song.wav",
            "audioDataFilename": "AudioData.dat",
            "bpm": 60,
            "previewStartTime": 0.5,
            "previewDuration": 1,
        },
        "coverImageFilename": "cover.png",
        "difficultyBeatmaps": [
            {
                "characteristic": "Standard",
                "difficulty": "ExpertPlus",
                "beatmapAuthors": {"mappers": ["Mapper"]},
                "beatmapDataFilename": "ExpertPlus.dat",
                "lightshowDataFilename": "Lightshow.dat",
                "noteJumpMovementSpeed": 12,
                "noteJumpStartBeatOffset": 0,
            }
        ],
        "customData": {"editors": {}},
    }
    for name, value in [
        ("Info.dat", info),
        ("AudioData.dat", audio()),
        ("ExpertPlus.dat", chart()),
        ("Lightshow.dat", empty_lights()),
    ]:
        (root / name).write_text(json.dumps(value))
    with wave.open(str(root / "song.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\0" * 88200 * 4)
    Image.new("RGB", (32, 32), "#1d305b").save(root / "cover.png")
    return root, info


def test_sparse_metadata_index_defaults_to_zero_not_event_position():
    out = v4.chart_to_v3(chart(), empty_lights(), [])
    assert out["colorNotes"] == [
        {"b": 0.25, "x": 1, "y": 0, "c": 0, "d": 0, "a": 0},
        {"b": 1, "x": 2, "y": 0, "c": 1, "d": 3, "a": 0},
    ]
    assert out["bombNotes"] == [{"b": 0.5, "x": 3, "y": 2}]
    assert out["obstacles"] == [{"b": 0.75, "x": 0, "y": 0, "d": 0.25, "w": 1, "h": 5}]
    assert chart()["colorNotes"][1] == {"b": 1}


@pytest.mark.parametrize("index", [-1, True, 0.5, 2, "0"])
def test_bad_metadata_indices_refused(index):
    raw = chart()
    raw["colorNotes"][0]["i"] = index
    with pytest.raises(ValueError, match="metadata index"):
        v4.chart_to_v3(raw, empty_lights(), [])


@pytest.mark.parametrize("field", ["arcs", "chains", "njsEvents", "rotationEvents"])
def test_unsupported_features_are_not_dropped(field):
    raw = chart()
    raw[field] = [{"b": 1}]
    with pytest.raises(ValueError, match=field):
        v4.chart_to_v3(raw, empty_lights(), [])


def test_rotating_objects_mod_data_and_authored_lights_refused():
    raw = chart()
    raw["colorNotes"][0]["r"] = 1
    with pytest.raises(ValueError, match="rotation"):
        v4.chart_to_v3(raw, empty_lights(), [])
    raw = chart()
    raw["colorNotesData"][0]["customData"] = {"coordinates": [5, 5]}
    with pytest.raises(ValueError, match="metadata"):
        v4.chart_to_v3(raw, empty_lights(), [])
    lights = empty_lights()
    lights["basicEvents"] = [{"b": 1}]
    with pytest.raises(ValueError, match="basicEvents"):
        v4.chart_to_v3(chart(), lights, [])


def test_sample_regions_preserve_seconds_through_existing_tempo():
    data = audio()
    data["bpmData"] = [{"si": 0, "ei": 44100, "sb": 0, "eb": 1}, {"si": 44100, "ei": 88200, "sb": 1, "eb": 3}]
    events = v4.tempo_events(data)
    assert events == [{"b": 0, "m": 60}, {"b": 1, "m": 120}]
    tempo = app.helper("import_v3_additive.py").Tempo(150, events)
    assert tempo.time(2) == pytest.approx(1.5)
    assert tempo.baked(2) * 60 / 150 == pytest.approx(1.5)


@pytest.mark.parametrize(
    "regions",
    [
        [],
        [{"si": 1, "ei": 88200, "sb": 0, "eb": 2}],
        [{"si": 0, "ei": 44100, "sb": 0, "eb": 1}],
        [{"si": 0, "ei": 44100, "sb": 0, "eb": 1}, {"si": 44100, "ei": 88200, "sb": 2, "eb": 3}],
    ],
)
def test_missing_or_discontinuous_sample_regions_refused(regions):
    data = audio()
    data["bpmData"] = regions
    with pytest.raises(ValueError):
        v4.tempo_events(data)


def test_source_metadata_and_actual_audio_media_conversion(tmp_path):
    root, info = source(tmp_path)
    converted = tmp_path / "v4"
    normalized = v4.normalize(root, converted, prepare.local_file)
    assert normalized["_songName"] == "Synthetic" and normalized["_levelAuthorName"] == "Mapper"
    assert normalized["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"][0]["_difficultyRank"] == 9
    assert json.loads((root / "Info.dat").read_text()) == info
    importer = app.helper("import_v3_additive.py")
    report = importer.import_song(converted, tmp_path / "prepared")
    assert report["note_counts"] == {"ExpertPlus": 2}
    assert report["duration_seconds"] == 2
    m = {"level_id": "bsd_additive_" + "a" * 24, "song_name": "Synthetic", "duration_seconds": 2}
    manifest = tmp_path / "level.json"
    manifest.write_text(json.dumps(m))
    media = app.helper("prepare_additive_media.py").prepare(converted, manifest, tmp_path / "media")
    assert media["preview_start_seconds"] == 0.5 and media["preview_duration_seconds"] == 1


def test_download_validates_v4_audio_chart_and_lightshow_hash(tmp_path, monkeypatch):
    root, info = source(tmp_path)
    refs = ["AudioData.dat", "ExpertPlus.dat", "Lightshow.dat"]
    assert v4.references(info) == refs
    content_hash = hashlib.sha1(
        (root / "Info.dat").read_bytes() + b"".join((root / n).read_bytes() for n in refs)
    ).hexdigest()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        for file in root.iterdir():
            z.writestr(file.name, file.read_bytes())
    meta = {"versions": [{"diffs": [], "hash": content_hash, "downloadURL": "https://r2cdn.beatsaver.com/source.zip"}]}

    class Response(io.BytesIO):
        def geturl(self):
            return "https://r2cdn.beatsaver.com/source.zip"

    def fetch(request, **kwargs):
        return Response(json.dumps(meta).encode() if "/maps/id/" in request.full_url else archive.getvalue())

    monkeypatch.setattr(app.urllib.request, "urlopen", fetch)
    result = app.download("5219c", tmp_path / "download")
    assert json.loads((result / "Info.dat").read_text())["version"] == "4.0.1"
    meta["versions"][0]["hash"] = "0" * 40
    with pytest.raises(ValueError, match="content hash mismatch"):
        app.download("5219c", tmp_path / "bad")


def test_banner_uses_current_brand(capsys, monkeypatch):
    import full_custom_song_pipeline as pipeline

    monkeypatch.setattr("sys.argv", ["pipeline", "--help"])
    with pytest.raises(SystemExit):
        pipeline.main()
    out = capsys.readouterr().out
    assert "OrBeats Pipeline" in out and "Beat Saber Deluxe Pipeline" not in out
