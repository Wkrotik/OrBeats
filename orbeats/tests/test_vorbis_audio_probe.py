"""Offline codec experiment: original packets, independent FMOD decode and seeks."""

import importlib.util
import io
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "development/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("vorbis_probe_test", SCRIPTS / "probe_vorbis_audio.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.fixture
def ogg():
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("fsb5")
    try:
        __import__("fsb5.vorbis")
    except OSError as exc:
        pytest.skip(f"optional developer libvorbis unavailable: {exc}")
    time = np.arange(12 * 44100 + 1) / 44100
    data = np.stack([0.25 * np.sin(2 * np.pi * 440 * time), 0.2 * np.sin(2 * np.pi * 660 * time)], axis=1)
    stream = io.BytesIO()
    sf.write(stream, data, 44100, format="OGG", subtype="VORBIS", compression_level=0.5)
    return stream.getvalue()


def test_fsb_preserves_original_packets_and_exact_non_aligned_count(ogg):
    import fsb5

    packets, frames = probe.parse_ogg(ogg)
    fsb, count, crc = probe.build_fsb(ogg)
    assert count == frames == 12 * 44100 + 1
    bank = fsb5.FSB5(fsb)
    assert bank.header.mode == fsb5.SoundFormat.VORBIS
    assert bank.samples[0].samples == frames
    assert bank.samples[0].frequency == 44100
    assert bank.samples[0].channels == 2
    assert struct.unpack_from("<I", fsb, 28)[0] == 1
    offset = 60 + bank.header.sampleHeadersSize
    for packet in packets[3:]:
        length = struct.unpack_from("<H", fsb, offset)[0]
        assert length == len(packet)
        assert fsb[offset + 2 : offset + 2 + length] == packet
        offset += 2 + length
    assert fsb[offset:] == b"\0\0"
    assert struct.unpack_from("<I", fsb, 72)[0] == crc
    table_bytes = struct.unpack_from("<I", fsb, 76)[0]
    assert table_bytes >= 8 * 11 and table_bytes % 8 == 0
    table = [struct.unpack_from("<iI", fsb, 80 + i) for i in range(0, table_bytes, 8)]
    assert table[0] == (0, 0)
    assert all(a[0] < b[0] and a[1] < b[1] for a, b in zip(table, table[1:]))
    assert table[-1][0] < frames


def test_independent_fmod_decode_and_random_access(ogg):
    pytest.importorskip("fmod_toolkit")
    fsb, frames, _ = probe.build_fsb(ogg)
    report = probe.verify_audio(fsb, ogg, frames)
    assert report["decoded_frames"] == frames
    assert report["max_clipped_source_error"] <= 4 / 32768
    assert len(report["compressed_seek_checks"]) == 6
    assert report["packets_reencoded"] is False


@pytest.mark.parametrize("change", ["truncate", "crc", "trailing", "chain", "signature"])
def test_corrupt_or_chained_ogg_refused(ogg, change):
    if change == "truncate":
        bad = ogg[:-1]
    elif change == "crc":
        bad = ogg[:-1] + bytes([ogg[-1] ^ 1])
    elif change == "trailing":
        bad = ogg + b"junk"
    elif change == "chain":
        bad = ogg + ogg
    else:
        bad = b"OOPS" + ogg[4:]
    with pytest.raises(ValueError):
        probe.build_fsb(bad)


def test_unknown_or_mismatched_setup_refused(ogg, monkeypatch):
    import fsb5.vorbis
    import fsb5.vorbis_headers

    packets, _ = probe.parse_ogg(ogg)
    crc = probe.zlib.crc32(packets[2])
    monkeypatch.setattr(fsb5.vorbis, "get_header_info", lambda *args: (256, 2048, b"wrong setup"))
    with pytest.raises(ValueError, match="mismatch"):
        probe.build_fsb(ogg)
    monkeypatch.delitem(fsb5.vorbis_headers.lookup, crc)
    with pytest.raises(ValueError, match="unknown"):
        probe.build_fsb(ogg)


