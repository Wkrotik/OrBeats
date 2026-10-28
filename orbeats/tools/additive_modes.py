"""Stable internal keys retain Standard compatibility and explicit native modes."""

MODES = ("Standard", "OneSaber", "NoArrows", "90Degree", "360Degree")
DIFFS = ("Easy", "Normal", "Hard", "Expert", "ExpertPlus")


def key(mode, difficulty):
    if mode not in MODES or difficulty not in DIFFS:
        raise ValueError("unsupported vanilla characteristic/difficulty")
    return difficulty if mode == "Standard" else mode + "/" + difficulty


def parts(value):
    items = value.split("/")
    mode, difficulty = ("Standard", items[0]) if len(items) == 1 else items
    key(mode, difficulty)
    return mode, difficulty


def order(value):
    mode, difficulty = parts(value)
    return MODES.index(mode), DIFFS.index(difficulty)
