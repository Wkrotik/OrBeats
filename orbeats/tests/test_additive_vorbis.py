"""Production Vorbis selection/validation, normal CLI and safe PCM fallbacks."""

import copy
import io
import json
import shutil
import struct
import sys
from pathlib import Path

import pytest
from test_additive_companion import StrictFTP, app, lib
from test_vorbis_audio_probe import ogg, ogg48  # noqa: F401 -- shared synthetic fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "development/scripts"))
sys.path.insert(0, str(ROOT / "webapp"))
import import_v3_additive as importer
import prepare_additive_bundle as prepare
import vorbis_audio

TEMPLATE = ROOT / "custom_songs/quick_test.bundle"


@pytest.fixture
def source(ogg, tmp_path):  # noqa: F811 -- pytest fixture injection
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")
    from PIL import Image

    folder = tmp_path / "source"
    prepare.generate_probe(folder)
    (folder / "song.egg").write_bytes(ogg)
    Image.new("RGB", (64, 64), "blue").save(folder / "cover.png")
    info = json.loads((folder / "Info.dat").read_bytes())
    info.update(_songFilename="song.egg", _coverImageFilename="cover.png", _previewStartTime=1, _previewDuration=1)
    (folder / "Info.dat").write_text(json.dumps(info))
    return folder


@pytest.fixture
def normalized(source, tmp_path):
    out = tmp_path / "normalized"
    importer.import_song(source, out)
    return out


def make(normalized, source, tmp_path, name="prepared", template=TEMPLATE):
    out = tmp_path / name
    manifest = prepare.prepare(normalized, template, out, original_audio=source / "song.egg")
    return manifest, out


def test_preferred_audio_is_original_packets_deterministic_and_independently_decoded(normalized, source, tmp_path):
    import numpy as np
    import soundfile as sf
    import UnityPy

    pcm = prepare.prepare(normalized, TEMPLATE, tmp_path / "pcm")
    a, out = make(normalized, source, tmp_path)
    b, other = make(normalized, source, tmp_path, "other")
    assert a == b and a["audio_codec"] == "vorbis"
    assert a["level_id"] != pcm["level_id"] and a["pcm_level_id"] == pcm["level_id"]
    assert a["audio_profile"] == vorbis_audio.PROFILE
    assert a["pcm_frames"] == pcm["pcm_frames"] == 12 * 44100 + 1
    assert a["difficulties"] == pcm["difficulties"] and a["note_counts"] == pcm["note_counts"]
    assert a["bundle"]["bytes"] < pcm["bundle"]["bytes"] / 3
    assert not a["runtime_ready"] and not a["deployment_attempted"]
    blob = (out / a["bundle"]["file"]).read_bytes()
    assert blob == (other / b["bundle"]["file"]).read_bytes()
    env = UnityPy.load(blob)
    bundle = next(iter(env.files.values()))
    fsb = bundle.files[a["cab_name"] + ".resource"].bytes
    reconstructed, frames = vorbis_audio.reconstruct_ogg(fsb)
    original_packets, _ = vorbis_audio.parse_ogg((source / "song.egg").read_bytes())
    reconstructed_packets, _ = vorbis_audio.parse_ogg(reconstructed)
    assert original_packets[2:] == reconstructed_packets[2:]
    original, rate = sf.read(source / "song.egg", dtype="float32", always_2d=True)
    decoded, rate2 = sf.read(io.BytesIO(reconstructed), dtype="float32", always_2d=True)
    assert frames == len(original) and rate == rate2 == 44100
    assert np.array_equal(original, decoded)
    clip = next(o.read_typetree() for o in env.objects if o.class_id == 83)
    assert (
        clip["m_CompressionFormat"],
        clip["m_LoadType"],
        clip["m_PreloadAudioData"],
        clip["m_LoadInBackground"],
    ) == (1, 0, True, False)
    prepare.validate(out, prepare.load_song(normalized))
    prepare.validate(out)  # No original source or proprietary FMOD decoder required.


