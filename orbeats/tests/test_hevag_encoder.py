"""
Unit tests for hevag_encoder.py
===============================
Tests the HEVAG ADPCM encoder, FSB5 container builder, PCM generation,
and audio I/O functions.
"""
import math
import os
import struct
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from hevag_encoder import (
    FSB5_SAMPLE_HEADER_SIZE,
    HEVAG_COEFFS,
    HEVAG_FRAME_SIZE,
    HEVAG_SAMPLES_PER_FRAME,
    _encode_with,
    _parse_ogg_packets,
    _resample_to_44100,
    build_fsb5,
    fast_encode_frame,
    fast_pcm_to_hevag,
    generate_test_tone_pcm,
    generate_tone_pcm,
    hevag_encode_block,
    hevag_frame_count,
    opt_encode_frame,
    parse_fsb5,
    pcm_to_hevag,
    read_audio_normalized,
    read_raw_pcm,
    read_wav,
)


# ======================================================================
# Constants
# ======================================================================
class TestHEVAGConstants:
    """Test that module-level constants are correct."""

    def test_samples_per_frame(self):
        assert HEVAG_SAMPLES_PER_FRAME == 28

    def test_frame_size(self):
        assert HEVAG_FRAME_SIZE == 16

    def test_fsb5_sample_header_size(self):
        assert FSB5_SAMPLE_HEADER_SIZE == 1732

    def test_hevag_coeffs_has_5_entries(self):
        assert len(HEVAG_COEFFS) == 5

    def test_hevag_coeffs_predictor0_is_zero(self):
        assert HEVAG_COEFFS[0] == [0, 0]

    def test_hevag_coeffs_all_are_length_2(self):
        for c in HEVAG_COEFFS:
            assert len(c) == 2


# ======================================================================
# hevag_encode_block
# ======================================================================
class TestHevagEncodeBlock:
    """Test the brute-force HEVAG frame encoder."""

    def test_silence_returns_zero_frame(self):
        samples = [0] * 28
        frame, h1, h2 = hevag_encode_block(samples)
        assert frame == bytes(16)
        assert h1 == 0
        assert h2 == 0

    def test_silence_preserves_history(self):
        samples = [0] * 28
        frame, h1, h2 = hevag_encode_block(samples, h1=100, h2=200)
        assert h1 == 100
        assert h2 == 200

    def test_output_size_is_16_bytes(self):
        samples = [100] * 28
        frame, _, _ = hevag_encode_block(samples)
        assert len(frame) == 16

    def test_header_bytes_contain_pred_shift(self):
        samples = [100] * 28
        frame, _, _ = hevag_encode_block(samples)
        header = struct.unpack_from('<H', frame, 0)[0]
        pred = header & 0xF
        shift = (header >> 4) & 0xF
        assert 0 <= pred < 5
        assert 0 <= shift < 16

    def test_zero_signal_returns_all_zero_bytes(self):
        """Zero samples should produce a completely zero frame."""
        frame, _, _ = hevag_encode_block([0] * 28)
        assert frame == b'\x00' * 16

    def test_negative_samples_encode_correctly(self):
        """Negative samples should encode without overflow."""
        samples = [-1000] * 28
        frame, h1, h2 = hevag_encode_block(samples)
        assert len(frame) == 16
        # History should be updated (non-zero for non-zero input)
        assert isinstance(h1, int)
        assert isinstance(h2, int)

    def test_alternating_samples_encode(self):
        """Alternating positive/negative samples should encode."""
        samples = [1000 if i % 2 == 0 else -1000 for i in range(28)]
        frame, h1, h2 = hevag_encode_block(samples)
        assert len(frame) == 16

    def test_sine_wave_encode(self):
        """A short sine segment should encode without errors."""
        samples = [int(math.sin(2 * math.pi * 440 * i / 44100) * 32767 * 0.5)
                   for i in range(28)]
        frame, h1, h2 = hevag_encode_block(samples)
        assert len(frame) == 16

    def test_max_positive_samples(self):
        """Samples at max int16 should not cause overflow."""
        samples = [32767] * 28
        frame, h1, h2 = hevag_encode_block(samples)
        assert len(frame) == 16

    def test_min_negative_samples(self):
        """Samples at min int16 should not cause overflow."""
        samples = [-32768] * 28
        frame, h1, h2 = hevag_encode_block(samples)
        assert len(frame) == 16

    def test_nonzero_history_affects_encoding(self):
        """Different initial history states should produce different encodings."""
        samples = [1000] * 28
        f1, _, _ = hevag_encode_block(samples, h1=0, h2=0)
        f2, _, _ = hevag_encode_block(samples, h1=10000, h2=5000)
        # The frames should differ because prediction differs
        assert f1 != f2

    def test_chained_frames_update_history(self):
        """Two consecutive frames should update history correctly."""
        s1 = [1000] * 28
        s2 = [2000] * 28
        f1, h1_a, h2_a = hevag_encode_block(s1)
        f2, h1_b, h2_b = hevag_encode_block(s2, h1_a, h2_a)
        assert f1 != f2
        # History should evolve
        assert h1_a != 0 or h2_a != 0


