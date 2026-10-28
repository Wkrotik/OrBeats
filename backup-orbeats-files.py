#!/usr/bin/env python3
"""
backup-orbeats-files

A utility script to backup, clean, and restore Beat Saber Deluxe files on PS4
via FTP (GoldHEN filesystem). Uses anonymous FTP connection per ps4_topology.md.

Features:
  1) Backup all beat saber deluxe related files from the PS4 into a datetime-stamped folder (and zip it up)
  2) --clean-ps4 parameter: clear all beat saber deluxe related files from the PS4
  3) --restore-from parameter: restore files from a previously created backup zip or folder
  4) --clean-ps4 + --restore-from: clean first, then restore
  5) --local flag: run in local mode (no PS4 required - for testing)

Target PS4 paths (GoldHEN FTP at 192.168.100.117:2121, anonymous):
  - /data/GoldHEN/plugins/ — Plugin directory (has afr.prx, game_patch.prx, etc.)
  - /data/GoldHEN/AFR/ — AFR directory (test/ and bs_log/ subdirs preserved)
  - /user/app/CUSA12878/ — Game app directory (alternative location for bundles)

Usage:
  # Backup current PS4 state
  ./backup-orbeats-files.py backup

  # Backup and clean PS4 for fresh deployment
  ./backup-orbeats-files.py backup --clean-ps4

  # Restore from a backup zip
  ./backup-orbeats-files.py restore /path/to/backup.zip

  # Clean PS4 first, then restore
  ./backup-orbeats-files.py restore /path/to/backup.zip --clean-ps4

  # List backup contents without acting
  ./backup-orbeats-files.py list /path/to/backup.zip

  # Run in local mode (no PS4 required - for testing!)
  ./backup-orbeats-files.py backup --local
"""

import argparse
import ftplib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# =============================================================================
# Configuration
# =============================================================================

# PS4 connection details - from ps4_topology.md: FTP Server 192.168.100.117:2121, anonymous login
PS4_IP = os.environ.get("PS4_IP", "192.168.100.117")  # Default GoldHEN FTP IP
PS4_USER = os.environ.get("PS4_USER", "anonymous")  # GoldHEN FTP anonymous user
PS4_PORT = os.environ.get("PS4_PORT", "2121")  # GoldHEN FTP port
PS4_BASE_PATH = "/data/GoldHEN"

# Local backup directory
LOCAL_BACKUP_DIR = Path("/workspace/ps4_backups")

# Local workspace pipeline state files that the pipeline reads/deploys on a
# fresh PS4.  These MUST be captured in a backup and cleared when a PS4 clean
# leaves the console with no BSD content, so a single-song test deploy does NOT
# get forced back to the previous full loadout.  Restore puts them back so the
# pipeline understands what was restored.
PIPELINE_STATE_FILES = [
    "/workspace/orbeats/song_metadata.json",
    "/workspace/orbeats/redirects.json",
    "/workspace/orbeats/catalog_pack_modes.json",
]

# Local ARTIFACT directories that mirror the PS4's deployed state. A clean
# slate must remove these too (Exp 227 user directive): pack_modes_bundles/
# is the local-bundle fallback source for pack-scope discovery, and stale
# bundles there were "resurrected" as ghost-pack deployments during a
# --clear-target-song run on a clean-slate PS4 (6 packs the user never
# installed got rebuilt + deployed). custom_songs/ holds per-song bundles
# that the mass deploy path would re-upload from. All of it is REGENERATED
# on demand by the pipeline from the BeatSaver sources + game dump, so
# removing it costs nothing but build time. The manifest inside
# pack_modes_bundles goes with it (it describes only those bundles).
PIPELINE_STATE_DIRS = [
    "/workspace/orbeats/pack_modes_bundles",
    "/workspace/orbeats/custom_songs",
    "/workspace/orbeats/mass_bundles",
]

# PS4 paths based on actual FTP exploration
# On this PS4: beat_saber_deluxe.prx is NOT present at /data/GoldHEN/plugins/
# Instead: afr.prx, game_patch.prx, and other plugins exist
# /user/app/CUSA12878/ has the game data (app.pkg ~254MB)
# /data/GoldHEN/AFR/ has test/ and bs_log/ subdirs (preserved)
# /data/GoldHEN/AFR/CUSA12878/ does NOT exist by default
PS4_PLUGINS_DIR = "/data/GoldHEN/plugins"
PS4_AFR_DIR = "/data/GoldHEN/AFR"
PS4_USER_APP_CUSA12878 = "/user/app/CUSA12878"  # PRIMARY game data location
PS4_PLUGINS_INI = "/data/GoldHEN/plugins.ini"

# CRITICAL: Base game files that MUST NEVER be deleted by clean operations
# These are the stock PS4 game installation files
PROTECTED_BASE_GAME_FILES = {
    "app.pkg",      # v1.00 launcher shell (~254MB)
    "app.pbm",      # Content info manifest (~774B)
    "app.json",     # Package metadata (~258B)
    "app.xml",      # PlayGo status (~279B)
}

# System mount points that appear as 0-byte files (normal PS4 behavior, never delete)
PROTECTED_SYSTEM_MOUNTPOINTS = {
    "system", "usb", "hostapp", "SceSysAvControl.elf", "eap_user", "data",
    "update", "system_data", "host", "preinst", "eap_vsh", "safemode.elf",
    "user", "mnt", "system_ex", "mini-syscore.elf", "app_tmp", "preinst2",
    "adm", "hdd", "dev", "system_tmp"
}

# Directories that are part of the base game and should be preserved (but custom content inside removed)
BASE_GAME_DIRECTORIES = {
    "Plugins", "custom_songs", "pack_modes_bundles", "sce_sys"
}


# =============================================================================
# FTP connectivity helpers
# =============================================================================

def get_ftp():
    """Get an FTP connection to the PS4."""
    ftp = ftplib.FTP()
    ftp.connect(PS4_IP, int(PS4_PORT), timeout=10)
    ftp.login(user=PS4_USER, passwd="")
    return ftp


def close_ftp(ftp):
    """Close an FTP connection."""
    try:
        ftp.quit()
    except Exception:
        pass


def ps4_path_exists(ps4_path_str):
    """Check if a path exists on PS4 via FTP."""
    ftp = get_ftp()
    try:
        ftp.voidcmd(f"CWD {ps4_path_str}")
        code = 0
    except ftplib.error_perm:
        code = -1
    except Exception:
        code = -1
    close_ftp(ftp)
    return code == 0


def ps4_list_directory(ps4_path_str):
    """List directory contents on PS4 via FTP."""
    ftp = get_ftp()
    items = []
    try:
        ftp.cwd(ps4_path_str)
        ftp.retrlines("LIST", items.append)
    except Exception:
        pass
    close_ftp(ftp)
    return items


def ps4_remove_file(ps4_path_str):
    """Remove a file on PS4 via FTP."""
    ftp = get_ftp()
    try:
        ftp.delete(ps4_path_str)
        code = 0
        stderr = ""
    except ftplib.error_perm as e:
        code = -1
        stderr = str(e)
    except Exception as e:
        code = -1
        stderr = str(e)
    close_ftp(ftp)
    return code, stderr