@pytest.mark.parametrize("problem", ["python", "native", "codebook", "frames", "crc", "chain", "profile", "wav"])
def test_unsupported_compression_keeps_identical_pcm_and_explicit_reason(
    normalized, source, tmp_path, monkeypatch, problem
):
    baseline = prepare.prepare(normalized, TEMPLATE, tmp_path / "baseline")
    audio = source / "song.egg"
    if problem in ("python", "native"):

        def absent(_, **kw):
            raise (ImportError if problem == "python" else OSError)("fixture unavailable")

        monkeypatch.setattr(vorbis_audio, "build_fsb", absent)
    elif problem == "codebook":
        import zlib

        import fsb5.vorbis_headers

        packets, _ = vorbis_audio.parse_ogg(audio.read_bytes())
        monkeypatch.delitem(fsb5.vorbis_headers.lookup, zlib.crc32(packets[2]))
    elif problem == "frames":
        fsb, frames, crc = vorbis_audio.build_fsb(audio.read_bytes())
        monkeypatch.setattr(vorbis_audio, "build_fsb", lambda _, **kw: (fsb, frames + 1, crc))
    elif problem == "crc":
        raw = bytearray(audio.read_bytes())
        raw[-1] ^= 1
        audio.write_bytes(raw)
    elif problem == "chain":
        audio.write_bytes(audio.read_bytes() * 2)
    elif problem == "profile":
        import numpy as np
        import soundfile as sf

        sf.write(audio, np.zeros((48000 * 12, 1)), 48000, format="OGG", subtype="VORBIS")
    else:
        audio.write_bytes((source / "probe.wav").read_bytes())
    manifest, out = make(normalized, source, tmp_path)
    assert manifest["audio_codec"] == "pcm16" and manifest["audio_fallback_reason"]
    assert manifest["level_id"] == baseline["level_id"]
    assert (out / manifest["bundle"]["file"]).read_bytes() == (
        tmp_path / "baseline" / baseline["bundle"]["file"]
    ).read_bytes()
    prepare.validate(out, prepare.load_song(normalized))


def test_selected_codec_verification_failure_is_fatal_not_silent_fallback(normalized, source, tmp_path, monkeypatch):
    def invalid(*a, **kw):
        raise ValueError("fixture independent decoder mismatch")

    monkeypatch.setattr(vorbis_audio, "verify_fsb", invalid)
    with pytest.raises(ValueError, match="independent decoder mismatch"):
        make(normalized, source, tmp_path)
    assert not (tmp_path / "prepared").exists()


@pytest.mark.parametrize(
    "problem",
    [
        "seek_sample",
        "seek_offset",
        "format",
        "setup",
        "packet",
        "descriptor",
        "terminator",
        "padding",
        "clip",
        "profile",
        "wrong_audio",
    ],
)
def test_saved_compressed_corruption_rejected_even_after_matching_bundle_hash(normalized, source, tmp_path, problem):
    import UnityPy
    from UnityPy.streams import EndianBinaryReader

    manifest, out = make(normalized, source, tmp_path)
    env = UnityPy.load(str(out / manifest["bundle"]["file"]))
    bundle = next(iter(env.files.values()))
    fsb = bytearray(bundle.files[manifest["cab_name"] + ".resource"].bytes)
    clip_obj = next(o for o in env.objects if o.class_id == 83)
    clip = clip_obj.read_typetree()
    if problem == "seek_sample":
        struct.pack_into("I", fsb, 80, 17)
    elif problem == "seek_offset":
        struct.pack_into("I", fsb, 84, 1)
    elif problem == "format":
        struct.pack_into("I", fsb, 28, 0)
    elif problem == "setup":
        struct.pack_into("I", fsb, 72, 0)
    elif problem == "packet":
        start = 60 + struct.unpack_from("<I", fsb, 12)[0]
        fsb[start + 2] |= 1
    elif problem == "descriptor":
        fsb[64] ^= 4
    elif problem == "terminator":
        fsb[-2:] = b"xx"
    elif problem == "padding":
        start = 60 + struct.unpack_from("<I", fsb, 12)[0]
        # This fixture's seek table lands exactly on a16-byte boundary. Add
        # one extra aligned block, then corrupt it (header/section lengths agree).
        fsb[start:start] = bytes(16)
        struct.pack_into("<I", fsb, 12, start - 60 + 16)
        fsb[start + 15] = 1
    elif problem == "clip":
        clip["m_LoadType"] = 1
    elif problem == "profile":
        manifest["audio_profile"] = "unknown"
    else:
        import numpy as np
        import soundfile as sf

        different = io.BytesIO()
        sf.write(
            different,
            np.zeros((manifest["pcm_frames"], 2)),
            44100,
            format="OGG",
            subtype="VORBIS",
            compression_level=0.5,
        )
        fsb = vorbis_audio.build_fsb(different.getvalue())[0]
    resource = EndianBinaryReader(bytes(fsb))
    resource.flags = 0
    resource.BaseOffset = 0
    bundle.files[manifest["cab_name"] + ".resource"] = resource
    clip["m_Resource"]["m_Size"] = len(fsb)
    clip_obj.save_typetree(clip)
    blob = bundle.save(packer="none")
    (out / manifest["bundle"]["file"]).write_bytes(blob)
    manifest["bundle"].update(bytes=len(blob), sha256=prepare.digest(blob))
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        prepare.validate(out, prepare.load_song(normalized))


