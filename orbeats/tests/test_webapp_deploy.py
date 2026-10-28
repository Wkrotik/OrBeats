"""
test_webapp_deploy.py — deploy argv builder + single-job runner tests.

The argv contract under test: the web app's Deploy button must produce the
EXACT command the example scripts run (the thin-layer rule made testable).

  python3 tools/full_custom_song_pipeline.py --download-beat-saver-song <ID>
      --target <SLOT> --pcm16 --no-pad --convert-to-v3 --deploy-full
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

from adapters import deploy, runner  # noqa: E402

SAFE_DEFAULT = ["--download-beat-saver-song", "1d6c7c2", "--target", "BadGuy",
                "--pcm16", "--no-pad", "--convert-to-v3", "--deploy-full"]


class TestDeployOptions:
    def test_safe_default_matches_example_scripts(self):
        opts = deploy.DeployOptions(map_id="1d6c7c2", target="BadGuy")
        assert opts.build_argv() == SAFE_DEFAULT

    def test_skip_plugin_appends_flag(self):
        opts = deploy.DeployOptions(map_id="x", target="y", skip_plugin=True)
        argv = opts.build_argv()
        assert argv[-1] == "--skip-plugin-deployment"
        assert "--deploy-full" in argv

    def test_vorbis_opts_out_of_pcm16(self):
        opts = deploy.DeployOptions(map_id="x", target="y", audio="vorbis")
        argv = opts.build_argv()
        assert "--vorbis" in argv and "--pcm16" not in argv

    def test_hevag_opts_out_of_pcm16(self):
        opts = deploy.DeployOptions(map_id="x", target="y", audio="hevag")
        argv = opts.build_argv()
        assert "--hevag" in argv and "--pcm16" not in argv

    def test_pad_fsb5_replaces_no_pad(self):
        opts = deploy.DeployOptions(map_id="x", target="y", pad_fsb5=True)
        argv = opts.build_argv()
        assert "--pad-fsb5" in argv and "--no-pad" not in argv

    def test_name_overrides(self):
        opts = deploy.DeployOptions(map_id="x", target="y",
                                    song_name="Take On Me", artist="A-ha")
        argv = opts.build_argv()
        assert argv[argv.index("--song-name") + 1] == "Take On Me"
        assert argv[argv.index("--artist") + 1] == "A-ha"

    def test_enable_modes(self):
        opts = deploy.DeployOptions(map_id="x", target="y",
                                    enable_modes="OneSaber,90Degree")
        argv = opts.build_argv()
        assert argv[argv.index("--enable-modes") + 1] == "OneSaber,90Degree"

    def test_requires_map_id(self):
        with pytest.raises(ValueError, match="map ID"):
            deploy.DeployOptions(map_id="", target="y").build_argv()

    def test_requires_target(self):
        with pytest.raises(ValueError, match="target slot"):
            deploy.DeployOptions(map_id="x", target="").build_argv()

    def test_rejects_unknown_audio(self):
        with pytest.raises(ValueError, match="codec"):
            deploy.DeployOptions(map_id="x", target="y", audio="mp3").build_argv()

    def test_every_flag_exists_in_pipeline_help(self):
        """Thin-layer proof: every argv flag is a real pipeline CLI flag."""
        help_text = subprocess.run(
            ["python3", str(PROJECT / "tools" / "full_custom_song_pipeline.py"),
             "--help"],
            capture_output=True, text=True, timeout=120).stdout
        opts = deploy.DeployOptions(map_id="x", target="y", skip_plugin=True,
                                    pad_fsb5=True, enable_modes="OneSaber",
                                    skip_mode_generation=True,
                                    disable_mode_mapping=True)
        for tok in opts.build_argv():
            if tok.startswith("--") and tok not in ("--no-pad",):
                assert tok in help_text, f"webapp emitted unknown flag: {tok}"


class TestFlagsAndClear:
    def test_flags_only_command(self):
        assert deploy.flags_only_command("enable_plugin", False) == [
            "--features-only", "--set-feature", "enable_plugin=false"]

    def test_clear_target_command(self):
        assert deploy.clear_target_command("BadGuy") == ["--clear-target-song", "BadGuy"]

    def test_verify_command(self):
        assert deploy.verify_command() == ["--verify-ps4"]


class TestPipelineCommandRender:
    def test_command_is_release_root_relative(self):
        cmd = deploy.pipeline_command(SAFE_DEFAULT)
        assert cmd.startswith("python3 orbeats/tools/full_custom_song_pipeline.py ")
        assert "--deploy-full" in cmd


class TestSingleJobRunner:
    def test_busy_refuses_second_job(self):
        r = runner.SingleJobRunner()
        first = r.start(["--help"], label="first")
        # --help may already have finished; if busy, second must raise
        if r.is_busy():
            with pytest.raises(RuntimeError, match="one at a time"):
                r.start(["--help"], label="second")
        # else the job finished and a second job is allowed
        else:
            second = r.start(["--help"], label="second")
            assert second.id >= first.id

    def test_lines_stream_and_job_ends(self):
        r = runner.SingleJobRunner()
        job = r.start(["--help"], label="help")
        deadline = time.time() + 120
        while job.exit_code is None and time.time() < deadline:
            time.sleep(0.05)
        assert job.exit_code == 0
        idx, lines = r.lines_since(0)
        assert idx > 0 and any("usage:" in ln for ln in lines)

    def test_cancel_marks_cancelled(self):
        r = runner.SingleJobRunner()
        # A long-running pipeline invocation would be needed to test cancel
        # mid-flight; instead verify cancel on a finished job is a no-op.
        job = r.start(["--help"], label="help")
        deadline = time.time() + 120
        while job.exit_code is None and time.time() < deadline:
            time.sleep(0.05)
        assert r.cancel() is False


class TestLocalSongDirM13:
    """--song-dir deploys: the Beat Sage + local-folder sections hand the
    pipeline a validated folder; the argv must mirror the pipeline's own
    precedence (song_dir overrides the BeatSaver download)."""

    def test_song_dir_builds_local_argv(self, tmp_path):
        d = tmp_path / "mymap"
        d.mkdir()
        opts = deploy.DeployOptions(song_dir=str(d), target="BadGuy")
        argv = opts.build_argv()
        assert argv[:4] == ["--song-dir", str(d), "--target", "BadGuy"]
        assert "--download-beat-saver-song" not in argv
        assert argv == ["--song-dir", str(d), "--target", "BadGuy",
                        "--pcm16", "--no-pad", "--convert-to-v3", "--deploy-full"]

    def test_song_dir_overrides_map_id(self, tmp_path):
        d = tmp_path / "mymap"
        d.mkdir()
        opts = deploy.DeployOptions(map_id="1d6c7c2", song_dir=str(d),
                                    target="BadGuy")
        argv = opts.build_argv()
        assert "--download-beat-saver-song" not in argv
        assert "--song-dir" in argv

    def test_no_source_raises_with_hint(self):
        opts = deploy.DeployOptions(target="BadGuy")
        with pytest.raises(ValueError, match="nothing was picked"):
            opts.build_argv()

    def test_missing_song_dir_raises_with_fix(self):
        opts = deploy.DeployOptions(song_dir="/no/such/folder", target="BadGuy")
        with pytest.raises(ValueError, match="To fix"):
            opts.build_argv()

    def test_describe_shows_local_folder(self, tmp_path):
        d = tmp_path / "mymap"
        d.mkdir()
        opts = deploy.DeployOptions(song_dir=str(d), target="BadGuy")
        assert "local folder" in opts.describe()
        assert "map 1d6c7c2" not in opts.describe()

    def test_describe_still_shows_map_id(self):
        opts = deploy.DeployOptions(map_id="1d6c7c2", target="BadGuy")
        assert "map 1d6c7c2" in opts.describe()
