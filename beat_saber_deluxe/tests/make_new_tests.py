#!/usr/bin/env python3
"""
Create two new tests that we haven't tried before:
1. Original audio snippet (3s) in our FSB5 - tests bundle building process
2. All-zero silence FSB5 - tests basic FSB5 structure compatibility
"""
import gzip
import io
import json
import os
import struct
import sys

import UnityPy

OUTPUT_DIR = "/workspace/beat_saber_deluxe/custom_songs"
TEMPLATE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData/startmeup"
sys.path.insert(0, '/workspace/beat_saber_deluxe/tools')
from UnityPy.streams import EndianBinaryReader

# Load original FSB5 for reference
with open('/workspace/beat_saber_deluxe/tests/reference/original_audio.fsb5', 'rb') as f:
    original_fsb5 = f.read()

print(f"Original FSB5: {len(original_fsb5)} bytes")
shsz = struct.unpack_from('<I', original_fsb5, 12)[0]
original_sh = original_fsb5[16:16+shsz]
original_audio = original_fsb5[16+shsz:]
print(f"Original SH size: {shsz}, audio data: {len(original_audio)} bytes")

# Build V3 beatmap data (simple, just to make the bundle loadable)
V3_DATA = {
    "version": "4.0.0",
    "colorNotes": [{"b": 1.0}, {"b": 1.5, "i": 1}],
    "colorNotesData": [{"x": 1, "d": 1}, {"x": 3, "c": 1, "d": 3}],
    "bombNotes": [], "bombNotesData": [],
    "obstacles": [], "obstaclesData": [],
    "arcs": [], "arcsData": [],
    "chains": [], "chainsData": [],
    "spawnRotations": [], "spawnRotationsData": [],
}
beatmap_gz = gzip.compress(json.dumps(V3_DATA, separators=(',', ':')).encode())

# ======================================================================
# TEST 1: First 3 seconds of ORIGINAL audio in our FSB5
# ======================================================================
print("\n--- TEST 1: Original audio snippet (3 seconds) ---")

frames_3s_per_ch = int(3.0 * 44100 / 28)  # frames per channel
bytes_for_3s = frames_3s_per_ch * 32  # 32 bytes per stereo frame
original_snippet = original_audio[:bytes_for_3s]

sh1 = bytearray(original_sh)
struct.pack_into('<I', sh1, 4, len(original_snippet))

buf1 = io.BytesIO()
buf1.write(b'FSB5')
buf1.write(struct.pack('<I', 1))
buf1.write(struct.pack('<I', 1))
buf1.write(struct.pack('<I', shsz))
buf1.write(bytes(sh1))
buf1.write(original_snippet)
fsb5_test1 = buf1.getvalue()

# Build bundle
env1 = UnityPy.load(TEMPLATE)
bf1 = list(env1.files.values())[0]
cab1 = bf1.files['CAB-6c9e66546e3e23434517417298a18b91']
resource_key = 'CAB-6c9e66546e3e23434517417298a18b91.resource'

new_res1 = EndianBinaryReader(fsb5_test1)
new_res1.flags = 0
new_res1.BaseOffset = 0
bf1.files[resource_key] = new_res1

# Update AudioClip
for pid, reader in cab1.objects.items():
    if reader.class_id == 83:
        tt = reader.read_typetree()
        tt['m_Resource']['m_Size'] = len(fsb5_test1)
        tt['m_Length'] = 3.0
        reader.save_typetree(tt)
        break

# Update audio.gz
for pid, reader in cab1.objects.items():
    if reader.class_id == 49 and 'audio.gz' in (reader.peek_name() or ''):
        meta = json.dumps({
            "version": "4.0.0", "songChecksum": "custom",
            "songSampleCount": 3 * 44100, "songFrequency": 44100,
            "bpmData": [{"si": 0, "ei": 3 * 44100, "sb": 0.0, "eb": 3.0}]
        }, separators=(',', ':'))
        tt = reader.read_typetree()
        tt['m_Script'] = gzip.compress(meta.encode()).decode('utf-8', 'surrogateescape')
        reader.save_typetree(tt)
        break

