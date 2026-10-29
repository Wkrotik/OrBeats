"""Offline release-feed, optional-plugin and desktop presentation regressions."""

import hashlib
import json
import struct
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp"))
import extras_manager as extras
import release_updates as updates
from test_companion_management import Console, CONFIG, PLUGIN, INI
import library_manager as library

ROOT = Path(__file__).resolve().parents[2]


def artifact(tmp_path):
    # Synthetic bounded ELF/FSELF; no code, native artifact or game input needed.
    elf = bytearray(256)
    elf[:4] = b"\x7fELF"
    struct.pack_into("<Q", elf, 32, 64)
    struct.pack_into("<H", elf, 56, 1)
    struct.pack_into("<IIQQQQQQ", elf, 64, 1, 5, 0, 0, 0, 256, 256, 16)
    text = b"OrBeats Extras 0.0009: synthetic test\x00"
    elf[128 : 128 + len(text)] = text
    blob = bytearray(64)
    blob[:4] = bytes.fromhex("4f153d1d")
    struct.pack_into("<H", blob, 24, 1)
    struct.pack_into("<QQQQ", blob, 32, 0x2804, 64, 256, 256)
    p = tmp_path / "orbeats_extras.prx"
    p.write_bytes(blob + elf)
    return p


@pytest.mark.parametrize(
    "initial",
    [
        b"",
        b"; keep\r\n[CUSA12878]\r\n/other.prx\r\n",
        b"[CUSA12878]\n" + extras.TARGET.encode() + b"=false\n[OTHER]\n/keep.prx",
    ],
)
def test_extras_registration_preserves_main_and_other_sections(initial):
    merged = extras.registration(initial, enable=True)
    assert extras.registration(merged) == "enabled"
    assert extras.registration(merged, enable=True) == merged
    assert merged.count(extras.TARGET.encode()) == 1
    assert b"/other.prx" not in initial or b"/other.prx" in merged
    assert b"[OTHER]\n/keep.prx" not in initial or merged.endswith(b"[OTHER]\n/keep.prx")
    assert extras.TARGET.encode() in library.merge_ini(merged)


@pytest.mark.parametrize(
    "raw",
    [b"[default]\n" + extras.TARGET.encode(), b"[CUSA12878]\n" + (extras.TARGET.encode() + b"\n") * 2, b"bad\0ini"],
)
def test_extras_invalid_registration_refuses(raw):
    with pytest.raises(ValueError):
        extras.registration(raw, enable=True)


@pytest.mark.parametrize("failure", [False, True])
def test_extras_install_is_scoped_and_rollback_safe(monkeypatch, tmp_path, failure):
    # Deliberately opaque existing library/song bytes: Extras must neither load
    # nor migrate them. No user-owned baseline fixture is required in source CI.
    ftp = Console(
        {
            "/data/GoldHEN/AFR/CUSA12878/additive/library.bin": b"opaque-existing-library",
            "/data/other-game/keep": b"unchanged",
            "/data/GoldHEN/AFR/CUSA12878/additive/existing-song.bundle": b"opaque-song",
        }
    )
    monkeypatch.setattr(library, "FTP", lambda: ftp)
    ftp.files[PLUGIN] = b"\x7fELF=== OrBeats v0.8079 started ===\x00"
    ftp.files[INI] = b"; original\n[CUSA12878]\n" + PLUGIN.encode() + b"\n"
    ftp.files[extras.TARGET] = b"\x7fELFOrBeats Extras 0.0008: old test\x00"
    before = dict(ftp.files)
    if failure:
        ftp.fail_target = INI
        with pytest.raises(OSError):
            extras.deploy(CONFIG, artifact(tmp_path))
        assert all(ftp.files[p] == b for p, b in before.items())
    else:
        assert extras.deploy(CONFIG, artifact(tmp_path))["ok"]
        assert extras.version(library.core.read(ftp, extras.TARGET)) == "0.0009"
        assert all(ftp.files[p] == b for p, b in before.items() if p not in (INI, extras.TARGET))
    assert not any(p.endswith(".install-lock") for p in ftp.directories)


def manifest(blob=b"plugin"):
    return {
        "schema": 1,
        "app": "0.1.13",
        "plugins": {
            k: {
                "asset": v,
                "version": "0.8079" if k == "main" else "0.0009",
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
            }
            for k, v in updates.NAMES.items()
        },
    }


def feed(monkeypatch, record, blob=b"plugin"):
    prefix = "https://github.com/Wkrotik/OrBeats/releases/download/v0.1.13/"
    metadata = {
        "tag_name": "v0.1.13",
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": n, "browser_download_url": prefix + n} for n in ["release-manifest.json", *updates.NAMES.values()]
        ],
    }

    def read(url, limit):
        assert limit <= 2000000
        if url == updates.API:
            return json.dumps(metadata).encode()
        if url.endswith("release-manifest.json"):
            return json.dumps(record).encode()
        return blob

    monkeypatch.setattr(updates, "read", read)
    return metadata


