#!/usr/bin/env python3
"""
Regression tests for the clean-slate wipe's git-tracked-file preservation.

History (why this file exists): the 3 git-tracked files inside
custom_songs/ (fsb5_header_template.bin — the hevag encoder's FSB5 header
template; quick_test.bundle, quick_test_gen.py — dev fixtures) were deleted
by `--clean-ps4` on EVERY real run across THREE consecutive fix attempts:

- Exp 229: added `_git_tracked_files` + preserve logic, but ran
  `git ls-files` inheriting the process cwd → [] from any non-repo launch
  dir → wholesale rmtree.
- Exp 231: pinned the git call's cwd to the script's dir — helper now
  returned the right files... as REPO-RELATIVE paths.
- Exp 233 (the actual bug): the wipe compared rglob()'s ABSOLUTE paths
  against those REPO-RELATIVE paths with `item not in tracked` — a Path
  can never equal across forms, so EVERY file was unlinked while the log
  printed "preserved git-tracked: ...". The two prior fixes tested the
  HELPER in isolation and never exercised the COMPARISON.

These tests run the REAL wipe function end-to-end against a scratch git
repository: tracked files must survive, untracked artifacts must be
removed, and the comparison must be exercised (not the helper alone).
"""
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

BACKUP_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'backup-orbeats-files.py')


def _load_backup_module():
    """Load the backup script as a module (functions only; no CLI run)."""
    spec = importlib.util.spec_from_file_location('bs_test', BACKUP_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_scratch_repo():
    """Scratch git repo mimicking the workspace layout: tracked production
    files inside a build-artifact dir, plus untracked artifacts."""
    scratch = Path(tempfile.mkdtemp())
    repo = scratch / 'repo'
    (repo / 'orbeats' / 'custom_songs').mkdir(parents=True)
    (repo / 'orbeats' / 'pack_modes_bundles').mkdir(parents=True)
    (repo / 'orbeats' / 'mass_bundles').mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 't@t'], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 't'], check=True)
    cs = repo / 'orbeats' / 'custom_songs'
    (cs / 'fsb5_header_template.bin').write_bytes(b'TEMPLATE-TRACKED')
    (cs / 'quick_test_gen.py').write_text('# tracked')
    subprocess.run(['git', '-C', str(repo), 'add',
                    str(cs / 'fsb5_header_template.bin'),
                    str(cs / 'quick_test_gen.py')], check=True)
    subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'fixtures'], check=True)
    # Untracked artifacts (what the wipe must remove)
    (cs / 'BadGuy_custom.bundle').write_bytes(b'BUNDLE-ARTIFACT')
    (repo / 'orbeats' / 'pack_modes_bundles' / 'x_pack_modes.bundle').write_bytes(b'X')
    (repo / 'orbeats' / 'mass_bundles' / 'y_v3.bundle').write_bytes(b'Y')
    return repo


class TestCleanSlatePreservesTrackedFiles:
    def test_wipe_end_to_end_preserves_tracked_removes_artifacts(self):
        """THE regression: run the REAL clear_local_pipeline_state against a
        scratch repo; tracked files must survive, artifacts must not."""
        mod = _load_backup_module()
        repo = _make_scratch_repo()
        try:
            cs = repo / 'orbeats' / 'custom_songs'
            mod.PIPELINE_STATE_DIRS = [
                str(cs),
                str(repo / 'orbeats' / 'pack_modes_bundles'),
                str(repo / 'orbeats' / 'mass_bundles'),
            ]
            mod.PIPELINE_STATE_FILES = []  # config-file clearing not under test

            # Simulate the script living in the scratch repo (its __file__
            # pins the repo root used by _git_tracked_files)
            def fake_git_tracked(dir_path):
                r = subprocess.run(
                    ['git', '-C', str(repo), 'ls-files', '--', str(dir_path)],
                    capture_output=True, text=True, timeout=15)
                if r.returncode != 0:
                    return []
                return [(repo / line).resolve()
                        for line in r.stdout.splitlines() if line.strip()]
            mod._git_tracked_files = fake_git_tracked

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.clear_local_pipeline_state()

            assert (cs / 'fsb5_header_template.bin').is_file(), \
                "tracked FSB5 template deleted by the wipe (the recurring bug)"
            assert (cs / 'quick_test_gen.py').is_file(), \
                "tracked dev fixture deleted by the wipe"
            assert not (cs / 'BadGuy_custom.bundle').is_file(), \
                "untracked artifact survived the wipe"
            assert not (repo / 'orbeats' / 'pack_modes_bundles' / 'x_pack_modes.bundle').is_file()
            assert not (repo / 'orbeats' / 'mass_bundles' / 'y_v3.bundle').is_file()
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_tracked_paths_are_absolute_and_comparison_matches(self, tmp_path):
        """Exercise real git output without relying on private tracked game assets."""
        repo_root = tmp_path / "repo"
        cs = repo_root / "orbeats/custom_songs"
        cs.mkdir(parents=True)
        (cs / "fsb5_header_template.bin").write_bytes(b"synthetic fixture")
        subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
        subprocess.run(["git", "-C", str(repo_root), "add", "orbeats/custom_songs"], check=True)
        mod = _load_backup_module()
        mod.__file__ = str(repo_root / "backup-orbeats-files.py")
        tracked = mod._git_tracked_files(cs)
        assert tracked and all(t.is_absolute() for t in tracked)
        assert (cs / "fsb5_header_template.bin").resolve() in tracked
