"""Synthetic conversion/preflight regressions; no network, game inputs or PS4 writes."""

import copy
import hashlib
import json

import additive_companion as core
import additive_library as wire
import additive_v4_native as native
import pytest
from additive_presentation import color, v4_color, v4_difficulty_custom
from test_additive_v4_import import chart, prepare, source, v4
from test_fresh_library import FTP, synthetic


@pytest.mark.parametrize("value", ["D08D46FF", "d08d46ff", "D08D4680"])
def test_v4_hex_rgba_preserves_every_channel(value):
    expected = [int(value[i:i + 2], 16) / 255 for i in range(0, 8, 2)]
    assert color(v4_color(value)) == expected
    assert color(v4_difficulty_custom({"colorLeft": value})["_colorLeft"]) == expected
    with pytest.raises(ValueError, match="authored RGBA"):
        color(value)  # Do not silently widen the legacy/object-only schema.


@pytest.mark.parametrize("value", ["D08D46", "#D08D46FF", "D08D46FG", " D08D46FF", "D08D46FF ", "", 123, True])
def test_invalid_v4_colors_still_refused(value):
    with pytest.raises(ValueError, match="RGBA"):
        v4_color(value)


def test_real_v4_normalizer_converts_scheme_hex_without_changing_source(tmp_path):
    root, info = source(tmp_path)
    info["colorSchemes"] = [{"overrideNotes": True, "overrideLights": True,
                             "saberAColor": "D08D46FF", "obstaclesColor": "00AACBFF"}]
    info["difficultyBeatmaps"][0]["beatmapColorSchemeIdx"] = 0
    original = json.dumps(info).encode()
    (root / "Info.dat").write_bytes(original)
    out = tmp_path / "normalized"
    v4.normalize(root, out, prepare.local_file)
    normalized = json.loads((out / "Info.dat").read_text())
    scheme = normalized["_colorSchemes"][0]["colorScheme"]
    assert color(scheme["saberAColor"]) == [208 / 255, 141 / 255, 70 / 255, 1]
    assert color(scheme["obstaclesColor"]) == [0, 170 / 255, 203 / 255, 1]
    assert (root / "Info.dat").read_bytes() == original


def test_ps4_unsupported_wall_layer_is_explained_not_clamped():
    data = chart()
    data["obstaclesData"][0]["y"] = 3
    before = copy.deepcopy(data)
    with pytest.raises(ValueError, match=r"unsupported PS4 wall layer 3.*supported layers are 0\.\.2"):
        native.chart(data, 2)
    assert data == before
    data["obstaclesData"][0]["y"] = 2
    assert native.chart(data, 2) > 0
    data["colorNotesData"][0]["y"] = 3
    with pytest.raises(ValueError, match="colorNotesData.y"):
        native.chart(data, 2)


class InstallFTP(FTP):
    def __init__(self, files):
        super().__init__(files, dirs=("/", "/data", "/mnt/sandbox"))
        self.reads = []
        self.locks = []

    def mkd(self, path):
        assert path == wire.BASE + "/.install-lock"
        self.dirs.add(path)
        self.locks.append("acquired")

    def rmd(self, path):
        assert path == wire.BASE + "/.install-lock"
        self.dirs.remove(path)
        self.locks.append("released")

    def retrbinary(self, command, callback):
        self.reads.append(command.removeprefix("RETR "))
        super().retrbinary(command, callback)

    def storbinary(self, *args):
        pytest.fail("Early duplicate detection must not upload or repair anything")


class ConversionReached(RuntimeError):
    pass


@pytest.fixture
def installed(monkeypatch, tmp_path):
    song, files = synthetic()
    song["title"] = "Swivel"
    metadata = {"id": "557a8", "versions": [{"hash": "a" * 40}]}
    path = wire.BASE + "/" + song["id"] + "-media/map-info.json"
    files[path] = json.dumps(metadata).encode()
    files[wire.BASE + "/library.bin"] = wire.encode([song])
    plugin = b"synthetic ELF"
    files["/data/GoldHEN/plugins/orbeats.prx"] = plugin
    files[wire.BASE + "/companion-protocol.json"] = json.dumps({"schema": 1, "title": "CUSA12878",
        "max_songs": 1, "active_elf_sha256": hashlib.sha256(plugin).hexdigest()}).encode()
    files["/data/GoldHEN/AFR/CUSA12878/features.json"] = b'{"enable_plugin":true,"enable_additive_song_packs":true}'
    ftp = InstallFTP(files)
    monkeypatch.setattr(core, "FTP", lambda: ftp)
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "Info.dat").write_text('{"_version":"2.1.0","_songName":"Swivel"}')
    (folder / "beatsaver-metadata.json").write_text(json.dumps(metadata))
    monkeypatch.setattr(core, "download", lambda *args: folder)

    def converter(*args):
        raise ConversionReached("No converter should be loaded for an installed revision")

    monkeypatch.setattr(core, "helper", converter)
    return ftp, song, metadata, path, folder, tmp_path / "reports"


def install_case(case, **kwargs):
    return core.install({"ps4": {"ip": "192.0.2.2"}, "title": {"id": "CUSA12878"}},
                        map_id="557a8", report_dir=case[-1], **kwargs)


