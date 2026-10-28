"""Release-workflow regression tests (Exp 278i audit findings).

The alpha01 release audit found the CI's features.json template had gone
STALE (hardcoded in the workflow since v0.5340-era, missing enable_song_previews
from M10 AND enable_in_game_plugin_toggle from M11 — shipped in every release
zip to date; a manual install booted with previews + the hotkey silently OFF).
These tests pin the fix (generate from the pipeline's DEFAULT_FEATURES — the
single source of truth) and the other release-zip invariants the audit
established.
"""
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "plugin-build.yml"
FEATURES_DOCS = Path(__file__).resolve().parent.parent / "docs" / "features"


def _workflow() -> str:
    assert WORKFLOW.is_file(), "plugin-build.yml not found"
    return WORKFLOW.read_text(encoding="utf-8")


class TestFeaturesJsonSingleSource:
    """features.json must be GENERATED from DEFAULT_FEATURES, never hardcoded."""

    def test_generated_from_default_features(self):
        wf = _workflow()
        assert "from full_custom_song_pipeline import DEFAULT_FEATURES" in wf
        assert "json.dump(DEFAULT_FEATURES" in wf

    def test_no_hardcoded_flag_template(self):
        """The stale v0.5340-era heredoc must never come back."""
        wf = _workflow()
        assert "cat > features.json" not in wf

    def test_generation_runs_after_the_dependency_install(self):
        """The single-source import needs the pipeline's deps (lz4 …) — the
        generation step must run AFTER 'Run tests with coverage' (which pip
        installs them)."""
        wf = _workflow()
        tests_pos = wf.find("Run tests with coverage")
        gen_pos = wf.find("Generate features.json (from the pipeline's DEFAULT_FEATURES")
        assert tests_pos > 0 and gen_pos > 0, "expected steps not found in workflow"
        assert tests_pos < gen_pos, \
            "features.json generation must come after the test/install step"

    def test_default_features_matches_expected_flags(self):
        """The template the workflow will now generate — the full current set."""
        import full_custom_song_pipeline as fp
        # Exp 281 (user directive): ALL flags default ON — fresh installs
        # work out of the box; plugin absent-file defaults mirror this dict.
        expected = {
            "enable_plugin": True,
            "enable_custom_song_replacements": True,
            "enable_song_metadata_modification": True,
            "enable_beatmap_mode_mapping": True,
            "enable_song_previews": True,
            "enable_in_game_plugin_toggle": True,
            "enable_game_data_extractor": True,
            # Exp 289: user-approved OFF-default risky experiment exception.
            "enable_additive_song_packs": False,
        }
        assert fp.DEFAULT_FEATURES == expected


class TestReleaseZipInvariants:
    """Other release-zip invariants established across the audits."""

    def test_coverage_report_ships(self):
        """The user explicitly requested the test-coverage report in the release
        (release-zip step copies htmlcov → coverage-report). Guard it."""
        wf = _workflow()
        assert "release-zip/coverage-report" in wf

    def test_all_feature_docs_bundle(self):
        """Every shipped feature doc must be copied into release-zip/docs/features/
        — a new doc without a copy line silently vanishes from the zip (exactly
        how the 5th doc would have shipped missing had the audit not caught
        the cp list). M13 hardened this: the workflow now copies the WHOLE
        directory (docs/features/*.md), so new docs ship automatically —
        this test still pins that (a) the glob (or an explicit cp list)
        exists and (b) an explicit-list regression would re-fail here."""
        wf = _workflow()
        glob_copy = "cp beat_saber_deluxe/docs/features/*.md release-zip/docs/features/" in wf
        bundled = set(re.findall(r"cp beat_saber_deluxe/docs/features/([\w.-]+\.md)", wf))
        on_disk = {p.name for p in FEATURES_DOCS.glob("*.md")}
        assert on_disk, "no feature docs found on disk?"
        if glob_copy:
            # the whole directory ships — nothing can be missing by construction
            assert "release-zip/docs/features/" in wf
            return
        missing = on_disk - bundled
        assert not missing, \
            f"feature docs exist but are NOT bundled into the release zip: {sorted(missing)}"
        assert "in-game-plugin-toggle.md" in bundled, "the M11 feature doc must ship"