# ======================================================================
# fast_encode_frame
# ======================================================================
class TestFastEncodeFrame:
    """Test the predictor-0-only fast encoder."""

    def test_silence_returns_zero_frame(self):
        frame, h1, h2 = fast_encode_frame([0] * 28)
        assert frame == bytes(16)
        assert h1 == 0
        assert h2 == 0

    def test_output_size(self):
        frame, _, _ = fast_encode_frame([100] * 28)
        assert len(frame) == 16

    def test_uses_predictor_zero(self):
        """Fast encoder always uses predictor 0."""
        frame, _, _ = fast_encode_frame([1000] * 28)
        header = struct.unpack_from('<H', frame, 0)[0]
        pred = header & 0xF
        assert pred == 0

    def test_shift_scales_with_amplitude(self):
        """Larger amplitude should produce larger shift values."""
        small = [10] * 28
        large = [10000] * 28
        f_s, _, _ = fast_encode_frame(small)
        f_l, _, _ = fast_encode_frame(large)
        shift_s = (struct.unpack_from('<H', f_s, 0)[0] >> 4) & 0xF
        shift_l = (struct.unpack_from('<H', f_l, 0)[0] >> 4) & 0xF
        assert shift_l >= shift_s

    def test_matches_brute_force_for_silence(self):
        """Both encoders should produce identical frames for silence."""
        fb, _, _ = fast_encode_frame([0] * 28)
        ff, _, _ = hevag_encode_block([0] * 28)
        assert fb == ff


# ======================================================================
# opt_encode_frame
# ======================================================================
class TestOptEncodeFrame:
    """Test the optimized 5-predictor encoder."""

    def test_silence(self):
        frame, h1, h2 = opt_encode_frame([0] * 28)
        assert frame == bytes(16)

    def test_output_size(self):
        frame, _, _ = opt_encode_frame([100] * 28)
        assert len(frame) == 16

    def test_header_valid_pred(self):
        frame, _, _ = opt_encode_frame([1000] * 28)
        header = struct.unpack_from('<H', frame, 0)[0]
        pred = header & 0xF
        assert 0 <= pred < 5

    def test_produces_different_frames_for_different_inputs(self):
        f1, _, _ = opt_encode_frame([100] * 28)
        f2, _, _ = opt_encode_frame([5000] * 28)
        assert f1 != f2

    def test_chained_frames(self):
        """Chained frames should work without errors."""
        s1 = [1000] * 28
        s2 = [2000] * 28
        f1, h1, h2 = opt_encode_frame(s1)
        f2, h1, h2 = opt_encode_frame(s2, h1, h2)
        assert f1 != f2


# ======================================================================
# _encode_with
# ======================================================================
class TestEncodeWith:
    """Test the low-level _encode_with function."""

    def test_predictor0_shift0(self):
        """Predictor 0 with shift 0 should work."""
        samples = [100] * 28
        frame, h1, h2 = _encode_with(samples, 0, 0, 0, 0)
        assert len(frame) == 16

    def test_predictor1_shift4(self):
        """Predictor 1 with shift 4 should work."""
        samples = [1000] * 28
        frame, h1, h2 = _encode_with(samples, 0, 0, 1, 4)
        assert len(frame) == 16

    def test_header_encodes_pred_and_shift(self):
        """Header should contain pred | (shift << 4)."""
        frame, _, _ = _encode_with([100] * 28, 0, 0, 2, 5)
        header = struct.unpack_from('<H', frame, 0)[0]
        assert (header & 0xF) == 2
        assert ((header >> 4) & 0xF) == 5


