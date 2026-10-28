"""Source-only publishing guards. No GitHub calls, real secrets or game inputs."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "source_export", ROOT / "beat_saber_deluxe/development/scripts/prepare_source_repository.py"
)
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


@pytest.mark.parametrize(
    "path",
    [
        ".git/config",
        ".agent/project_summary.md",
        ".ai_memory/transcript.md",
        "beat_saber_deluxe/ps4_config.json",
        "beat_saber_deluxe/catalog_full.json",
        "beat_saber_deluxe/catalog_custom.csv",
        "beat_saber_deluxe/redirects_local.json",
        "beat_saber_deluxe/custom_songs/song.bundle",
        "desktop/src-tauri/target/a.exe",
        "beat_saber_deluxe/development/fixtures/private.json",
        "docs/overnight-audit.md",
        "docs/installation-failure-audit.md",
        "docs/example-scripts/old-deployment.sh",
        ".github/workflows/pages.yml",
        "beat_saber_deluxe/tools/native/orbeats_hash.so",
    ],
)
def test_export_default_denies_personal_inputs_history_and_binaries(path):
    assert not export.eligible(path)


@pytest.mark.parametrize(
    "path",
    [
        "desktop/src-tauri/src/main.rs",
        "desktop/src-tauri/Cargo.lock",
        ".github/workflows/private-build.yml",
        ".devcontainer/setup_additive_host.sh",
        "beat_saber_deluxe/webapp/static/dumper.cfg",
        "beat_saber_deluxe/tools/native/fnv.c",
        "LICENSE",
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
        "beat_saber_deluxe/ps4_config.example.json": json.dumps({"ps4": {"ip": "192.0.2.2"}}),
        "beat_saber_deluxe/beat_saber_song_ids.json": "PRIVATE CATALOG",
        "beat_saber_deluxe/ps4_config.json": "PRIVATE PASSWORD",
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
    assert json.loads((out / "beat_saber_deluxe/beat_saber_song_ids.json").read_text())["albums"] == []
    assert json.loads((out / "beat_saber_deluxe/ps4_config.example.json").read_text())["ps4"]["ip"] == "127.0.0.1"
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
