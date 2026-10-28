"""Validated vanilla InfoV4/V4 -> normalized InfoV2 with native or simple V3 data.

Schemas: https://bsmg.wiki/mapping/map-format{,/info,/audio,/beatmap}.html
V4 omitted scalar fields, including metadata index i, default to zero. Never
use event position as the metadata index or drop unsupported gameplay/lighting.
"""

import json
import math
import shutil
from pathlib import Path
from typing import TypedDict


class DifficultyRoute(TypedDict, total=False):
    _difficulty: str
    _difficultyRank: int
    _beatmapFilename: str
    _noteJumpMovementSpeed: float
    _noteJumpStartBeatOffset: float
    _orbeatsLightshow: str
    _environmentNameIdx: int
    _beatmapColorSchemeIdx: int
    _customData: dict


class CharacteristicGroup(TypedDict):
    _beatmapCharacteristicName: str
    _difficultyBeatmaps: list[DifficultyRoute]


def finite(value, name, lo=0, hi=1000000):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not lo <= value <= hi
    ):
        raise ValueError("invalid V4 " + name)
    return value


def shape(value, allowed, name):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError("unsupported V4 " + name + " fields")
    return value


def references(info):
    """Source bytes for BeatSaver content hashing, in Info order."""
    if str(info.get("_version", "")).startswith("2."):
        return [
            d["_beatmapFilename"]
            for g in info.get("_difficultyBeatmapSets", [])
            for d in g.get("_difficultyBeatmaps", [])
        ]
    if info.get("version") not in ("4.0.0", "4.0.1"):
        raise ValueError(
            "Unsupported Info format: " + str(info.get("version", info.get("_version", "missing version")))
        )
    return [info["audio"]["audioDataFilename"]] + [
        name for d in info["difficultyBeatmaps"] for name in (d["beatmapDataFilename"], d["lightshowDataFilename"])
    ]


def tempo_events(data):
    shape(data, ("version", "songChecksum", "songSampleCount", "songFrequency", "bpmData", "lufsData"), "AudioData")
    if data.get("version") != "4.0.0" or data.get("songChecksum") or data.get("lufsData"):
        raise ValueError("unsupported V4 AudioData checksum/LUFS or version")
    samples = data["songSampleCount"]
    rate = data["songFrequency"]
    if type(samples) is not int or type(rate) is not int or not 1 <= rate <= 192000 or not 1 <= samples <= rate * 600:
        raise ValueError("invalid V4 audio sample bounds")
    regions = data.get("bpmData")
    if not isinstance(regions, list) or not 1 <= len(regions) <= 10000:
        raise ValueError("V4 AudioData needs a bounded BPM region list")
    events = []
    last_sample = 0
    last_beat = 0
    for r in regions:
        shape(r, ("si", "ei", "sb", "eb"), "BPM region")
        si, ei = r["si"], r["ei"]
        sb, eb = finite(r["sb"], "start beat"), finite(r["eb"], "end beat")
        if (
            type(si) is not int
            or type(ei) is not int
            or si != last_sample
            or not si < ei <= samples
            or abs(sb - last_beat) > 1e-7
            or eb <= sb
        ):
            raise ValueError("V4 BPM regions must cover contiguous samples and beats from zero")
        bpm = finite((eb - sb) * rate * 60 / (ei - si), "region BPM", 1, 1000)
        events.append({"b": sb, "m": bpm})
        last_sample, last_beat = ei, eb
    if last_sample != samples:
        raise ValueError("V4 BPM regions must cover the entire audio")
    return events


