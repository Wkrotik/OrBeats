"""
test_webapp_beatsage.py — M13.3: the Beat Sage client contract.

Hermetic (plan §6): every HTTP call is monkeypatched — CI NEVER touches
beatsage.com (the same respect rule the live client follows: one job at a
time, their cadence, their failure budget). The tests pin:
- the captured API surface (routes, multipart field names, status values)
- the option validation (fail fast on unknown values)
- the client job state machine: create → poll (with hiccups) → download →
  stage → "STAGED <id>"; every failure path exits non-zero
- the guided-flow payload (Tier 2 — the always-works fallback)
"""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

from adapters import beatsage, songs  # noqa: E402


@pytest.fixture()
def staging(tmp_path, monkeypatch):
    st = tmp_path / "staged_songs"
    monkeypatch.setattr(songs, "STAGING_DIR", st)
    monkeypatch.setattr(songs, "MANIFEST_PATH", st / "manifest.json")
    return st


def _valid_zip() -> bytes:
    import io
    import zipfile
    info = {"_version": "3.3.0", "_songName": "AI Song", "_songAuthorName": "Beat Sage",
            "_beatsPerMinute": 128,
            "_difficultyBeatmapsSets": None,
            "_difficultyBeatmapSets": [{"_beatmapCharacteristicName": "Standard",
                                         "_difficultyBeatmaps": [
                                             {"_difficulty": "Expert",
                                              "_beatmapFilename": "Expert.dat"}]}]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Info.dat", json.dumps(info))
        zf.writestr("Expert.dat", "{}")
        zf.writestr("song.ogg", "audio-bytes")
    return buf.getvalue()


# ------------------------------------------------------------ the captured contract

def test_captured_constants():
    """The live-captured API surface (M13.3 research) — changing any of
    these means re-capturing from beatsage.com, not editing blindly."""
    assert beatsage.SERVER_HOST.startswith("https://")
    assert "beatsage" in beatsage.SERVER_HOST
    assert beatsage.DIFFICULTIES == ["Normal", "Hard", "Expert", "ExpertPlus"]
    assert "Standard" in beatsage.MODES
    assert beatsage.SYSTEM_TAGS == ["v2", "v1"]
    assert beatsage.HEARTBEAT_INTERVAL_SECONDS == 3.0
    assert beatsage.HEARTBEAT_MAX_FAILURES == 3


def test_events_are_the_probed_valid_set():
    """Exp 283b live probes: Bombs/DotBlocks/Obstacles all ACCEPTED (any
    combination); 'Lights' REJECTED with HTTP 400 in BOTH v1 and v2 — a
    broken checkbox on their own site. We never offer a can-never-succeed
    option; passing it fails client-side with the story."""
    assert beatsage.EVENTS == ["Bombs", "DotBlocks", "Obstacles"]
    errs = beatsage.validate_options({
        "difficulties": ["Normal"], "modes": ["Standard"],
        "events": ["Lights"], "environment": "DefaultEnvironment"})
    assert any("Lights" in e and "400" in e for e in errs)
    # their default combo + Bombs all validate clean
    assert beatsage.validate_options({
        "difficulties": ["Normal"], "modes": ["Standard"],
        "events": ["Bombs", "DotBlocks", "Obstacles"],
        "environment": "PanicEnvironment"}) == []


def test_recommended_options_are_our_ps4_defaults():
    """Standard only (the pipeline generates extra modes itself) + every
    difficulty Beat Sage offers + their own event defaults."""
    r = beatsage.guidance_payload()["recommended"]
    assert r["modes"] == ["Standard"]
    assert r["difficulties"] == ["Normal", "Hard", "Expert", "ExpertPlus"]
    assert r["system_tag"] == "v2"


def test_validate_options_accepts_recommendations():
    rec = beatsage.guidance_payload()["recommended"]
    assert beatsage.validate_options(rec) == []


def test_validate_options_rejects_unknowns():
    errs = beatsage.validate_options({"difficulties": ["Easy"],   # not offered!
                                      "modes": ["Standard"],
                                      "events": []})
    assert any("Unknown difficulties" in e for e in errs)
    assert any("at least one event" in e.lower() for e in errs)
    errs = beatsage.validate_options({"difficulties": ["Normal"], "modes": ["Standard"],
                                      "events": ["DotBlocks"], "environment": "NotAPlace"})
    assert any("environment" in e.lower() for e in errs)


def test_guidance_payload_is_self_sufficient():
    g = beatsage.guidance_payload()
    assert g["tier"] == 2
    assert g["site_url"].startswith("https://beatsage.com")
    assert any("zip" in s.lower() for s in g["steps"])


# ------------------------------------------------------------ the HTTP client

def test_create_job_builds_their_multipart(tmp_path):
    """The multipart body must carry THEIR field names verbatim (captured
    from their bundle): audio_file, audio_metadata_title/artist,
    difficulties, modes, events, environment, system_tag."""
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"WAVDATA")
    captured: dict = {}

    def fake_request(route, data=None, content_type=None, timeout=60):
        captured["route"] = route
        captured["data"] = data
        captured["ct"] = content_type
        return 200, json.dumps({"id": "job-123"}).encode()

    with mock.patch.object(beatsage, "_request", fake_request):
        jid = beatsage.create_job(str(audio), "My Song", "Me", {
            "difficulties": ["Normal", "Hard"], "modes": ["Standard"],
            "events": ["DotBlocks"], "environment": "DefaultEnvironment",
            "system_tag": "v2"})
    assert jid == "job-123"
    assert captured["route"] == "beatsaber_custom_level_create"
    assert "multipart/form-data" in captured["ct"]
    body = captured["data"].decode("utf-8", "replace")
    for field, value in (("audio_file", "song.wav"),
                         ("audio_metadata_title", "My Song"),
                         ("audio_metadata_artist", "Me"),
                         ("difficulties", "Normal,Hard"),
                         ("modes", "Standard"),
                         ("events", "DotBlocks"),
                         ("environment", "DefaultEnvironment"),
                         ("system_tag", "v2")):
        assert f'name="{field}"' in body, field
    assert "WAVDATA" in body