@pytest.mark.parametrize("rate,channels", [(48000, 2), (44100, 1)])
def test_unsupported_profiles_keep_pcm_fallback(ogg, rate, channels):
    import numpy as np
    import soundfile as sf

    stream = io.BytesIO()
    sf.write(stream, np.zeros((rate * 2, channels)), rate, format="OGG", subtype="VORBIS")
    with pytest.raises(ValueError, match="requires Vorbis stereo 44100"):
        probe.build_fsb(stream.getvalue())


def test_candidate_roundtrip_is_isolated_and_keeps_maps_and_source(ogg, tmp_path):
    pytest.importorskip("UnityPy")
    import prepare_additive_bundle as pcm
    import UnityPy

    song = tmp_path / "song"
    pcm.generate_probe(song)
    # Match the additional single sample in the compressed fixture.
    import wave

    path = song / "probe.wav"
    with wave.open(str(path), "rb") as wavefile:
        data = wavefile.readframes(wavefile.getnframes())
    with wave.open(str(path), "wb") as wavefile:
        wavefile.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
        wavefile.writeframes(data + bytes(4))
    source = tmp_path / "pcm"
    before = pcm.prepare(song, ROOT / "custom_songs/quick_test.bundle", source)
    audio = tmp_path / "source-audio" / "song.egg"
    audio.parent.mkdir()
    audio.write_bytes(ogg)
    bundle_source = source / before["bundle"]["file"]
    source_hash = pcm.digest(bundle_source.read_bytes())
    target = tmp_path / "vorbis"
    report = probe.prepare_candidate(source, audio, target)
    after = json.loads((target / "manifest.json").read_bytes())
    assert after["level_id"] != before["level_id"]
    assert after["cab_name"] != before["cab_name"]
    assert after["audio_format"].startswith("FSB5 Vorbis")
    assert after["kind"] == "orbeats_compressed_audio_probe"
    assert after["runtime_ready"] is False and after["deployment_attempted"] is False
    assert report["compressed_bundle_bytes"] < before["bundle"]["bytes"] / 3
    assert pcm.digest(bundle_source.read_bytes()) == source_hash
    assert audio.read_bytes() == ogg
    assert pcm.validate(source) == before
    with pytest.raises(ValueError):
        pcm.validate(target)  # Normal installer cannot accidentally accept the experiment.
    old = UnityPy.load(str(bundle_source))
    new = UnityPy.load(str(target / after["bundle"]["file"]))
    old_text = [obj.read_typetree()["m_Script"] for obj in old.objects if obj.class_id == 49]
    new_text = [obj.read_typetree()["m_Script"] for obj in new.objects if obj.class_id == 49]
    assert old_text == new_text
    clip = next(obj.read_typetree() for obj in new.objects if obj.class_id == 83)
    original_clip = next(obj.read_typetree() for obj in old.objects if obj.class_id == 83)
    for key in ("m_Length", "m_Channels", "m_Frequency", "m_LoadType", "m_PreloadAudioData"):
        assert clip[key] == original_clip[key]
    assert clip["m_CompressionFormat"] == 1 and clip["m_LoadType"] == 0
    with pytest.raises(ValueError, match="new and outside"):
        probe.prepare_candidate(source, audio, target)
    with pytest.raises(ValueError, match="new and outside"):
        probe.prepare_candidate(source, audio, source / "must-not-create")
    assert not (source / "must-not-create").exists()


def test_cli_optin_and_no_console_interface(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPTS / "probe_vorbis_audio.py")], capture_output=True, text=True)
    assert result.returncode != 0 and "--experimental" in result.stderr
    code = (SCRIPTS / "probe_vorbis_audio.py").read_text()
    for forbidden in ("from ftplib", "import socket", "storbinary", "--deploy", "--ps4-ip"):
        assert forbidden not in code