# Replace beatmaps
for pid, reader in cab1.objects.items():
    if reader.class_id == 49:
        n = reader.peek_name() or ''
        if '.beatmap' in n:
            tt = reader.read_typetree()
            tt['m_Script'] = beatmap_gz.decode('utf-8', 'surrogateescape')
            reader.save_typetree(tt)

result1 = bf1.save(packer="none")
t1_path = f'{OUTPUT_DIR}/test_original_audio_3s.bundle'
with open(t1_path, 'wb') as f:
    f.write(result1)
print(f"  Saved: {len(result1)} bytes -> {os.path.basename(t1_path)}")
print(f"  FSB5: {len(fsb5_test1)} bytes, {len(original_snippet)} bytes audio (from original)")

# ======================================================================
# TEST 2: All-zero silence FSB5
# ======================================================================
print("\n--- TEST 2: All-zero silence (3 seconds) ---")

silence_data = bytes(frames_3s_per_ch * 32)  # All zeros, 32 bytes per stereo frame

sh2 = bytearray(original_sh)
struct.pack_into('<I', sh2, 4, len(silence_data))

buf2 = io.BytesIO()
buf2.write(b'FSB5')
buf2.write(struct.pack('<I', 1))
buf2.write(struct.pack('<I', 1))
buf2.write(struct.pack('<I', shsz))
buf2.write(bytes(sh2))
buf2.write(silence_data)
fsb5_test2 = buf2.getvalue()

# Build bundle
env2 = UnityPy.load(TEMPLATE)
bf2 = list(env2.files.values())[0]
cab2 = bf2.files['CAB-6c9e66546e3e23434517417298a18b91']

new_res2 = EndianBinaryReader(fsb5_test2)
new_res2.flags = 0
new_res2.BaseOffset = 0
bf2.files[resource_key] = new_res2

# Update AudioClip
for pid, reader in cab2.objects.items():
    if reader.class_id == 83:
        tt = reader.read_typetree()
        tt['m_Resource']['m_Size'] = len(fsb5_test2)
        tt['m_Length'] = 3.0
        reader.save_typetree(tt)
        break

# Update audio.gz
for pid, reader in cab2.objects.items():
    if reader.class_id == 49 and 'audio.gz' in (reader.peek_name() or ''):
        meta = json.dumps({
            "version": "4.0.0", "songChecksum": "custom",
            "songSampleCount": 3 * 44100, "songFrequency": 44100,
            "bpmData": [{"si": 0, "ei": 3 * 44100, "sb": 0.0, "eb": 3.0}]
        }, separators=(',', ':'))
        tt = reader.read_typetree()
        tt['m_Script'] = gzip.compress(meta.encode()).decode('utf-8', 'surrogateescape')
        reader.save_typetree(tt)
        break

# Replace beatmaps
for pid, reader in cab2.objects.items():
    if reader.class_id == 49:
        n = reader.peek_name() or ''
        if '.beatmap' in n:
            tt = reader.read_typetree()
            tt['m_Script'] = beatmap_gz.decode('utf-8', 'surrogateescape')
            reader.save_typetree(tt)

result2 = bf2.save(packer="none")
t2_path = f'{OUTPUT_DIR}/test_silence.bundle'
with open(t2_path, 'wb') as f:
    f.write(result2)
print(f"  Saved: {len(result2)} bytes -> {os.path.basename(t2_path)}")

print("\n" + "=" * 60)
print("NEW TESTS READY FOR PS4:")
print(f"  1. {os.path.basename(t1_path)} - ORIGINAL audio (3s) in our FSB5 ({len(fsb5_test1)}b)")
print("     -> Tests if our FSB5 BUILDING process is correct")
print(f"  2. {os.path.basename(t2_path)} - SILENCE (all zeros) ({len(fsb5_test2)}b)")
print("     -> Tests if PS4 accepts our FSB5 structure at all")
print("=" * 60)
print("\nDeploy command:")
print("  lftp -u anonymous, -p 2121 192.168.100.117 \\")
print("    -e 'put test_original_audio_3s.bundle -o /data/GoldHEN/AFR/CUSA12878/startmeup_v3; quit'")