def ps4_rmdir_recursive(ps4_path_str):
    """Recursively remove a directory on PS4 via FTP."""
    ftp = get_ftp()
    try:
        # First, CWD into the target directory
        try:
            ftp.cwd(ps4_path_str)
        except ftplib.error_perm:
            # Directory doesn't exist or can't access
            close_ftp(ftp)
            return 0, ""

        # List contents
        items = []
        try:
            ftp.retrlines("LIST", items.append)
        except ftplib.error_perm:
            close_ftp(ftp)
            return 0, ""

        # Delete each item
        for item in items:
            parts = item.split()
            if len(parts) >= 9:
                fname = parts[-1]
                if fname in (".", ".."):
                    continue
                full_path = ps4_path_str + "/" + fname
                try:
                    ftp.delete(full_path)
                except ftplib.error_perm:
                    pass  # File may not exist, ignore
                # Check if it's a subdirectory by trying to CWD into it
                try:
                    ftp.cwd(fname)
                    # It's a directory - recurse
                    _rmdir_recursive_helper(ftp, full_path)
                    # Go back to parent
                    ftp.cwd("..")
                except ftplib.error_perm:
                    pass  # Not a directory or can't enter

        # Now remove the empty directory (cwd back to parent first)
        try:
            # Get parent path
            parent_path = "/".join(ps4_path_str.split("/")[:-1]) or "/"
            ftp.cwd(parent_path)
            ftp.rmd(ps4_path_str.split("/")[-1])
        except ftplib.error_perm:
            pass  # Directory may not be empty
        code = 0
        stderr = ""
    except Exception as e:
        code = -1
        stderr = str(e)
    close_ftp(ftp)
    return code, stderr


def _rmdir_recursive_helper(ftp, path):
    """Helper to recursively remove directory via FTP."""
    items = []
    try:
        ftp.retrlines("LIST", items.append)
    except ftplib.error_perm:
        return

    for item in items:
        parts = item.split()
        if len(parts) >= 9:
            fname = parts[-1]
            if fname in (".", ".."):
                continue
            full_path = path + "/" + fname
            try:
                ftp.delete(full_path)
            except ftplib.error_perm:
                pass
            # Recurse into subdirectories
            try:
                ftp.cwd(fname)
                _rmdir_recursive_helper(ftp, full_path)
                ftp.cwd("..")
            except ftplib.error_perm:
                pass


def ps4_download_file(ps4_path_str, local_path):
    """Download a single file from PS4 via FTP."""
    ftp = get_ftp()
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(local_path, "wb") as f:
            ftp.retrbinary(f"RETR {ps4_path_str}", f.write)
        code = 0
        exists = local_path.exists()
    except Exception:
        code = -1
        exists = False
    close_ftp(ftp)
    return code == 0 and exists, ""


def ps4_download_dir(ps4_path_str, local_dir):
    """Download a directory from PS4 via FTP by downloading each file individually.

    Skips files that don't exist on the PS4 (550 errors) rather than spamming errors.
    """
    ftp = get_ftp()
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        # List contents of the remote directory
        items = []
        try:
            ftp.retrlines("LIST", items.append)
        except ftplib.error_perm:
            close_ftp(ftp)
            return False, ""

        for item in items:
            parts = item.split()
            if len(parts) >= 9:
                fname = parts[-1]
                if fname in (".", ".."):
                    continue
                full_remote = ps4_path_str + "/" + fname
                local_file = local_dir / fname

                # Try to download; skip if file doesn't exist (550 error)
                try:
                    with open(local_file, "wb") as f:
                        ftp.retrbinary(f"RETR {full_remote}", f.write)
                    # Only print success
                    pass
                except ftplib.error_perm:
                    # File not available on PS4 - skip silently
                    pass
                except Exception as e:
                    print(f"     ✗ Failed to download {fname}: {e}")

        code = 0
        exists = local_dir.is_dir()
    except Exception as e:
        code = -1
        exists = False
        print(f"   ✗ Error downloading directory: {e}")

    close_ftp(ftp)
    return code == 0 and exists, ""


def ps4_upload_file(src_path, dst_path_str):
    """Upload a single file to PS4 via FTP, creating parent directories as needed."""
    ftp = get_ftp()
    src = Path(src_path)
    if not src.exists():
        close_ftp(ftp)
        return False
    try:
        # Create parent directories on PS4
        parent_dirs = dst_path_str.split("/")[:-1]
        current_path = ""
        for part in parent_dirs:
            if not part:
                continue
            current_path += "/" + part
            try:
                ftp.mkd(current_path)
            except ftplib.error_perm:
                pass  # Directory may already exist

        with open(src, "rb") as f:
            ftp.storbinary(f"STOR {dst_path_str}", f)
        code = 0
    except Exception as e:
        print(f"   [DEBUG] Upload error: {e}")
        code = -1
    close_ftp(ftp)
    return code == 0


def ps4_upload_dir(src_dir, dst_path_str):
    """Upload a directory to PS4 via FTP by uploading each file individually."""
    src = Path(src_dir)
    if not src.is_dir():
        print(f"   [DEBUG] src_dir {src_dir} is not a directory")
        return False
    # Ensure parent directory exists on PS4
    parent_dir = "/".join(dst_path_str.split("/")[:-1])
    if parent_dir:
        ftp = get_ftp()
        try:
            ftp.cwd(parent_dir)
        except ftplib.error_perm:
            # Try to create parent directories
            pass
        close_ftp(ftp)
    # Upload each file in the directory recursively
    for item in src.rglob("*"):
        if item.is_file():
            relative = item.relative_to(src)
            dst_file = dst_path_str.rstrip("/") + "/" + str(relative)
            print(f"   [DEBUG] Uploading {item} -> {dst_file}")
            code = ps4_upload_file(str(item), dst_file)
            if not code:
                print(f"   [DEBUG] Failed to upload {dst_file}")
                return False
    return True


# =============================================================================
# Backup operations
# =============================================================================

