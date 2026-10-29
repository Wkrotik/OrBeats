"""Bounded V3 lighting matching CUSA12878/2.04 save-data classes.

Omitted serialized scalar fields have their native zero defaults. No conversion
of light-group IDs, environment layouts or distribution curves is attempted.
"""

from __future__ import annotations

import copy
import math

LIGHT_KEYS = (
    "basicBeatmapEvents",
    "colorBoostBeatmapEvents",
    "lightColorEventBoxGroups",
    "lightRotationEventBoxGroups",
    "lightTranslationEventBoxGroups",
)
BOX_KEYS = LIGHT_KEYS[2:4]  # Translation/FX need their own reviewed conversion.
REVIEWED_ENVIRONMENT = "WeaveEnvironment"
# Owned PS4 2.04 catalog scene assets; no custom/downloading environment support.
NATIVE_ENVIRONMENTS = frozenset(('BTSEnvironment', 'BigMirrorEnvironment', 'BillieEnvironment', 'BritneyEnvironment', 'ColliderEnvironment', 'CrabRaveEnvironment', 'DaftPunkEnvironment', 'DefaultEnvironment', 'Dragons2Environment', 'DragonsEnvironment', 'EDMEnvironment', 'FitBeatEnvironment', 'GagaEnvironment', 'GreenDayEnvironment', 'GreenDayGrenadeEnvironment', 'HalloweenEnvironment', 'HipHopEnvironment', 'InterscopeEnvironment', 'KDAEnvironment', 'KaleidoscopeEnvironment', 'LatticeEnvironment', 'LinkinPark2Environment', 'LinkinParkEnvironment', 'LizzoEnvironment', 'MetallicaEnvironment', 'Monstercat2Environment', 'MonstercatEnvironment', 'NiceEnvironment', 'OriginsEnvironment', 'Panic2Environment', 'PanicEnvironment', 'PyroEnvironment', 'QueenEnvironment', 'RockMixtapeEnvironment', 'RocketEnvironment', 'SkrillexEnvironment', 'TheRollingStonesEnvironment', 'TheSecondEnvironment', 'TheWeekndEnvironment', 'TimbalandEnvironment', 'TriangleEnvironment', 'WeaveEnvironment'))
EASE_TYPES = frozenset((*range(-1, 31), 100, 101, 102))
# CUSA12878/2.04 BasicBeatmapEventType: additional environment lighting
# channels 16..19 are ordinary basic events (e.g. Gaga). Deliberately exclude
# legacy spawn rotations 14/15, unreviewed 20/21, specials 40..43, BPM 100 and
# NJS 1000. Enum membership alone does not establish lighting support.
BASIC_LIGHT_EVENT_TYPES = frozenset((*range(14), *range(16, 20)))


def is_basic_light_event_type(value):
    return type(value) is int and value in BASIC_LIGHT_EVENT_TYPES


def scalar(value, label, low, high, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not low <= value <= high or not math.isfinite(value):
        raise ValueError("invalid lighting " + label)
    return value


def record(value, fields, label):
    if not isinstance(value, dict) or set(value) - set(fields):
        raise ValueError("unsupported lighting " + label + " fields")
    for key, (low, high, integer) in fields.items():
        if key in value:
            scalar(value[key], label + "." + key, low, high, integer)
            if (low, high, integer) == (-1, 102, True) and value[key] not in EASE_TYPES:
                raise ValueError("invalid lighting ease enum")


def boosts(entries, maxbeat):
    if not isinstance(entries, list) or len(entries) > 200000:
        raise ValueError("invalid colorBoostBeatmapEvents list")
    out = []
    for item in entries:
        if not isinstance(item, dict) or set(item) - {"b", "o"}:
            raise ValueError("invalid colorBoostBeatmapEvents shape")
        beat = scalar(item.get("b", 0), "boost beat", 0, maxbeat)
        on = item.get("o", False)
        if type(on) is not bool:
            raise ValueError("invalid colorBoostBeatmapEvents boost boolean")
        out.append({"b": beat, "o": on})
    return out


def validate_boxes(data, maxbeat):
    total = 0
    ease = (-1, 102, True)
    for key in BOX_KEYS:
        groups = data.get(key, [])
        if not isinstance(groups, list) or len(groups) > 20000:
            raise ValueError("invalid lighting group list")
        color = key == BOX_KEYS[0]
        for group in groups:
            if not isinstance(group, dict) or set(group) - {"b", "g", "e"}:
                raise ValueError("unsupported lighting group fields")
            start = scalar(group.get("b", 0), "group beat", 0, maxbeat)
            scalar(group.get("g", 0), "group ID", 0, 1023, True)
            boxes = group.get("e", [])
            if not isinstance(boxes, list) or len(boxes) > 1024:
                raise ValueError("invalid lighting box list")
            for box in boxes:
                total += 1
                if not isinstance(box, dict):
                    raise ValueError("invalid lighting box object")
                fields = {"w": (0, maxbeat, False), "d": (0, 2, True), "t": (0, 2, True), "b": (0, 1, True), "i": ease}
                fields.update(
                    {"r": (-10000, 10000, False)}
                    if color
                    else {"s": (-10000, 10000, False), "a": (0, 2, True), "r": (0, 1, True)}
                )
                record({k: v for k, v in box.items() if k not in ("f", "e" if color else "l")}, fields, "box")
                record(
                    box.get("f", {}),
                    {
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
                    "filter",
                )
                events = box.get("e" if color else "l", [])
                if not isinstance(events, list) or len(events) > 20000:
                    raise ValueError("invalid lighting base-event list")
                for event in events:
                    total += 1
                    fields = {"b": (0, maxbeat, False)}
                    fields.update(
                        {
                            "i": (0, 2, True),
                            "c": (-1, 2, True),
                            "s": (0, 100, False),
                            "f": (0, 10000, True),
                            "sb": (0, 100, False),
                            "sf": (0, 10000, True),
                        }
                        if color
                        else {
                            "p": (0, 1, True),
                            "e": ease,
                            "l": (0, 10000, True),
                            "r": (-100000, 100000, False),
                            "o": (0, 2, True),
                        }
                    )
                    record(event, fields, "base event")
                    if start + event.get("b", 0) > maxbeat + 1e-5:
                        raise ValueError("lighting base event exceeds song")
                if total > 400000:
                    raise ValueError("lighting event budget exceeded")


def has_boxes(data):
    return any(data.get(key) for key in BOX_KEYS)


def lightshow(data):
    out = {"version": "3.3.0", **{key: copy.deepcopy(data.get(key, [])) for key in LIGHT_KEYS}}
    if "useNormalEventsAsCompatibleEvents" in data:
        out["useNormalEventsAsCompatibleEvents"] = data["useNormalEventsAsCompatibleEvents"]
    return out


def constant_boxes(data, factor):
    """Scale relative beats/distribution uniformly; changing BPM is refused upstream."""
    out = {key: copy.deepcopy(data.get(key, [])) for key in BOX_KEYS}
    for key, groups in out.items():
        for group in groups:
            group["b"] = group.get("b", 0) * factor
            for box in group.get("e", []):
                if "w" in box:
                    box["w"] *= factor
                for event in box.get("e" if key == BOX_KEYS[0] else "l", []):
                    event["b"] = event.get("b", 0) * factor
    return out