def ftp_state():
    import hashlib

    plugin = b"ELF fixture"
    return {
        lib.BASE + "/library.bin": lib.encode([]),
        lib.BASE + "/template.bundle": TEMPLATE.read_bytes(),
        "/data/GoldHEN/plugins/orbeats.prx": plugin,
        lib.BASE + "/companion-protocol.json": json.dumps(
            {
                "schema": 1,
                "title": "CUSA12878",
                "max_songs": 64,
                "active_elf_sha256": hashlib.sha256(plugin).hexdigest(),
            }
        ).encode(),
        "/data/GoldHEN/AFR/CUSA12878/features.json": json.dumps(
            {"enable_plugin": True, "enable_additive_song_packs": True}
        ).encode(),
    }


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("existing_pcm", [False, True])
def test_real_install_first_compressed_map_reimport_and_existing_pcm_preserved(
    source,
    tmp_path,
    monkeypatch,
    existing_pcm,
    rate,
    ogg48,  # noqa: F811 -- pytest fixture injection
):
    if rate == 48000:
        (source / "song.egg").write_bytes(ogg48)
    normalized = tmp_path / "normalized"
    importer.import_song(source, normalized)
    files = ftp_state()
    if existing_pcm:
        import prepare_additive_media as media

        pcm = prepare.prepare(normalized, TEMPLATE, tmp_path / "pcm")
        menu = tmp_path / "menu"
        m = media.prepare(source, tmp_path / "pcm/manifest.json", menu)
        blobs = [
            (tmp_path / "pcm" / pcm["bundle"]["file"]).read_bytes(),
            (menu / "song-cover.png").read_bytes(),
            (menu / "preview.wav").read_bytes(),
        ]
        song = lib.descriptor(pcm, *blobs, m["preview_duration_seconds"])
        files[lib.BASE + "/library.bin"] = lib.encode([song])
        files.update(zip(lib.paths(song), blobs))
    ftp = StrictFTP(files)
    monkeypatch.setattr(app, "FTP", lambda: ftp)
    config = {"title": {"id": "CUSA12878"}, "ps4": {"ip": "fake"}}
    result = app.install(config, song_dir=str(source), report_dir=tmp_path / "reports")
    assert result["already_present"] == existing_pcm
    assert result["count"] == 1
    songs = lib.decode(ftp.files[lib.BASE + "/library.bin"])
    if existing_pcm:
        assert ftp.files == files
    else:
        import UnityPy

        bundle = app.checked_bundle(ftp, songs[0])
        env = UnityPy.load(bundle)
        clip = next(o.read_typetree() for o in env.objects if o.class_id == 83)
        assert clip["m_CompressionFormat"] == 1 and clip["m_Frequency"] == rate
    old = copy.deepcopy(ftp.files)
    again = app.install(config, song_dir=str(source), report_dir=tmp_path / "reports")
    assert again["already_present"] and again["count"] == 1
    assert ftp.files == old
    assert lib.BASE + "/.install-lock" not in ftp.directories
    for path, blob in files.items():
        if not path.endswith("/library.bin"):
            assert ftp.files[path] == blob