# ======================================================================
# fast_pcm_to_hevag
# ======================================================================
class TestFastPcmToHevag:
    """Test the optimized PCM-to-HEVAG converter."""

    def test_silence_produces_zero_frames(self):
        """Silence input should produce all-zero HEVAG frames."""
        pcm = b'\x00\x00' * 28 * 2  # 28 frames * 2 channels, each sample = 0
        result = fast_pcm_to_hevag(pcm, channels=2)
        assert all(b == 0 for b in result)

    def test_output_size_stereo(self):
        """Output size should be correct for stereo audio."""
        # 56 samples per channel (2 frames of 28)
        pcm = b'\x00\x00' * (56 * 2)
        result = fast_pcm_to_hevag(pcm, channels=2)
        assert len(result) == 2 * 2 * HEVAG_FRAME_SIZE  # 2 channels * 2 frames * 16 bytes

    def test_output_size_mono(self):
        """Output size should be correct for mono audio."""
        pcm = b'\x00\x00' * 56
        result = fast_pcm_to_hevag(pcm, channels=1)
        assert len(result) == 1 * 2 * HEVAG_FRAME_SIZE  # 1 channel * 2 frames * 16 bytes

    def test_accepts_bytearray_input(self):
        """Should accept bytearray input as well as bytes."""
        pcm = bytearray(b'\x00\x00' * 56)
        result = fast_pcm_to_hevag(pcm, channels=2)
        assert isinstance(result, bytes)

    def test_partial_frames_truncated(self):
        """Partial frames (incomplete 28 samples) should be truncated."""
        pcm = b'\x00\x00' * 30  # 30 samples = 1 frame (28) + 2 leftover
        result = fast_pcm_to_hevag(pcm, channels=1)
        # Should produce exactly 1 frame
        assert len(result) == HEVAG_FRAME_SIZE


# ======================================================================
# pcm_to_hevag
# ======================================================================
class TestPcmToHevag:
    """Test the brute-force PCM-to-HEVAG converter."""

    def test_silence_produces_zero_frames(self):
        pcm = b'\x00\x00' * (28 * 2)
        result = pcm_to_hevag(pcm, channels=2)
        assert all(b == 0 for b in result)

    def test_output_size_stereo(self):
        pcm = b'\x00\x00' * (56 * 2)
        result = pcm_to_hevag(pcm, channels=2)
        assert len(result) == 2 * 2 * HEVAG_FRAME_SIZE

    def test_output_size_mono(self):
        pcm = b'\x00\x00' * 56
        result = pcm_to_hevag(pcm, channels=1)
        assert len(result) == 1 * 2 * HEVAG_FRAME_SIZE

    def test_matches_fast_encoder_for_silence(self):
        """Both should produce identical results for silence."""
        pcm = b'\x00\x00' * (56 * 2)
        f1 = pcm_to_hevag(pcm, channels=2)
        f2 = fast_pcm_to_hevag(pcm, channels=2)
        assert f1 == f2

    def test_accepts_list_of_ints(self):
        """Should accept a list of int16 values instead of bytes."""
        samples = [0] * (56 * 2)
        result = pcm_to_hevag(samples, channels=2)
        assert len(result) == 2 * 2 * HEVAG_FRAME_SIZE


# ======================================================================
# hevag_frame_count
# ======================================================================
class TestHevagFrameCount:
    """Test the frame count calculator."""

    def test_one_frame_stereo(self):
        pcm = b'\x00\x00' * (28 * 2)
        assert hevag_frame_count(pcm, channels=2) == 1

    def test_two_frames_stereo(self):
        pcm = b'\x00\x00' * (56 * 2)
        assert hevag_frame_count(pcm, channels=2) == 2

    def test_one_frame_mono(self):
        pcm = b'\x00\x00' * 28
        assert hevag_frame_count(pcm, channels=1) == 1

    def test_partial_frame_truncated(self):
        pcm = b'\x00\x00' * 30  # 30 samples = 1 frame + 2 leftover
        assert hevag_frame_count(pcm, channels=1) == 1

    def test_zero_samples(self):
        pcm = b''
        assert hevag_frame_count(pcm, channels=2) == 0


