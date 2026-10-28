#!/usr/bin/env python3
"""
Create multiple test FSB5 bundles to isolate the audio freeze issue.
Tests:
1. PCM format (0) - to check if any FSB5 audio plays
2. HEVAG with frequency set
3. HEVAG with padded audio (15 bytes for offset=15)
4. Minimal monotone pure sine
"""
import gzip
import io
import json
import math
import os
import struct
import sys

sys.path.insert(0, '/workspace/beat_saber_deLuxe/tools')

from hevag_encoder import _load_fsb5_header_template, pcm_to_hevag

# First, analyze the original FSB5
print("=" * 60)
print("ANALYZING ORIGINAL FSB5")
print("=" * 60)

with open('tests/reference/original_audio.fsb5', 'rb') as f:
    orig = f.read()

print(f"Original FSB5: {len(orig)} bytes")

# Parse header
magic = orig[0:4]
ver = struct.unpack_from('<I', orig, 4)[0]
nsamp = struct.unpack_from('<I', orig, 8)[0]
shsz = struct.unpack_from('<I', orig, 12)[0]
print(f"Header: magic={magic} ver={ver} nsamples={nsamp} sh_size={shsz}")

# Sample header
orig_sh = orig[16:916]
orig_ds = struct.unpack_from('<I', orig_sh, 4)[0]
orig_off = struct.unpack_from('<I', orig_sh, 8)[0]
orig_fmt = struct.unpack_from('<H', orig_sh, 12)[0]
orig_flags = struct.unpack_from('<H', orig_sh, 14)[0]
orig_freq = struct.unpack_from('<i', orig_sh, 16)[0]
print("Sample header:")
print(f"  data_size={orig_ds}")
print(f"  offset={orig_off}")
print(f"  format=0x{orig_fmt:04x}")
print(f"  flags=0x{orig_flags:04x}")
print(f"  freq={orig_freq}")
print(f"  Name offset: {struct.unpack_from('<I', orig_sh, 0)[0]}")
print(f"  Channel mode byte: {orig_sh[30] if len(orig_sh) > 30 else 'N/A'}")

# What format code is actually used?
fmt_names = {0: 'PCM', 1: 'HEVAG', 2: 'ADPCM', 8: 'Vorbis', 10: 'ATRAC9'}
print(f"  Format: {fmt_names.get(orig_fmt, f'UNKNOWN({orig_fmt})')}")

# Audio data starts at byte 916 (after 16 header + 900 sh)
# But let's verify by checking what offset=15 points to
audio_offset_to_check = orig_off
if audio_offset_to_check < len(orig):
    # Offset from various reference points
    print(f"\n  Testing offset={audio_offset_to_check}:")
    print(f"    From file start: byte {audio_offset_to_check}: {orig[audio_offset_to_check:audio_offset_to_check+16].hex()}")
    print(f"    From SH start (+16): byte {16+audio_offset_to_check}: {orig[16+audio_offset_to_check:16+audio_offset_to_check+16].hex()}")
    print(f"    From SH end (+916): byte {916+audio_offset_to_check}: {orig[916+audio_offset_to_check:916+audio_offset_to_check+16].hex()}")

# Audio starts at byte 916 in FSB5
audio_start = 916
audio_data = orig[audio_start:audio_start + orig_ds]
print("\nActual audio data:")
print(f"  Start byte: {audio_start}")
print(f"  Size: {len(audio_data)} bytes (declared: {orig_ds})")
print(f"  First 32 bytes: {audio_data[:32].hex()}")

# HEVAG frame analysis of original audio
n_frames_total = len(audio_data) // 16
print(f"  Total HEVAG frames (mono): {n_frames_total}")
print(f"  Estimated duration: {n_frames_total * 28 / orig_freq:.2f}s (at {orig_freq}Hz)")

# Frame type analysis of original audio
frame_types = {}
for i in range(min(5000, n_frames_total)):  # Sample first 5000 frames
    f = audio_data[i*16:(i+1)*16]
    if len(f) >= 16:
        pred = f[0] & 0xF
        shift = (f[0] >> 4) & 0xF
        key = f"P{pred}S{shift}"
        frame_types[key] = frame_types.get(key, 0) + 1

print("\nOriginal frame type distribution (first 5000 frames):")
for k, v in sorted(frame_types.items(), key=lambda x: -x[1])[:15]:
    print(f"  {k}: {v} ({100*v/5000:.1f}%)")

