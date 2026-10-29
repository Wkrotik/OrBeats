"""Source-only publishing guards. No GitHub calls, real secrets or game inputs."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "source_export", ROOT / "orbeats/development/scripts/prepare_source_repository.py"
)
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


@pytest.mark.parametrize(
    "path",
    [
        "beat_saber_deluxe/src/main.cpp",
        "orbeats/MEMORY_INJECTION_STATUS.md",
        "orbeats/development/scripts/memory_inject_plugin.cpp",
        "orbeats_extras/orbeats_extras.prx",
        "orbeats_extras/obj/main.o",
        ".git/config",
        ".agent/project_summary.md",
        ".ai_memory/transcript.md",
        "orbeats/ps4_config.json",
        "orbeats/catalog_full.json",
        "orbeats/catalog_custom.csv",
        "orbeats/redirects_local.json",
        "orbeats/custom_songs/song.bundle",
        "desktop/src-tauri/target/a.exe",
        "orbeats/development/fixtures/private.json",
        "docs/overnight-audit.md",
        "docs/installation-failure-audit.md",
        "docs/example-scripts/old-deployment.sh",
        ".github/workflows/pages.yml",
        ".github/workflows/bug_report.yml",
        ".github/ISSUE_TEMPLATE/private-build.yml",
        ".github/ISSUE_TEMPLATE/private_notes.yml",
        ".github/ISSUE_TEMPLATE/nested/bug_report.yml",
        "orbeats/tools/native/orbeats_hash.so",
    ],
)
def test_export_default_denies_personal_inputs_history_and_binaries(path):
    assert not export.eligible(path)


@pytest.mark.parametrize(
    "path",
    [
        "desktop/legal/ffmpeg-8.0.1-signature.txt",
        "desktop/legal/ffmpeg-8.0.1-key.txt",
        "orbeats_extras/src/main.cpp",
        "orbeats_extras/include/health.h",
        "orbeats_extras/development/scoresaber.py",
        "desktop/src-tauri/src/main.rs",
        "desktop/src-tauri/Cargo.lock",
        ".github/workflows/private-build.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/compatibility_report.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/pull_request_template.md",
        ".devcontainer/setup_additive_host.sh",
        "orbeats/webapp/static/dumper.cfg",
        "orbeats/tools/native/fnv.c",
        "LICENSE",
        "icon.svg",
        "docs/images/companion-dark.png",
        "docs/getting-started.md",
    ],
)
def test_export_allows_required_source_and_safe_build_inputs(path):
    assert export.eligible(path)


def fake_source(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "ROOT", tmp_path)
    monkeypatch.setattr(export.subprocess, "check_output", lambda *a, **k: "a" * 40)
    for rel, value in {
        "LICENSE": "GPL notice",
        "README.md": "source",
        "orbeats/ps4_config.example.json": json.dumps({"ps4": {"ip": "192.0.2.2"}}),
        "orbeats/beat_saber_song_ids.json": "PRIVATE CATALOG",
        "orbeats/ps4_config.json": "PRIVATE PASSWORD",
        ".agent/notes.md": "PRIVATE CHAT",
        ".git/config": "PRIVATE HISTORY",
    }.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)


def test_source_export_replaces_catalog_never_copies_configuration_or_history(tmp_path, monkeypatch):
    fake_source(tmp_path, monkeypatch)
    out = tmp_path / ".publication/review"
    result = export.prepare(out)
    assert result["git_history_copied"] is False and result["published"] is False
    assert not any("PRIVATE" in p.read_text() for p in out.rglob("*") if p.is_file())
    assert not (out / ".git").exists() and not (out / ".agent").exists()
    assert json.loads((out / "orbeats/beat_saber_song_ids.json").read_text())["albums"] == []
    assert json.loads((out / "orbeats/ps4_config.example.json").read_text())["ps4"]["ip"] == "127.0.0.1"
    manifest = json.loads((out / "source-export-manifest.json").read_text())
    assert all(hashlib.sha256((out / name).read_bytes()).hexdigest() == value for name, value in manifest.items())
    with pytest.raises(ValueError, match="fresh"):
        export.prepare(out)
    with pytest.raises(ValueError, match="fresh"):
        export.prepare(tmp_path / "elsewhere")


def test_export_refuses_credential_like_source_without_printing_it(tmp_path, monkeypatch):
    fake_source(tmp_path, monkeypatch)
    bad = tmp_path / "desktop/credential.py"
    bad.parent.mkdir(parents=True)
    bad.write_text("gh" + "p_" + "A" * 36)
    with pytest.raises(ValueError, match="credential-like"):
        export.prepare(tmp_path / ".publication/review")
    assert not (tmp_path / ".publication/review").exists()


def test_export_refuses_source_symlinks(tmp_path, monkeypatch):
    fake_source(tmp_path, monkeypatch)
    bad = tmp_path / "desktop/test.py"
    bad.parent.mkdir(parents=True)
    bad.symlink_to(tmp_path / "README.md")
    with pytest.raises(ValueError, match="symlinks"):
        export.prepare(tmp_path / ".publication/review")


def test_export_preserves_owned_binary_icon_without_text_decoding(tmp_path, monkeypatch):
    fake_source(tmp_path, monkeypatch)
    icon = tmp_path / "desktop/src-tauri/icons/icon.ico"
    icon.parent.mkdir(parents=True)
    data = b"\x00\x00\x01\x00\x01\x00\xc9\xff"
    icon.write_bytes(data)
    out = tmp_path / ".publication/review"
    export.prepare(out)
    assert (out / icon.relative_to(tmp_path)).read_bytes() == data