def test_release_version_comparison_and_unknowns(monkeypatch):
    feed(monkeypatch, manifest())
    r = updates.check("0.8078", None)
    assert r["state"] == "checked"
    assert r["versions"]["main"]["update_available"] is True
    assert r["versions"]["app"]["update_available"] is False
    assert r["versions"]["extras"]["update_available"] is None


@pytest.mark.parametrize("bad", ["digest", "size", "url", "duplicate", "draft", "tag"])
def test_release_invalid_manifest_refuses_before_install(monkeypatch, bad):
    record = manifest()
    meta = feed(monkeypatch, record)
    if bad == "digest":
        record["plugins"]["extras"]["sha256"] = "no"
    if bad == "size":
        record["plugins"]["extras"]["bytes"] = 3000000
    if bad == "url":
        meta["assets"][0]["browser_download_url"] = "https://attacker.invalid/manifest"
    if bad == "duplicate":
        meta["assets"].append(meta["assets"][0])
    if bad == "draft":
        meta["draft"] = True
    if bad == "tag":
        meta["tag_name"] = "../../escape"
    assert updates.check()["state"] == "unavailable"


def test_integrity_mismatch_never_reaches_ftp(monkeypatch):
    record = manifest()
    record["plugins"]["extras"]["sha256"] = "0" * 64
    feed(monkeypatch, record)
    monkeypatch.setattr(library, "connection", lambda _: pytest.fail("must not connect"))
    with pytest.raises(ValueError, match="integrity"):
        updates.install(CONFIG, "extras")


def test_update_offline_is_not_up_to_date(monkeypatch):
    monkeypatch.setattr(updates, "read", lambda *_: (_ for _ in ()).throw(OSError("offline")))
    assert updates.check()["state"] == "unavailable"
    with pytest.raises(ValueError):
        updates.install(CONFIG, "unknown")


def test_sidebar_and_owned_window_close_regressions():
    html = (ROOT / "orbeats/webapp/static/companion.html").read_text()
    css = (ROOT / "orbeats/webapp/static/companion.css").read_text()
    native = (ROOT / "desktop/src-tauri/src/main.rs").read_text()
    assert 'id="theme"' not in html and 'id="theme-settings"' in html
    assert "Local companion" not in html and 'id="deploy-extras"' in html
    assert "overscroll-behavior: none" in css and "overflow-anchor: none" in css
    close = native.split("if let tauri::WindowEvent::CloseRequested")[1].split(".build(tauri::generate_context!())")[0]
    assert "show_status(" not in close and "request_stop(" in close and "view.hide()" in close
    assert ".visible(false)" in native and "PageLoadEvent::Finished" in native


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/file",
        "https://attacker.invalid/file",
        "https://github.com:444/file",
        "https://user@github.com/file",
    ],
)
def test_release_redirect_is_https_and_allowlisted(url):
    import urllib.request

    with pytest.raises(ValueError, match="redirect"):
        updates.ReleaseRedirect().redirect_request(urllib.request.Request(updates.API), None, 302, "redirect", {}, url)


@pytest.mark.parametrize(
    "raw",
    [b"[CUSA12878]\n" + extras.TARGET.encode() + b"=0", b"[CUSA12878]\n" + extras.TARGET.encode() + b" # comment"],
)
def test_extras_ambiguous_registration_refuses(raw):
    with pytest.raises(ValueError, match="Ambiguous"):
        extras.registration(raw, enable=True)


def test_extras_wrong_title_never_connects(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "connection", lambda _: pytest.fail("must not connect"))
    with pytest.raises(ValueError, match="only supports"):
        extras.deploy({"title": {"id": "CUSA00000"}}, artifact(tmp_path))


@pytest.mark.parametrize(
    "bad",
    [[], {"schema": 1, "app": "0.1.13", "plugins": None}, {"schema": 1, "app": "0.1.13", "plugins": {"main": []}}],
)
def test_release_malformed_json_is_unavailable(monkeypatch, bad):
    feed(monkeypatch, bad)
    assert updates.check()["state"] == "unavailable"


def main_artifact(tmp_path):
    blob = bytearray(artifact(tmp_path).read_bytes())
    blob[192:320] = bytes(128)
    banner = b"=== OrBeats v0.8079 started ===\0"
    blob[192 : 192 + len(banner)] = banner
    path = tmp_path / "main.prx"
    path.write_bytes(blob)
    return path


@pytest.mark.parametrize("kind", ["main", "extras"])
def test_verified_release_reaches_only_explicit_installer(monkeypatch, tmp_path, kind):
    source = main_artifact(tmp_path) if kind == "main" else artifact(tmp_path)
    blob = source.read_bytes()
    feed(monkeypatch, manifest(blob), blob)
    calls = []

    def install(config, path, **kwargs):
        assert config == CONFIG and path.read_bytes() == blob
        calls.append((path, kwargs))
        return {"ok": True}

    monkeypatch.setattr(library if kind == "main" else extras, "deploy_plugin" if kind == "main" else "deploy", install)
    assert updates.install(CONFIG, kind) == {"ok": True}
    assert len(calls) == 1 and not calls[0][0].exists()
    assert calls[0][1] == ({"release_version": "0.8079"} if kind == "main" else {})


