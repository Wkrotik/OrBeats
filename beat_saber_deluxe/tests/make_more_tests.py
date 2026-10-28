#!/usr/bin/env python3
"""
Additional test bundles for audio freeze investigation.
Only run these after determining which of the first two tests (silence, original_audio_3s) works.
"""
import gzip
import io
import json
import struct
import sys

import UnityPy

sys.path.insert(0, '/workspace/beat_saber_deluxe/tools')
from hevag_encoder import HEVAG_FRAME_SIZE, HEVAG_SAMPLES_PER_FRAME, generate_test_tone_pcm
from UnityPy.streams import EndianBinaryReader

OUTPUT_DIR = "/workspace/beat_saber_deluxe/custom_songs"
TEMPLATE = "/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/BeatmapLevelsData/startmeup"

with open('/workspace/beat_saber_deluxe/tests/reference/original_audio.fsb5', 'rb') as f:
    original_fsb5 = f.read()
shsz = struct.unpack_from('<I', original_fsb5, 12)[0]
original_sh = original_fsb5[16:16+shsz]

# Build V3 beatmap data
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

def build_fsb5_and_bundle(audio_data, duration=3.0, label="test"):
    """Build FSB5 and then bundle it."""
    sh = bytearray(original_sh)
    struct.pack_into('<I', sh, 4, len(audio_data))
    buf = io.BytesIO()
    buf.write(b'FSB5')
    buf.write(struct.pack('<I', 1))
    buf.write(struct.pack('<I', 1))
    buf.write(struct.pack('<I', shsz))
    buf.write(bytes(sh))
    buf.write(audio_data)
    fsb5 = buf.getvalue()

    env = UnityPy.load(TEMPLATE)
    bf = list(env.files.values())[0]
    cab = bf.files['CAB-6c9e66546e3e23434517417298a18b91']
    new_res = EndianBinaryReader(fsb5)
    new_res.flags = 0
    new_res.BaseOffset = 0
    bf.files['CAB-6c9e66546e3e23434517417298a18b91.resource'] = new_res

    for pid, reader in cab.objects.items():
        if reader.class_id == 83:
            tt = reader.read_typetree()
            tt['m_Resource']['m_Size'] = len(fsb5)
            tt['m_Length'] = duration
            reader.save_typetree(tt)
            break

    for pid, reader in cab.objects.items():
        if reader.class_id == 49 and 'audio.gz' in (reader.peek_name() or ''):
            meta = json.dumps({
                "version": "4.0.0", "songChecksum": "custom",
                "songSampleCount": int(duration * 44100), "songFrequency": 44100,
                "bpmData": [{"si": 0, "ei": int(duration * 44100), "sb": 0.0, "eb": duration}]
            }, separators=(',', ':'))
            tt = reader.read_typetree()
            tt['m_Script'] = gzip.compress(meta.encode()).decode('utf-8', 'surrogateescape')
            reader.save_typetree(tt)
            break

    for pid, reader in cab.objects.items():
        if reader.class_id == 49:
            n = reader.peek_name() or ''
            if '.beatmap' in n:
                tt = reader.read_typetree()
                tt['m_Script'] = beatmap_gz.decode('utf-8', 'surrogateescape')
                reader.save_typetree(tt)

    result = bf.save(packer="none")
    path = f'{OUTPUT_DIR}/{label}.bundle'
    with open(path, 'wb') as f:
        f.write(result)
    print(f"  Created: {label}.bundle ({len(result)} bytes)")
    return path

