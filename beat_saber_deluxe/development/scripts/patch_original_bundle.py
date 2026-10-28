#!/usr/bin/env python3
"""
Patch the original bundle binary in-place.
Overwrites the .resource data with our silence FSB5.
WARNING: This modifies the original bundle file.
"""
import struct, os

ORIGINAL_BUNDLE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData/startmeup"
PADDED_FSB5 = "/workspace/beat_saber_deluxe/custom_songs/fullsize_silence_padded.bin"
OUTPUT = "/workspace/beat_saber_deluxe/custom_songs/patched_original_bundle.bundle"

# Load the padded FSB5
with open(PADDED_FSB5, 'rb') as f:
    new_res = f.read()

# Load the original bundle
with open(ORIGINAL_BUNDLE, 'rb') as f:
    bundle = bytearray(f.read())

# The .resource BaseOffset is at the reader's position
# We need to find the exact offset in the binary
# Check if EndianBinaryReader_Memoryview.BaseOffset is the offset

import UnityPy
env = UnityPy.load(ORIGINAL_BUNDLE)
bf = list(env.files.values())[0]
res = bf.files['CAB-6c9e66546e3e23434517417298a18b91.resource']
offset = res.BaseOffset
orig_size = res.Length

print(f"Original .resource at offset {offset}, size {orig_size}")
print(f"New .resource size: {len(new_res)}")

if len(new_res) != orig_size:
    print(f"⚠️ Size mismatch: new={len(new_res)}, orig={orig_size}")
    print(f"Only in-place overwrite is safe with same size")
    exit(1)

# Verify the data at that offset is indeed FSB5
if bundle[offset:offset+4] == b'FSB5':
    print(f"✅ FSB5 magic confirmed at offset {offset}")
else:
    print(f"❌ Expected FSB5 at offset {offset}, got {bundle[offset:offset+4]}")
    exit(1)

# Overwrite the .resource data in-place
bundle[offset:offset+len(new_res)] = new_res

# Save patched bundle
os.makedirs(os.path.dirname(OUTPUT) or '.', exist_ok=True)
with open(OUTPUT, 'wb') as f:
    f.write(bundle)

print(f"✅ Patched bundle saved to {OUTPUT}")
print(f"  Size: {len(bundle)} bytes (original: {len(bundle)} bytes)")

# Verify the patched bundle loads in UnityPy
try:
    v_env = UnityPy.load(OUTPUT)
    v_bf = list(v_env.files.values())[0]
    v_res = v_bf.files['CAB-6c9e66546e3e23434517417298a18b91.resource']
    v_res.seek(0)
    v_data = v_res.read(min(16, v_res.Length))
    print(f"✅ Patched bundle loads correctly. Resource starts: {v_data[:4]}")
except Exception as e:
    print(f"❌ Patched bundle failed to load: {e}")