# ==========================================================
# Detect if this is mono or stereo
# ==========================================================
# HEVAG for stereo uses frame interleaving: L, R, L, R...
# Check if frames alternate similar/different patterns
print("\nMono or Stereo check:")
# Compare frame 0 and frame 1
f0 = audio_data[0:16]
f1 = audio_data[16:32]
pred0, pred1 = f0[0] & 0xF, f1[0] & 0xF
shift0, shift1 = (f0[0] >> 4) & 0xF, (f1[0] >> 4) & 0xF
print(f"  Frame 0: pred={pred0} shift={shift0}")
print(f"  Frame 1: pred={pred1} shift={shift1}")
if pred0 != pred1 or shift0 != shift1:
    print("  ⚠ Frames alternate differently - likely stereo")
else:
    print("  Frames look similar - may be mono or both")

# Check the first 10 frames' bytes to look for alternating patterns
print("  First 10 frame headers: ", end="")
for i in range(10):
    if i*16+16 <= len(audio_data):
        print(f"{audio_data[i*16]:02x} ", end="")
print()

# ==========================================================
# Create Test Bundles
# ==========================================================
print("\n" + "=" * 60)
print("CREATING TEST BUNDLES")
print("=" * 60)

import UnityPy


def generate_pcm_tone(duration=3.0, sample_rate=44100, channels=2, freq=440):
    """Generate a simple sine wave PCM."""
    pcm = bytearray()
    for i in range(int(sample_rate * duration)):
        t = i / sample_rate
        s = int(math.sin(2 * math.pi * freq * t) * 32767 * 0.4)
        pcm.extend(struct.pack('<h', s))
        if channels == 2:
            pcm.extend(struct.pack('<h', s))
    return bytes(pcm)

def update_audio_metadata(env, sls, sr, dur, new_fsb5):
    """Update AudioClip and audio.gz in the bundle."""
    bf = list(env.files.values())[0]
    cab = bf.files['CAB-6c9e66546e3e23434517417298a18b91']
    resource_key = 'CAB-6c9e66546e3e23434517417298a18b91.resource'

    # Replace resource
    from UnityPy.streams import EndianBinaryReader
    new_res = EndianBinaryReader(new_fsb5)
    new_res.flags = 0
    new_res.BaseOffset = 0
    bf.files[resource_key] = new_res

    # Update AudioClip
    for pid, reader in cab.objects.items():
        if reader.class_id == 83:
            tt = reader.read_typetree()
            tt['m_Resource']['m_Size'] = len(new_fsb5)
            tt['m_Length'] = float(dur)
            reader.save_typetree(tt)
            break

    # Update audio.gz
    for pid, reader in cab.objects.items():
        if reader.class_id == 49 and 'audio.gz' in (reader.peek_name() or ''):
            meta = json.dumps({
                "version": "4.0.0", "songChecksum": "custom",
                "songSampleCount": sls, "songFrequency": sr,
                "bpmData": [{"si": 0, "ei": sls, "sb": 0.0, "eb": float(dur)}]
            }, separators=(',', ':'))
            tt = reader.read_typetree()
            tt['m_Script'] = gzip.compress(meta.encode()).decode('utf-8', 'surrogateescape')
            reader.save_typetree(tt)
            break

    return bf

# Template bundle path
template = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData/startmeup"

# ========== TEST 1: PCM FSB5 ==========
print("\nTest 1: PCM format FSB5 (no HEVAG)")
pcm_data = generate_pcm_tone(duration=3.0, freq=440)

# Build PCM FSB5 (format=0)
hdr = bytearray(_load_fsb5_header_template())
struct.pack_into('<I', hdr, 4, len(pcm_data))
struct.pack_into('<H', hdr, 12, 0)  # format=0 = PCM
struct.pack_into('<I', hdr, 16, 44100)  # freq

buf = io.BytesIO()
buf.write(b'FSB5')
buf.write(struct.pack('<I', 1))
buf.write(struct.pack('<I', 1))
buf.write(struct.pack('<I', 900))
buf.write(bytes(hdr))
buf.write(pcm_data)
pcm_fsb5 = buf.getvalue()