def chart_to_v3(data, lightshow, events):
    categories = {
        "colorNotes": {"x": 0, "y": 0, "c": 0, "d": 0, "a": 0},
        "bombNotes": {"x": 0, "y": 0},
        "obstacles": {"x": 0, "y": 0, "d": 0, "w": 0, "h": 0},
    }
    empty = ("arcs", "arcsData", "chains", "chainsData", "njsEvents", "njsEventData", "rotationEvents")
    known = {"version", "customData", *empty, *categories, *(k + "Data" for k in categories)}
    shape(data, known, "chart")
    if data.get("version") not in ("4.0.0", "4.0.1", "4.1.0"):
        raise ValueError("unsupported V4 chart version")
    refused = [k for k in empty if data.get(k)]
    if data.get("customData"):
        refused.append("customData")
    if refused:
        raise ValueError("unsupported V4 features: " + ", ".join(refused))
    if not isinstance(lightshow, dict) or lightshow.get("version") != "4.0.0":
        raise ValueError("V4 lightshow required")
    # shortcut: only empty V4 lightshows; add a tested event-box conversion before accepting authored lights.
    active_lights = [
        k
        for k, v in lightshow.items()
        if k not in ("version", "basicEventTypesWithKeywords", "useNormalEventsAsCompatibleEvents") and v
    ]
    if active_lights or lightshow.get("basicEventTypesWithKeywords", {}) not in ({}, {"d": []}):
        raise ValueError("unsupported V4 lightshow features: " + ", ".join(active_lights or ["keywords"]))
    if type(lightshow.get("useNormalEventsAsCompatibleEvents", False)) is not bool:
        raise ValueError("invalid V4 lightshow compatibility flag")
    result = {"version": "3.3.0", "bpmEvents": events, "sliders": [], "basicBeatmapEvents": []}
    for key, defaults in categories.items():
        items, rows = data.get(key, []), data.get(key + "Data", [])
        if not isinstance(items, list) or not isinstance(rows, list) or len(items) > 200000 or len(rows) > 200000:
            raise ValueError("invalid bounded V4 " + key)
        for row in rows:
            shape(row, defaults, key + " metadata")
        converted = []
        for item in items:
            shape(item, ("b", "r", "i"), key + " event")
            index = item.get("i", 0)
            if type(index) is not int or not 0 <= index < len(rows):
                raise ValueError("invalid V4 " + key + " metadata index")
            if finite(item.get("r", 0), "rotation lane", -1000000) != 0:
                raise ValueError("unsupported V4 object rotation")
            converted.append({"b": finite(item.get("b", 0), "beat"), **defaults, **rows[index]})
        result[key] = converted
    return result


