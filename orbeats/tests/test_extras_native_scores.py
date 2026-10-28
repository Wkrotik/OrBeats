"""Run production native ScoreSaber decoding with ASAN/UBSan, no network or game."""

import copy
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXTRAS = ROOT / "orbeats_extras"


@pytest.fixture(scope="module")
def decoder(tmp_path_factory):
    cc, cxx = shutil.which("clang"), shutil.which("clang++")
    if not cc or not cxx:
        pytest.skip("Native sanitizers need clang/clang++")
    out = tmp_path_factory.mktemp("extras-scores")
    flags = ["-g", "-O1", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    subprocess.run(
        [
            cc,
            *flags,
            "-DCJSON_NESTING_LIMIT=16",
            "-c",
            str(EXTRAS / "third_party/cjson/cJSON.c"),
            "-o",
            str(out / "json.o"),
        ],
        check=True,
    )
    subprocess.run(
        [
            cxx,
            *flags,
            "-std=c++11",
            "-I" + str(EXTRAS / "include"),
            str(ROOT / "orbeats/tests/native/extras_scores_test.cpp"),
            str(EXTRAS / "src/scoresaber.cpp"),
            str(out / "json.o"),
            "-o",
            str(out / "decode"),
        ],
        check=True,
    )
    return out / "decode"


def page():
    return {
        "metadata": {"total": 108, "page": 1, "itemsPerPage": 12},
        "scores": [
            {
                "rank": n + 1,
                "modifiedScore": 99999,
                "fullCombo": True,
                "leaderboardPlayerInfo": {"name": "<b>Player</b>\u202e\n\t"},
            }
            for n in range(12)
        ],
    }


def run(decoder, raw, mode=""):
    if not isinstance(raw, bytes):
        raw = json.dumps(raw, ensure_ascii=False).encode()
    return subprocess.run(
        [str(decoder), *([mode] if mode else [])],
        input=raw,
        capture_output=True,
        timeout=10,
        check=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"},
    )


def test_top_fifty_and_hundred_pagination_and_name_sanitizing(decoder):
    run(decoder, page())


@pytest.mark.parametrize(
    "kind",
    [
        "wrong-page",
        "wrong-size",
        "negative-total",
        "boolean-total",
        "extra-row",
        "missing-row",
        "duplicate-rank",
        "negative-score",
        "overflow-score",
        "fraction-score",
        "boolean-score",
        "string-score",
        "invalid-combo",
        "missing-name",
        "name-object",
        "long-name",
        "total-short",
    ],
)
def test_untrusted_schema_failure_clears_output(decoder, kind):
    value = copy.deepcopy(page())
    meta, scores = value["metadata"], value["scores"]
    row = scores[0]
    if kind == "wrong-page":
        meta["page"] = 2
    elif kind == "wrong-size":
        meta["itemsPerPage"] = 100
    elif kind == "negative-total":
        meta["total"] = -1
    elif kind == "boolean-total":
        meta["total"] = True
    elif kind == "extra-row":
        scores.append(copy.deepcopy(row))
    elif kind == "missing-row":
        scores.pop()
    elif kind == "duplicate-rank":
        scores[1]["rank"] = 1
    elif kind == "negative-score":
        row["modifiedScore"] = -1
    elif kind == "overflow-score":
        row["modifiedScore"] = 2**31
    elif kind == "fraction-score":
        row["modifiedScore"] = 1.5
    elif kind == "boolean-score":
        row["modifiedScore"] = True
    elif kind == "string-score":
        row["modifiedScore"] = "99999"
    elif kind == "invalid-combo":
        row["fullCombo"] = 1
    elif kind == "missing-name":
        del row["leaderboardPlayerInfo"]["name"]
    elif kind == "name-object":
        row["leaderboardPlayerInfo"]["name"] = {}
    elif kind == "long-name":
        row["leaderboardPlayerInfo"]["name"] = "x" * 4097
    elif kind == "total-short":
        meta["total"] = 11
    run(decoder, value, "bad")


@pytest.mark.parametrize(
    "kind",
    [
        "truncated",
        "trailing",
        "duplicate-key",
        "invalid-utf8",
        "embedded-nul",
        "oversized",
        "deep",
        "empty",
        "surrogate",
        "nul-key",
        "nul-name",
    ],
)
def test_malformed_and_bounded_json_failure(decoder, kind):
    raw = json.dumps(page()).encode()
    if kind == "truncated":
        raw = raw[:-4]
    elif kind == "trailing":
        raw += b"evil"
    elif kind == "duplicate-key":
        raw = raw.replace(b'"rank": 1,', b'"rank": 1,"rank": 1,', 1)
    elif kind == "invalid-utf8":
        raw = raw.replace(b"Player", b"\xff", 1)
    elif kind == "embedded-nul":
        raw = raw.replace(b"Player", b"\x00", 1)
    elif kind == "oversized":
        raw += b" " * (512 * 1024)
    elif kind == "deep":
        raw = b"[" * 32 + b"0" + b"]" * 32
    elif kind == "empty":
        raw = b""
    elif kind == "surrogate":
        raw = raw.replace(b"Player", b"\\ud800", 1)
    elif kind == "nul-key":
        raw = raw.replace(b'"rank"', b'"rank\\u0000extra"', 1)
    elif kind == "nul-name":
        raw = raw.replace(b"Player", b"Pla\\u0000yer", 1)
    run(decoder, raw, "bad")


@pytest.mark.parametrize(
    "name,expected", [("日本語 🎵", "日本語 🎵"), ("🙂" * 100, "🙂" * 64), ("\u2066\u202e\n", "Unknown player")]
)
def test_unicode_truncation_and_invisible_only_name(decoder, name, expected):
    value = page()
    value["scores"][0]["leaderboardPlayerInfo"]["name"] = name
    assert run(decoder, value, "name").stdout.decode().rstrip("\n") == expected


def test_vendored_json_integrity_and_source_export_license():
    vendor = EXTRAS / "third_party/cjson"
    manifest = json.loads((vendor / "source.json").read_text())
    assert manifest["version"] == "v1.7.19"
    for name, checksum in manifest["files"].items():
        assert hashlib.sha256((vendor / name).read_bytes()).hexdigest() == checksum
    assert "Permission is hereby granted, free of charge" in (vendor / "LICENSE").read_text()
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "score_export", ROOT / "orbeats/development/scripts/prepare_source_repository.py"
    )
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)
    for name in ["cJSON.c", "cJSON.h", "source.json", "LICENSE"]:
        assert export.eligible("orbeats_extras/third_party/cjson/" + name)