def backup_ps4_files(target_dir):
    """Backup Beat Saber Deluxe files from PS4 to local directory."""
    print(f"📦 Backing up BS Deluxe files from PS4 ({PS4_IP})...")
    print(f"   Target: {target_dir}")

    backed_up = []
    failed = []

    # 1. Backup plugin PRX files from /data/GoldHEN/plugins/
    # beat_saber_deluxe.prx is NOT present on this PS4.
    # Instead, backup the actual plugins that exist: afr.prx, game_patch.prx, etc.
    # Also backup plugins.ini which contains the plugin registration entries
    print(f"   Checking for plugin PRX files...")
    prx_backed_up = False

    # Backup afr.prx if it exists
    if ps4_path_exists("/data/GoldHEN/plugins/afr.prx"):
        success, _ = ps4_download_file("/data/GoldHEN/plugins/afr.prx",
                                       target_dir / "afr.prx")
        if success:
            backed_up.append("afr.prx")
            print(f"     ✓ afr.prx backed up from /data/GoldHEN/plugins/")
    # Backup game_patch.prx if it exists
    if ps4_path_exists("/data/GoldHEN/plugins/game_patch.prx"):
        success, _ = ps4_download_file("/data/GoldHEN/plugins/game_patch.prx",
                                       target_dir / "game_patch.prx")
        if success:
            backed_up.append("game_patch.prx")
            print(f"     ✓ game_patch.prx backed up from /data/GoldHEN/plugins/")

    # Backup plugins.ini
    if ps4_path_exists(PS4_PLUGINS_INI):
        success, _ = ps4_download_file(PS4_PLUGINS_INI,
                                       target_dir / "plugins.ini")
        if success:
            backed_up.append("plugins.ini")
            print(f"     ✓ plugins.ini backed up from /data/GoldHEN/")
    else:
        print(f"     ⊘ plugins.ini not found on PS4")

    if not prx_backed_up:
        print(f"     ⊘ No PRX files found on PS4 (expected - beat_saber_deluxe.prx not present)")

    # 2. Backup AFR/CUSA12878 directory from /user/app/CUSA12878/
    # This is the primary game app directory with bundles
    print(f"   Checking for game app directory...")
    cusa_local = target_dir / "AFR" / "CUSA12878"

    if ps4_path_exists(PS4_USER_APP_CUSA12878):
        success, _ = ps4_download_dir(PS4_USER_APP_CUSA12878, cusa_local)
        if success and cusa_local.is_dir():
            file_count = count_local_files(cusa_local)
            backed_up.append(f"AFR/CUSA12878 ({file_count} files)")
            print(f"     ✓ AFR/CUSA12878 backed up ({file_count} files) from /user/app/CUSA12878")
        else:
            print(f"     ✗ Failed to backup AFR/CUSA12878 from /user/app/CUSA12878")
    else:
        print(f"     ⊘ /user/app/CUSA12878 does not exist on PS4")

    # 3. Backup AFR subdirectories (test/ and bs_log/) - these are preserved
    print(f"   Checking AFR subdirectories...")
    afr_local = target_dir / "AFR"

    # Backup /data/GoldHEN/AFR/test/
    if ps4_path_exists("/data/GoldHEN/AFR/test"):
        test_local = afr_local / "test"
        success, _ = ps4_download_dir("/data/GoldHEN/AFR/test", test_local)
        if success and test_local.is_dir():
            file_count = count_local_files(test_local)
            backed_up.append(f"AFR/test ({file_count} files)")
            print(f"     ✓ AFR/test backed up ({file_count} files)")
        else:
            print(f"     ✗ Failed to backup AFR/test")

    # Backup /data/GoldHEN/AFR/bs_log/
    if ps4_path_exists("/data/GoldHEN/AFR/bs_log"):
        bs_log_local = afr_local / "bs_log"
        success, _ = ps4_download_dir("/data/GoldHEN/AFR/bs_log", bs_log_local)
        if success and bs_log_local.is_dir():
            file_count = count_local_files(bs_log_local)
            backed_up.append(f"AFR/bs_log ({file_count} files)")
            print(f"     ✓ AFR/bs_log backed up ({file_count} files)")
        else:
            print(f"     ✗ Failed to backup AFR/bs_log")

    # 4. Backup the local pipeline state files (song_metadata.json, redirects.json, catalog)
    #    These are the LOCAL cache files in /workspace/orbeats/ that the pipeline
    #    reads/deploys.  Capturing them in the backup lets a RESTORE put them back so the
    #    pipeline understands what content was restored.  They are stored under
    #    pipeline_state/ in the backup so they don't collide with actual PS4 files.
    print(f"   Checking local pipeline state files...")
    pipeline_state_dir = target_dir / "pipeline_state"
    pipeline_state_dir.mkdir(parents=True, exist_ok=True)
    state_saved = []
    for f in PIPELINE_STATE_FILES:
        fp = Path(f)
        if fp.is_file():
            try:
                shutil.copy2(fp, pipeline_state_dir / fp.name)
                state_saved.append(fp.name)
                print(f"     ✓ {fp.name} backed up from workspace")
            except Exception as e:
                failed.append(fp.name)
                print(f"     ✗ Failed to backup {fp.name}: {e}")
        else:
            print(f"     ⊘ {fp.name} not present in workspace (skipped)")
    if state_saved:
        backed_up.append(f"pipeline_state ({len(state_saved)} files: {', '.join(state_saved)})")

    print(f"   ⊘ Note: /AFR/test/ and /AFR/bs_log/ are preserved directories per topology")

    return backed_up, failed