# ======================================================================
# PCM Generation
# ======================================================================
class TestPCMGeneration:
    """Test PCM generation functions."""

    def test_generate_tone_pcm_length_stereo(self):
        """Stereo tone should have 2 samples per frame."""
        pcm = generate_tone_pcm(frequency=440, duration=0.1,
                                sample_rate=44100, channels=2, volume=0.4)
        expected_frames = int(44100 * 0.1)
        # Each frame = 2 channels * 2 bytes = 4 bytes
        assert len(pcm) == expected_frames * 2 * 2

    def test_generate_tone_pcm_length_mono(self):
        pcm = generate_tone_pcm(frequency=440, duration=0.1,
                                sample_rate=44100, channels=1, volume=0.4)
        expected_frames = int(44100 * 0.1)
        assert len(pcm) == expected_frames * 2  # 1 channel * 2 bytes

    def test_generate_tone_pcm_no_clipping(self):
        """Volume 0.4 should not produce samples near int16 max."""
        pcm = generate_tone_pcm(frequency=440, duration=0.1,
                                sample_rate=44100, channels=1, volume=0.4)
        samples = struct.unpack(f'<{len(pcm)//2}h', pcm)
        assert max(samples) < 32767
        assert min(samples) > -32768

    def test_generate_tone_pcm_dc_offset(self):
        """Zero-volume tone should produce silence."""
        pcm = generate_tone_pcm(frequency=440, duration=0.01,
                                sample_rate=44100, channels=1, volume=0.0)
        assert pcm == b'\x00\x00' * int(44100 * 0.01)

    def test_generate_test_tone_pcm_length(self):
        """Test tone should match expected duration."""
        pcm = generate_test_tone_pcm(duration=0.1, sample_rate=44100, channels=2)
        expected = int(44100 * 0.1) * 2 * 2
        assert len(pcm) == expected

    def test_generate_test_tone_has_silence_gap(self):
        """Test tone from 1.0-1.5s should be silent (samples near 0)."""
        pcm = generate_test_tone_pcm(duration=2.0, sample_rate=44100, channels=1)
        # Samples at 1.2s should be near zero
        offset = int(1.2 * 44100) * 2
        sample = struct.unpack_from('<h', pcm, offset)[0]
        assert abs(sample) < 100


# ======================================================================
# FSB5 Container Building
# ======================================================================
class TestFSB5Building:
    """Test FSB5 container building functions."""

    def test_build_fsb5_starts_with_magic(self, fsb5_template):
        """FSB5 output should start with 'FSB5' magic."""
        hevag_data = b'\x00' * 16  # 1 frame
        result = build_fsb5(hevag_data, template_path=fsb5_template)
        assert result[:4] == b'FSB5'

    def test_build_fsb5_version(self, fsb5_template):
        hevag_data = b'\x00' * 16
        result = build_fsb5(hevag_data, template_path=fsb5_template)
        version = struct.unpack_from('<I', result, 4)[0]
        assert version == 1

    def test_build_fsb5_num_samples(self, fsb5_template):
        hevag_data = b'\x00' * 16
        result = build_fsb5(hevag_data, template_path=fsb5_template)
        num = struct.unpack_from('<I', result, 8)[0]
        assert num == 1

    def test_build_fsb5_header_size(self, fsb5_template):
        hevag_data = b'\x00' * 16
        result = build_fsb5(hevag_data, template_path=fsb5_template)
        shsz = struct.unpack_from('<I', result, 12)[0]
        assert shsz == FSB5_SAMPLE_HEADER_SIZE

    def test_build_fsb5_total_size(self, fsb5_template):
        hevag_data = b'\x00' * 32  # 2 frames
        result = build_fsb5(hevag_data, template_path=fsb5_template)
        expected = 16 + FSB5_SAMPLE_HEADER_SIZE + 32
        assert len(result) == expected

    def test_build_fsb5_data_size_field(self, fsb5_template):
        """The data_size field at sample header offset 4 should match input."""
        hevag_data = b'\x00' * 64
        result = build_fsb5(hevag_data, template_path=fsb5_template)
        data_size = struct.unpack_from('<I', result, 20)[0]
        assert data_size == 64

    def test_build_fsb5_full_fsb5_template(self, full_fsb5_template):
        """Should detect FSB5 magic and extract sample header."""
        hevag_data = b'\x00' * 16
        result = build_fsb5(hevag_data, template_path=full_fsb5_template)
        assert result[:4] == b'FSB5'

    def test_build_fsb5_with_pcm_frames(self, fsb5_template):
        """pcm_frames > 0 should update the sample descriptor."""
        hevag_data = b'\x00' * 16
        result = build_fsb5(hevag_data, template_path=fsb5_template, pcm_frames=44100)
        # Sample descriptor is at sample_header offset 44 (file offset 60)
        sd = struct.unpack_from('<Q', result, 60)[0]
        total_frames = (sd >> 34) & ((1 << 30) - 1)
        assert total_frames == 44100

    def test_build_fsb5_hashes_zeroed(self, fsb5_template):
        """Hash/dummy fields at offsets 28-59 should be zeroed."""
        hevag_data = b'\x00' * 16
        result = build_fsb5(hevag_data, template_path=fsb5_template)
        # Offsets 28-59 in the FSB5 file = offsets 12-43 in sample header
        for off in range(28, 60):
            assert result[off] == 0

    def test_build_fsb5_large_data(self, fsb5_template):
        """Build FSB5 with a larger zero data block to verify size."""
        hevag_data = bytes(160)  # 10 frames
        result = build_fsb5(hevag_data, template_path=fsb5_template)
        assert result[:4] == b'FSB5'
        expected = 16 + FSB5_SAMPLE_HEADER_SIZE + 160
        assert len(result) == expected