def test_expert_only_compressed_template_supports_all_later_authored_difficulties(normalized, source, tmp_path):
    import UnityPy

    limited = tmp_path / "limited"
    shutil.copytree(normalized, limited)
    path = limited / "Info.dat"
    info = json.loads(path.read_bytes())
    info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"] = [
        d for d in info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"] if d["_difficulty"] == "Expert"
    ]
    path.write_text(json.dumps(info))
    one, directory = make(limited, source, tmp_path, "expert-only")
    template = directory / one["bundle"]["file"]
    # Make every target chart different so aliasing cloned TextAssets/lights
    # cannot hide behind the generated fixture's otherwise identical patterns.
    for index, name in enumerate(prepare.DIFFICULTIES):
        chart_path = normalized / (name + ".dat")
        chart = json.loads(chart_path.read_bytes())
        chart["colorNotes"][0]["x"] = index % 4
        chart["basicBeatmapEvents"] = [{"b": 1 + index, "et": 0, "i": index, "f": 1.0}]
        chart_path.write_text(json.dumps(chart))
    five, out = make(normalized, source, tmp_path, "all-five", template=template)
    assert len(five["difficulties"]) == 5 and five["audio_codec"] == "vorbis"
    prepare.validate(out, prepare.load_song(normalized))
    # Also prove the PCM fallback generates fresh PCM headers from this same
    # compressed single-difficulty template, not its codec or seek metadata.
    pcm = prepare.prepare(normalized, template, tmp_path / "pcm-from-expert")
    assert pcm["audio_codec"] == "pcm16" and len(pcm["difficulties"]) == 5
    prepare.validate(tmp_path / "pcm-from-expert", prepare.load_song(normalized))
    env = UnityPy.load(str(out / five["bundle"]["file"]))
    level = next(o.read_typetree() for o in env.objects if o.class_id == 114)
    entries = level["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"]
    assert len({e["_beatmapAsset"]["m_PathID"] for e in entries}) == 5
    assert len({e["_lightshowAsset"]["m_PathID"] for e in entries}) == 5
    container = next(o.read_typetree() for o in env.objects if o.class_id == 142)
    preloads = {e["m_PathID"] for e in container["m_PreloadTable"]}
    assert all(
        e["_beatmapAsset"]["m_PathID"] in preloads and e["_lightshowAsset"]["m_PathID"] in preloads for e in entries
    )


def test_exact_id_with_modified_content_cannot_evade_retained_bundle_verification(source, tmp_path, monkeypatch):
    import hashlib

    import UnityPy

    ftp = StrictFTP(ftp_state())
    monkeypatch.setattr(app, "FTP", lambda: ftp)
    config = {"title": {"id": "CUSA12878"}, "ps4": {"ip": "fake"}}
    app.install(config, song_dir=str(source), report_dir=tmp_path / "reports")
    songs = lib.decode(ftp.files[lib.BASE + "/library.bin"])
    path = lib.paths(songs[0])[0]
    env = UnityPy.load(ftp.files[path])
    # Simulate an externally modified descriptor with matching SHA/FNV. Content
    # verification must still reject the clip load mode before any publication.
    clip = next(o for o in env.objects if o.class_id == 83)
    tree = clip.read_typetree()
    tree["m_LoadType"] = 1
    clip.save_typetree(tree)
    blob = next(iter(env.files.values())).save(packer="none")
    songs[0].update(bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(), fnv=lib.fnv(blob))
    ftp.files[path] = blob
    ftp.files[lib.BASE + "/library.bin"] = lib.encode(songs)
    before = copy.deepcopy(ftp.files)
    with pytest.raises(ValueError, match="audio resource/header"):
        app.install(config, song_dir=str(source), report_dir=tmp_path / "reports")
    assert ftp.files == before
    assert lib.BASE + "/.install-lock" not in ftp.directories


def test_v4_normalization_retains_original_audio_for_compressed_installer(source, tmp_path, monkeypatch):
    # The production V4 adapter must carry the original Vorbis file through the
    # intermediate InfoV2 folder, rather than selecting its decoded PCM instead.
    info = {
        "version": "4.0.0",
        "song": {"title": "V4 compressed test", "author": "Synthetic"},
        "audio": {
            "songFilename": "song.egg",
            "songDuration": 12,
            "audioDataFilename": "AudioData.dat",
            "bpm": 120,
            "previewStartTime": 1,
            "previewDuration": 1,
        },
        "coverImageFilename": "cover.png",
        "difficultyBeatmaps": [
            {
                "characteristic": "Standard",
                "difficulty": "Expert",
                "beatmapDataFilename": "Expert.dat",
                "lightshowDataFilename": "Lightshow.dat",
                "noteJumpMovementSpeed": 10,
                "noteJumpStartBeatOffset": 0,
            }
        ],
    }
    chart = {
        "version": "4.0.0",
        "colorNotes": [{"b": 4, "i": 0}],
        "colorNotesData": [{"x": 1, "y": 0, "c": 0, "d": 1, "a": 0}],
    }
    (source / "Info.dat").write_text(json.dumps(info))
    (source / "Expert.dat").write_text(json.dumps(chart))
    (source / "Lightshow.dat").write_text(json.dumps({"version": "4.0.0"}))
    # AudioData uses original exact sample coordinates.
    import soundfile as sf

    samples = sf.info(source / "song.egg").frames
    (source / "AudioData.dat").write_text(
        json.dumps(
            {
                "version": "4.0.0",
                "songSampleCount": samples,
                "songFrequency": 44100,
                "bpmData": [{"si": 0, "ei": samples, "sb": 0, "eb": samples / 44100 * 2}],
            }
        )
    )
    ftp = StrictFTP(ftp_state())
    monkeypatch.setattr(app, "FTP", lambda: ftp)
    result = app.install(
        {"title": {"id": "CUSA12878"}, "ps4": {"ip": "fake"}}, song_dir=str(source), report_dir=tmp_path / "reports"
    )
    assert result["count"] == 1
    import UnityPy

    song = lib.decode(ftp.files[lib.BASE + "/library.bin"])[0]
    env = UnityPy.load(app.checked_bundle(ftp, song))
    assert next(o.read_typetree() for o in env.objects if o.class_id == 83)["m_CompressionFormat"] == 1


