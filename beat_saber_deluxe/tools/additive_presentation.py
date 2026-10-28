"""Unmodded per-map palette and level timing/loudness metadata."""

import math

COLORS = (
    "saberAColor",
    "saberBColor",
    "environmentColor0",
    "environmentColor1",
    "environmentColorW",
    "environmentColor0Boost",
    "environmentColor1Boost",
    "environmentColorWBoost",
    "obstaclesColor",
)
LEGACY = (
    "_colorLeft",
    "_colorRight",
    "_envColorLeft",
    "_envColorRight",
    "_envColorWhite",
    "_envColorLeftBoost",
    "_envColorRightBoost",
    "_envColorWhiteBoost",
    "_obstacleColor",
)
DIFFS = ("Easy", "Normal", "Hard", "Expert", "ExpertPlus")


def scalar(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("invalid authored presentation scalar")
    return value


def color(value):
    if not isinstance(value, dict) or set(value) - {"r", "g", "b", "a"} or not {"r", "g", "b"} <= set(value):
        raise ValueError("invalid authored RGBA color")
    return [scalar(value[k], 0, 1) for k in ("r", "g", "b")] + [scalar(value.get("a", 1), 0, 1)]


def v4_difficulty_custom(value):
    """Translate only known InfoV4 cosmetic keys into existing palette handling.

    Never treat the presence of colors as permission to discard requirements or
    other custom behaviour. Validate the entire dictionary before returning it.
    """
    names = {legacy[1:]: legacy for legacy in LEGACY}
    if not isinstance(value, dict) or set(value) - names.keys() - {"difficultyLabel"}:
        raise ValueError("unsupported mod-dependent InfoV4 difficulty metadata")
    result = {}
    for name, item in value.items():
        if name == "difficultyLabel":
            if not isinstance(item, str) or len(item) > 200:
                raise ValueError("invalid InfoV4 difficulty label")
            result["_difficultyLabel"] = item
        else:
            color(item)
            result[names[name]] = dict(item)
    return result


def validate(profile):
    if not isinstance(profile, dict) or set(profile) != {"lufs", "offset", "colors"}:
        raise ValueError("invalid authored presentation profile")
    scalar(profile["lufs"], -100, 100)
    scalar(profile["offset"], -10, 10)
    if not isinstance(profile["colors"], list) or len(profile["colors"]) != 5:
        raise ValueError("five presentation difficulty slots required")
    for palette in profile["colors"]:
        if not isinstance(palette, dict) or set(palette) - set(COLORS):
            raise ValueError("unsupported authored palette field")
        for rgba in palette.values():
            if not isinstance(rgba, list) or len(rgba) != 4:
                raise ValueError("invalid authored color")
            for v in rgba:
                scalar(v, 0, 1)
    return profile


def from_info(info):
    profile = dict(
        lufs=info.get("_orbeatsLufs", -14), offset=info.get("_songTimeOffset", 0), colors=[{} for _ in DIFFS]
    )
    schemes = info.get("_colorSchemes", [])
    if not isinstance(schemes, list) or len(schemes) > 64:
        raise ValueError("invalid authored color schemes")
    selected = {}
    for group in info.get("_difficultyBeatmapSets", []):
        for d in group.get("_difficultyBeatmaps", []):
            palette = {}
            idx = d.get("_beatmapColorSchemeIdx", -1)
            if type(idx) is not int or idx < -1 or idx >= len(schemes):
                raise ValueError("invalid authored color scheme index")
            if idx >= 0:
                scheme = schemes[idx]
                if (
                    not isinstance(scheme, dict)
                    or set(scheme) - {"useOverride", "colorScheme"}
                    or type(scheme.get("useOverride", False)) is not bool
                ):
                    raise ValueError("invalid InfoV2 color scheme")
                content = scheme.get("colorScheme", {})
                if not isinstance(content, dict) or set(content) - set(COLORS) - {"colorSchemeId"}:
                    raise ValueError("unsupported InfoV2 color scheme fields")
                if scheme.get("useOverride", False):
                    palette.update({k: color(v) for k, v in content.items() if k in COLORS})
            custom = d.get("_customData", {})
            if not isinstance(custom, dict) or set(custom) - set(LEGACY) - {"_difficultyLabel"}:
                raise ValueError("unsupported mod-dependent difficulty metadata")
            palette.update({new: color(custom[old]) for old, new in zip(LEGACY, COLORS) if old in custom})
            name = d["_difficulty"]
            if name not in DIFFS:
                raise ValueError("invalid presentation difficulty")
            prior = selected.get(name)
            if prior is not None and prior != palette:
                raise ValueError(
                    "different palettes for same difficulty across characteristics need expanded presentation support"
                )
            selected[name] = palette
            profile["colors"][DIFFS.index(name)] = palette
    validate(profile)
    return profile if profile["offset"] or profile["lufs"] != -14 or any(profile["colors"]) else None