@pytest.fixture
def ogg48(ogg):
    import numpy as np
    import soundfile as sf

    t = np.arange(12 * 48000 + 1) / 48000
    data = np.stack([0.25 * np.sin(2 * np.pi * 440 * t), 0.2 * np.sin(2 * np.pi * 660 * t)], axis=1)
    stream = io.BytesIO()
    sf.write(stream, data, 48000, format="OGG", subtype="VORBIS", compression_level=0.5)
    return stream.getvalue()


def test_48k_profile_is_explicit_and_preserves_packets(ogg48, tmp_path):
    import fsb5
    import prepare_additive_bundle as pcm
    from vorbis_audio import build_fsb, reconstruct_ogg, verify_fsb

    with pytest.raises(ValueError, match="44100"):
        build_fsb(ogg48)
    fsb, frames, _ = build_fsb(ogg48, sample_rate=48000)
    bank = fsb5.FSB5(fsb)
    assert frames == 12 * 48000 + 1 and bank.samples[0].frequency == 48000
    rebuilt, count = reconstruct_ogg(fsb, sample_rate=48000)
    assert (
        count == frames
        and probe.parse_ogg(rebuilt, sample_rate=48000)[0][3:] == probe.parse_ogg(ogg48, sample_rate=48000)[0][3:]
    )
    assert verify_fsb(fsb, frames, sample_rate=48000)["packets_reencoded"] is False
    with pytest.raises(ValueError, match="descriptor"):
        verify_fsb(fsb, frames)
    for rate in [32000, 96000, 48000.0, True]:
        with pytest.raises(ValueError, match="sample rate"):
            build_fsb(ogg48, sample_rate=rate)
    source = tmp_path / "source.ogg"
    source.write_bytes(ogg48)
    selected, reason = pcm.select_audio(source, {"samples": 12 * 44100, "pcm": b""})
    assert selected is not None and reason is None  #48k path hardware-confirmed and promoted


def test_independent_48k_fmod_decode_and_random_seek(ogg48):
    pytest.importorskip("fmod_toolkit")
    fsb, frames, _ = probe.build_fsb(ogg48, sample_rate=48000)
    report = probe.verify_audio(fsb, ogg48, frames, sample_rate=48000)
    assert report["decoded_frames"] == frames and report["packets_reencoded"] is False
    assert len(report["compressed_seek_checks"]) == 6
    assert report["max_clipped_source_error"] <= 4 / 32768


def test_48k_candidate_updates_audio_data_coordinates(ogg48, tmp_path):
    import gzip

    import prepare_additive_bundle as pcm
    import UnityPy

    template = ROOT / "custom_songs/quick_test.bundle"
    if not template.is_file():
        pytest.skip("owned local template unavailable")
    song = tmp_path / "source"
    pcm.generate_probe(song)
    candidate = tmp_path / "pcm"
    pcm.prepare(song, template, candidate)
    audio = song / "original.ogg"
    audio.write_bytes(ogg48)
    output = tmp_path / "48k"
    report = probe.prepare_candidate(candidate, audio, output, sample_rate=48000)
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert report["sample_rate"] == 48000 and report["runtime_ready"] is False
    assert manifest["decoded_frames"] == 12 * 48000 + 1
    assert manifest["baseline_pcm_frames"] == 12 * 44100 and "pcm_frames" not in manifest
    env = UnityPy.load(str(output / manifest["bundle"]["file"]))
    clip = next(o.read_typetree() for o in env.objects if o.class_id == 83)
    assert clip["m_Frequency"] == 48000 and abs(clip["m_Length"] - (12 + 1 / 48000)) < 0.0001
    level = next(o.read_typetree() for o in env.objects if o.class_id == 114 and "_audioDataAsset" in o.read_typetree())
    pid = level["_audioDataAsset"]["m_PathID"]
    audio_tree = next(o.read_typetree() for o in env.objects if o.path_id == pid)
    data = json.loads(gzip.decompress(audio_tree["m_Script"].encode("utf-8", "surrogateescape")))
    assert data["songFrequency"] == 48000 and data["songSampleCount"] == data["bpmData"][0]["ei"] == 12 * 48000 + 1
    with pytest.raises(ValueError):
        pcm.validate(output)  # not a normal import