@pytest.mark.parametrize("keep_other", [False, True])
def test_compressed_test_map_removal_uses_normal_guarded_manager_and_retains_last_seed(
    normalized, source, tmp_path, monkeypatch, keep_other
):
    import library_manager as manager
    import prepare_additive_media as media
    from test_additive_companion import synthetic
    from test_companion_management import CONFIG, Console

    manifest, out = make(normalized, source, tmp_path)
    assert manifest["audio_codec"] == "vorbis"
    menu = tmp_path / "menu"
    menu_manifest = media.prepare(source, out / "manifest.json", menu)
    blob = (out / manifest["bundle"]["file"]).read_bytes()
    blobs = [blob, (menu / "song-cover.png").read_bytes(), (menu / "preview.wav").read_bytes()]
    song = lib.descriptor(manifest, *blobs, menu_manifest["preview_duration_seconds"])
    song["title"] += " [Vorbis test]"
    files = dict(zip(lib.paths(song), blobs))
    songs = [song]
    other_files = {}
    if keep_other:
        other, other_files = synthetic(7)
        songs.append(other)
        files.update(other_files)
    files[lib.BASE + "/library.bin"] = lib.encode(songs)
    files["/data/unrelated/keep"] = b"unchanged"
    ftp = Console(files)
    monkeypatch.setattr(manager, "FTP", lambda: ftp)
    result = manager.remove(CONFIG, song["id"])
    assert result["ok"] and result["count"] == int(keep_other)
    assert not result["cleanup_pending"]
    assert ftp.files[lib.BASE + "/library.bin"] == lib.encode(songs[1:])
    assert [s["id"] for s in lib.decode(ftp.files[lib.BASE + "/library.bin"])] == [s["id"] for s in songs[1:]]
    assert all(path not in ftp.files for path in lib.paths(song))
    assert all(ftp.files[path] == data for path, data in other_files.items())
    assert ftp.files["/data/unrelated/keep"] == b"unchanged"
    assert lib.BASE + "/.install-lock" not in ftp.directories
    if not keep_other:
        assert ftp.files[lib.BASE + "/template.bundle"] == blob
    assert all(path.startswith(lib.BASE + "/" + song["id"]) or
               path.startswith(lib.BASE + "/library.bin.rollback-") for path in ftp.deletes)
    assert not any('.backup-' in path or '.rollback-' in path for path in ftp.files)


@pytest.fixture
def prepared48(source, ogg48, tmp_path):  # noqa: F811 -- pytest fixture injection
    (source / "song.egg").write_bytes(ogg48)
    normalized = tmp_path / "normalized48"
    importer.import_song(source, normalized)
    manifest, out = make(normalized, source, tmp_path)
    return source, normalized, manifest, out