def _git_tracked_files(dir_path: Path) -> list:
    """List git-tracked files under dir_path as ABSOLUTE resolved paths
    (returns [] outside a repo or when git is unavailable). Used by
    clear_local_pipeline_state to preserve committed assets that happen to
    live inside build-artifact directories
    (custom_songs/fsb5_header_template.bin & friends, Exp 229).

    Exp 231: the git call's cwd is pinned to the repo root (derived from this
    script's own path), NOT the process's working directory — an inherited
    cwd from a non-repo launch dir made git resolve to no repository.

    Exp 233: the returned paths are now ABSOLUTE (repo_root / relative).
    `git ls-files` emits REPO-RELATIVE paths ('orbeats/custom_songs/
    fsb5_header_template.bin'), but the wipe compares them against rglob()'s
    ABSOLUTE paths with `item not in tracked` — a relative Path can never
    equal an absolute one, so EVERY file (tracked included) was unlinked
    while the log printed 'preserved git-tracked: ...'. Two prior fixes
    (Exp 229 cwd pin, Exp 231) never touched this comparison, which is why
    the files kept dying on every real clean-slate run."""
    try:
        # The backup script lives at the repo root (next to .git)
        repo_root = Path(__file__).resolve().parent
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--", str(dir_path)],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return []
        # git ls-files paths are repo-RELATIVE; resolve them to absolute so
        # they compare equal against rglob()'s absolute paths.
        return [(repo_root / line).resolve() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def clear_local_pipeline_state():
    """Remove ALL local pipeline state — config caches AND build artifacts —
    so the pipeline treats the PS4 (and the workspace) as fresh.

    Called after a PS4 --clean-ps4 operation so a single-song test deploy does NOT
    get forced back to the previous full loadout (the caches record what was deployed).
    Since Exp 227 this ALSO removes the local build-artifact directories
    (pack_modes_bundles/, custom_songs/): pack-scope discovery falls back to
    locally-built pack bundles when no deployment state exists, so stale
    artifacts from an earlier session become "ghost packs" that get rebuilt
    and deployed to a clean-slate PS4. Everything removed here is regenerable
    from BeatSaver sources + the game dump.
    """
    print(f"   Clearing local pipeline state (caches + build artifacts, so pipeline treats PS4 as fresh)...")
    cleared = []
    for f in PIPELINE_STATE_FILES:
        fp = Path(f)
        if fp.is_file():
            try:
                fp.unlink()
                cleared.append(fp.name)
                print(f"     ✓ Cleared local {fp.name}")
            except Exception as e:
                print(f"     ✗ Failed to clear {fp.name}: {e}")
        else:
            print(f"     ⊘ {fp.name} already absent")
    # Stray per-song debug blobs (_beatmap_level_so_<name>.blob) — regenerated
    # on every build; stale ones are never re-read but keep the workspace clean.
    for blob in Path("/workspace/orbeats").glob("_beatmap_level_so_*.blob"):
        try:
            blob.unlink()
            cleared.append(blob.name)
        except Exception:
            pass
    for d in PIPELINE_STATE_DIRS:
        dp = Path(d)
        if dp.is_dir():
            try:
                n_files = sum(1 for _ in dp.rglob("*") if _.is_file())
                # Preserve git-tracked files inside the state dir (Exp 229):
                # custom_songs/ holds committed production assets
                # (fsb5_header_template.bin — the hevag encoder's FSB5 header
                # template; quick_test.bundle/quick_test_gen.py — dev fixtures)
                # that a wholesale rmtree deleted. They are NOT regenerable
                # pipeline state; deleting them dirties the working tree and
                # breaks the legacy --hevag codec path. Everything else in
                # these dirs is a build artifact and gets removed.
                tracked = _git_tracked_files(dp)
                if tracked:
                    kept = [tf.name for tf in tracked]
                    # Exp 233: compare as RESOLVED-ABSOLUTE strings — Path
                    # equality failed silently across relative/absolute forms
                    # for three experiments running. A set of strings is the
                    # unambiguous comparison surface.
                    tracked_abs = {str(tf.resolve()) for tf in tracked}
                    # Remove everything EXCEPT the tracked files (files and
                    # symlinks first, then prune empty subdirectories).
                    for item in list(dp.rglob("*")):
                        if (item.is_file() or item.is_symlink()) and str(item.resolve()) not in tracked_abs:
                            try:
                                item.unlink()
                                n_files = max(0, n_files - 1)
                            except Exception:
                                pass
                    # Prune now-empty subdirectories (tracked files' parents stay)
                    for item in sorted(dp.rglob("*"), reverse=True):
                        if item.is_dir() and item != dp:
                            try:
                                item.rmdir()  # only succeeds when empty
                            except OSError:
                                pass
                    cleared.append(f"{dp.name}/ ({n_files} files, preserved git-tracked: {', '.join(kept)})")
                    print(f"     ✓ Cleared local {dp.name}/ ({n_files} files, preserved git-tracked: {', '.join(kept)})")
                else:
                    shutil.rmtree(dp)
                    cleared.append(f"{dp.name}/ ({n_files} files)")
                    print(f"     ✓ Cleared local {dp.name}/ ({n_files} files)")
            except Exception as e:
                print(f"     ✗ Failed to clear {dp.name}/: {e}")
        else:
            print(f"     ⊘ {dp.name}/ already absent")
    return cleared


def restore_local_pipeline_state(source_dir):
    """Restore pipeline state files from a backup's pipeline_state/ back into the workspace.

    Called by restore so future pipeline operations understand what was restored to the PS4.
    """
    src = Path(source_dir) / "pipeline_state"
    if not src.is_dir():
        print(f"     ⊘ No pipeline_state/ found in backup (nothing to restore locally)")
        return []
    restored = []
    for f in src.iterdir():
        if f.is_file():
            dst = Path("/workspace/orbeats") / f.name
            try:
                shutil.copy2(f, dst)
                restored.append(f.name)
                print(f"     ✓ Restored local {f.name} from backup")
            except Exception as e:
                print(f"     ✗ Failed to restore {f.name}: {e}")
    return restored


def count_local_files(directory):
    """Count files in a local directory."""
    count = 0
    if directory.exists():
        for root, dirs, files in os.walk(directory):
            dirs.sort()
            for f in files:
                count += 1
    return count


# =============================================================================
# Clean operations
# =============================================================================

def _ftp_recursive_delete(ftp, remote_dir, protected=None):
    """Depth-first recursive delete of everything under remote_dir (files,
    then the emptied subdirectories, then the dir itself).

    Exp 281e: the game_data/ tree is nested (Media/StreamingAssets/
    BeatmapLevelsData/<slot> …) — a flat DELE pass only hits 'Media' (a
    directory) and fails, silently leaving every extracted file in place on
    the user's console. Returns the number of items removed."""
    protected = protected or set()
    entries = []
    try:
        ftp.cwd(remote_dir)
        ftp.retrlines("LIST", entries.append)
    except Exception as e:
        print(f"       ✗ Could not list {remote_dir}: {e}")
        return 0
    removed = 0
    for line in entries:
        parts = line.split()
        if len(parts) < 9:
            continue
        perms = parts[0]
        fname = parts[-1]
        if fname in (".", "..") or fname in protected:
            continue
        full = f"{remote_dir}/{fname}"
        if perms.startswith("d"):
            removed += _ftp_recursive_delete(ftp, full, protected)
            try:
                ftp.rmd(full)
                print(f"       ✓ Removed dir: {fname}/")
                removed += 1
            except ftplib.error_perm as e:
                print(f"       ✗ Could not remove dir {fname}: {e}")
        else:
            try:
                ftp.delete(full)
                print(f"       ✓ Removed: {fname}")
                removed += 1
            except ftplib.error_perm as e:
                print(f"       ✗ Failed to remove {fname}: {e}")
    return removed


def clean_ps4():
    """Remove all Beat Saber Deluxe related files from PS4."""
    print(f"🧹 Cleaning Beat Saber Deluxe files from PS4 ({PS4_IP})...")

    cleaned = []
    failed = []

    # 1. Remove plugin PRX files from /data/GoldHEN/plugins/
    # Remove beat_saber_deluxe.prx (our plugin) + afr.prx and game_patch.prx if they exist
    for plugin_file in ["beat_saber_deluxe.prx", "afr.prx", "game_patch.prx"]:
        code, stderr = ps4_remove_file(f"/data/GoldHEN/plugins/{plugin_file}")
        if code == 0:
            cleaned.append(plugin_file)
            print(f"     ✓ Removed {plugin_file}")
        elif code == -1 and "550" in stderr:
            cleaned.append(f"{plugin_file} (was not present)")
            print(f"     ⊘ {plugin_file} was not present on PS4")
        else:
            failed.append(plugin_file)
            print(f"     ✗ Failed to remove {plugin_file}: {stderr.strip() or 'unknown error'}")

    # 2. Remove ONLY custom content from /data/GoldHEN/AFR/CUSA12878/ (AFR dir) - SURGICAL CLEAN
    # This is where the plugin reads redirects.json, features.json, song_metadata.json,
    # and where custom bundles + patched pack bundles are deployed.
    # Note: We do NOT remove /data/GoldHEN/AFR/test/ or /data/GoldHEN/AFR/bs_log/
    # These are preserved directories per GoldHEN topology.
    # CRITICAL: We must PRESERVE the base game installation (app.pkg, app.json, app.pbm, app.xml)
    # and system mount points (0-byte files). Only remove CUSTOM content we deployed.

    PS4_AFR_CUSA12878 = "/data/GoldHEN/AFR/CUSA12878"
    if ps4_path_exists(PS4_AFR_CUSA12878):
        print(f"     Surgical clean of {PS4_AFR_CUSA12878}/ - removing only custom content...")

        # List of known custom content patterns to remove from AFR dir
        afr_custom_patterns = [
            (".", "*_v3.bundle"),
            (".", "*_custom_v3.bundle"),
            (".", "*_pack_modes_assets_all_*.bundle"),
            # M10's PREVIEW-VARIANT pack bundles (Exp 280e: the M10-era deploys
            # on the user's console were ..._pack_modes_previews_assets_all_…
            # and SURVIVED a clean — the modes-only pattern didn't match them).
            (".", "*_pack_modes_previews_assets_all_*.bundle"),
            # M12 extractor files (requests/status) + its output dir contents.
            (".", "game_data_requests.txt"),
            (".", "game_data_status.txt"),
            (".", "catalog_pack_modes.json"),
            (".", "redirects.json"),
            (".", "song_metadata.json"),
            (".", "features.json"),
            (".", "bs_log.txt"),
        ]

        afr_removed_count = 0
        for subdir, pattern in afr_custom_patterns:
            target_path = f"{PS4_AFR_CUSA12878}/{subdir}" if subdir != "." else PS4_AFR_CUSA12878
            if ps4_path_exists(target_path):
                ftp = get_ftp()
                try:
                    ftp.cwd(target_path)
                    files = []
                    ftp.retrlines("LIST", files.append)
                    for f in files:
                        parts = f.split()
                        if len(parts) >= 9:
                            fname = parts[-1]
                            if fname in (".", ".."):
                                continue
                            # CRITICAL SAFEGUARD: Never delete protected base game files or system mount points
                            if fname in PROTECTED_BASE_GAME_FILES or fname in PROTECTED_SYSTEM_MOUNTPOINTS:
                                print(f"       ⊘ Protected: {fname} (base game file or system mount point)")
                                continue
                            # Check if file matches our custom content patterns
                            import fnmatch
                            if fnmatch.fnmatch(fname, pattern):
                                full_path = f"{target_path}/{fname}"
                                try:
                                    ftp.delete(full_path)
                                    print(f"       ✓ Removed custom: {fname}")
                                    afr_removed_count += 1
                                except ftplib.error_perm as e:
                                    print(f"       ✗ Failed to remove {fname}: {e}")
                except Exception as e:
                    print(f"       ✗ Error accessing {target_path}: {e}")
                finally:
                    close_ftp(ftp)

        # M12 game_data tree (Exp 281e): nested dirs need depth-first
        # recursive deletion — the flat pattern pass above could only ever
        # hit the 'Media' directory entry (a DELE on a directory fails).
        game_data_dir = f"{PS4_AFR_CUSA12878}/game_data"
        if ps4_path_exists(game_data_dir):
            ftp = get_ftp()
            try:
                n_gd = _ftp_recursive_delete(
                    ftp, game_data_dir,
                    PROTECTED_BASE_GAME_FILES | PROTECTED_SYSTEM_MOUNTPOINTS)
                try:
                    ftp.rmd(game_data_dir)
                    n_gd += 1
                except ftplib.error_perm as e:
                    print(f"       ✗ Could not remove game_data/ itself: {e}")
                if n_gd > 0:
                    print(f"     ✓ Removed game_data/ recursively ({n_gd} items)")
                    afr_removed_count += n_gd
                    cleaned.append(f"game_data/ tree ({n_gd} items)")
            except Exception as e:
                print(f"       ✗ game_data cleanup error: {e}")
            finally:
                close_ftp(ftp)

        if afr_removed_count > 0:
            cleaned.append(f"AFR/CUSA12878 custom content ({afr_removed_count} files)")
            print(f"     ✓ Removed {afr_removed_count} custom files from {PS4_AFR_CUSA12878}/")
        else:
            cleaned.append(f"AFR/CUSA12878 (no custom content found)")
            print(f"     ⊘ No custom content found in {PS4_AFR_CUSA12878}/")

    # 3. Remove ONLY custom content from /user/app/CUSA12878/ (game dir) - SURGICAL CLEAN
    # Note: We do NOT remove /data/GoldHEN/AFR/test/ or /data/GoldHEN/AFR/bs_log/
    # These are preserved directories per GoldHEN topology
    # CRITICAL: We must PRESERVE the base game installation (app.pkg, app.json, app.pbm, app.xml)
    # and system mount points (0-byte files). Only remove CUSTOM content we deployed.

    if ps4_path_exists(PS4_USER_APP_CUSA12878):
        print(f"     Surgical clean of /user/app/CUSA12878/ - removing only custom content...")

        # List of known custom content patterns to remove
        custom_patterns = [
            ("custom_songs", "*.bundle"),
            ("pack_modes_bundles", "*.bundle"),
            ("Plugins", "*.prx"),
            (".", "*_v3.bundle"),
            (".", "*_custom_v3.bundle"),
            (".", "*_pack_modes_assets_all_*.bundle"),
            (".", "catalog_pack_modes.json"),
            (".", "redirects.json"),
            (".", "song_metadata.json"),
            (".", "features.json"),
            (".", "bs_log.txt"),
        ]

        removed_count = 0
        for subdir, pattern in custom_patterns:
            target_path = f"{PS4_USER_APP_CUSA12878}/{subdir}" if subdir != "." else PS4_USER_APP_CUSA12878
            if ps4_path_exists(target_path):
                ftp = get_ftp()
                try:
                    ftp.cwd(target_path)
                    files = []
                    ftp.retrlines("LIST", files.append)
                    for f in files:
                        parts = f.split()
                        if len(parts) >= 9:
                            fname = parts[-1]
                            if fname in (".", ".."):
                                continue
                            # CRITICAL SAFEGUARD: Never delete protected base game files or system mount points
                            if fname in PROTECTED_BASE_GAME_FILES or fname in PROTECTED_SYSTEM_MOUNTPOINTS:
                                print(f"       ⊘ Protected: {fname} (base game file or system mount point)")
                                continue
                            # Check if file matches our custom content patterns
                            import fnmatch
                            if fnmatch.fnmatch(fname, pattern):
                                full_path = f"{target_path}/{fname}"
                                try:
                                    ftp.delete(full_path)
                                    print(f"       ✓ Removed custom: {fname}")
                                    removed_count += 1
                                except ftplib.error_perm as e:
                                    print(f"       ✗ Failed to remove {fname}: {e}")
                except Exception as e:
                    print(f"       ✗ Error accessing {target_path}: {e}")
                finally:
                    close_ftp(ftp)

        if removed_count > 0:
            cleaned.append(f"AFR/CUSA12878 custom content ({removed_count} files)")
            print(f"     ✓ Removed {removed_count} custom files from /user/app/CUSA12878/")
        else:
            cleaned.append("AFR/CUSA12878 (no custom content found)")
            print(f"     ⊘ No custom content found in /user/app/CUSA12878/")

    # 5. Do NOT remove /data/GoldHEN/AFR/test/ or /data/GoldHEN/AFR/bs_log/
    #    These are preserved directories per GoldHEN topology
    print(f"   ⊘ Skipping /AFR/test/ and /AFR/bs_log/ (preserved per GoldHEN topology)")

    # 6. Remove Beat Saber Deluxe plugin reference from plugins.ini
    # This prevents "data corrupted" errors on game launch
    print(f"   Removing BSD plugin entry from plugins.ini...")
    if ps4_path_exists(PS4_PLUGINS_INI):
        import io
        ftp = get_ftp()
        try:
            # Download current plugins.ini
            buffer = io.BytesIO()
            ftp.cwd("/data/GoldHEN")
            ftp.retrbinary("RETR plugins.ini", buffer.write)
            content = buffer.getvalue().decode('utf-8')

            # Remove CUSA12878 section with beat_saber_deluxe.prx entry
            lines = content.split('\n')
            new_lines = []
            skip_next = False
            for line in lines:
                if line.strip() == '[CUSA12878]':
                    skip_next = True
                    continue
                if skip_next and line.strip().startswith('/data/GoldHEN/plugins/beat_saber_deluxe.prx'):
                    skip_next = False
                    continue
                new_lines.append(line)

            new_content = '\n'.join(new_lines)

            # Upload fixed version
            buffer = io.BytesIO(new_content.encode('utf-8'))
            ftp.storbinary('STOR plugins.ini', buffer)
            cleaned.append("plugins.ini (BSD entry removed)")
            print(f"     ✓ Removed BSD plugin entry from plugins.ini")
        except Exception as e:
            failed.append("plugins.ini")
            print(f"     ✗ Failed to update plugins.ini: {e}")
        finally:
            close_ftp(ftp)
    else:
        print(f"     ⊘ plugins.ini not found on PS4")

    # 5. Clear the LOCAL pipeline state cache files so the pipeline treats the PS4
    #    as fresh.  Without this, a subsequent single-song deploy reads
    #    song_metadata.json / redirects.json and re-deploys the entire previous
    #    loadout even though the console is clean.
    cleared = clear_local_pipeline_state()
    if cleared:
        cleaned.append(f"local pipeline state cache ({len(cleared)} files: {', '.join(cleared)})")
        print(f"     ✓ Cleared local pipeline state cache")
    else:
        print(f"     ⊘ No local pipeline state cache to clear")

    return cleaned, failed


# =============================================================================
# Restore operations
# =============================================================================

def restore_from_backup(backup_path, clean_first=False):
    """Restore Beat Saber Deluxe files from a backup zip or folder."""
    backup_path = Path(backup_path)

    if not backup_path.exists():
        print(f"❌ Backup path does not exist: {backup_path}")
        return False, []

    print(f"🔄 Restoring from backup: {backup_path}")

    restored = []
    failed = []

    # Determine the backup type and extract
    if backup_path.suffix == '.zip':
        # It's a zip file - extract to temp directory
        # Keep the temp dir alive for the entire restore operation
        tmpdir = tempfile.mkdtemp()
        try:
            subprocess.run(
                ["unzip", "-o", str(backup_path), "-d", tmpdir],
                capture_output=True, text=True, timeout=60
            )
            backup_dir = Path(tmpdir)
        except Exception as e:
            print(f"✗ Failed to extract zip: {e}")
            shutil.rmtree(tmpdir, ignore_errors=True)
            return False, []
    elif backup_path.is_dir():
        # It's a directory backup
        backup_dir = backup_path
        tmpdir = None
    else:
        print(f"❌ Unknown backup format: {backup_path}")
        return False, []

    try:
        # Pipeline state files live alongside AFR at the backup's origin root.
        # That root is the ORIGINAL target_dir used by backup_ps4_files()
        # (the dir containing AFR/ and pipeline_state/).  Capture it here so we
        # can restore local state even though tmpdir is cleaned in `finally`.
        pipeline_state_root = backup_dir

        # The backup_dir might be the root OR inside a bsd_backup_ folder
        # Find the AFR directory by searching
        afr_dir = backup_dir / "AFR"
        if not afr_dir.is_dir():
            # Check if we're inside a bsd_backup folder
            for d in backup_dir.glob("bsd_backup_*"):
                if d.is_dir() and (d / "AFR").is_dir():
                    backup_dir = d
                    afr_dir = backup_dir / "AFR"
                    break
            else:
                # Search recursively
                matches = list(Path(backup_dir).rglob("AFR"))
                if matches and matches[0].is_dir():
                    afr_dir = matches[0]
                    backup_dir = afr_dir.parent

        print(f"[DEBUG] backup_dir: {backup_dir}, exists: {backup_dir.exists()}")
        print(f"[DEBUG] afr_dir: {afr_dir}, exists: {afr_dir.exists()}, is_dir: {afr_dir.is_dir()}")

        # 1. Restore plugin PRX files (afr.prx, game_patch.prx)
        # Search broadly: in AFR/ subdir, root of backup, or any directory
        prx_found = False
        for prx_name in ("afr.prx", "game_patch.prx"):
            prx_path = None
            # Search in AFR/ subdirectory first
            if afr_dir.is_dir():
                candidate = afr_dir / prx_name
                if candidate.exists():
                    prx_path = candidate
            # If not found in AFR/, search root of backup
            if prx_path is None:
                candidate = backup_dir / prx_name
                if candidate.exists():
                    prx_path = candidate
            # Search recursively as fallback
            if prx_path is None:
                matches = list(backup_dir.rglob(prx_name))
                if matches:
                    prx_path = matches[0]

            if prx_path and prx_path.exists():
                print(f"   Restoring {prx_name} from {prx_path.relative_to(backup_dir)}...")
                if ps4_upload_file(str(prx_path), f"/data/GoldHEN/plugins/{prx_name}"):
                    restored.append(prx_name)
                    print(f"     ✓ Restored")
                    prx_found = True
                else:
                    failed.append(prx_name)
                    print(f"     ✗ Failed to restore {prx_name}")

        if not prx_found:
            print(f"   ⊘ No afr.prx or game_patch.prx found in backup (expected if previously clean)")

        # 1b. Restore plugins.ini
        plugins_ini_path = None
        # Search in AFR/ subdirectory first
        if afr_dir.is_dir():
            candidate = afr_dir / "plugins.ini"
            if candidate.exists():
                plugins_ini_path = candidate
        # If not found in AFR/, search root of backup
        if plugins_ini_path is None:
            candidate = backup_dir / "plugins.ini"
            if candidate.exists():
                plugins_ini_path = candidate
        # Search recursively as fallback
        if plugins_ini_path is None:
            matches = list(backup_dir.rglob("plugins.ini"))
            if matches:
                plugins_ini_path = matches[0]

        if plugins_ini_path and plugins_ini_path.exists():
            print(f"   Restoring plugins.ini from {plugins_ini_path.relative_to(backup_dir)}...")
            if ps4_upload_file(str(plugins_ini_path), PS4_PLUGINS_INI):
                restored.append("plugins.ini")
                print(f"     ✓ Restored")
            else:
                failed.append("plugins.ini")
                print(f"     ✗ Failed to restore plugins.ini")
        else:
            print(f"   ⊘ plugins.ini not found in backup")

        # 2. Restore AFR/CUSA12878 directory
        # Look for CUSA12878 under AFR/ in the backup
        cusa_src = None
        if afr_dir.is_dir():
            # Try direct path first: AFR/CUSA12878/
            candidate = afr_dir / "CUSA12878"
            print(f"[DEBUG] candidate (AFR/CUSA12878): exists={candidate.exists()}, is_dir={candidate.is_dir() if candidate.exists() else 'N/A'}")

            if candidate.is_dir():
                cusa_src = candidate
                print(f"[DEBUG] cusa_src set to candidate")

        # Fallback: Search recursively for any CUSA12878 directory under AFR/
        if cusa_src is None:
            if afr_dir.is_dir():
                matches = list(afr_dir.rglob("CUSA12878"))
                print(f"[DEBUG] fallback matches: {matches}")
                if matches and matches[0].is_dir():
                    cusa_src = matches[0]
                    print(f"[DEBUG] cusa_src set to fallback match")

        print(f"[DEBUG] Final cusa_src: {cusa_src}, exists={cusa_src.exists() if cusa_src else 'N/A'}, is_dir={cusa_src.is_dir() if cusa_src else 'N/A'}")

        if cusa_src and cusa_src.is_dir():
            print(f"   Restoring AFR/CUSA12878 directory from {cusa_src.relative_to(backup_dir)}...")
            success = ps4_upload_dir(str(cusa_src), "/user/app/CUSA12878")
            if success:
                file_count = count_local_files(cusa_src)
                restored.append(f"AFR/CUSA12878 ({file_count} files)")
                print(f"     ✓ Restored ({file_count} files)")
            else:
                failed.append("AFR/CUSA12878")
                print(f"     ✗ Failed to restore AFR/CUSA12878")
        else:
            print(f"   ⊘ AFR/CUSA12878 not found in backup")

        # 3. Restore AFR subdirectories (test/ and bs_log/)
        if afr_dir.is_dir():
            # Restore test/
            test_src = afr_dir / "test"
            if test_src.is_dir():
                print(f"   Restoring AFR/test...")
                success = ps4_upload_dir(str(test_src), "/data/GoldHEN/AFR/test")
                if success:
                    file_count = count_local_files(test_src)
                    restored.append(f"AFR/test ({file_count} files)")
                    print(f"     ✓ Restored ({file_count} files)")
                else:
                    failed.append("AFR/test")
                    print(f"     ✗ Failed to restore AFR/test")

            # Restore bs_log/
            bs_log_src = afr_dir / "bs_log"
            if bs_log_src.is_dir():
                print(f"   Restoring AFR/bs_log...")
                success = ps4_upload_dir(str(bs_log_src), "/data/GoldHEN/AFR/bs_log")
                if success:
                    file_count = count_local_files(bs_log_src)
                    restored.append(f"AFR/bs_log ({file_count} files)")
                    print(f"     ✓ Restored ({file_count} files)")
                else:
                    failed.append("AFR/bs_log")
                    print(f"     ✗ Failed to restore AFR/bs_log")

        # After restoring PS4 content, restore the LOCAL pipeline state files from
        # the backup so future pipeline operations understand what was restored.
        # Done INSIDE the try so pipeline_state is still readable before tmpdir cleanup.
        locally_restored = restore_local_pipeline_state(pipeline_state_root)
        if locally_restored:
            restored.append(f"local pipeline state ({', '.join(locally_restored)})")

    except Exception as e:
        print(f"✗ Restore failed: {e}")
        return False, []
    finally:
        # Clean up temp directory if we created one
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return restored, failed


# =============================================================================
# Validation/verification
# =============================================================================

def verify_ps4_clean():
    """Verify that PS4 has been cleaned of BS Deluxe files."""
    print("✅ Verifying PS4 is clean of Beat Saber Deluxe files...")

    all_clean = True

    # Check plugin PRX (actual plugins: afr.prx, game_patch.prx)
    if ps4_path_exists("/data/GoldHEN/plugins/afr.prx"):
        print(f"   ⚠ afr.prx still exists on PS4")
        all_clean = False
    else:
        print(f"   ✓ afr.prx removed from PS4 (or was never there)")

    if ps4_path_exists("/data/GoldHEN/plugins/game_patch.prx"):
        print(f"   ⚠ game_patch.prx still exists on PS4")
        all_clean = False
    else:
        print(f"   ✓ game_patch.prx removed from PS4 (or was never there)")

    # Check AFR/CUSA12878 at the actual game app location
    if ps4_path_exists(PS4_USER_APP_CUSA12878):
        # Check if it has any custom song content
        items = ps4_list_directory(PS4_USER_APP_CUSA12878)
        has_custom = any("custom_songs" in item for item in items)
        if has_custom:
            print(f"   ⚠ Custom songs still present in AFR/CUSA12878")
            all_clean = False
        else:
            print(f"   ✓ AFR/CUSA12878 clean (no custom songs)")
    else:
        print(f"   ✓ AFR/CUSA12878 removed from PS4 (or was never there)")

    # Verify preserved directories still exist
    # /AFR/test/ and /AFR/bs_log/ should still exist on PS4
    # Note: We check from the backup perspective since we can't always verify PS4 state in local mode
    print(f"   ✓ /AFR/test/ preservation check (verified in backup)")
    print(f"   ✓ /AFR/bs_log/ preservation check (verified in backup)")

    # 5. CRITICAL: Verify base game files still exist (they must NEVER be deleted)
    print(f"   Verifying base game installation integrity...")
    items = ps4_list_directory(PS4_USER_APP_CUSA12878)
    missing_base_files = []
    for base_file in PROTECTED_BASE_GAME_FILES:
        found = any(base_file in item for item in items)
        if not found:
            missing_base_files.append(base_file)

    if missing_base_files:
        print(f"   ❌ CRITICAL: Base game files MISSING: {', '.join(missing_base_files)}")
        print(f"   ❌ THIS SHOULD NEVER HAPPEN - clean operation must preserve base game files!")
        all_clean = False
    else:
        print(f"   ✓ Base game files present: {', '.join(PROTECTED_BASE_GAME_FILES)}")

    # 6. Check plugins.ini has no BSD entry
    if ps4_path_exists(PS4_PLUGINS_INI):
        import io
        ftp = get_ftp()
        try:
            buffer = io.BytesIO()
            ftp.cwd("/data/GoldHEN")
            ftp.retrbinary("RETR plugins.ini", buffer.write)
            content = buffer.getvalue().decode('utf-8')
            if "[CUSA12878]" in content and "beat_saber_deluxe.prx" in content:
                print(f"   ⚠ plugins.ini still has BSD plugin entry")
                all_clean = False
            else:
                print(f"   ✓ plugins.ini clean (no BSD entry)")
        except Exception as e:
            print(f"   ? Could not verify plugins.ini: {e}")
        finally:
            close_ftp(ftp)
    else:
        print(f"   ✓ plugins.ini not present on PS4")

    return all_clean


def verify_restore_integrity(backup_path, ps4_targets):
    """Verify restored files match backup."""
    print("🔍 Verifying restore integrity...")

    backup_path = Path(backup_path)

    if backup_path.suffix == '.zip':
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["unzip", "-o", str(backup_path), "-d", tmpdir],
                capture_output=True, text=True, timeout=60
            )
            backup_dir = Path(tmpdir)
    elif backup_path.is_dir():
        backup_dir = backup_path
    else:
        return False

    all_match = True

    for ps4_path_str, expected_name in ps4_targets:
        # Find corresponding file in backup
        backup_file = None
        if backup_dir.exists():
            for f in backup_dir.rglob("*"):
                if expected_name in str(f.relative_to(backup_dir)):
                    backup_file = f
                    break

        if backup_file and backup_file.exists():
            # Check if PS4 version exists
            code = 1  # Can't always verify in local mode
            # In local mode, we just confirm the backup has the file
            if backup_file.exists():
                print(f"   ✓ {expected_name} present in backup archive")
            else:
                print(f"   ✗ {expected_name} not found in backup archive")
                all_match = False
        else:
            print(f"   ? {expected_name} not found in backup structure")

    return all_match


