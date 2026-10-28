#!/usr/bin/env python3
"""
Build a bundle using the ORIGINAL 12MB FSB5 audio (unmodified).
Only beatmaps and AudioClip metadata (m_Size, m_Length) are changed.
This tests whether our bundle building process itself is correct.
"""
import gzip
import json
import struct
import sys

import UnityPy

sys.path.insert(0, '/workspace/beat_saber_deluxe/tools')

TEMPLATE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData/startmeup"
OUTPUT = "/workspace/beat_saber_deluxe/custom_songs/test_original_12mb.bundle"

# Load the original bundle
print("Loading template bundle...")
env = UnityPy.load(TEMPLATE)
bf = list(env.files.values())[0]
cab = bf.files['CAB-6c9e66546e3e23434517417298a18b91']

# Get original FSB5 data directly from the original bundle's .resource
print("Reading original .resource data...")
orig_res = bf.files['CAB-6c9e66546e3e23434517417298a18b91.resource']
orig_res.seek(0)
original_fsb5 = orig_res.read(orig_res.Length)
print(f"Original FSB5: {len(original_fsb5)} bytes")

# Keep the ORIGINAL .resource data - don't replace it!
# Just update the beatmaps

# Simple V3 beatmap
V3_DATA = {
    "version": "4.0.0",
    "colorNotes": [{"b": 1.0}, {"b": 1.5, "i": 1}],
    "colorNotesData": [{"x": 1, "d": 1}, {"x": 3, "c": 1, "d": 3}],
    "bombNotes": [], "bombNotesData": [],
    "obstacles": [], "obstaclesData": [],
    "arcs": [], "arcsData": [],
    "chains": [], "chainsData": [],
}
beatmap_gz = gzip.compress(json.dumps(V3_DATA, separators=(',', ':')).encode())

# Replace beatmaps
print("Replacing beatmaps...")
replaced = 0
for pid, reader in cab.objects.items():
    if reader.class_id == 49:
        n = reader.peek_name() or ''
        if '.beatmap' in n:
            tt = reader.read_typetree()
            tt['m_Script'] = beatmap_gz.decode('utf-8', 'surrogateescape')
            reader.save_typetree(tt)
            replaced += 1
print(f"  Replaced {replaced} beatmaps")

# Update audio.gz metadata but keep the same duration
# Parse original FSB5 to get sample count
shsz = struct.unpack_from('<I', original_fsb5, 12)[0]
orig_audio_data = original_fsb5[16+shsz:]
orig_frames = len(orig_audio_data) // 32  # stereo frames
orig_samples = orig_frames * 28
orig_duration = orig_samples / 44100

print(f"Original audio: {orig_frames} frames, {orig_samples} samples, {orig_duration:.1f}s")

# Update audio.gz to match original duration
for pid, reader in cab.objects.items():
    if reader.class_id == 49 and 'audio.gz' in (reader.peek_name() or ''):
        meta = json.dumps({
            "version": "4.0.0", "songChecksum": "custom",
            "songSampleCount": orig_samples,
            "songFrequency": 44100,
            "bpmData": [{"si": 0, "ei": orig_samples, "sb": 0.0, "eb": orig_duration}]
        }, separators=(',', ':'))
        tt = reader.read_typetree()
        tt['m_Script'] = gzip.compress(meta.encode()).decode('utf-8', 'surrogateescape')
        reader.save_typetree(tt)
        print(f"  Updated audio.gz: {orig_samples} samples, {orig_duration:.1f}s")
        break

# DO NOT replace the .resource - keep original audio intact
# But update AudioClip.m_Resource.m_Size to match (should be same size already)
for pid, reader in cab.objects.items():
    if reader.class_id == 83:
        tt = reader.read_typetree()
        # Keep original size
        print(f"  AudioClip resource size: {tt['m_Resource']['m_Size']}")
        print(f"  AudioClip length: {tt['m_Length']}")
        reader.save_typetree(tt)
        break

# Save bundle with LZ4 compression (matching original)
print("Saving bundle with LZ4 compression...")
result = bf.save(packer="lz4")
with open(OUTPUT, 'wb') as f:
    f.write(result)
print(f"Saved: {OUTPUT} ({len(result)} bytes)")

# Verify
print("Verifying...")
v_env = UnityPy.load(OUTPUT)
v_bf = list(v_env.files.values())[0]
v_res = v_bf.files.get('CAB-6c9e66546e3e23434517417298a18b91.resource')
if v_res:
    v_res.seek(0)
    data = v_res.read(min(16, v_res.Length))
    print(f"  .resource holds {v_res.Length} bytes, starting with {data[:4]}")
print("Done!")