# ======================================================================
# parse_fsb5
# ======================================================================
class TestParseFSB5:
    """Test the FSB5 parser."""

    def test_parse_valid_fsb5(self, fsb5_template):
        hevag_data = b'\x00' * 16
        fsb5 = build_fsb5(hevag_data, template_path=fsb5_template)
        info = parse_fsb5(fsb5)
        assert info['magic'] == 'FSB5'
        assert info['version'] == 1
        assert info['num_samples'] == 1
        assert info['total_size'] == len(fsb5)

    def test_parse_from_file(self, fsb5_template, tmp_dir):
        hevag_data = b'\x00' * 16
        fsb5 = build_fsb5(hevag_data, template_path=fsb5_template)
        path = os.path.join(tmp_dir, "test.fsb5")
        with open(path, 'wb') as f:
            f.write(fsb5)
        info = parse_fsb5(path)
        assert info['magic'] == 'FSB5'

    def test_parse_invalid_magic(self):
        with pytest.raises(ValueError, match="Not a valid FSB5"):
            parse_fsb5(b'NOT_FSB5' + b'\x00' * 100)

    def test_parse_data_size(self, fsb5_template):
        hevag_data = b'\xAA' * 32
        fsb5 = build_fsb5(hevag_data, template_path=fsb5_template)
        info = parse_fsb5(fsb5)
        assert info['data_size'] == 32


# ======================================================================
# WAV Reading
# ======================================================================
class TestReadWAV:
    """Test WAV file reading."""

    def test_read_valid_wav(self, silence_wav):
        pcm, sr, ch = read_wav(silence_wav)
        assert sr == 44100
        assert ch == 2
        assert len(pcm) > 0

    def test_read_wav_pcm16(self, silence_wav):
        pcm, sr, ch = read_wav(silence_wav)
        # 8820 frames * 2 channels * 2 bytes = 35280 bytes
        assert len(pcm) == 8820 * 2 * 2

    def test_read_wav_invalid_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.wav")
        with open(path, 'wb') as f:
            f.write(b'NOT_A_WAV')
        with pytest.raises(ValueError, match="Not a valid WAV"):
            read_wav(path)

    def test_read_wav_no_fmt_chunk(self, tmp_dir):
        """WAV without fmt chunk should raise ValueError."""
        path = os.path.join(tmp_dir, "no_fmt.wav")
        # Minimal RIFF with only data chunk
        # Construct manually: RIFF header + data chunk only (no fmt)
        header = b'RIFF'
        header += struct.pack('<I', 20)  # file size
        header += b'WAVE'
        header += b'data'
        header += struct.pack('<I', 4)
        header += b'\x00\x00\x00\x00'
        with open(path, 'wb') as f:
            f.write(header)
        with pytest.raises(ValueError, match="No fmt chunk"):
            read_wav(path)

    def test_read_wav_with_audio(self, tone_wav):
        pcm, sr, ch = read_wav(tone_wav)
        assert sr == 44100
        assert ch == 2
        # Should have non-zero samples (tone)
        samples = struct.unpack(f'<{len(pcm)//2}h', pcm)
        assert any(s != 0 for s in samples)