def test_create_job_http_error_raises_beatsageerror(tmp_path):
    """_request translates HTTP errors into BeatSageError with the guided-flow
    pointer — patch urlopen (the layer that owns HTTPError handling)."""
    import urllib.error
    audio = tmp_path / "s.wav"
    audio.write_bytes(b"x")
    err = urllib.error.HTTPError("url", 500, "Server Error", {}, None)  # type: ignore[arg-type]
    with mock.patch.object(beatsage.urllib.request, "urlopen", side_effect=err):
        with pytest.raises(beatsage.BeatSageError, match="HTTP 500"):
            beatsage.create_job(str(audio), "T", "A", {})


def test_create_job_no_id_in_response(tmp_path):
    audio = tmp_path / "s.wav"
    audio.write_bytes(b"x")
    with mock.patch.object(beatsage, "_request",
                           return_value=(200, b'{"status": "weird"}')):
        with pytest.raises(beatsage.BeatSageError, match="no job id"):
            beatsage.create_job(str(audio), "T", "A", {})


def test_heartbeat_parses_status():
    with mock.patch.object(beatsage, "_request",
                           return_value=(200, json.dumps({"status": "CREATING_LEVEL"}).encode())):
        assert beatsage.heartbeat("j1")["status"] == "CREATING_LEVEL"


def test_download_zip_rejects_non_zip():
    with mock.patch.object(beatsage, "_request",
                          return_value=(200, b"<html>not a zip</html>")):
        with pytest.raises(beatsage.BeatSageError, match="wasn't a zip"):
            beatsage.download_zip("j1")


# ------------------------------------------------------------ the client job script