# ======================================================================
# Generate HEVAG frames using ONLY predictor 0
# ======================================================================
def encode_frame_predictor0_only(samples, h1=0, h2=0):
    """Encode using ONLY predictor 0 (no prediction, simple 4-bit PCM)."""
    c1, c2 = 0, 0  # noqa: F841 — predictor 0 coefficients (documented, unused by design)
    best_shift = 0
    best_err = float('inf')

    # Find best shift for predictor 0
    for shift in range(13):
        err = 0
        for s in samples:
            predicted = 0  # predictor 0: always predict 0
            diff = max(-32768, min(32767, s - predicted))
            if diff < 0:
                nib = max(-8, diff >> shift) & 0xF
            else:
                nib = min(7, diff >> shift) & 0xF
            if nib & 0x8:
                deq = (nib | 0xF0) << shift
            else:
                deq = nib << shift
            err += (diff - deq) ** 2
        if err < best_err:
            best_err, best_shift = err, shift
        if best_err == 0:
            break

    # Encode with best shift, predictor 0 always
    shift = best_shift
    frame = bytearray(HEVAG_FRAME_SIZE)
    struct.pack_into('<H', frame, 0, 0 | (shift << 4))  # predictor=0

    for i in range(len(samples)):
        predicted = 0
        diff = max(-32768, min(32767, samples[i] - predicted))
        if diff < 0:
            nib = max(-8, diff >> shift) & 0xF
        else:
            nib = min(7, diff >> shift) & 0xF
        bi = 1 + (i // 2)
        if i % 2 == 0:
            frame[bi] = (frame[bi] & 0xF0) | nib
        else:
            frame[bi] = (frame[bi] & 0x0F) | (nib << 4)
        if nib & 0x8:
            dequant = (nib | 0xF0) << shift
        else:
            dequant = nib << shift
        reconstructed = max(-32768, min(32767, predicted + dequant))
        h2, h1 = h1, reconstructed

    return bytes(frame), h1, h2

def pcm_to_hevag_predictor0(pcm_data, channels=2):
    """Convert PCM to HEVAG using ONLY predictor 0."""
    samples = list(struct.unpack_from('<' + 'h' * (len(pcm_data) // 2), pcm_data))
    per_ch = len(samples) // channels
    result = bytearray((per_ch // HEVAG_SAMPLES_PER_FRAME) * HEVAG_FRAME_SIZE * channels)
    offset = 0
    left = samples[0::2] if channels == 2 else samples
    right = samples[1::2] if channels == 2 else []
    frames = per_ch // HEVAG_SAMPLES_PER_FRAME
    h1_l = h2_l = h1_r = h2_r = 0

    for i in range(frames):
        start = i * HEVAG_SAMPLES_PER_FRAME
        end = start + HEVAG_SAMPLES_PER_FRAME
        fl, h1_l, h2_l = encode_frame_predictor0_only(left[start:end], h1_l, h2_l)
        result[offset:offset + HEVAG_FRAME_SIZE] = fl
        offset += HEVAG_FRAME_SIZE
        if right:
            fr, h1_r, h2_r = encode_frame_predictor0_only(right[start:end], h1_r, h2_r)
            result[offset:offset + HEVAG_FRAME_SIZE] = fr
            offset += HEVAG_FRAME_SIZE

    return bytes(result)

# ======================================================================
# TEST 3: Predictor 0 only - 3 second sine wave
# ======================================================================
print("\n--- TEST 3: Predictor 0 only (3 seconds, 440Hz) ---")
pcm_tone = generate_test_tone_pcm(duration=3.0)
hevag_p0 = pcm_to_hevag_predictor0(pcm_tone, channels=2)
build_fsb5_and_bundle(hevag_p0, 3.0, "test_p0_only")

# ======================================================================
# TEST 4: Predictor 0 only with SILENCE (all zero nibbles)
# ======================================================================
print("\n--- TEST 4: Predictor 0 silence (3 seconds) ---")
# With predictor 0 and shift=0, silence = all zero nibbles
silence_data = bytes(int(3 * 44100 / 28) * 32)  # stereo frames of zeros
build_fsb5_and_bundle(silence_data, 3.0, "test_p0_silence")

print("\n" + "=" * 60)
print("TESTING STRATEGY")
print("=" * 60)
print("""
Step 1: Test 'test_silence.bundle' (already deployed)
  - All-zero HEVAG frames (predictor=0, shift=0, all nibbles=0)
  - If WORKS (no freeze): PS4 accepts our FSB5 structure. Problem is in our encoding algorithm.

Step 2: If silence works, test 'test_p0_only.bundle'
  - Predictor 0 only, normal nibble encoding of 440Hz sine wave
  - If WORKS: Problem is specifically in predictors 1-4
  - If FREEZES: Problem is in the nibble range/encoding itself

Step 3: Test 'test_original_audio_3s.bundle'
  - Original Start Me Up HEVAG frames (first 3 seconds)
  - If WORKS: Our FSB5 building process is correct
  - If FREEZES: Something wrong with the FSB5 wrapper structure

Additional tests if needed:
  - PCM format (0) instead of HEVAG
  - Single frequency sine wave only (no multi-tone transitions)
  - Different sample rates
""")
