#!/usr/bin/env python3
"""
BeatSaver Song Downloader
=========================
Downloads full song packs from BeatSaver by hash or key.
Can bulk-restore missing audio for songs in the songs_repo.

Usage:
    python3 download_beatsaver_songs.py --hash <sha1_hash>
    python3 download_beatsaver_songs.py --key <beatsaver_key>
    python3 download_beatsaver_songs.py --restore-missing  # check songs_repo for missing audio
    python3 download_beatsaver_songs.py --restore-missing --search "artist:song"
    python3 download_beatsaver_songs.py --list-missing
"""

import argparse
import glob
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BEATSAVER_API = "https://api.beatsaver.com"
REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..",
                        "beat-saber-ps4-custom-songs", "songs_repo")
REPO_DIR = os.path.normpath(REPO_DIR)


def api_get(path: str, retries=3):
    """Make a GET request to the BeatSaver API."""
    url = f"{BEATSAVER_API}{path}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "BeatSaberPS4CustomSongSupport/1.0",
                "Accept": "application/json"
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if resp.status == 200:
                    return json.loads(data)
                else:
                    print(f"  API returned {resp.status}")
                    return None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("  Not found (404)")
                return None
            if e.code == 429:
                wait = (attempt + 1) * 5
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  HTTP error: {e}")
            return None
        except Exception as e:
            print(f"  Error: {e}")
            if attempt < retries - 1:
                time.sleep(2)
                continue
            return None
    return None


