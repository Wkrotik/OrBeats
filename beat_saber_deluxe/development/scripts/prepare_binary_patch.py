#!/usr/bin/env python3
"""
Patch the ORIGINAL bundle binary in-place, replacing ONLY the .resource audio data
while keeping the CAB (objects) INTACT. This BYPASSES UnityPy's save() entirely.

The .resource data in the original bundle is at a known offset.
If we can overwrite it in-place (same size), we avoid any file table changes.

Strategy:
1. Find the .resource data block in the original bundle binary
2. Create an FSB5 silence file that pads to EXACTLY the same size as the original .resource
3. Overwrite the .resource block in the binary

This tests whether UnityPy's save() is the source of the freeze.
"""
import struct, os, sys

# ============================================================
# Step 1: Find the .resource offset in the original bundle
# ============================================================
with open('/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData/startmeup', 'rb') as f:
    bundle = f.read()

# The original bundle has a UnityFS file table at the end.
# Let me search for the file entries by looking for CAB strings
# In the original bundle, the file table stores names with null terminators

# First, find the uncompressed data blocks in the file
# UnityFS format: header, then data blocks, then block info, then file table

# Actually, let me use UnityPy to get the exact offset of the .resource
import UnityPy
env = UnityPy.load('/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData/startmeup')
bf = list(env.files.values())[0]

# Check if .resource reader has a BaseOffset that tells us its position
res = bf.files['CAB-6c9e66546e3e23434517417298a18b91.resource']
print(f"Resource reader type: {type(res)}")
print(f"Resource Length: {res.Length}")
print(f"Resource BaseOffset: {res.BaseOffset}")
print(f"Resource flags: {res.flags}")

# Also check the CAB
cab = bf.files['CAB-6c9e66546e3e23434517417298a18b91']
print(f"CAB reader type: {type(cab)}")
if hasattr(cab, 'reader'):
    print(f"CAB reader BaseOffset: {cab.reader.BaseOffset}")
    print(f"CAB reader Length: {cab.reader.Length}")

# The .resource BaseOffset might point to the position in the original bundle
# Let me see if that gives us the exact location
# Actually, for EndianBinaryReader_Memoryview, BaseOffset is the offset in the parent's buffer

print(f"\n--- Resource offset investigation ---")
print(f"If BaseOffset={res.BaseOffset} is the offset in the bundle file...")
print(f"then .resource data is at byte {res.BaseOffset} in the original bundle")

# Read from that position in the original bundle
if res.BaseOffset < len(bundle):
    data_at_offset = bundle[res.BaseOffset:res.BaseOffset+min(16, res.Length)]
    print(f"Data at offset {res.BaseOffset}: {data_at_offset.hex()}")
    if data_at_offset[:4] == b'FSB5':
        print(f"✅ FSB5 found at expected offset!")
    else:
        print(f"❌ Data doesn't start with FSB5 - offset may be wrong")

# ============================================================
# Step 2: Create a silence FSB5 that pads to EXACTLY original .resource size
# ============================================================
with open('/workspace/beat_saber_deluxe/tests/reference/original_audio.fsb5', 'rb') as f:
    original_fsb5 = f.read()

original_res_size = res.Length  # 12305632
print(f"\nOriginal .resource size: {original_res_size} bytes")

# Parse original FSB5 structure to rebuild with silence data
shsz = struct.unpack_from('<I', original_fsb5, 12)[0]
sh_bytes = original_fsb5[16:16+shsz]
orig_ds = struct.unpack_from('<I', sh_bytes, 4)[0]

# Create silence data of the EXACT original audio data size
silence_audio = bytes(orig_ds)  # 12,303,840 bytes of zero HEVAG frames

# Build FSB5: 16 + shsz + silence_audio = 16 + 1732 + 12303840 = 12305588
fsb5_size = 16 + shsz + orig_ds
assert fsb5_size == 12305588, f"FSB5 size {fsb5_size} != 12305588"

# Pad to match original .resource size exactly
padding_needed = original_res_size - fsb5_size  # 44 bytes
print(f"FSB5 size: {fsb5_size}")
print(f"Padding needed: {padding_needed} bytes")

sh = bytearray(sh_bytes)
struct.pack_into('<I', sh, 4, len(silence_audio))

buf = bytearray()
buf.extend(b'FSB5')
buf.extend(struct.pack('<I', 1))      # version
buf.extend(struct.pack('<I', 1))      # num_samples
buf.extend(struct.pack('<I', shsz))   # sample_header_size
buf.extend(sh)                        # 1732-byte sample header
buf.extend(silence_audio)             # 12,303,840 bytes of silence
buf.extend(b'\x00' * padding_needed)  # 44 bytes padding to match original size

assert len(buf) == original_res_size, f"Padded FSB5 {len(buf)} != {original_res_size}"
print(f"✅ Padded silence FSB5: {len(buf)} bytes (matches original .resource)")

out_path = "/workspace/beat_saber_deluxe/custom_songs/fullsize_silence_padded.bin"
with open(out_path, 'wb') as f:
    f.write(buf)
print(f"Saved padded silence FSB5 to {out_path}")

# ============================================================
# Step 3: Create patching script
# ============================================================
patch_script = '''#!/usr/bin/env python3
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
'''

patch_path = "/workspace/beat_saber_deluxe/tools/patch_original_bundle.py"
with open(patch_path, 'w') as f:
    f.write(patch_script)
print(f"\nPatching script saved to {patch_path}")

print(f"\nTo deploy the patched bundle:")
print(f"  timeout 120 lftp -u anonymous, -p 2121 192.168.100.117 \\")
print(f"    -e 'put /workspace/beat_saber_deluxe/custom_songs/patched_original_bundle.bundle \\")
print(f"         -o /data/GoldHEN/AFR/CUSA12878/startmeup_v3; quit'")
