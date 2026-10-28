"""
test_webapp_config.py — config adapter unit tests (no PS4, no network).

Dump-validation fixtures build tiny fake dump trees in tmp_path; every
per-missing-piece error path is asserted (plan §4.1b: the wizard must say
exactly WHAT is wrong, never a bare "not found").
"""

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

from adapters import config, paths  # noqa: E402


@pytest.fixture
def good_dump(tmp_path):
    """A structurally-valid dump tree (minimal files, real layout)."""
    root = tmp_path / "ps4_dump"
    patch = root / "CUSA12878-patch"
    (patch / "Media/StreamingAssets/aa/PS4").mkdir(parents=True)
    (patch / "eboot.bin").write_bytes(b"\x7fELF-fake")
    (patch / "Media/StreamingAssets/aa/catalog.json").write_text("{}")
    (root / "CUSA12878-app").mkdir()
    (patch / "Media/StreamingAssets/aa/PS4"
     / f"lizzo_pack_assets_all_{'a' * 32}.bundle").write_bytes(b"x")
    return root


class TestValidateDump:
    def test_good_dump_ok(self, good_dump):
        res = config.validate_dump(good_dump)
        assert res.ok, res.errors
        assert res.app_dir_present and res.patch_dir_present
        assert res.eboot_present and res.origin_catalog_present
        assert res.dlc_packs_found == ["lizzo"]

    def test_missing_folder(self, tmp_path):
        res = config.validate_dump(tmp_path / "nope")
        assert not res.ok
        assert any("does not exist" in e for e in res.errors)

    def test_empty_folder_names_both_dirs(self, tmp_path):
        (tmp_path / "empty").mkdir()
        res = config.validate_dump(tmp_path / "empty")
        assert not res.ok
        assert any("CUSA12878-app" in e and "CUSA12878-patch" in e for e in res.errors)
        # The hint must mention split=3 (the dumper.cfg recipe)
        assert any("split=3" in e for e in res.errors)

    def test_missing_app_dir(self, good_dump):
        (good_dump / "CUSA12878-app").rmdir()
        res = config.validate_dump(good_dump)
        assert not res.ok
        assert any("CUSA12878-app/ missing" in e for e in res.errors)
        assert res.patch_dir_present  # the rest still reports

    def test_missing_patch_dir(self, tmp_path):
        (tmp_path / "CUSA12878-app").mkdir()
        res = config.validate_dump(tmp_path)
        assert not res.ok
        assert any("CUSA12878-patch/ missing" in e for e in res.errors)
        assert any("REQUIRED" in e for e in res.errors)

    def test_missing_eboot(self, good_dump):
        (good_dump / "CUSA12878-patch/eboot.bin").unlink()
        res = config.validate_dump(good_dump)
        assert not res.ok
        assert any("eboot.bin" in e for e in res.errors)

    def test_missing_origin_catalog(self, good_dump):
        (good_dump / "CUSA12878-patch/Media/StreamingAssets/aa/catalog.json").unlink()
        res = config.validate_dump(good_dump)
        assert not res.ok
        assert any("catalog.json" in e for e in res.errors)

    def test_no_dlc_is_warning_not_error(self, good_dump):
        for b in (good_dump / "CUSA12878-patch/Media/StreamingAssets/aa/PS4").iterdir():
            b.unlink()
        res = config.validate_dump(good_dump)
        assert res.ok  # no DLC is valid — just can't patch packs
        assert res.dlc_packs_found == []
        assert any("#1 setup symptom" in w for w in res.warnings)

    def test_multiple_dlc_packs_found_sorted(self, good_dump):
        ps4 = good_dump / "CUSA12878-patch/Media/StreamingAssets/aa/PS4"
        for pack in ("billieeilish", "camellia"):
            (ps4 / f"{pack}_pack_assets_all_{'b' * 32}.bundle").write_bytes(b"x")
        res = config.validate_dump(good_dump)
        assert res.dlc_packs_found == ["billieeilish", "camellia", "lizzo"]


class TestWizardConfig:
    def test_build_wizard_config_localizes_everything(self, good_dump):
        cfg = config.build_wizard_config(good_dump, "10.1.2.3")
        assert cfg["ps4"] == {"ip": "10.1.2.3", "ftp_port": 2121,
                              "ftp_user": "anonymous", "ftp_password": ""}
        assert cfg["title"]["id"] == "CUSA12878"
        assert cfg["paths"]["game_dump_dir"] == str(good_dump / "CUSA12878-patch")
        assert cfg["paths"]["output_dir"] == str(paths.PROJECT_DIR / "custom_songs")
        assert cfg["paths"]["afr_base"] == "/data/GoldHEN/AFR"
        # pack_modes auto-discover scope (Exp 224): empty list
        assert cfg["pack_modes"]["packs"] == []
        assert cfg["pack_modes"]["dump_dir"] == str(good_dump / "CUSA12878-patch")
        assert cfg["pack_modes"]["song_ids_path"] == str(paths.SONG_CATALOG)
        assert cfg["mass_deploy"]["slots"] == []

    def test_save_and_load_roundtrip(self, good_dump, tmp_path, monkeypatch):
        # Point CONFIG_PATH at a scratch copy so the dev config is untouched
        scratch = tmp_path / "ps4_config.json"
        monkeypatch.setattr(paths, "CONFIG_PATH", scratch)
        monkeypatch.setattr(config.paths, "CONFIG_PATH", scratch)
        cfg = config.build_wizard_config(good_dump, "1.2.3.4", ftp_port=2122)
        written = config.save_config(cfg)
        assert written == scratch
        loaded = config.load_config()
        assert loaded == cfg


class TestPaths:
    def test_release_layout_resolution(self):
        # In the dev checkout, the release root contains .git
        assert paths.PIPELINE.exists()
        assert paths.RELEASE_ROOT == PROJECT.parent

    def test_find_pipeline_raises_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "PIPELINE", tmp_path / "missing.py")
        with pytest.raises(FileNotFoundError):
            paths.find_pipeline()


class TestPagesBuild:
    """The Pages bundle must load its own assets (the first shipped bundle
    404'd its own JS/CSS — the UI appeared dead at the Pages URL) and must
    bake the component versions into the badge."""

    def test_pages_bundle_assets_resolve(self, tmp_path):
        import subprocess
        out = tmp_path / "pages"
        r = subprocess.run(
            ["python3", str(PROJECT / "webapp" / "build_pages.py"),
             "--out", str(out)],
            capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        import re
        html = (out / "index.html").read_text(encoding="utf-8")
        assert 'data-mode="pages"' in html
        # every local href/src resolves inside the bundle
        refs = re.findall(r'(?:href|src)="([^"#?]+)"', html)
        for ref in refs:
            if ref.startswith(("http", "javascript:")):
                continue
            assert (out / ref.lstrip("/")).is_file(), f"missing asset: {ref}"
        assert not any(r.startswith("/static/") for r in refs), \
            "unrewritten /static/ refs remain — the Pages UI would 404 its own JS"

    def test_pages_bundle_bakes_versions(self, tmp_path):
        import subprocess
        out = tmp_path / "pages"
        subprocess.run(
            ["python3", str(PROJECT / "webapp" / "build_pages.py"),
             "--out", str(out)],
            capture_output=True, text=True, timeout=60, check=True)
        html = (out / "index.html").read_text(encoding="utf-8")
        assert 'id="ver-webapp">web app <b>' in html
        assert "<b>…</b>" not in html, "versions not baked into the badge"
