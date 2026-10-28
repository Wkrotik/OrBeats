"""Source-helper integration and packaging guards; no console operations."""

import http.cookiejar
import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "desktop/backend"


def load(name):
    spec = importlib.util.spec_from_file_location("desktop_" + name, BACKEND / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(BACKEND))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(BACKEND))
    return module


resources = load("resources")
storage = load("storage")


@pytest.fixture
def packaged(tmp_path):
    source = tmp_path / "source"
    for name in resources.FILES:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        # Source-helper tests need no built PS4 artifacts or acquired templates.
        value = (
            b"not a deployable plugin fixture"
            if name == "orbeats.prx"
            else (ROOT / "beat_saber_deluxe" / name).read_bytes()
        )
        target.write_bytes(value)
    # Dangerous private fixtures must never appear in resources.
    (source / "ps4_config.json").write_text('{"password":"PRIVATE"}')
    (source / "private.bundle").write_bytes(b"private game input")
    out = tmp_path / "resources"
    resources.build(source, out, ROOT / "LICENSE")
    return out


def test_curated_inventory_excludes_private_data(packaged):
    resources.verify(packaged)
    assert not (packaged / "ps4_config.json").exists()
    assert not (packaged / "private.bundle").exists()
    assert b"PRIVATE" not in b"".join(p.read_bytes() for p in packaged.rglob("*") if p.is_file())


@pytest.mark.parametrize("path", ["../escape", "/absolute", "a/../b", "a//b", "C:/root", "x\\file", "./file"])
def test_resource_paths_refuse_escape(path):
    with pytest.raises(ValueError):
        resources.safe_relative(path)


def test_tampered_or_extra_resources_refuse(packaged):
    (packaged / "VERSION").write_text("TAMPER")
    with pytest.raises(ValueError, match="integrity"):
        resources.verify(packaged)


def test_extra_resource_refuses(packaged):
    (packaged / "ps4_config.json").write_text("private")
    with pytest.raises(ValueError, match="Unexpected"):
        resources.verify(packaged)


def test_symlink_resource_refuses(packaged, tmp_path):
    target = tmp_path / "outside"
    target.write_text("secret")
    (packaged / "VERSION").unlink()
    try:
        (packaged / "VERSION").symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink"):
        resources.verify(packaged)


def test_runtime_workspace_is_versioned_and_preserves_state(packaged, tmp_path):
    state = tmp_path / "state"
    with storage.ownership(state):
        storage.atomic_json(state / "settings.json", {"keep": True})
        first = resources.install(packaged, state)
        assert resources.install(packaged, state) == first
        assert json.loads((state / "settings.json").read_text()) == {"keep": True}
        with pytest.raises(RuntimeError, match="Another"):
            with storage.ownership(state):
                pass
    with storage.ownership(state):
        assert resources.install(packaged, state) == first