def test_normal_48k_import_keeps_packets_frames_and_all_timing(prepared48, tmp_path):
    import gzip

    import numpy as np
    import soundfile as sf
    import UnityPy

    source, normalized, manifest, out = prepared48
    assert manifest["audio_sample_rate"] == 48000
    assert manifest["audio_codec"] == "vorbis"
    assert manifest["audio_profile"] == vorbis_audio.PROFILE_48000
    assert manifest["pcm_frames"] == 12 * 48000 + 1
    assert manifest["duration_seconds"] == manifest["pcm_frames"] / 48000
    again, other = make(normalized, source, tmp_path, "again")
    assert again == manifest
    env = UnityPy.load(str(out / manifest["bundle"]["file"]))
    bundle = next(iter(env.files.values()))
    fsb = bundle.files[manifest["cab_name"] + ".resource"].bytes
    original = (source / "song.egg").read_bytes()
    rebuilt, frames = vorbis_audio.reconstruct_ogg(fsb, sample_rate=48000)
    assert (
        vorbis_audio.parse_ogg(original, sample_rate=48000)[0][2:]
        == vorbis_audio.parse_ogg(rebuilt, sample_rate=48000)[0][2:]
    )
    assert np.array_equal(sf.read(io.BytesIO(original))[0], sf.read(io.BytesIO(rebuilt))[0])
    clip = next(o.read_typetree() for o in env.objects if o.class_id == 83)
    assert clip["m_Frequency"] == 48000 and clip["m_CompressionFormat"] == 1
    level = next(o.read_typetree() for o in env.objects if o.class_id == 114)
    audio_obj = bundle.files[manifest["cab_name"]].objects[level["_audioDataAsset"]["m_PathID"]]
    data = json.loads(gzip.decompress(audio_obj.read_typetree()["m_Script"].encode("utf-8", "surrogateescape")))
    assert (data["songSampleCount"], data["songFrequency"], data["bpmData"][0]["ei"]) == (frames, 48000, frames)
    assert data["bpmData"][0]["eb"] == frames / 48000 * manifest["bpm"] / 60
    prepare.validate(out, prepare.load_song(normalized))
    prepare.validate(out)
    # Existing44.1kHz PCM identity is retained; no new duplicate on reimport.
    pcm = prepare.prepare(normalized, TEMPLATE, tmp_path / "pcm48baseline")
    assert manifest["pcm_level_id"] == pcm["level_id"]
    assert (manifest["difficulties"], manifest["difficulty_stats"], manifest["note_counts"]) == (
        pcm["difficulties"],
        pcm["difficulty_stats"],
        pcm["note_counts"],
    )


@pytest.mark.parametrize(
    "problem",
    [
        "manifest_rate",
        "manifest_frames",
        "duration",
        "clip_rate",
        "audio_rate",
        "audio_frames",
        "bpm",
        "profile",
        "wrong_audio",
    ],
)
def test_48k_independent_validation_rejects_matching_hash_corruption(prepared48, problem):
    import gzip

    import numpy as np
    import soundfile as sf
    import UnityPy
    from UnityPy.streams import EndianBinaryReader

    _, normalized, manifest, out = prepared48
    env = UnityPy.load(str(out / manifest["bundle"]["file"]))
    bundle = next(iter(env.files.values()))
    clip_obj = next(o for o in env.objects if o.class_id == 83)
    clip = clip_obj.read_typetree()
    level = next(o.read_typetree() for o in env.objects if o.class_id == 114)
    audio_obj = bundle.files[manifest["cab_name"]].objects[level["_audioDataAsset"]["m_PathID"]]
    audio_tree = audio_obj.read_typetree()
    data = json.loads(gzip.decompress(audio_tree["m_Script"].encode("utf-8", "surrogateescape")))
    if problem == "manifest_rate":
        manifest["audio_sample_rate"] = 44100
    elif problem == "manifest_frames":
        manifest["pcm_frames"] += 1
    elif problem == "duration":
        manifest["duration_seconds"] += 1
    elif problem == "clip_rate":
        clip["m_Frequency"] = 44100
    elif problem == "audio_rate":
        data["songFrequency"] = 44100
    elif problem == "audio_frames":
        data["songSampleCount"] += 1
    elif problem == "bpm":
        data["bpmData"][0]["eb"] += 1
    elif problem == "profile":
        manifest["audio_profile"] = vorbis_audio.PROFILE
    else:
        stream = io.BytesIO()
        sf.write(
            stream, np.zeros((manifest["pcm_frames"], 2)), 48000, format="OGG", subtype="VORBIS", compression_level=0.5
        )
        fsb, _, _ = vorbis_audio.build_fsb(stream.getvalue(), sample_rate=48000)
        resource = EndianBinaryReader(fsb)
        resource.flags = 0
        resource.BaseOffset = 0
        bundle.files[manifest["cab_name"] + ".resource"] = resource
        clip["m_Resource"]["m_Size"] = len(fsb)
    audio_tree["m_Script"] = gzip.compress(prepare.canonical(data), mtime=0).decode("utf-8", "surrogateescape")
    audio_obj.save_typetree(audio_tree)
    clip_obj.save_typetree(clip)
    blob = bundle.save(packer="none")
    (out / manifest["bundle"]["file"]).write_bytes(blob)
    manifest["bundle"].update(bytes=len(blob), sha256=prepare.digest(blob))
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        prepare.validate(out, prepare.load_song(normalized))