@pytest.mark.parametrize("info", [{"_version": "2.1.0", "_songName": "Swivel"},
                                   {"version": "4.0.1", "song": {"title": "Swivel"}}])
def test_exact_installed_version_skips_all_converters_and_uploads(installed, info, capsys):
    ftp, song, metadata, path, folder, _ = installed
    (folder / "Info.dat").write_text(json.dumps(info))
    before = copy.deepcopy(ftp.files)
    result = install_case(installed)
    assert result == {"ok": True, "already_present": True, "title": "Swivel", "count": 1, "restart_required": False}
    assert "skipping conversion and upload" in capsys.readouterr().out
    assert ftp.files == before and ftp.locks == ["acquired", "released"] and ftp.closed
    assert all(p in ftp.reads for p in wire.paths(song))


@pytest.mark.parametrize("previous", [None, b"{bad", b"[]", b'{"id":"557a8"}',
    b'{"id":"557a8","versions":null}', b'{"id":"557a8","versions":[null]}',
    json.dumps({"id": "557a8", "versions": [{"hash": "b" * 40}, {"hash": "a" * 40}]}).encode(),
    json.dumps({"id": "ffff", "versions": [{"hash": "a" * 40}]}).encode()])
def test_same_title_missing_or_different_provenance_still_uses_conversion(installed, previous):
    ftp, _, _, path, _, _ = installed
    if previous is None:
        ftp.files.pop(path)
    else:
        ftp.files[path] = previous
    with pytest.raises(ConversionReached):
        install_case(installed)
    assert ftp.locks == ["acquired", "released"] and ftp.closed


@pytest.mark.parametrize("kind", [0, 1, 2])
def test_corrupt_installed_files_cannot_be_reported_as_success(installed, kind):
    ftp, song, *_ = installed
    ftp.files[wire.paths(song)[kind]] = b"corrupted"
    with pytest.raises(ValueError, match="verification failed"):
        install_case(installed)
    assert ftp.locks == ["acquired", "released"]


def test_unreadable_metadata_is_not_treated_as_absent(installed):
    ftp, _, _, path, *_ = installed
    ftp.denied.add(path)
    with pytest.raises(ValueError, match="Cannot read existing"):
        install_case(installed)


def test_local_sources_are_not_skipped_by_optional_beatsaver_metadata(installed):
    with pytest.raises(ConversionReached):
        install_case(installed, song_dir=str(installed[4]))


def test_library_changed_during_duplicate_check_is_not_success(installed, monkeypatch):
    ftp = installed[0]
    original = core.checked

    def checked(*args):
        result = original(*args)
        ftp.files[wire.BASE + "/library.bin"] = wire.encode([])
        return result

    monkeypatch.setattr(core, "checked", checked)
    with pytest.raises(ValueError, match="Library changed"):
        install_case(installed)


def test_duplicate_check_does_not_read_unrelated_maps_or_the_first_template(installed):
    ftp, song, *_ = installed
    unrelated = dict(song, id="bsd_additive_" + "b" * 24, title="Other map")
    ftp.files[wire.BASE + "/library.bin"] = wire.encode([unrelated, song])
    result = install_case(installed)
    assert result["already_present"] and result["count"] == 2
    assert not any(unrelated["id"] in path for path in ftp.reads)


def test_game_opened_during_duplicate_check_is_not_success(installed, monkeypatch):
    ftp = installed[0]
    original = core.checked

    def checked(*args):
        result = original(*args)
        ftp.dirs.add("/mnt/sandbox/CUSA12878-app0")
        return result

    monkeypatch.setattr(core, "checked", checked)
    with pytest.raises(ValueError, match="Fully close Beat Saber"):
        install_case(installed)


@pytest.mark.parametrize("metadata", [None, [], {}, {"id": None}, {"id": "557a8", "versions": []},
    {"id": "557a8", "versions": [{"hash": "not-a-content-hash"}]}])
def test_invalid_selected_version_cannot_be_installed_proof(installed, metadata):
    ftp, song, *_ = installed
    assert core.installed_version(ftp, [song], metadata, song["title"]) is None
    assert not ftp.reads


def test_compiled_legacy_defaults_are_not_installed_proof(installed, monkeypatch):
    ftp, song, *_ = installed
    monkeypatch.setattr(core, "load_library", lambda f: ([song], None))
    with pytest.raises(ConversionReached):
        install_case(installed)
    assert ftp.files[wire.BASE + "/library.bin"] == wire.encode([song])


def test_local_setup_template_avoids_remote_bundle_download(installed):
    ftp, song, _, path, _, reports = installed
    ftp.files.pop(path)  # No proven duplicate: exercise new-map preparation.
    template = reports.parent / "template.bundle"
    template.write_bytes(b"synthetic template; converter must validate it later")
    with pytest.raises(ConversionReached):
        core.install({"ps4": {"ip": "192.0.2.2"}, "title": {"id": "CUSA12878"},
                      "additive_template": str(template)}, map_id="557a8", report_dir=reports)
    assert wire.paths(song)[0] not in ftp.reads
    assert ftp.closed and ftp.locks == ["acquired", "released"]