def download_zip(url: str, dest_dir: str) -> bool:
    """Download a zip file from a URL and extract it."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "BeatSaberPS4CustomSongSupport/1.0"
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except Exception as e:
        print(f"  Download failed: {e}")
        return False

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest_dir)
        return True
    except zipfile.BadZipFile:
        print("  Not a valid zip file")
        return False


def download_by_hash(hash_str: str, dest_dir: str = None) -> str:
    """
    Download a song from BeatSaver by its map hash.
    Returns the destination directory path, or None on failure.
    """
    if dest_dir is None:
        dest_dir = os.path.join(REPO_DIR, hash_str)

    # Check BeatSaver API for map info
    print(f"Looking up hash: {hash_str}")
    info = api_get(f"/maps/hash/{hash_str}")
    if not info:
        print(f"  Could not find map with hash {hash_str}")
        return None

    key = info.get("id", "unknown")
    name = info.get("name", "Unknown Song")
    metadata = info.get("metadata", {})
    song_name = metadata.get("songName", name)
    artist = metadata.get("songAuthorName", "Unknown")
    mapper = metadata.get("levelAuthorName", "Unknown")
    bpm = metadata.get("bpm", 0)
    duration = metadata.get("duration", 0)
    # Check for characteristics/beatmaps
    versions = info.get("versions", [])
    char_info = []
    if versions:
        diffs = versions[0].get("diffs", [])
        for d in diffs:
            chars = d.get("characteristic", "Standard")
            diff = d.get("difficulty", "Unknown")
            char_info.append(f"{chars}:{diff}")

    print(f"  Song: {song_name} by {artist} (mapped by {mapper})")
    print(f"  Key: {key}, BPM: {bpm}, Duration: {duration}s")
    print(f"  Difficulties: {', '.join(char_info[:10])}")

    # Check if arks/chains exist
    _has_arcs = any("arc" in str(d).lower() for d in versions[0].get("diffs", [])) if versions else False
    for d in versions[0].get("diffs", []) if versions else []:
        if d.get("arcs", False) or d.get("chains", False):
            _has_arcs = True
            print("  ✅ Has arcs/chains!")
            break

    # Download
    download_url = f"https://beatsaver.com/api/download/key/{key}"
    print(f"  Downloading from: {download_url}")
    os.makedirs(dest_dir, exist_ok=True)
    success = download_zip(download_url, dest_dir)

    if success:
        print(f"  ✅ Downloaded to: {dest_dir}")
        # Verify audio files exist
        audio_files = []
        for ext in ['.ogg', '.wav', '.mp3', '.flac', '.egg']:
            audio_files.extend(glob.glob(os.path.join(dest_dir, f"*{ext}")))
        beatmap_files = glob.glob(os.path.join(dest_dir, "*.dat"))
        print(f"  Audio files: {[os.path.basename(f) for f in audio_files]}")
        print(f"  Beatmap files: {len(beatmap_files)}")
        return dest_dir
    else:
        print("  ❌ Download failed")
        return None


def list_missing_audio():
    """List all songs in REPO_DIR that are missing audio files."""
    missing = []
    for d in sorted(os.listdir(REPO_DIR)):
        dir_path = os.path.join(REPO_DIR, d)
        if not os.path.isdir(dir_path):
            continue
        audio_files = []
        for ext in ['.wav', '.ogg', '.mp3', '.flac', '.egg']:
            audio_files.extend(glob.glob(os.path.join(dir_path, f"*{ext}")))
        if not audio_files:
            beatmaps = glob.glob(os.path.join(dir_path, "*.dat"))
            missing.append((d, len(beatmaps), dir_path))
    return missing


def restore_missing_audio(search: str = None, max_songs: int = None):
    """Restore missing audio for songs in REPO_DIR."""
    missing = list_missing_audio()
    print(f"\nFound {len(missing)} songs missing audio")

    if search:
        missing = [(h, bm, p) for h, bm, p in missing if search.lower() in p.lower()]
        print(f"  Filtered by '{search}': {len(missing)} songs")

    if max_songs:
        missing = missing[:max_songs]

    for i, (hash_str, bm_count, dir_path) in enumerate(missing, 1):
        print(f"\n[{i}/{len(missing)}] {hash_str[:16]}... ({bm_count} beatmaps)")
        download_by_hash(hash_str, dir_path)
        time.sleep(1)  # Be nice to BeatSaver API

    return len(missing)


def download_by_key(key: str, dest_dir: str = None):
    """Download a song by its BeatSaver key."""
    print(f"Looking up key: {key}")
    info = api_get(f"/maps/id/{key}")
    if not info:
        print(f"  Could not find map with key {key}")
        return None

    # Get the hash from the latest version
    versions = info.get("versions", [])
    if not versions:
        print("  No versions found")
        return None

    hash_str = versions[0].get("hash", "")
    if hash_str:
        if dest_dir is None:
            dest_dir = os.path.join(REPO_DIR, hash_str)
        print(f"  Hash: {hash_str}")
        return download_by_hash(hash_str, dest_dir)

    return None


def search_and_download(query: str, max_results: int = 10):
    """Search BeatSaver and download matching songs."""
    print(f"Searching BeatSaver for: {query}")
    results = api_get(f"/search/text/0?q={urllib.parse.quote(query)}&sortOrder=Relevance")
    if not results:
        print("  Search failed or no results")
        return 0

    docs = results.get('docs', [])
    total = results.get('total', 0)
    print(f"  Found {total} results, downloading up to {min(max_results, len(docs))}")

    downloaded = 0
    for i, doc in enumerate(docs[:max_results]):
        key = doc.get('id', '')
        _name = doc.get('name', 'Unknown')
        metadata = doc.get('metadata', {})
        song = metadata.get('songName', 'Unknown')
        artist = metadata.get('songAuthorName', 'Unknown')
        print(f"\n[{i+1}/{min(max_results, len(docs))}] {song} by {artist} (key: {key})")

        versions = doc.get('versions', [])
        if versions:
            hash_str = versions[0].get('hash', '')
            dest_dir = os.path.join(REPO_DIR, hash_str)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)

            download_url = f"https://beatsaver.com/api/download/key/{key}"
            if download_zip(download_url, dest_dir):
                downloaded += 1
                print(f"    Downloaded to: {hash_str[:16]}...")
            else:
                print("    Download failed")
        time.sleep(1)  # Be nice to BeatSaver API

    print(f"\nDone! Downloaded {downloaded} songs")
    return downloaded


def main():
    parser = argparse.ArgumentParser(description="BeatSaver Song Downloader")
    parser.add_argument('--hash', help='Download by SHA1 hash')
    parser.add_argument('--key', help='Download by BeatSaver key (e.g., "1abcd")')
    parser.add_argument('--restore-missing', action='store_true',
                        help='Restore missing audio in songs_repo')
    parser.add_argument('--list-missing', action='store_true',
                        help='List songs missing audio')
    parser.add_argument('--search', default=None,
                        help='Search filter for --restore-missing')
    parser.add_argument('--search-download', default=None,
                        help='Search BeatSaver and download matching songs (e.g., "artist:Fox Stevenson")')
    parser.add_argument('--max', type=int, default=10,
                        help='Max songs to download with --restore-missing or --search-download')
    args = parser.parse_args()

    if args.list_missing:
        missing = list_missing_audio()
        print(f"\nSongs missing audio ({len(missing)}):")
        for hash_str, bm_count, dir_path in missing:
            name = os.path.basename(dir_path)
            print(f"  {name[:16]}... ({bm_count} beatmaps)")
        return 0

    if args.search_download:
        count = search_and_download(args.search_download, args.max)
        return 0

    if args.restore_missing:
        count = restore_missing_audio(args.search, args.max)
        print(f"\nDone! Restored audio for {count} songs")
        return 0

    if args.hash:
        download_by_hash(args.hash)
        return 0

    if args.key:
        download_by_key(args.key)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