# Build bundle
env = UnityPy.load(template)
bf = update_audio_metadata(env, len(pcm_data)//4, 44100, 3.0, pcm_fsb5)
result = bf.save(packer="none")
t1_path = 'custom_songs/test_pcm.bundle'
with open(t1_path, 'wb') as f:
    f.write(result)
print(f"  PCM bundle: {len(result)} bytes -> {t1_path}")

# ========== TEST 2: HEVAG with frequency + PCM fallback ==========
print("\nTest 2: HEVAG FSB5 with corrected fields")
pcm_tone = generate_pcm_tone(duration=3.0, freq=440)
hevag_data = pcm_to_hevag(pcm_tone, channels=2)

hdr2 = bytearray(_load_fsb5_header_template())
struct.pack_into('<I', hdr2, 4, len(hevag_data))
# Keep format=1 (HEVAG)
struct.pack_into('<I', hdr2, 16, 44100)  # Set frequency

buf2 = io.BytesIO()
buf2.write(b'FSB5')
buf2.write(struct.pack('<I', 1))
buf2.write(struct.pack('<I', 1))
buf2.write(struct.pack('<I', 900))
buf2.write(bytes(hdr2))
buf2.write(hevag_data)
hevag_fsb5 = buf2.getvalue()

env2 = UnityPy.load(template)
bf2 = update_audio_metadata(env2, len(pcm_tone)//4, 44100, 3.0, hevag_fsb5)
result2 = bf2.save(packer="none")
t2_path = 'custom_songs/test_hevag_freq.bundle'
with open(t2_path, 'wb') as f:
    f.write(result2)
print(f"  HEVAG+freq bundle: {len(result2)} bytes -> {t2_path}")

# ========== TEST 3: Use original's format bytes directly ==========
print("\nTest 3: Original header with only data_size changed")
hdr3 = bytearray(orig_sh)  # Use the ORIGINAL sample header bytes
struct.pack_into('<I', hdr3, 4, len(hevag_data))  # Update data size only

buf3 = io.BytesIO()
buf3.write(b'FSB5')
buf3.write(struct.pack('<I', 1))
buf3.write(struct.pack('<I', 1))
buf3.write(struct.pack('<I', 900))
buf3.write(bytes(hdr3))
buf3.write(hevag_data)
exact_fsb5 = buf3.getvalue()

env3 = UnityPy.load(template)
bf3 = update_audio_metadata(env3, len(pcm_tone)//4, 44100, 3.0, exact_fsb5)
result3 = bf3.save(packer="none")
t3_path = 'custom_songs/test_exact_header.bundle'
with open(t3_path, 'wb') as f:
    f.write(result3)
print(f"  Exact header bundle: {len(result3)} bytes -> {t3_path}")

# ========== TEST 4: Extremely minimal (1 second, single frequency) ==========
print("\nTest 4: Minimal HEVAG (1 second, 440Hz, bare minimum)")
pcm_min = generate_pcm_tone(duration=1.0, freq=440)
hevag_min = pcm_to_hevag(pcm_min, channels=2)

hdr4 = bytearray(orig_sh)
struct.pack_into('<I', hdr4, 4, len(hevag_min))

buf4 = io.BytesIO()
buf4.write(b'FSB5')
buf4.write(struct.pack('<I', 1))
buf4.write(struct.pack('<I', 1))
buf4.write(struct.pack('<I', 900))
buf4.write(bytes(hdr4))
buf4.write(hevag_min)
min_fsb5 = buf4.getvalue()

env4 = UnityPy.load(template)
bf4 = update_audio_metadata(env4, len(pcm_min)//4, 44100, 1.0, min_fsb5)
result4 = bf4.save(packer="none")
t4_path = 'custom_songs/test_minimal.bundle'
with open(t4_path, 'wb') as f:
    f.write(result4)
print(f"  Minimal bundle: {len(result4)} bytes -> {t4_path}")

print("\n" + "=" * 60)
print("ALL TEST BUNDLES CREATED")
print("=" * 60)
print(f"1. PCM test:     {t1_path} - {os.path.getsize(t1_path)} bytes")
print(f"2. HEVAG+freq:   {t2_path} - {os.path.getsize(t2_path)} bytes")
print(f"3. Exact header: {t3_path} - {os.path.getsize(t3_path)} bytes")
print(f"4. Minimal:      {t4_path} - {os.path.getsize(t4_path)} bytes")
print()
print("Deploy with: lftp -u anonymous, -p 2121 192.168.100.117")