@pytest.mark.parametrize("problem", ["codebook", "duration", "selection"])
def test_48k_unsupported_setup_or_duration_uses_unchanged_pcm(source, ogg48, tmp_path, monkeypatch, problem):  # noqa: F811 -- pytest fixture injection
    import zlib

    import fsb5.vorbis_headers

    (source / "song.egg").write_bytes(ogg48)
    normalized = tmp_path / "normalized48"
    importer.import_song(source, normalized)
    if problem == "codebook":
        packets, _ = vorbis_audio.parse_ogg(ogg48, sample_rate=48000)
        monkeypatch.delitem(fsb5.vorbis_headers.lookup, zlib.crc32(packets[2]))
    elif problem == "duration":
        fsb, frames, crc = vorbis_audio.build_fsb(ogg48, sample_rate=48000)
        monkeypatch.setattr(vorbis_audio, "build_fsb", lambda *a, **kw: (fsb, frames + 100, crc))
    else:
        # Selection errors only: do not make a later verification failure soft.
        monkeypatch.setattr(
            vorbis_audio, "build_fsb", lambda *a, **kw: (_ for _ in ()).throw(ValueError("unsupported source profile"))
        )
    pcm = prepare.prepare(normalized, TEMPLATE, tmp_path / "pcm")
    manifest, out = make(normalized, source, tmp_path)
    assert manifest["audio_codec"] == "pcm16" and manifest["audio_sample_rate"] == 44100
    assert manifest["level_id"] == pcm["level_id"] and manifest["audio_fallback_reason"]
    assert (out / manifest["bundle"]["file"]).read_bytes() == (tmp_path / "pcm" / pcm["bundle"]["file"]).read_bytes()


@pytest.mark.parametrize("rate", [32000, 96000])
def test_unproven_rates_still_fall_back(source, tmp_path, rate):
    import numpy as np
    import soundfile as sf

    sf.write(source / "song.egg", np.zeros((rate * 12, 2)), rate, format="OGG", subtype="VORBIS")
    normalized = tmp_path / "normalized"
    importer.import_song(source, normalized)
    manifest, out = make(normalized, source, tmp_path)
    assert manifest["audio_codec"] == "pcm16" and manifest["audio_sample_rate"] == 44100
    assert "sample rate" in manifest["audio_fallback_reason"]
    prepare.validate(out, prepare.load_song(normalized))


def test_48k_selected_decoder_failure_does_not_downgrade_to_pcm(prepared48, tmp_path, monkeypatch):
    source, normalized, _, _ = prepared48

    def invalid(*a, **kw):
        raise ValueError("48k independent decoder mismatch")

    monkeypatch.setattr(vorbis_audio, "verify_fsb", invalid)
    with pytest.raises(ValueError, match="48k independent decoder mismatch"):
        make(normalized, source, tmp_path, "must-not-publish")
    assert not (tmp_path / "must-not-publish").exists()


def test_48k_template_does_not_leak_rate_into_later_44100_or_pcm(prepared48, source, ogg, tmp_path):  # noqa: F811 -- pytest fixture injection
    src, _, first, first_dir = prepared48
    template = first_dir / first["bundle"]["file"]
    (src / "song.egg").write_bytes(ogg)
    normalized = tmp_path / "later44100"
    importer.import_song(src, normalized)
    manifest, out = make(normalized, src, tmp_path, "44100-from48", template=template)
    assert manifest["audio_sample_rate"] == 44100 and manifest["audio_profile"] == vorbis_audio.PROFILE
    prepare.validate(out, prepare.load_song(normalized))
    pcm = prepare.prepare(normalized, template, tmp_path / "pcm-from48")
    assert pcm["audio_sample_rate"] == 44100 and pcm["audio_codec"] == "pcm16"
    prepare.validate(tmp_path / "pcm-from48", prepare.load_song(normalized))