# ======================================================================
# Raw PCM Reading
# ======================================================================
class TestReadRawPCM:
    """Test raw PCM file reading."""

    def test_read_raw_16bit(self, tmp_dir):
        path = os.path.join(tmp_dir, "raw.pcm")
        data = b'\x01\x00' * 100
        with open(path, 'wb') as f:
            f.write(data)
        result, sr, ch = read_raw_pcm(path, sample_rate=22050, channels=1)
        assert result == data
        assert sr == 22050
        assert ch == 1

    def test_read_raw_rejects_non_16bit(self, tmp_dir):
        path = os.path.join(tmp_dir, "raw.pcm")
        with open(path, 'wb') as f:
            f.write(b'\x00' * 10)
        with pytest.raises(ValueError, match="Only 16-bit"):
            read_raw_pcm(path, bits=8)


# ======================================================================
# Audio Normalization
# ======================================================================
class TestReadAudioNormalized:
    """Test audio reading with normalization."""

    def test_returns_int16_array(self, tone_wav):
        data, sr = read_audio_normalized(tone_wav)
        assert data.dtype.name == 'int16'
        assert sr == 44100

    def test_clips_within_range(self, silence_wav):
        data, sr = read_audio_normalized(silence_wav)
        assert np.all(np.abs(data) <= 32767)


# ======================================================================
# Resampling
# ======================================================================
class TestResampleTo44100:
    """Test the resampling function."""

    def test_no_resample_at_44100(self):
        import numpy as np
        data = np.zeros((44100, 2), dtype=np.int16)
        result = _resample_to_44100(data, 44100)
        assert len(result) == 44100

    def test_upsample_22050_to_44100(self):
        import numpy as np
        data = np.zeros((22050, 2), dtype=np.int16)
        result = _resample_to_44100(data, 22050)
        # Should be approximately 2x length
        assert abs(len(result) - 44100) < 2

    def test_output_is_int16(self):
        import numpy as np
        data = np.zeros((22050, 2), dtype=np.int16)
        result = _resample_to_44100(data, 22050)
        assert result.dtype == np.int16


# ======================================================================
# OGG Packet Parsing
# ======================================================================
class TestParseOGGPackets:
    """Test OGG Vorbis packet parsing."""

    def test_empty_input_returns_empty(self):
        result = _parse_ogg_packets(b'')
        assert result == []

    def test_invalid_ogg_returns_empty(self):
        result = _parse_ogg_packets(b'NOT_OGG')
        assert result == []


# ======================================================================
# Integration: encode-decode roundtrip sanity
# ======================================================================
class TestEncodeRoundtrip:
    """Integration tests for encode + build FSB5 pipeline."""

    def test_build_fsb5_from_silence(self, fsb5_template):
        """Full pipeline: silence -> HEVAG -> FSB5 should produce valid container."""
        pcm = b'\x00\x00' * (28 * 2)
        hevag = pcm_to_hevag(pcm, channels=2)
        fsb5 = build_fsb5(hevag, template_path=fsb5_template)
        info = parse_fsb5(fsb5)
        assert info['magic'] == 'FSB5'
        assert info['data_size'] == len(hevag)

    def test_build_fsb5_from_tone(self, fsb5_template):
        """Full pipeline: tone -> HEVAG -> FSB5."""
        samples = [int(math.sin(2 * math.pi * 440 * i / 44100) * 32767 * 0.4)
                   for i in range(28 * 2)]  # 2 frames stereo
        pcm = struct.pack(f'<{len(samples)}h', *samples)
        hevag = pcm_to_hevag(pcm, channels=1)  # treat as mono
        fsb5 = build_fsb5(hevag, template_path=fsb5_template)
        assert fsb5[:4] == b'FSB5'

    def test_frame_count_matches_build(self, fsb5_template):
        """Frame count from hevag_frame_count should match actual build."""
        pcm = b'\x00\x00' * (56 * 2)  # 2 frames stereo
        count = hevag_frame_count(pcm, channels=2)
        hevag = pcm_to_hevag(pcm, channels=2)
        assert len(hevag) == count * 2 * HEVAG_FRAME_SIZE  # 2 channels

    def test_build_fsb5_size_relationship(self, fsb5_template):
        """FSB5 size = 16 + template_size + hevag_data_size."""
        pcm = b'\x00\x00' * (28 * 2)
        hevag = pcm_to_hevag(pcm, channels=2)
        fsb5 = build_fsb5(hevag, template_path=fsb5_template)
        assert len(fsb5) == 16 + FSB5_SAMPLE_HEADER_SIZE + len(hevag)
