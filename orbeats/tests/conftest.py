"""
Shared fixtures and helpers for Beat Saber Deluxe unit tests.
"""
import json
import os
import shutil
import struct
import sys
import tempfile

import pytest

# Make sure the tools/ directory is importable
TOOLS_DIR = os.path.join(os.path.dirname(__file__), '..', 'tools')
sys.path.insert(0, os.path.abspath(TOOLS_DIR))


# ---------------------------------------------------------------------------
# Temporary directory fixture (shared across a test, cleaned up after)
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_dir():
    """Provide a temporary directory, cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="bs_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Minimal WAV file fixtures
# ---------------------------------------------------------------------------
def _write_wav(path: str, pcm_bytes: bytes, sample_rate: int = 44100, channels: int = 2):
    """Write a minimal PCM16 WAV file."""
    import wave
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


@pytest.fixture
def silence_wav(tmp_dir):
    """A 0.1s silent stereo WAV at 44100Hz (8820 frames)."""
    frames = 8820
    pcm = b'\x00\x00' * frames * 2  # stereo silence
    path = os.path.join(tmp_dir, "silence.wav")
    _write_wav(path, pcm, 44100, 2)
    return path


@pytest.fixture
def tone_wav(tmp_dir):
    """A 0.1s 440Hz sine tone stereo WAV at 44100Hz."""
    import math
    frames = 4410
    pcm = bytearray()
    for i in range(frames):
        t = i / 44100.0
        s = int(math.sin(2 * math.pi * 440 * t) * 32767 * 0.5)
        pcm.extend(struct.pack('<hh', s, s))
    path = os.path.join(tmp_dir, "tone.wav")
    _write_wav(path, bytes(pcm), 44100, 2)
    return path


@pytest.fixture
def short_wav(tmp_dir):
    """A very short (28 samples = 1 HEVAG frame) stereo WAV at 44100Hz."""
    frames = 28
    import math
    pcm = bytearray()
    for i in range(frames):
        t = i / 44100.0
        s = int(math.sin(2 * math.pi * 440 * t) * 32767 * 0.5)
        pcm.extend(struct.pack('<hh', s, s))
    path = os.path.join(tmp_dir, "short.wav")
    _write_wav(path, bytes(pcm), 44100, 2)
    return path


# ---------------------------------------------------------------------------
# Minimal FSB5 header template fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def fsb5_template(tmp_dir):
    """
    Create a minimal 1732-byte FSB5 header template file.
    This is the raw sample header area extracted from a PS4 Beat Saber FSB5.
    """
    template = bytearray(1732)
    # Magic and size fields at well-known offsets in the header
    struct.pack_into('<I', template, 4, 0)     # data_size (placeholder)
    struct.pack_into('<H', template, 12, 1)    # format = 1 (HEVAG)
    struct.pack_into('<I', template, 16, 44100)  # frequency
    # 1732 bytes total — matches FSB5_SAMPLE_HEADER_SIZE
    path = os.path.join(tmp_dir, "fsb5_header_template.bin")
    with open(path, 'wb') as f:
        f.write(template)
    return path


@pytest.fixture
def full_fsb5_template(tmp_dir):
    """
    Create a minimal full FSB5 file (magic + header + 1732 sample header + 0 audio).
    Used to test _load_fsb5_header_template's FSB5-magic detection path.
    """
    sample_hdr_size = 1732
    header = bytearray(16 + sample_hdr_size)
    header[0:4] = b'FSB5'
    struct.pack_into('<I', header, 4, 1)  # version
    struct.pack_into('<I', header, 8, 1)  # num_samples
    struct.pack_into('<I', header, 12, sample_hdr_size)
    # sample header starts at offset 16
    struct.pack_into('<I', header, 20, 0)  # data_size = 0 (no audio)
    struct.pack_into('<H', header, 28, 1)  # format = 1 (HEVAG)
    struct.pack_into('<I', header, 32, 44100)  # frequency
    path = os.path.join(tmp_dir, "full_fsb5_template.bin")
    with open(path, 'wb') as f:
        f.write(header)
    return path


# ---------------------------------------------------------------------------
# Beatmap .dat file fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def v2_beatmap(tmp_dir):
    """A minimal V2-format beatmap dict saved to a .dat file."""
    data = {
        "_version": "2.0.0",
        "_notes": [
            {"_time": 0.0, "_lineIndex": 0, "_lineLayer": 0, "_type": 0, "_cutDirection": 1},
            {"_time": 1.0, "_lineIndex": 1, "_lineLayer": 1, "_type": 1, "_cutDirection": 2},
            {"_time": 2.0, "_lineIndex": 2, "_lineLayer": 2, "_type": 3, "_cutDirection": 0},
        ],
        "_obstacles": [
            {"_time": 0.5, "_lineIndex": 0, "_type": 0, "_duration": 2.0, "_width": 4},
        ],
        "_events": [
            {"_time": 0.0, "_type": 0, "_value": 1},
            {"_time": 1.0, "_type": 4, "_value": 3},
        ],
    }
    path = os.path.join(tmp_dir, "Hard.dat")
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


@pytest.fixture
def v3_beatmap(tmp_dir):
    """A minimal V3-format beatmap dict saved to a .dat file."""
    data = {
        "version": "3.2.0",
        "colorNotes": [
            {"b": 0.0, "x": 0, "y": 0, "a": 0, "c": 0, "d": 1},
            {"b": 1.0, "x": 1, "y": 1, "a": 1, "c": 1, "d": 2},
        ],
        "bombNotes": [],
        "obstacles": [
            {"b": 0.5, "x": 0, "y": 0, "d": 2.0, "w": 4, "h": 3},
        ],
        "sliders": [],
        "burstSliders": [],
        "basicBeatmapEvents": [
            {"b": 0.0, "et": 0, "i": 1},
            {"b": 1.0, "et": 4, "i": 3},
        ],
        "colorBoostBeatmapEvents": [],
        "bpmEvents": [{"b": 0, "m": 120.0}],
        "rotationEvents": [],
        "basicEventTypesWithKeywords": {"d": []},
        "useNormalEventsAsCompatibleEvents": True,
        "customData": {},
    }
    path = os.path.join(tmp_dir, "Normal.dat")
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


@pytest.fixture
def info_dat(tmp_dir):
    """A minimal Info.dat file."""
    data = {
        "_songName": "Test Song",
        "_songAuthorName": "Test Artist",
        "_beatsPerMinute": 128.0,
        "_version": "4.0.0",
        "_difficultyBeatmapSets": [
            {
                "_beatmapCharacteristicSerializedName": "Standard",
                "_difficultyBeatmaps": [
                    {"_difficulty": "Easy", "_difficultyRank": 1, "_beatmapFilename": "Easy.dat"},
                    {"_difficulty": "Normal", "_difficultyRank": 3, "_beatmapFilename": "Normal.dat"},
                    {"_difficulty": "Hard", "_difficultyRank": 5, "_beatmapFilename": "Hard.dat"},
                    {"_difficulty": "Expert", "_difficultyRank": 7, "_beatmapFilename": "Expert.dat"},
                    {"_difficulty": "ExpertPlus", "_difficultyRank": 9, "_beatmapFilename": "ExpertPlus.dat"},
                ],
            }
        ],
    }
    path = os.path.join(tmp_dir, "Info.dat")
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


@pytest.fixture
def bpm_info_dat(tmp_dir):
    """A minimal BPMInfo.dat file."""
    data = {
        "_version": "2.0.0",
        "_fps": 60,
        "_regions": [
            {"_startSampleIndex": 0, "_endSampleIndex": 1323000, "_startBeat": 0.0, "_endBeat": 480.0},
        ],
    }
    path = os.path.join(tmp_dir, "BPMInfo.dat")
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# Config dict fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def default_config():
    """A standard config dict (no file I/O required)."""
    return {
        "ps4": {
            "ip": "192.168.100.99",
            "ftp_port": 2121,
            "ftp_user": "anonymous",
            "ftp_password": "",
        },
        "title": {
            "id": "CUSA12878",
            "patch_suffix": "-patch",
        },
        "paths": {
            "afr_base": "/data/GoldHEN/AFR",
            "afr_target_suffix": "_v3",
            "game_dump_dir": "/workspace/ps4_dump/CUSA12878-patch",
            "template_dir": "Media/StreamingAssets/BeatmapLevelsData",
            "output_dir": "/workspace/orbeats/custom_songs",
        },
        "pipeline": {
            "default_target": "startmeup",
            "sample_rate": 44100,
        },
    }


@pytest.fixture
def song_ids_map():
    """A mock beat_saber_song_ids mapping."""
    return {
        "StartMeUp": "Start Me Up",
        "Angry": "Angry",
        "Crystallized": "Crystallized",
        "BadGuy": "bad guy",
    }


# ---------------------------------------------------------------------------
# Exp 248: PS4-safety net for ALL tests
# ---------------------------------------------------------------------------
# A webapp endpoint test once started a REAL `--features-only` pipeline job
# that pushed a stale local features.json over the user's live PS4 (turning
# the metadata flag off in-game). Structural fix: the webapp tests mock the
# runner (test_webapp_tools.py::no_real_jobs). This guard makes the RULE
# executable suite-wide: any lftp UPLOAD from inside the test suite fails
# loudly. Read-only lftp (get/ls/cls) is allowed — hardware-gated tests use
# those legitimately. Real-write hardware tests must mark `real_ps4_write`.
# ---------------------------------------------------------------------------
import subprocess as _sp

import pytest as _pytest


@_pytest.fixture(autouse=True)
def _block_real_ps4_uploads(monkeypatch):
    real_run = _sp.run

    def _guarded_run(cmd, *a, **kw):
        tokens = [str(c) for c in cmd] if isinstance(cmd, list) else [str(cmd)]
        if tokens and tokens[0] == "lftp":
            joined = " ".join(tokens)
            # uploads: put/push. Downloads + listings pass through.
            if " put " in f" {joined} " or "mirror -R" in joined:
                raise AssertionError(
                    "BLOCKED (Exp 248): a test attempted a real PS4 UPLOAD via "
                    f"lftp: {joined[:120]} — tests must mock state writes; "
                    "deliberate hardware write-tests need the real_ps4_write marker.")
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(_sp, "run", _guarded_run)
    yield


@pytest.fixture(autouse=True)
def isolated_recovery_archive(tmp_path, monkeypatch):
    """Host tests must not share recovery journals or touch operator archives."""
    import console_transaction
    monkeypatch.setattr(console_transaction, "LOCAL_BACKUPS", tmp_path / "recovery")