def normalize(source, output, local_file):
    """Write a new, private source directory; the original download stays intact."""
    source, output = Path(source).resolve(), Path(output).resolve()
    infos = [p for p in source.iterdir() if p.name.lower() == "info.dat"]
    if len(infos) != 1:
        raise ValueError("one Info.dat required")
    info = json.loads(infos[0].read_text(encoding="utf-8-sig"))
    references(info)  # supported Info version and required filenames
    shape(
        info,
        (
            "version",
            "song",
            "audio",
            "songPreviewFilename",
            "coverImageFilename",
            "environmentNames",
            "colorSchemes",
            "difficultyBeatmaps",
            "customData",
        ),
        "Info",
    )
    shape(info.get("customData", {}), ("editors", "contributors"), "Info custom metadata")
    song = shape(info["song"], ("title", "subTitle", "author"), "song metadata")
    audio = shape(
        info["audio"],
        ("songFilename", "songDuration", "audioDataFilename", "bpm", "lufs", "previewStartTime", "previewDuration"),
        "audio metadata",
    )
    separate_preview = info.get("songPreviewFilename", audio["songFilename"]) != audio["songFilename"]
    lufs = finite(audio.get("lufs", -14), "LUFS", -100, 100)
    audio_data = json.loads(local_file(source, audio["audioDataFilename"]).read_text(encoding="utf-8-sig"))
    from additive_v4_native import audio as validate_audio

    validate_audio(audio_data)
    events = tempo_events({**audio_data, "songChecksum": "", "lufsData": []})
    native_mode = bool(audio_data.get("lufsData")) or any(
        d.get("characteristic") in ("90Degree", "360Degree") for d in info["difficultyBeatmaps"]
    )
    for item in info["difficultyBeatmaps"]:
        candidate = json.loads(local_file(source, item["beatmapDataFilename"]).read_text(encoding="utf-8-sig"))
        show = json.loads(local_file(source, item["lightshowDataFilename"]).read_text(encoding="utf-8-sig"))
        native_mode |= any(candidate.get(k) for k in ("arcs", "chains", "njsEvents")) or any(
            e.get("r", 0) for k in ("colorNotes", "bombNotes", "obstacles") for e in candidate.get(k, [])
        )
        native_mode |= any(
            v
            for k, v in show.items()
            if k not in ("version", "basicEventTypesWithKeywords", "useNormalEventsAsCompatibleEvents")
        )
    groups: list[CharacteristicGroup] = []
    normalized = {
        "_version": "2.1.0",
        "_songName": song["title"],
        "_songSubName": song.get("subTitle", ""),
        "_songAuthorName": song["author"],
        "_levelAuthorName": "",
        "_beatsPerMinute": finite(audio["bpm"], "base BPM", 1, 1000),
        "_songTimeOffset": 0,
        "_orbeatsLufs": lufs,
        "_songFilename": audio["songFilename"],
        "_coverImageFilename": info["coverImageFilename"],
        "_previewStartTime": audio.get("previewStartTime", 0),
        "_previewDuration": audio.get("previewDuration", 10),
        "_difficultyBeatmapSets": groups,
    }
    diffs = info["difficultyBeatmaps"]
    if not isinstance(diffs, list) or not 1 <= len(diffs) <= 25:
        raise ValueError("one to twenty-five supported characteristic/difficulty entries required")
    output.mkdir()  # never overwrite caller content
    authors = []
    seen = set()
    names = ("Easy", "Normal", "Hard", "Expert", "ExpertPlus")
    for d in diffs:
        shape(
            d,
            (
                "characteristic",
                "difficulty",
                "beatmapAuthors",
                "environmentNameIdx",
                "beatmapColorSchemeIdx",
                "noteJumpMovementSpeed",
                "noteJumpStartBeatOffset",
                "beatmapDataFilename",
                "lightshowDataFilename",
                "customData",
            ),
            "difficulty",
        )
        name = d["difficulty"]
        from additive_modes import key as map_key

        mode = d["characteristic"]
        route = map_key(mode, name)
        if route in seen:
            raise ValueError("unique vanilla V4 characteristic/difficulty entries required")
        from additive_presentation import v4_difficulty_custom

        custom = v4_difficulty_custom(d.get("customData", {}))
        seen.add(route)
        people = shape(d.get("beatmapAuthors", {}), ("mappers", "lighters"), "authors")
        mappers = people.get("mappers", [])
        if not isinstance(mappers, list) or any(not isinstance(n, str) for n in mappers):
            raise ValueError("invalid V4 mappers")
        for mapper in mappers:
            if mapper not in authors:
                authors.append(mapper)
        try:
            chart = json.loads(local_file(source, d["beatmapDataFilename"]).read_text(encoding="utf-8-sig"))
            light = json.loads(local_file(source, d["lightshowDataFilename"]).read_text(encoding="utf-8-sig"))
            if native_mode:
                from additive_v4_native import chart as validate_chart
                from additive_v4_native import lighting as validate_lighting

                maxbeat = validate_audio(audio_data)
                validate_chart(chart, maxbeat, d["noteJumpMovementSpeed"])
                validate_lighting(light, maxbeat)
                converted = chart
            else:
                converted = chart_to_v3(chart, light, events)
        except ValueError as e:
            raise ValueError(f"{name} ({d['beatmapDataFilename']}): {e}") from e
        if native_mode:
            light_name = route.replace("/", "-") + ".lightshow.dat"
            (output / light_name).write_text(json.dumps(light, separators=(",", ":")), encoding="utf8")
        filename = route.replace("/", "-") + ".dat"
        (output / filename).write_text(json.dumps(converted, separators=(",", ":")), encoding="utf8")
        group = next((g for g in groups if g["_beatmapCharacteristicName"] == mode), None)
        if group is None:
            group = CharacteristicGroup(_beatmapCharacteristicName=mode, _difficultyBeatmaps=[])
            groups.append(group)
        group["_difficultyBeatmaps"].append(
            {
                "_difficulty": name,
                "_difficultyRank": names.index(name) * 2 + 1,
                "_beatmapFilename": filename,
                "_noteJumpMovementSpeed": d["noteJumpMovementSpeed"],
                "_noteJumpStartBeatOffset": d["noteJumpStartBeatOffset"],
            }
        )
        if custom:
            group["_difficultyBeatmaps"][-1]["_customData"] = custom
        if native_mode:
            group["_difficultyBeatmaps"][-1]["_orbeatsLightshow"] = light_name
        environments = info.get("environmentNames", [])
        if environments:
            idx = d.get("environmentNameIdx", 0)
            if type(idx) is not int or not 0 <= idx < len(environments):
                raise ValueError("invalid V4 environment index")
            group["_difficultyBeatmaps"][-1]["_environmentNameIdx"] = idx
            normalized["_environmentNames"] = environments
            normalized["_environmentName"] = environments[0]
    schemes = info.get("colorSchemes", [])
    if schemes:
        from additive_presentation import COLORS, color

        if not isinstance(schemes, list) or len(schemes) > 64:
            raise ValueError("invalid InfoV4 color scheme array")
        normalized["_colorSchemes"] = []
        for scheme in schemes:
            shape(scheme, ("colorSchemeName", "overrideNotes", "overrideLights", *COLORS), "color scheme")
            if (
                type(scheme.get("overrideNotes", False)) is not bool
                or type(scheme.get("overrideLights", False)) is not bool
            ):
                raise ValueError("invalid InfoV4 color override flags")
            chosen = {}
            for key in COLORS:
                if key not in scheme:
                    continue
                color(scheme[key])
                if scheme.get(
                    "overrideNotes" if key in ("saberAColor", "saberBColor", "obstaclesColor") else "overrideLights",
                    False,
                ):
                    chosen[key] = scheme[key]
            normalized["_colorSchemes"].append(dict(useOverride=bool(chosen), colorScheme=chosen))
        for old in diffs:
            group = next(g for g in groups if g["_beatmapCharacteristicName"] == old["characteristic"])
            new = next(d for d in group["_difficultyBeatmaps"] if d["_difficulty"] == old["difficulty"])
            idx = old.get("beatmapColorSchemeIdx", 0 if schemes else -1)
            if type(idx) is not int or not -1 <= idx < len(schemes):
                raise ValueError("invalid InfoV4 palette index")
            new["_beatmapColorSchemeIdx"] = idx
    if native_mode:
        normalized["_orbeatsAudioData"] = "native-audio.dat"
        (output / "native-audio.dat").write_text(json.dumps(audio_data, separators=(",", ":")), encoding="utf8")
    normalized["_levelAuthorName"] = ", ".join(authors)
    # Use fixed destination names: audio/cover filenames must not collide with charts or Info.dat.
    audio_path = local_file(source, audio["songFilename"])
    cover_path = local_file(source, info["coverImageFilename"])
    normalized["_songFilename"] = "source-audio" + audio_path.suffix
    normalized["_coverImageFilename"] = "source-cover" + cover_path.suffix
    shutil.copyfile(audio_path, output / normalized["_songFilename"])
    shutil.copyfile(cover_path, output / normalized["_coverImageFilename"])
    if separate_preview:
        preview_path = local_file(source, info["songPreviewFilename"])
        normalized["_orbeatsPreviewFilename"] = "source-preview" + preview_path.suffix
        shutil.copyfile(preview_path, output / normalized["_orbeatsPreviewFilename"])
    (output / "Info.dat").write_text(json.dumps(normalized, separators=(",", ":")), encoding="utf8")
    return normalized
