#!/usr/bin/env python3
"""
Adopt pack bundles built by the older `build_all_pack_modes.py` dev script into
the production manifest (<build_dir>/manifest.json).

The production builder `tools/build_pack_mode_bundles.py` maintains the manifest
itself, but the first 36 patched bundles were produced before that module existed.
This script computes size + decompressed-stream CRC for every existing
*_pack_modes_assets_all_*.bundle in the build dir, matches its album (and thus
catalogBundleName) via beat_saber_song_ids.json, and writes the manifest so the
pipeline's `_regenerate_merged_catalog` / `_ensure_pack_mode_bundles` can treat
them as already-built.

Usage:
    python3 development/scripts/adopt_pack_modes_manifest.py [--build-dir DIR] [--write]
"""

import os
import sys
import json
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'tools'))

import build_pack_mode_bundles as bpm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build-dir', default=os.path.join(PROJECT_ROOT, 'pack_modes_bundles'))
    ap.add_argument('--song-ids', default=os.path.join(PROJECT_ROOT, 'beat_saber_song_ids.json'))
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    with open(args.song_ids) as f:
        data = json.load(f)
    by_bundle = {}
    for album in data['albums']:
        if album.get('packBundle'):
            by_bundle[album['packBundle']] = album

    adopted = []
    for name in sorted(os.listdir(args.build_dir)):
        if not name.endswith('.bundle') or '_modes_assets_all_' not in name:
            continue
        path = os.path.join(args.build_dir, name)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            continue
        original = name.replace('_modes_assets_all_', '_assets_all_')
        album = by_bundle.get(original)
        if album is None:
            print(f"  ⚠️  No album match for {name} (skipped)")
            continue
        with open(path, 'rb') as f:
            bundle_bytes = f.read()
        adopted.append({
            'pack': album['pack'],
            'packBundle': album['packBundle'],
            'patchedBundle': name,
            'local_path': path,
            'size': len(bundle_bytes),
            'crc': bpm.crc_decompressed_stream(bundle_bytes),
            'catalogBundleName': album.get('catalogBundleName', ''),
            'patched_slots': album.get('patched_slots', 0),
        })

    print(f"Adopted {len(adopted)} bundles")
    for a in adopted:
        print(f"  {a['pack']:20s} {a['patchedBundle']} ({a['size']:,} B, crc={a['crc']})")
    if args.write:
        bpm._save_manifest(args.build_dir, adopted)
        print(f"Wrote {os.path.join(args.build_dir, 'manifest.json')}")
    else:
        print("Dry run (use --write to save the manifest).")


if __name__ == '__main__':
    main()
