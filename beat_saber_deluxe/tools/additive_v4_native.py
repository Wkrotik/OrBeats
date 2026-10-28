"""Reviewed CUSA12878/2.04 native V4 payload validation, not lossy V3 conversion.

Schema evidence: owned dump TypeDef12099/12115; BSMG format documentation.
All column indices, even unused metadata rows, and aggregate budgets are checked.
"""

from __future__ import annotations

import copy
import math

from additive_lighting import EASE_TYPES


def number(v, name, lo=0, hi=1000000, integer=False):
    if type(v) not in ((int,) if integer else (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError("invalid native V4 " + name)
    return v


def obj(v, fields, name):
    if not isinstance(v, dict) or set(v) - set(fields):
        raise ValueError("unsupported native V4 " + name + " fields")
    return v


def rows(v, name, limit=200000):
    if not isinstance(v, list) or len(v) > limit:
        raise ValueError("invalid bounded native V4 " + name)
    return v


def scalar_record(v, fields, name):
    obj(v, fields, name)
    for k, (low, high, integer) in fields.items():
        n = number(v.get(k, 0), name + "." + k, low, high, integer)
        if (low, high, integer) == (-1, 102, True) and n not in EASE_TYPES:
            raise ValueError("invalid native V4 easing enum")


def index(v, items, name):
    return items[number(v, name + " index", 0, len(items) - 1, True)]


def audio(data):
    obj(data, ("version", "songChecksum", "songSampleCount", "songFrequency", "bpmData", "lufsData"), "AudioData")
    if data.get("version") != "4.0.0":
        raise ValueError("unsupported native AudioData version")
    checksum = data.get("songChecksum", "")
    if not isinstance(checksum, str) or len(checksum) > 128 or any(ord(c) < 32 for c in checksum):
        raise ValueError("invalid native AudioData checksum")
    rate = number(data.get("songFrequency"), "sample rate", 1, 192000, True)
    count = number(data.get("songSampleCount"), "sample count", rate, rate * 600, True)
    last_sample, last_beat = 0, 0
    regions = rows(data.get("bpmData"), "BPM regions", 10000)
    if not regions:
        raise ValueError("native AudioData needs BPM regions")
    for r in regions:
        obj(r, ("si", "ei", "sb", "eb"), "BPM region")
        si = number(r.get("si", 0), "start sample", 0, count, True)
        ei = number(r.get("ei", 0), "end sample", 0, count, True)
        sb, eb = number(r.get("sb", 0), "start beat"), number(r.get("eb", 0), "end beat")
        if si != last_sample or not si < ei or abs(sb - last_beat) > 1e-7 or eb <= sb:
            raise ValueError("native BPM regions must cover contiguous samples and beats from zero")
        number((eb - sb) * rate * 60 / (ei - si), "region BPM", 1, 1000)
        last_sample, last_beat = ei, eb
    if last_sample != count:
        raise ValueError("native BPM regions must cover entire audio")
    last_end = 0
    for r in rows(data.get("lufsData", []), "LUFS regions", 10000):
        scalar_record(r, {"si": (0, count, True), "ei": (0, count, True), "l": (-100, 100, False)}, "LUFS region")
        if r.get("si", 0) < last_end or r.get("ei", 0) <= r.get("si", 0):
            raise ValueError("invalid native LUFS region order")
        last_end = r.get("ei", 0)
    return last_beat


def audio_duration_matches(data, rate, count):
    """Existing one-44.1kHz-sample tolerance, without float cancellation at its boundary."""
    difference = abs(count * data["songFrequency"] - data["songSampleCount"] * rate)
    return difference * 44100 <= rate * data["songFrequency"]


def resample_audio(data, rate, count, checksum):
    """Keep beat boundaries; quantize sample boundaries once at the stored rate."""
    audio(data)
    if not audio_duration_matches(data, rate, count):
        raise ValueError("native AudioData and stored audio durations disagree")
    out = copy.deepcopy(data)
    out.update(songFrequency=rate, songSampleCount=count, songChecksum=checksum)
    for key in ("bpmData", "lufsData"):
        for r in out.get(key, []):
            for field in ("si", "ei"):
                value = r.get(field, 0)
                r[field] = count if value == data["songSampleCount"] else round(value * rate / data["songFrequency"])
    audio(out)
    return out


def chart(data, maxbeat, base_njs=10):
    metadata = {
        "colorNotesData": {
            "x": (0, 3, True),
            "y": (0, 2, True),
            "c": (0, 1, True),
            "d": (0, 8, True),
            "a": (-180, 180, True),
        },
        "bombNotesData": {"x": (0, 3, True), "y": (0, 2, True)},
        "obstaclesData": {
            "x": (-4, 7, True),
            "y": (0, 2, True),
            "d": (0, maxbeat, False),
            "w": (1, 4, True),
            "h": (1, 5, True),
        },
        "arcsData": {"m": (0, 100, False), "tm": (0, 100, False), "a": (0, 2, True)},
        "chainsData": {"tx": (0, 3, True), "ty": (0, 2, True), "c": (2, 128, True), "s": (0.001, 100, False)},
        "njsEventData": {"d": (-100, 100, False), "p": (0, 1, True), "e": (-1, 102, True)},
    }
    event_keys = ("colorNotes", "bombNotes", "obstacles", "arcs", "chains", "njsEvents")
    obj(data, ("version", *metadata, *event_keys, "customData"), "chart")
    if data.get("version") not in ("4.0.0", "4.0.1", "4.1.0"):
        raise ValueError("unsupported native chart version")
    if data.get("version") not in ("4.0.0", "4.0.1", "4.1.0") or data.get("customData"):
        raise ValueError("unsupported native V4 version/mod data")
    total = 0
    for key, fields in metadata.items():
        for row in rows(data.get(key, []), key):
            scalar_record(row, fields, key)
            if key == "obstaclesData" and row.get("x", 0) + row.get("w", 0) > 8:
                raise ValueError("native wall exceeds vanilla extent")
            if key == "njsEventData":
                number(base_njs + row.get("d", 0), "resulting NJS", 0.1, 100)
        total += len(data.get(key, []))
    slices = 0
    for key in event_keys:
        last = -1
        for event in rows(data.get(key, []), key):
            fields = (
                ("hb", "tb", "hr", "tr", "hi", "ti", "ai")
                if key == "arcs"
                else (
                    ("hb", "tb", "hr", "tr", "i", "ci")
                    if key == "chains"
                    else ("b", "i", "r")
                    if key != "njsEvents"
                    else ("b", "i")
                )
            )
            obj(event, fields, key)
            head = number(event.get("hb" if key in ("arcs", "chains") else "b", 0), key + " beat", 0, maxbeat)
            if key == "njsEvents" and head <= last:
                raise ValueError("NJS event beats must increase strictly")
            last = head
            for r in ("hr", "tr") if key in ("arcs", "chains") else (("r",) if key != "njsEvents" else ()):
                number(event.get(r, 0), "rotation lane", -360, 360, True)
            if key in ("arcs", "chains"):
                tail = number(event.get("tb", 0), key + " tail beat", 0, maxbeat)
                if tail <= head:
                    raise ValueError(key + " tail must follow head")
                index(event.get("hi" if key == "arcs" else "i", 0), data.get("colorNotesData", []), key + " head")
                if key == "arcs":
                    # Native ArcItemConverter.Convert (CUSA12878 RVA0x9E57C0)
                    # takes color from hi; ti supplies position/direction only.
                    # Its unused color need not equal hi. Still validate both refs.
                    index(event.get("ti", 0), data.get("colorNotesData", []), "arc tail")
                    index(event.get("ai", 0), data.get("arcsData", []), "arc")
                else:
                    meta = index(event.get("ci", 0), data.get("chainsData", []), "chain")
                    slices += meta.get("c", 0) - 1
            else:
                meta = index(
                    event.get("i", 0), data.get("njsEventData" if key == "njsEvents" else key + "Data", []), key
                )
                if key == "obstacles" and head + meta.get("d", 0) > maxbeat + 1e-6:
                    raise ValueError("native wall exceeds audio")
        total += len(data.get(key, []))
    notes = len(data.get("colorNotes", [])) + slices
    if total > 1000000 or not 1 <= notes <= 100000:
        raise ValueError("native V4 object budget or playable notes invalid")
    return notes


def lighting(data, maxbeat):
    ease = (-1, 102, True)
    fields = {
        "basicEventsData": {"t": (0, 13, True), "i": (-100000, 100000, True), "f": (-100000, 100000, False)},
        "colorBoostEventsData": {"b": (0, 1, True)},
        "indexFilters": {
            "f": (0, 2, True),
            "p": (0, 100000, True),
            "t": (0, 100000, True),
            "r": (0, 1, True),
            "c": (0, 100000, True),
            "n": (0, 3, True),
            "s": (-2147483648, 2147483647, True),
            "l": (0, 1, False),
            "d": (0, 3, True),
        },
        "lightColorEvents": {
            "p": (0, 1, True),
            "e": ease,
            "c": (-1, 2, True),
            "b": (0, 100, False),
            "f": (0, 10000, True),
            "sb": (0, 100, False),
            "sf": (0, 10000, True),
        },
        "lightRotationEvents": {
            "p": (0, 1, True),
            "e": ease,
            "l": (0, 10000, True),
            "r": (-100000, 100000, False),
            "d": (0, 2, True),
        },
        "lightTranslationEvents": {"p": (0, 1, True), "e": ease, "t": (-100000, 100000, False)},
        "floatFxEvents": {"p": (0, 1, True), "e": ease, "v": (-100000, 100000, False)},
        "waypointsData": {"x": (0, 3, True), "y": (0, 2, True), "o": (-1, 8, True)},
    }
    for kind in ("Color", "Rotation", "Translation", "Fx"):
        key = "fxEventBoxes" if kind == "Fx" else "light" + kind + "EventBoxes"
        fields[key] = {
            "w": (0, maxbeat, False),
            "d": (0, 2, True),
            "s": (-10000, 10000, False),
            "t": (0, 2, True),
            "b": (0, 1, True),
            "e": ease,
        }
        if kind in ("Rotation", "Translation"):
            fields[key].update(a=(0, 2, True), f=(0, 1, True))
    obj(
        data,
        (
            "version",
            *fields,
            "basicEvents",
            "colorBoostEvents",
            "waypoints",
            "eventBoxGroups",
            "basicEventTypesWithKeywords",
            "useNormalEventsAsCompatibleEvents",
        ),
        "lightshow",
    )
    if data.get("version") != "4.0.0" or type(data.get("useNormalEventsAsCompatibleEvents", False)) is not bool:
        raise ValueError("invalid native V4 lightshow version/compatibility")
    if data.get("basicEventTypesWithKeywords", {}) not in ({}, {"d": []}):
        raise ValueError("native V4 light keywords need separate support")
    total = 0
    for key, schema in fields.items():
        for row in rows(data.get(key, []), key):
            scalar_record(row, schema, key)
        total += len(data.get(key, []))
    for key, table in [
        ("basicEvents", "basicEventsData"),
        ("colorBoostEvents", "colorBoostEventsData"),
        ("waypoints", "waypointsData"),
    ]:
        for event in rows(data.get(key, []), key):
            obj(event, ("b", "i", "r") if key == "waypoints" else ("b", "i"), key)
            number(event.get("b", 0), "light beat", 0, maxbeat)
            if key == "waypoints":
                number(event.get("r", 0), "waypoint rotation", -360, 360, True)
            index(event.get("i", 0), data.get(table, []), key)
        total += len(data.get(key, []))
    kinds = {
        1: ("lightColorEventBoxes", "lightColorEvents"),
        2: ("lightRotationEventBoxes", "lightRotationEvents"),
        3: ("lightTranslationEventBoxes", "lightTranslationEvents"),
        4: ("fxEventBoxes", "floatFxEvents"),
    }
    for group in rows(data.get("eventBoxGroups", []), "eventBoxGroups", 20000):
        obj(group, ("b", "g", "t", "e"), "event group")
        start = number(group.get("b", 0), "group beat", 0, maxbeat)
        number(group.get("g", 0), "group ID", 0, 1023, True)
        kind = number(group.get("t", 0), "group type", 1, 4, True)
        box_key, event_key = kinds[kind]
        for box in rows(group.get("e", []), "group boxes", 1024):
            obj(box, ("f", "e", "l"), "event box index")
            index(box.get("f", 0), data.get("indexFilters", []), "filter")
            index(box.get("e", 0), data.get(box_key, []), "event box")
            total += 1
            for event in rows(box.get("l", []), "box events", 20000):
                obj(event, ("b", "i"), "box event")
                number(
                    start + number(event.get("b", 0), "relative beat", 0, maxbeat), "absolute light beat", 0, maxbeat
                )
                index(event.get("i", 0), data.get(event_key, []), event_key)
                total += 1
        total += 1
    if total > 400000:
        raise ValueError("native V4 lighting budget exceeded")
    return bool(data.get("eventBoxGroups"))
