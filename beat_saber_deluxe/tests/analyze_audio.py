#!/usr/bin/env python3
"""
Direct analysis: Build FSB5, examine every byte, find the freeze cause.
"""
import os
import struct
import sys

sys.path.insert(0, '/workspace/beat_saber_deluxe/tools')
from importlib import reload

import hevag_encoder
from hevag_encoder import HEVAG_COEFFS, build_fsb5, generate_test_tone_pcm, pcm_to_hevag

reload(hevag_encoder)

print("=" * 60)
print("AUDIO PIPELINE INVESTIGATION")
print("=" * 60)

# 1. Generate a pure tone and build FSB5
pcm = generate_test_tone_pcm(duration=3.0)
print(f"\n1. Generated PCM: {len(pcm)} bytes ({len(pcm)//4} stereo samples)")

hevag = pcm_to_hevag(pcm, channels=2)
print(f"2. HEVAG data: {len(hevag)} bytes ({len(hevag)//32} stereo frames)")

# Parse FSB5 structure
fsb5 = build_fsb5(hevag, sample_rate=44100, channels=2)
print(f"3. FSB5 file: {len(fsb5)} bytes")

# Check FSB5 header
magic = fsb5[0:4]
ver = struct.unpack_from('<I', fsb5, 4)[0]
ns = struct.unpack_from('<I', fsb5, 8)[0]
shsz = struct.unpack_from('<I', fsb5, 12)[0]
print(f"   Magic: {magic} ver: {ver} nsamples: {ns} hdr_size: {shsz}")

# Sample header (900 bytes)
sh = fsb5[16:916]
ds = struct.unpack_from('<I', sh, 4)[0]
off = struct.unpack_from('<I', sh, 8)[0]
fmt = struct.unpack_from('<H', sh, 12)[0]
flg = struct.unpack_from('<H', sh, 14)[0]
print(f"   Sample header: size={ds} offset={off} format={fmt} flags=0x{flg:04x}")

# Compare with template
tpl_path = hevag_encoder.DEFAULT_FSB5_TEMPLATE
print(f"\n4. Template: {tpl_path}")
print(f"   Template exists: {os.path.exists(tpl_path)}")

# Read template
with open(tpl_path, 'rb') as f:
    tpl = f.read()
print(f"   Template bytes: {len(tpl)}")

# Compare sample header with template
match_count = sum(1 for a, b in zip(sh, tpl) if a == b)
print(f"   Header vs template: {match_count}/900 bytes match ({100*match_count/900:.1f}%)")

# Show differences in critical fields
crit_diff_count = 0
for i in range(900):
    if sh[i] != tpl[i]:
        if crit_diff_count < 10 or (4 <= i < 8):
            print(f"     diff [{i:3d}]: ours={sh[i]:3d}(0x{sh[i]:02x}) tpl={tpl[i]:3d}(0x{tpl[i]:02x})")
            if i == 4:
                orig_ds = struct.unpack_from('<I', tpl, 4)[0]
                print(f"       -> original data_size field = {orig_ds}")
        crit_diff_count += 1

if crit_diff_count > 0:
    print(f"   Total diffs: {crit_diff_count}")

# 5. Analyze HEVAG frames for PS4 compatibility
print(f"\n5. Frame Analysis ({len(hevag)//32} stereo frames):")
frame_types = {}
for i in range(len(hevag)//32):
    for ch in range(2):
        fstart = i*32 + ch*16
        frame = hevag[fstart:fstart+16]
        pred = frame[0] & 0xF
        shift = (frame[0] >> 4) & 0xF
        key = f"P{pred}S{shift}"
        frame_types[key] = frame_types.get(key, 0) + 1

print("   Frame type distribution (top 20):")
for k, v in sorted(frame_types.items(), key=lambda x: -x[1])[:20]:
    print(f"     {k}: {v} frames")

# Check for predictor=4 frames
p4_count = sum(frame_types[k] for k in frame_types if k.startswith('P4'))
if p4_count > 0:
    print(f"   ⚠️ Predictor 4 frames: {p4_count}")
else:
    print("   ✅ No predictor 4 frames")

# 6. Decode and verify one frame
print("\n6. Frame decoding verification:")
frame0 = hevag[0:16]
pred = frame0[0] & 0xF
shift = (frame0[0] >> 4) & 0xF
c1, c2 = HEVAG_COEFFS[pred]
print(f"   Frame 0: pred={pred} (c1={c1},c2={c2}) shift={shift}")

h1, h2 = 0, 0
reconstructed = []
for j in range(28):
    nib = (frame0[1 + j//2] >> (4*(j%2))) & 0xF
    predicted = ((h1 * c1 + h2 * c2) + 32) >> 6
    if nib & 0x8:
        deq = (nib | 0xF0) << shift
    else:
        deq = nib << shift
    r = max(-32768, min(32767, predicted + deq))
    reconstructed.append(r)
    h2, h1 = h1, r

samples_all = list(struct.unpack_from('<' + 'h' * (len(pcm) // 2), pcm))
left = samples_all[0::2][:28]
err = sum(abs(left[j] - reconstructed[j]) for j in range(min(28, len(left), len(reconstructed))))
print(f"   Reconstruction error (first frame): {err}")

# 7. Validate all nibbles
print("\n7. Nibble validation...")
all_valid = True
bad_count = 0
for i in range(len(hevag)):
    high_nib = (hevag[i] >> 4) & 0xF
    low_nib = hevag[i] & 0xF
    if high_nib > 7 and bad_count < 5:
        print(f"     High nibble >7 at byte {i}: {high_nib}")
        all_valid = False
        bad_count += 1
    if low_nib > 7 and bad_count < 5:
        print(f"     Low nibble >7 at byte {i}: {low_nib}")
        all_valid = False
        bad_count += 1

if all_valid:
    print("   ✅ All nibbles in valid signed 4-bit range (0-7)")
else:
    print(f"   ❌ Invalid nibbles found ({bad_count}+ violations)")

# 8. Examine the quick_test.bundle
print("\n8. Quick test bundle analysis:")
qt_path = 'custom_songs/quick_test.bundle'
with open(qt_path, 'rb') as f:
    qt = f.read()
fsb_start = qt.find(b'FSB5')
if fsb_start >= 0:
    qt_audio = qt[fsb_start+916:]
    print(f"   Bundle size: {len(qt)} bytes")
    print(f"   FSB5 at offset: {fsb_start}")
    print(f"   Audio data: {len(qt_audio)} bytes")
    print(f"   Stereo frames: {len(qt_audio)//32}")
    print(f"   Duration ~{len(qt_audio)//32*28/44100:.2f}s")

    # Check if this matches our generated FSB5
    print(f"   Our FSB5: {len(hevag)+916} bytes")
    if len(qt_audio) == len(hevag):
        print("   ✅ Audio data size matches our generated FSB5")
    else:
        print(f"   ⚠️ Size mismatch: bundle={len(qt_audio)} vs generated={len(hevag)}")

print("\n" + "=" * 60)
print("INVESTIGATION COMPLETE")
print("=" * 60)
