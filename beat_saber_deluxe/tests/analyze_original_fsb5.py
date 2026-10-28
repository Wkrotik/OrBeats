#!/usr/bin/env python3
"""
Analyze the ORIGINAL FSB5's sample header structure to find the correct
sample_header_size and any additional fields we're missing.
"""
import struct

with open('/workspace/beat_saber_deluxe/tests/reference/original_audio.fsb5', 'rb') as f:
    orig = f.read()

print(f"Original FSB5: {len(orig)} bytes")
print()

# Header
magic = orig[0:4]
ver = struct.unpack_from('<I', orig, 4)[0]
nsamp = struct.unpack_from('<I', orig, 8)[0]
shsz = struct.unpack_from('<I', orig, 12)[0]
print("FSB5 Header:")
print(f"  magic: {magic}")
print(f"  version: {ver}")
print(f"  num_samples: {nsamp}")
print(f"  sample_header_size: {shsz}")
print(f"  First 16 bytes hex: {orig[:16].hex()}")
print()

# Sample header area
sh = orig[16:16+shsz]
print(f"Sample header area: {len(sh)} bytes (from byte 16 to byte {16+shsz})")
print(f"  First 32 bytes: {sh[:32].hex()}")
print()

# Parse sample entry (first 32 bytes of the header area)
name_offset = struct.unpack_from('<I', sh, 0)[0]
data_size = struct.unpack_from('<I', sh, 4)[0]
offset = struct.unpack_from('<I', sh, 8)[0]
fmt = struct.unpack_from('<H', sh, 12)[0]
flags = struct.unpack_from('<H', sh, 14)[0]
freq_bytes = sh[16:20]
freq = struct.unpack_from('<I', sh, 16)[0]
more16 = struct.unpack_from('<H', sh, 20)[0]
more32 = struct.unpack_from('<I', sh, 24)[0]

print("Sample Entry (first 32 bytes):")
print(f"  [0:4]   name_offset: {name_offset}")
print(f"  [4:8]   data_size: {data_size}")
print(f"  [8:12]  offset: {offset}")
print(f"  [12:14] format: {fmt} (0x{fmt:04x})")
print(f"  [14:16] flags: {flags} (0x{flags:04x})")
print(f"  [16:20] frequency bytes: {freq_bytes.hex()} = {freq}")
print(f"  [20:22] word: {more16} (0x{more16:04x})")
print(f"  [24:28] dword: {more32} (0x{more32:08x})")
print(f"  [28:32] bytes: {sh[28:32].hex()}")
print()

# Check if there's a sample name GUID or hash following the entry
# FSB5 v1 includes a hash table at the end of the sample header area
# The hash is typically 8 bytes per sample, padded to the end

# Let's look at the structure between byte 32 and byte shsz for clues
print(f"Rest of sample header (bytes 32 to {shsz}):")
print(f"  Bytes 32-48: {sh[32:48].hex()}")
print(f"  Bytes 48-64: {sh[48:64].hex()}")
print(f"  Bytes 64-80: {sh[64:80].hex()}")

# Find non-zero regions in the rest of the sample header
nonzero_regions = []
in_region = False
region_start = 0
for i in range(32, len(sh)):
    if sh[i] != 0 and not in_region:
        in_region = True
        region_start = i
    elif sh[i] == 0 and in_region:
        non_zero_count = i - region_start
        if non_zero_count > 4:
            nonzero_regions.append((region_start, i, non_zero_count))
        in_region = False
if in_region:
    nonzero_regions.append((region_start, len(sh), len(sh) - region_start))

print("\nNon-zero regions (excluding first 32 bytes):")
for start, end, count in nonzero_regions[:10]:
    print(f"  [{start}:{end}] ({count} bytes non-zero): {sh[start:start+min(32, end-start)].hex()}")
    if end - start > 100:
        print(f"    ... plus {end - start - min(32, end-start)} more bytes")

print()

# Check: where does the hash table end?
# In FMOD FSB5, the hash table (if present) is at the end of the sample header area
# Hash is typically 8 bytes: [4-byte hash][4-byte offset to sample]
# Also check for mode-specific signatures

# Look for audio data patterns between entries and before audio data
# Check what's at the end of the sample header area
print("Last 32 bytes of sample header area:")
print(f"  Bytes {shsz-32}-{shsz}: {sh[-32:].hex()}")

# What follows the sample header area?
audio_start = 16 + shsz
print(f"\nAudio data starts at byte {audio_start}")

# Check offset=15 behavior
print(f"\nOffset field = {offset}:")
for base_name, base in [("file start", 0), ("SH start", 16), ("SH end", 16+shsz)]:
    actual_byte = base + offset
    if actual_byte < len(orig):
        print(f"  From {base_name}: byte {actual_byte} = {orig[actual_byte:actual_byte+16].hex()}")
    else:
        print(f"  From {base_name}: byte {actual_byte} (beyond file)")

# The actual audio data should start at byte audio_start
print(f"\nActual audio data at byte {audio_start}: {orig[audio_start:audio_start+32].hex()}")

# Count total frames
audio_len = data_size
audio_bytes = orig[audio_start:audio_start+audio_len] if data_size > 0 else b''
n_frames = len(audio_bytes) // 16
print(f"\nTotal HEVAG frames: {n_frames} ({len(audio_bytes)} bytes / 16 per frame)")

# ============================================================
# KEY FINDING: extract the COMPLETE sample header for use as template
# ============================================================
print("\n" + "=" * 60)
print("GENERATING CORRECT SAMPLE HEADER TEMPLATE")
print("=" * 60)

# Extract the complete sample header (1732 bytes)
complete_sh = bytearray(sh)
print(f"Complete sample header: {len(complete_sh)} bytes")

# Update data_size to a smaller value (for our test audio)
# Let's say 50400 bytes (3 seconds of HEVAG stereo = 4725 frames * 32 bytes per stereo frame)
test_size = 1575 * 32
struct.pack_into('<I', complete_sh, 4, test_size)
print(f"Updated data_size to {test_size}")

# Save as new template
tpl_path = '/workspace/beat_saber_deluxe/custom_songs/fsb5_full_header_template.bin'
with open(tpl_path, 'wb') as f:
    f.write(complete_sh)
print(f"Saved {len(complete_sh)}-byte template to {tpl_path}")

# Also show the difference between our old 900-byte template and the full one
old_tpl_path = '/workspace/beat_saber_deluxe/custom_songs/fsb5_header_template.bin'
with open(old_tpl_path, 'rb') as f:
    old_tpl = f.read()

print(f"\nOld template: {len(old_tpl)} bytes")
print(f"New template: {len(complete_sh)} bytes")
print(f"We were missing {shsz - len(old_tpl)} bytes!")

# == Extract the hash area ==
if shsz > len(old_tpl):
    missing = sh[len(old_tpl):shsz]
    print(f"\nBytes 900-{shsz} of sample header contain:")
    non_zero = sum(1 for b in missing if b != 0)
    print(f"  {non_zero}/{len(missing)} bytes non-zero")
    print(f"  First missing 64 bytes: {missing[:64].hex()}")
    print(f"  Last missing 64 bytes: {missing[-64:].hex() if len(missing) >= 64 else missing.hex()}")

print("\n✅ Analysis complete")