CLIENT = PROJECT / "webapp" / "beatsage_client.py"


def load_client_module():
    """Import beatsage_client in-process (mocks on the shared adapters
    modules apply — a subprocess would bypass them and touch the REAL
    service; hermetic rule: CI never contacts beatsage.com)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("beatsage_client_under_test", CLIENT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def run_client_inprocess(spec: dict, monkeypatch) -> tuple[int, str]:
    """Call the client's main() with argv patched; capture stdout.
    Returns (exit_code, output)."""
    import contextlib
    import io
    mod = load_client_module()
    monkeypatch.setattr(sys, "argv", [str(CLIENT), "--job", json.dumps(spec)])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = mod.main()
    return (code if isinstance(code, int) else 0), buf.getvalue()


def run_client_subprocess(spec: dict) -> tuple[int, str]:
    """The real script invocation — ONLY for paths that provably never
    touch the network (CLI arg errors fail before any HTTP call)."""
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(CLIENT), "--job", json.dumps(spec)],
        capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout + proc.stderr


def _spec(tmp_path, **over):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"mp3-data")
    spec = {"audio_path": str(audio), "title": "AI Tune", "artist": "Me",
            "difficulties": ["Normal", "Expert"], "modes": ["Standard"],
            "events": ["DotBlocks"], "environment": "DefaultEnvironment",
            "system_tag": "v2"}
    spec.update(over)
    return spec


def test_client_happy_path_stages_the_result(tmp_path, staging, monkeypatch):
    """create → poll PENDING→CREATING_LEVEL→DONE → download → STAGED line.
    In-process so every beat of beatsage.* is mocked — hermetic."""
    monkeypatch.setattr(beatsage, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    states = iter(["PENDING", "CREATING_LEVEL", "DONE"])
    with mock.patch.object(beatsage, "create_job", return_value="job-9"), \
         mock.patch.object(beatsage, "heartbeat",
                           side_effect=lambda j: {"status": next(states)}), \
         mock.patch.object(beatsage, "download_zip", return_value=_valid_zip()):
        code, out = run_client_inprocess(_spec(tmp_path), monkeypatch)
    assert code == 0, out
    assert "STAGED" in out
    assert "job-9" in out
    assert "CREATING_LEVEL" in out
    staged = songs.list_staged()
    assert len(staged) == 1
    assert staged[0]["name"] == "AI Song"
    assert staged[0]["source"] == "beatsage"


def test_client_tolerates_heartbeat_hiccups(tmp_path, staging, monkeypatch):
    """Two failed polls (< their 3-failure budget) then DONE — succeeds."""
    monkeypatch.setattr(beatsage, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    calls = {"n": 0}

    def flaky(j):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise beatsage.BeatSageError("network blip")
        return {"status": "DONE"}

    with mock.patch.object(beatsage, "create_job", return_value="j"), \
         mock.patch.object(beatsage, "heartbeat", side_effect=flaky), \
         mock.patch.object(beatsage, "download_zip", return_value=_valid_zip()):
        code, out = run_client_inprocess(_spec(tmp_path), monkeypatch)
    assert code == 0, out
    assert "hiccup 1/3" in out and "hiccup 2/3" in out


def test_client_fails_after_max_heartbeat_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(beatsage, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    with mock.patch.object(beatsage, "create_job", return_value="j"), \
         mock.patch.object(beatsage, "heartbeat",
                           side_effect=beatsage.BeatSageError("down")):
        code, out = run_client_inprocess(_spec(tmp_path), monkeypatch)
    assert code == 1
    assert "guided flow" in out  # the always-works fallback is named


def test_client_create_failure_points_to_guided_flow(tmp_path, monkeypatch):
    with mock.patch.object(beatsage, "create_job",
                          side_effect=beatsage.BeatSageError("HTTP 429 (busy)")):
        code, out = run_client_inprocess(_spec(tmp_path), monkeypatch)
    assert code == 1
    assert "HTTP 429" in out
    assert "guided flow" in out


def test_client_rejects_bad_options_before_any_upload(tmp_path):
    # subprocess is safe here: option validation fails before any HTTP call
    code, out = run_client_subprocess(_spec(tmp_path, difficulties=["Easy"]))
    assert code == 2
    assert "Unknown difficulties" in out


def test_client_missing_audio_file(tmp_path):
    code, out = run_client_subprocess(_spec(tmp_path, audio_path=str(tmp_path / "nope.wav")))
    assert code == 2
    assert "missing" in out


def test_client_unknown_status_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(beatsage, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    with mock.patch.object(beatsage, "create_job", return_value="j"), \
         mock.patch.object(beatsage, "heartbeat",
                           return_value={"status": "EXPLODED"}):
        code, out = run_client_inprocess(_spec(tmp_path), monkeypatch)
    assert code == 1
    assert "unknown status" in out


# ------------------------------------------------------------ the LIVE gated contract test
# (plan §6: "the live-service contract test is gated (HAS-network class like
# the existing hardware gates) so CI never touches the real service").
# Run locally with:  pytest tests/test_webapp_beatsage.py -k live -rA
#   BEATSAGE_LIVE=1 pytest tests/test_webapp_beatsage.py::TestLiveContract -v
import os


@pytest.mark.skipif(not os.environ.get("BEATSAGE_LIVE"),
                    reason="gated: BEATSAGE_LIVE=1 to verify the live "
                           "beatsage.com contract (never in CI)")
class TestLiveContract:
    """ONE real generation with a rights-clean synthesized tone (a few
    seconds, well under their queue's expectations) — verifies the whole
    captured contract: create → heartbeat statuses → download zip."""

    def _tone(self, tmp_path):
        import math
        import struct
        import wave
        path = tmp_path / "bsd_test_tone.wav"
        sr = 44100
        secs = 8
        with wave.open(str(path), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            frames = bytearray()
            for i in range(sr * secs):
                # a simple beeping melody — unrecognizable, ours, tiny
                t = i / sr
                beep = (int(t * 2) % 2) == 0
                freq = 440.0 if beep else 554.37
                amp = 0.5 if beep else 0.3
                val = int(amp * 20000 * math.sin(2 * math.pi * freq * t) *
                          (0.6 + 0.4 * math.sin(2 * math.pi * 2 * t)))
                frames += struct.pack("<h", val)
            w.writeframes(bytes(frames))
        return path

    def test_live_generation_contract(self, tmp_path):
        tone = self._tone(tmp_path)
        jid = beatsage.create_job(str(tone), "BSD Contract Test", "Beat Saber Deluxe",
                                  {"difficulties": ["Normal"], "modes": ["Standard"],
                                   "events": [], "environment": "DefaultEnvironment",
                                   "system_tag": "v2"})
        assert jid
        status = ""
        import time
        deadline = time.time() + 600  # their AI is slow; 10 min is generous
        while time.time() < deadline:
            doc = beatsage.heartbeat(jid)
            status = doc.get("status", "")
            if status == "DONE":
                break
            assert status in ("PENDING", "LOADING_AUDIO", "CREATING_LEVEL",
                              "FORMATTING_LEVEL"), f"unexpected status: {status!r}"
            time.sleep(3.0)
        assert status == "DONE", f"job never finished (last={status!r})"
        data = beatsage.download_zip(jid)
        assert data[:2] == b"PK"
        # the zip must validate as a deployable map
        import sys as _sys
        _sys.path.insert(0, str(PROJECT / "webapp"))
        from adapters import songs as _songs
        st = tmp_path / "staged_songs"
        _songs.STAGING_DIR = st
        _songs.MANIFEST_PATH = st / "manifest.json"
        entry = _songs.stage_zip_bytes(data, source="beatsage")
        assert entry["name"] == "BSD Contract Test"