def test_storage_does_not_follow_symlink(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("untouched")
    try:
        (tmp_path / "state.json").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink"):
        storage.atomic_json(tmp_path / "state.json", {})
    assert outside.read_text() == "untouched"


def spawn(packaged, state, log):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ORBEATS_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.Popen(
        [sys.executable, str(BACKEND / "entrypoint.py"), "--state-dir", str(state), "--resources", str(packaged)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=log,
        text=True,
        env=env,
    )
    result = queue.Queue()
    threading.Thread(target=lambda: result.put(process.stdout.readline()), daemon=True).start()
    try:
        line = result.get(timeout=15)
        assert line, "Backend exited before readiness"
        return process, json.loads(line)
    except BaseException:
        process.stdin.close()
        process.wait(timeout=15)
        raise


@pytest.mark.parametrize("close_pipe", [False, True])
def test_private_source_helper_bootstrap_shutdown_and_restore(packaged, tmp_path, close_pipe):
    state = tmp_path / "persistent"
    initial = {
        "pending": [{"id": "123", "map_id": "555fe", "title": "Pending only", "status": "queued"}],
        "history": [],
        "active": None,
        "paused": True,
        "error": False,
    }
    state.mkdir()
    storage.atomic_json(state / "queue.json", initial)
    with (tmp_path / "helper.log").open("w+") as log:
        process, ready = spawn(packaged, state, log)
        try:
            assert ready["protocol"] == 1
            origin = ready["url"].split("/_desktop/")[0]
            plain = build_opener()
            with pytest.raises(HTTPError) as refused:
                plain.open(origin + "/api/ping", timeout=5)
            assert refused.value.code == 403
            cookie = http.cookiejar.CookieJar()
            client = build_opener(HTTPCookieProcessor(cookie))
            assert client.open(ready["url"], timeout=5).status == 200
            with client.open(origin + "/api/ping", timeout=5) as response:
                assert json.load(response)["mode"] == "local-backend"
            # Persisted pending work is paused, not automatically sent to FTP.
            with client.open(origin + "/api/install-queue", timeout=5) as response:
                status = json.load(response)
            assert status["paused"] and status["pending"] == initial["pending"] and status["active"] is None
            with pytest.raises(HTTPError) as refused:
                client.open(Request(origin + "/api/install-queue/pause", data=b"{}", method="POST"), timeout=5)
            assert refused.value.code == 403
            # The same user's second desktop cannot run against these settings.
            second = subprocess.run(
                [
                    sys.executable,
                    str(BACKEND / "entrypoint.py"),
                    "--state-dir",
                    str(state),
                    "--resources",
                    str(packaged),
                ],
                input="",
                text=True,
                capture_output=True,
                timeout=10,
            )
            assert second.returncode != 0 and "Another OrBeats desktop" in second.stderr and not second.stdout
            if not close_pipe:
                process.stdin.write("STOP\n")
                process.stdin.flush()
            process.stdin.close()
            assert process.wait(timeout=15) == 0
            assert not process.stdout.read()  # no banners/secrets leaked after readiness
            log.flush()
            log.seek(0)
            assert ready["url"] not in log.read()
            saved = json.loads((state / "queue.json").read_text())
            assert saved["paused"] and saved["active"] is None and saved["pending"] == initial["pending"]
            assert json.loads((state / "ps4_config.json").read_text())["ps4"]["ip"] == "127.0.0.1"
        finally:
            if process.poll() is None:
                if not process.stdin.closed:
                    process.stdin.close()
                process.wait(timeout=15)


def test_frozen_dispatch_accepts_only_owned_helpers(monkeypatch, tmp_path):
    import runtime_dispatch

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("ORBEATS_RUNTIME_ROOT", str(tmp_path))
    argv = ["--song-dir", "folder with spaces", "--additive-install"]
    assert runtime_dispatch.command(tmp_path / "tools/full_custom_song_pipeline.py", argv) == [
        sys.executable,
        "--desktop-task",
        "pipeline",
        "--",
        *argv,
    ]
    with pytest.raises(ValueError, match="outside"):
        runtime_dispatch.command(tmp_path.parent / "outside.py", [])
    with pytest.raises(ValueError, match="not supported"):
        runtime_dispatch.command(tmp_path / "unknown.py", [])


FAKE_TRANSACTION_PIPELINE = "import os,time,json\nfrom pathlib import Path\nfrom console_transaction import Transaction\nstate=Path(os.environ['ORBEATS_STATE_DIR'])\nclass FTP:\n    def __init__(self):self.files={'/active':b'old'}\n    def rename(self,a,b):\n        if b in self.files:raise ValueError('Destination exists')\n        self.files[b]=self.files.pop(a)\n    def delete(self,p):self.files.pop(p)\nclass Core:\n    @staticmethod\n    def closed(f):pass\n    @staticmethod\n    def read(f,p,limit,missing=False):\n        if missing:return f.files.get(p)\n        return f.files[p]\n    @staticmethod\n    def stage(f,p,value,run):\n        path=p+'.stage-'+run;f.files[path]=value\n        (state/'transaction-active').write_text('stage before readback')\n        # Parent STOP/EOF arrives here; a force-kill would leave no commit marker.\n        time.sleep(.8)\n        assert f.files[path]==value\n        return path\nf=FTP();tx=Transaction(Core,f,'fake-close-publication');tx.publish('/active',b'new',b'old');tx.finish()\nassert f.files=={'/active':b'new'}\n(state/'transaction-complete').write_text(json.dumps({'readback':True,'remote_backups':False}))\n"


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("close_pipe", [False, True])
def test_close_during_fake_publication_drains_without_killing(packaged, tmp_path, frozen, close_pipe):
    import time

    executable = os.environ.get("ORBEATS_TEST_FROZEN_BACKEND")
    if frozen and not executable:
        pytest.skip("Optional locally built frozen helper not provided")
    # Test-only route and fake pipeline are curated fixture resources, never
    # installed into the real app or connected to an actual FTP server.
    pipeline = packaged / "tools/full_custom_song_pipeline.py"
    pipeline.write_text(FAKE_TRANSACTION_PIPELINE)
    server = packaged / "webapp/server.py"
    server.write_text(
        server.read_text()
        + '\n@app.post("/_test/start")\ndef fixture_start():\n    RUNNER.start([], label="Fake transaction")\n    return {"ok": True}\n'
    )
    manifest = json.loads((packaged / "runtime-manifest.json").read_text())
    for path in [pipeline, server]:
        value = path.read_bytes()
        manifest[path.relative_to(packaged).as_posix()] = {"bytes": len(value), "sha256": resources.digest(value)}
    (packaged / "runtime-manifest.json").write_text(json.dumps(manifest))
    state = tmp_path / "state"
    command = [executable] if frozen else [sys.executable, str(BACKEND / "entrypoint.py")]
    command += ["--state-dir", str(state), "--resources", str(packaged)]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ORBEATS_", "PYTHON"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if frozen:
        env["PATH"] = "/no-host-python-or-tools"
    with (tmp_path / "active-helper.log").open("w+") as log:
        p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, env=env, text=True)
        q = queue.Queue()
        threading.Thread(target=lambda: q.put(p.stdout.readline()), daemon=True).start()
        try:
            ready = json.loads(q.get(timeout=20))
            origin = ready["url"].split("/_desktop/")[0]
            client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
            client.open(ready["url"], timeout=5).read()
            client.open(
                Request(origin + "/_test/start", data=b"{}", headers={"Origin": origin}, method="POST"), timeout=5
            ).read()
            for _ in range(100):
                if (state / "transaction-active").exists():
                    break
                time.sleep(0.02)
            assert (state / "transaction-active").exists(), "Fake transaction never started"
            assert not (state / "transaction-complete").exists()
            if not close_pipe:
                p.stdin.write("STOP\n")
                p.stdin.flush()
            p.stdin.close()
            assert p.wait(timeout=15) == 0
            assert json.loads((state / "transaction-complete").read_text()) == {
                "readback": True,
                "remote_backups": False,
            }
            journal = state / "ps4_backups/transactions/fake-close-publication/journal.json"
            assert json.loads(journal.read_text())["complete"]
            assert (journal.parent / "0-before.bin").read_bytes() == b"old"
            assert json.loads((state / "queue.json").read_text())["paused"]
        finally:
            if p.poll() is None:
                if not p.stdin.closed:
                    p.stdin.close()
                p.wait(timeout=15)


@pytest.fixture
def media_payload(tmp_path):
    media = tmp_path / "media"
    rows = {}
    for name in resources.MEDIA_FILES:
        relative = name.removeprefix("media/")
        value = (
            b"\x7fELFfake Linux tool fixture"
            if name in resources.MEDIA_EXECUTABLES
            else b"public license/build fixture"
        )
        target = media / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        rows[relative] = resources.digest(value)
    (media / "manifest.json").write_text(json.dumps(rows))
    return media


def test_optional_media_inventory_preserves_executable_mode(packaged, media_payload, tmp_path):
    out = tmp_path / "with-media"
    resources.build(packaged, out, ROOT / "LICENSE", media=media_payload)
    resources.verify(out)
    assert (out / "media/bin/ffmpeg").stat().st_mode & 0o111
    state = tmp_path / "state"
    state.mkdir()
    installed = resources.install(out, state)
    assert (installed / "media/bin/ffprobe").stat().st_mode & 0o111


@pytest.mark.parametrize("fault", ["tamper", "extra", "partial"])
def test_media_payload_refuses_unreviewed_data(packaged, media_payload, tmp_path, fault):
    if fault == "tamper":
        (media_payload / "bin/ffmpeg").write_bytes(b"changed")
    elif fault == "extra":
        (media_payload / "PRIVATE.json").write_text("no copy")
    else:
        rows = json.loads((media_payload / "manifest.json").read_text())
        rows.pop("bin/ffprobe")
        (media_payload / "manifest.json").write_text(json.dumps(rows))
    out = tmp_path / "refused"
    with pytest.raises(ValueError, match="Media|media"):
        resources.build(packaged, out, ROOT / "LICENSE", media=media_payload)
    assert not out.exists()


@pytest.fixture
def full_codec_payload(media_payload):
    rows = json.loads((media_payload / "manifest.json").read_text())
    for name in resources.CODEC_FILES:
        relative = name.removeprefix("media/")
        value = b"\x7fELF codec fixture" if name in resources.MEDIA_ELF_FILES else b"public codec legal fixture"
        target = media_payload / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        rows[relative] = resources.digest(value)
    (media_payload / "manifest.json").write_text(json.dumps(rows))
    return media_payload


def test_complete_codec_inventory(packaged, full_codec_payload, tmp_path):
    out = tmp_path / "codecs"
    rows = resources.build(packaged, out, ROOT / "LICENSE", media=full_codec_payload)
    resources.verify(out)
    assert all(name in rows for name in resources.CODEC_FILES)


@pytest.mark.parametrize("fault", ["partial", "symlink", "header"])
def test_refuse_unsafe_codec_profiles(packaged, full_codec_payload, tmp_path, fault):
    target = full_codec_payload / "lib/libvorbis.so.0"
    rows = json.loads((full_codec_payload / "manifest.json").read_text())
    if fault == "partial":
        del rows["lib/libvorbis.so.0"]
        target.unlink()
    elif fault == "symlink":
        target.unlink()
        target.symlink_to(full_codec_payload / "lib/libogg.so.0")
    else:
        target.write_bytes(b"not ELF")
        rows["lib/libvorbis.so.0"] = resources.digest(target.read_bytes())
    (full_codec_payload / "manifest.json").write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        resources.build(packaged, tmp_path / "bad", ROOT / "LICENSE", media=full_codec_payload)
    assert not (tmp_path / "bad").exists()


def test_frozen_bundled_codec_roundtrip_without_host_discovery(tmp_path):
    executable = os.environ.get("ORBEATS_TEST_FROZEN_BACKEND")
    if not executable:
        pytest.skip("Provide optional frozen helper")
    runtime = Path(executable).resolve().parent / "_internal/runtime"
    if not (runtime / "media/lib/libvorbis.so.0").is_file():
        pytest.skip("Frozen helper has no full codec profile")
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    t = np.arange(12 * 44100 + 1) / 44100
    source = tmp_path / "original.ogg"
    sf.write(
        source,
        np.stack([0.25 * np.sin(2 * np.pi * 440 * t), 0.2 * np.sin(2 * np.pi * 660 * t)], axis=1),
        44100,
        format="OGG",
        subtype="VORBIS",
        compression_level=0.5,
    )
    empty = tmp_path / "empty"
    empty.mkdir()
    result = subprocess.run(
        [executable, "--desktop-check-codecs", str(source)],
        env={**os.environ, "PATH": str(empty), "ORBEATS_RUNTIME_ROOT": str(runtime)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    row = json.loads(result.stdout)
    assert row["bundled_codecs_only"] and row["host_discovery_disabled"] and row["independent_decode"]
    assert row["frames"] == 529201 and row["rate"] == 44100 and row["console_writes"] is False


def pe_fixture(dll=False):
    import struct

    value = bytearray(128)
    value[:2] = b"MZ"
    struct.pack_into("<I", value, 0x3C, 64)
    value[64:68] = b"PE\0\0"
    struct.pack_into("<HH", value, 68, 0x8664, 1)
    struct.pack_into("<H", value, 86, 2 | (0x2000 if dll else 0))
    struct.pack_into("<H", value, 88, 0x20B)
    return bytes(value)


@pytest.fixture
def windows_payload(tmp_path):
    from media_profiles import WINDOWS_BASE, WINDOWS_CODECS

    out = tmp_path / "windows-media"
    out.mkdir()
    rows = {}
    for name in WINDOWS_BASE + WINDOWS_CODECS:
        relative = name.removeprefix("media/")
        value = (
            pe_fixture(name.startswith("media/lib/"))
            if name.endswith((".exe", ".dll"))
            else b"Windows recipe/legal fixture"
        )
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        rows[relative] = resources.digest(value)
    (out / "manifest.json").write_text(json.dumps(rows))
    return out


def test_complete_windows_profile(packaged, windows_payload, tmp_path):
    root = tmp_path / "runtime-win"
    resources.build(packaged, root, ROOT / "LICENSE", media=windows_payload)
    resources.verify(root)
    assert (root / "media/bin/ffmpeg.exe").is_file()
    assert not (root / "media/bin/ffmpeg").exists()


@pytest.mark.parametrize("fault", ["architecture", "dll", "magic", "partial", "mixed"])
def test_refuse_wrong_windows_media(packaged, windows_payload, tmp_path, fault):
    import struct

    path = windows_payload / "bin/ffmpeg.exe"
    value = bytearray(path.read_bytes())
    rows = json.loads((windows_payload / "manifest.json").read_text())
    if fault == "architecture":
        struct.pack_into("<H", value, 68, 0x14C)
    elif fault == "dll":
        struct.pack_into("<H", value, 86, 0x2002)
    elif fault == "magic":
        value[:2] = b"EL"
    elif fault == "partial":
        del rows["bin/ffmpeg.exe"]
        path.unlink()
    else:
        replacement = windows_payload / "lib/libogg.so.0"
        replacement.write_bytes(b"\x7fELF")
        rows["lib/libogg.so.0"] = resources.digest(replacement.read_bytes())
    if fault not in ("partial", "mixed"):
        path.write_bytes(value)
        rows["bin/ffmpeg.exe"] = resources.digest(value)
    (windows_payload / "manifest.json").write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        resources.build(packaged, tmp_path / "bad-win", ROOT / "LICENSE", media=windows_payload)
    assert not (tmp_path / "bad-win").exists()


def test_installer_configs_are_explicit_candidates():
    win = json.loads((ROOT / "desktop/packaging/windows-x64.json").read_text())["bundle"]
    linux = json.loads((ROOT / "desktop/packaging/linux-x64.json").read_text())["bundle"]
    assert win["targets"] == ["nsis"] and win["windows"]["nsis"]["installMode"] == "currentUser"
    assert win["windows"]["webviewInstallMode"]["type"] == "embedBootstrapper"  # runtime installation needs internet
    assert linux["targets"] == ["appimage", "deb"]
    assert linux["linux"]["appimage"]["bundleMediaFramework"] is True
    assert "libc6 (>= 2.35)" in linux["linux"]["deb"]["depends"]
    assert not win["createUpdaterArtifacts"] and not linux["createUpdaterArtifacts"]
    assert json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text())["bundle"]["active"] is False


def test_platform_freezing_and_execution_are_not_cross_target():
    from media_profiles import LINUX_BASE, LINUX_CODECS, WINDOWS_BASE, WINDOWS_CODECS, validate_host_profile

    for platform, correct, wrong in [
        ("linux", LINUX_BASE + LINUX_CODECS, WINDOWS_BASE + WINDOWS_CODECS),
        ("win32", WINDOWS_BASE + WINDOWS_CODECS, LINUX_BASE + LINUX_CODECS),
    ]:
        validate_host_profile(correct, platform)
        validate_host_profile([], platform)  # source-only prototype remains explicit
        with pytest.raises(ValueError, match="platform"):
            validate_host_profile(wrong, platform)
    with pytest.raises(ValueError, match="platform"):
        validate_host_profile(LINUX_BASE, "darwin")


def test_stage_windows_candidate_is_not_a_native_build(packaged, windows_payload, tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("desktop_stager", ROOT / "desktop/packaging/stage_candidate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    backend = tmp_path / "frozen-win"
    runtime = backend / "_internal/runtime"
    resources.build(packaged, runtime, ROOT / "LICENSE", media=windows_payload)
    (backend / "orbeats-backend.exe").write_bytes(pe_fixture())
    output = tmp_path / "temp/candidate"
    result = module.stage("windows-x64", backend, output)
    assert result["candidate_only"] and result["native_build_required"] and result["published"] is False
    assert not result["legal_review_complete"]
    resources.verify(output / "backend/_internal/runtime")
    cfg = json.loads((output / "tauri-candidate.json").read_text())
    assert cfg["bundle"]["resources"] == {str(output / "backend") + "/": "backend/"}
    assert not (output / "installer.exe").exists()
    with pytest.raises(ValueError):
        module.stage("windows-x64", backend, output)
    with pytest.raises(ValueError, match="target platform"):
        module.stage("linux-x64", backend, tmp_path / "temp/wrong")


@pytest.fixture
def image_inputs(packaged, full_codec_payload, tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("desktop_appimage_seal", ROOT / "desktop/packaging/seal_appimage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    backend = tmp_path / "backend"
    resources.build(packaged, backend / "_internal/runtime", ROOT / "LICENSE", media=full_codec_payload)
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    header[18:20] = (62).to_bytes(2, "little")
    (backend / "orbeats-backend").write_bytes(header)
    appdir = tmp_path / "upstream.AppDir"
    (appdir / "usr/bin").mkdir(parents=True)
    (appdir / "usr/bin/orbeats-desktop").write_bytes(header)
    old = appdir / "usr/lib/OrBeats/backend"
    old.mkdir(parents=True)
    (old / "corrupt-patched-library.so").write_bytes(b"old rewritten backend must not survive")
    (appdir / "AppRun").write_text("#!/bin/sh\n")
    (appdir / "orbeats-desktop.png").write_bytes(b"icon fixture")
    (appdir / ".DirIcon").symlink_to("nonexistent-product-icon.png")
    return module, backend, appdir, tmp_path / "temp/sealed.AppDir"


def test_appimage_restores_sealed_backend_not_its_manifest(image_inputs):
    module, backend, appdir, output = image_inputs
    before = module.inventory(backend)
    report = module.copy_sealed_appdir(appdir, backend, output)
    assert report["backend_unchanged"] and report["resource_hashes_valid"]
    assert module.inventory(output / module.BACKEND) == before == module.inventory(backend)
    assert not (output / module.BACKEND / "corrupt-patched-library.so").exists()
    assert (output / ".DirIcon").is_file()
    assert (appdir / ".DirIcon").readlink() == Path("nonexistent-product-icon.png")
    with pytest.raises(ValueError, match="fresh"):
        module.copy_sealed_appdir(appdir, backend, output)


@pytest.mark.parametrize(
    "fault", ["resource-hash", "external-link", "private-profile", "wrong-architecture", "symlink-parent"]
)
def test_appimage_refuses_unsafe_assembly(image_inputs, tmp_path, fault):
    module, backend, appdir, output = image_inputs
    if fault == "resource-hash":
        (backend / "_internal/runtime/media/lib/libogg.so.0").write_bytes(b"corrupted")
    elif fault == "external-link":
        (appdir / "escape").symlink_to("/etc/passwd")
    elif fault == "private-profile":
        (appdir / "ps4_config.json").write_text("{}")
    elif fault == "wrong-architecture":
        (backend / "orbeats-backend").write_bytes(b"MZ" + b"\0" * 62)
    else:
        owned = appdir / "usr/lib/OrBeats"
        owned.rename(tmp_path / "escaped-parent")
        owned.symlink_to(tmp_path / "escaped-parent", target_is_directory=True)
    with pytest.raises(ValueError):
        module.copy_sealed_appdir(appdir, backend, output)
    assert not output.exists()


def test_appimage_tool_lock_and_cache_refuse_mutation(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "desktop_appimage_tools", ROOT / "desktop/development/setup_appimage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lock = json.loads(module.LOCK.read_text())
    assert lock["tauri_cli"] == "2.12.4"
    assert len(lock["assets"]) == 4
    assert all(
        len(row["sha256"]) == 64 and row["asset_id"] > 0 and row["url"].startswith("https://github.com/")
        for row in lock["assets"]
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    cache = tmp_path / ".tools/downloads/appimage"
    cache.mkdir(parents=True)
    (cache / lock["assets"][0]["name"]).write_bytes(b"wrong cached download")
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *a, **k: pytest.fail("Corrupt cached tool must not be silently redownloaded"),
    )
    with pytest.raises(ValueError, match="integrity failure"):
        module.prepare(tmp_path / ".tools/tools")
    assert not (tmp_path / ".tools/tools").exists()


def test_appimage_compressor_is_verified_before_assembly(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "desktop_appimage_compressor", ROOT / "desktop/packaging/seal_appimage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plugin = tmp_path / "changed-plugin"
    plugin.write_bytes(b"bad tool")
    monkeypatch.setattr(
        module, "copy_sealed_appdir", lambda *a, **k: pytest.fail("Must reject compressor before copying")
    )
    with pytest.raises(ValueError, match="tool integrity failure"):
        module.assemble(tmp_path / "appdir", tmp_path / "backend", tmp_path / "output", plugin)
    assert not (tmp_path / "output").exists()