def test_release_binary_version_mismatch_never_connects(monkeypatch, tmp_path):
    blob = artifact(tmp_path).read_bytes()
    record = manifest(blob)
    record["plugins"]["extras"]["version"] = "0.0010"
    feed(monkeypatch, record, blob)
    monkeypatch.setattr(library, "connection", lambda _: pytest.fail("must not connect"))
    with pytest.raises(ValueError, match="version mismatch"):
        updates.install(CONFIG, "extras")


def test_release_stager_derives_manifest_and_marks_missing_platform(monkeypatch, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("release_stage", ROOT / "desktop/packaging/stage_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Isolated source-root fixture, not a real release or native binary.
    (tmp_path / "temp").mkdir()
    config = tmp_path / "desktop/src-tauri/tauri.conf.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"version": updates.APP_VERSION}))
    monkeypatch.setattr(module, "ROOT", tmp_path)
    output = tmp_path / "temp/assets"
    result = module.stage(output, main_artifact(tmp_path), artifact(tmp_path))
    assert result["published"] is False and result["complete_platform_set"] is False
    record = json.loads((output / "release-manifest.json").read_text())
    assert record["plugins"]["main"]["version"] == "0.8079"
    assert record["plugins"]["extras"]["version"] == "0.0009"
    for name in updates.NAMES.values():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() in (output / "SHA256SUMS").read_text()
    with pytest.raises(ValueError, match="fresh"):
        module.stage(output, main_artifact(tmp_path), artifact(tmp_path))


def test_dependency_notices_are_verbatim_and_never_copy_pip_credentials(monkeypatch, tmp_path):
    import importlib.util
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location("release_legal", ROOT / "desktop/build_legal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "site"
    (source / "sample-1.0.dist-info/licenses").mkdir(parents=True)
    (source / "sample-1.0.dist-info/licenses/LICENSE").write_bytes(b"Verbatim owner notice\r\n")
    (source / "sample-1.0.dist-info/direct_url.json").write_text("private build metadata must not ship")
    files = ["sample-1.0.dist-info/licenses/LICENSE", "sample-1.0.dist-info/direct_url.json"]
    dist = SimpleNamespace(
        metadata={"Name": "sample", "License-Expression": "MIT"},
        version="1.0",
        files=files,
        locate_file=lambda p: source / p,
    )
    monkeypatch.setattr(module.importlib.metadata, "distributions", lambda: [dist])
    out = module.dependency_notices(tmp_path / "notices")
    record = json.loads((out / "environment.json").read_text())
    assert record["scope"] == "installed-build-environment-superset"
    assert record["complete_native_or_source_closure"] is False
    assert (out / "sample-1.0/sample-1.0.dist-info/licenses/LICENSE").read_bytes() == b"Verbatim owner notice\r\n"
    assert not list(out.rglob("direct_url.json"))
    with pytest.raises(FileExistsError):
        module.dependency_notices(out)


@pytest.mark.parametrize("relative", ["../LICENSE", "/LICENSE"])
def test_dependency_notices_refuse_escaping_paths(monkeypatch, tmp_path, relative):
    import importlib.util
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location("release_legal", ROOT / "desktop/build_legal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dist = SimpleNamespace(metadata={"Name": "sample"}, version="1.0", files=[relative])
    monkeypatch.setattr(module.importlib.metadata, "distributions", lambda: [dist])
    with pytest.raises(ValueError, match="Escaping"):
        module.dependency_notices(tmp_path / "notices")


def test_offline_ffmpeg_attestation_matches_pinned_vendor_bytes():
    import hashlib
    lock = json.loads((ROOT / "desktop/development/media-linux-lock.json").read_text())["ffmpeg"]
    for key in ("signature", "key"):
        data = (ROOT / "desktop/legal" / ("ffmpeg-8.0.1-" + key + ".txt")).read_bytes()
        assert hashlib.sha256(data).hexdigest() == lock[key + "_sha256"]
        assert b"PRIVATE KEY" not in data


def test_settings_updates_share_compact_connection_column_without_form_side_effects():
    from html.parser import HTMLParser

    class SettingsParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.nodes = {}

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            node = {"tag": tag, "attrs": attrs, "parents": tuple(self.stack)}
            if "id" in attrs:
                assert attrs["id"] not in self.nodes
                self.nodes[attrs["id"]] = node
            if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
                self.stack.append((tag, attrs.get("id")))

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break

    parser = SettingsParser()
    parser.feed((ROOT / "orbeats/webapp/static/companion.html").read_text())
    for element in ("connection", "release-settings", "check-updates", "release-main", "release-extras"):
        assert ("div", "connection-settings") in parser.nodes[element]["parents"]
    for element in ("check-plugin-version", "deploy-plugin", "check-extras-version", "deploy-extras", "theme-settings"):
        assert ("div", "plugin-settings") in parser.nodes[element]["parents"]
    for element in ("check-updates", "copy-release-link", "release-main", "release-extras"):
        node = parser.nodes[element]
        assert node["attrs"]["type"] == "button"
        assert not any(tag == "form" for tag, _ in node["parents"])