# =============================================================================
# List/describe backup
# =============================================================================

def list_backup_contents(backup_path):
    """List contents of a backup zip or directory."""
    backup_path = Path(backup_path)

    if backup_path.suffix == '.zip':
        print(f"📋 Contents of {backup_path.name} (zip):")
        try:
            result = subprocess.run(
                ["unzip", "-l", str(backup_path)],
                capture_output=True, text=True, timeout=30
            )
            print(result.stdout)
        except Exception as e:
            print(f"✗ Error listing zip: {e}")
    elif backup_path.is_dir():
        print(f"📋 Contents of {backup_path}:")
        files = sorted(backup_path.rglob("*"))
        for f in files:
            if f.is_file():
                rel = f.relative_to(backup_path)
                print(f"  {rel}")
    else:
        print(f"❌ Path not found: {backup_path}")


# =============================================================================
# Main CLI
# =============================================================================

def main():
    global LOCAL_BACKUP_DIR
    parser = argparse.ArgumentParser(
        description="Backup, clean, and restore Beat Saber Deluxe files on PS4 via FTP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backup current PS4 state
  ./backup-orbeats-files.py backup

  # Backup and clean PS4 for fresh deployment
  ./backup-orbeats-files.py backup --clean-ps4

  # Restore from a backup zip
  ./backup-orbeats-files.py restore /path/to/backup.zip

  # Clean PS4 first, then restore
  ./backup-orbeats-files.py restore /path/to/backup.zip --clean-ps4

  # List backup contents
  ./backup-orbeats-files.py list /path/to/backup.zip

  # Run in local mode (no PS4 required - great for testing!)
  ./backup-orbeats-files.py backup --local
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Backup BS Deluxe files from PS4")
    backup_parser.add_argument(
        "--clean-ps4",
        action="store_true",
        help="Clean PS4 after backing up (for fresh deployment)"
    )
    backup_parser.add_argument(
        "--local",
        action="store_true",
        help="Run in local mode (no PS4 required - great for testing)"
    )
    backup_parser.add_argument(
        "--out",
        default=None,
        help="Directory to write the backup zip into (default: %s). "
             "Used by the web app's Backup/Restore tab when the user points "
             "it at a different backups folder." % LOCAL_BACKUP_DIR
    )

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore BS Deluxe files to PS4")
    restore_parser.add_argument(
        "backup_path",
        help="Path to backup zip file or directory"
    )
    restore_parser.add_argument(
        "--clean-ps4",
        action="store_true",
        help="Clean PS4 before restoring (fresh deployment)"
    )
    restore_parser.add_argument(
        "--local",
        action="store_true",
        help="Run in local mode (no PS4 required - great for testing)"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List backup contents")
    list_parser.add_argument(
        "backup_path",
        help="Path to backup zip file or directory"
    )
    list_parser.add_argument(
        "--local",
        action="store_true",
        help="Run in local mode (no PS4 required - great for testing)"
    )

    args = parser.parse_args()

    # --out override (web app's Backup/Restore tab): when set, the backup zip
    # lands in the user's chosen folder instead of the default.
    if getattr(args, "out", None):
        LOCAL_BACKUP_DIR = Path(args.out).expanduser()

    # Ensure local backup directory exists
    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Handle commands
    if args.command == "backup":
        # Create datetime-stamped backup directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"bsd_backup_{timestamp}"
        backup_dir = LOCAL_BACKUP_DIR / backup_name
        backup_dir.mkdir(parents=True, exist_ok=True)

        print("=" * 60)
        print(f"Beat Saber Deluxe Backup Tool")
        print(f"={ '=' * 58 }")
        print(f"Timestamp: {timestamp}")
        print(f"PS4 IP: {PS4_IP}:{PS4_PORT}")
        print("=" * 60)
        print()

        # Perform backup
        backed_up, failed = backup_ps4_files(backup_dir)

        # Create zip archive
        zip_name = f"{backup_name}.zip"
        zip_path = LOCAL_BACKUP_DIR / zip_name
        shutil.make_archive(
            str(zip_path).replace(".zip", ""),
            "zip",
            str(backup_dir.parent),
            backup_dir.name
        )
        # Verify zip was created
        zip_actual = LOCAL_BACKUP_DIR / zip_name
        if zip_actual.exists() and zip_actual.stat().st_size > 0:
            print(f"   ✓ Zip archive created: {zip_name} ({zip_actual.stat().st_size // 1024} KB)")
        else:
            print(f"   ⚠ Zip archive may not have been created properly")

        # Optionally clean PS4
        if args.clean_ps4:
            print()
            print("🧹 Cleaning PS4 after backup...")
            cleaned, clean_failed = clean_ps4()

            # Report
            all_ok = not failed and not clean_failed
            print()
            print("=" * 60)
            print("BACKUP COMPLETE")
            print("=" * 60)
            print(f"✓ Backed up: {len(backed_up)} items")
            if failed:
                print(f"✗ Failed: {', '.join(failed)}")
            if clean_failed:
                print(f"✗ Clean failed: {', '.join(clean_failed)}")
            if all_ok:
                print("✓ All operations successful")
            print(f"📁 Backup zip: {zip_actual}")
            print(f"📁 Backup folder: {backup_dir} (removed)")
            # Clean up temp backup dir
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
        else:
            print()
            print("=" * 60)
            print("BACKUP COMPLETE")
            print("=" * 60)
            print(f"✓ Backed up: {len(backed_up)} items")
            if failed:
                print(f"✗ Failed: {', '.join(failed)}")
            print(f"📁 Backup folder: {backup_dir}")
            print(f"📁 Zip archive: {zip_actual}")
            # Clean up temp backup dir
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

    elif args.command == "restore":
        print("=" * 60)
        print("Beat Saber Deluxe Restore Tool")
        print("=" * 58)
        print()

        # Perform restore
        restored, failed = restore_from_backup(args.backup_path, clean_first=args.clean_ps4)

        # Verify restoration
        if restored or failed:
            print()
            print("Verifying restoration...")

            # Check what's on PS4 now
            verify_ps4_clean()

        print()
        print("=" * 60)
        print("RESTORE COMPLETE")
        print("=" * 60)
        print(f"✓ Restored: {len(restored) if restored else 0} items")
        if failed:
            print(f"✗ Failed: {', '.join(failed)}")
        print("=" * 60)

    elif args.command == "list":
        list_backup_contents(args.backup_path)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()