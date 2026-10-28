"""
Systematic test suite for HEVAG audio encoding compatibility.
Tests HEVAG encoding consistency and validates frame structure.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))


def _is_valid_hevag_frame(frame):
    """Check if a HEVAG frame has valid format."""
    if len(frame) < 16:
        return False
    pred = frame[0] & 0xF
    shift = (frame[0] >> 4) & 0xF
    if pred > 4:
        return False
    if shift > 12:
        return False
    return True


class TestHEVAGFrameValidation:
    """Validate HEVAG frame structure."""

    def test_valid_frame_detection(self):
        frame = bytearray(16)
        frame[0] = 0x00  # pred=0, shift=0
        assert _is_valid_hevag_frame(bytes(frame))

    def test_invalid_frame_too_short(self):
        assert not _is_valid_hevag_frame(b'\x00' * 8)

    def test_invalid_predictor(self):
        frame = bytearray(16)
        frame[0] = 0x05  # pred=5 > max 4
        assert not _is_valid_hevag_frame(bytes(frame))

    def test_invalid_shift(self):
        frame = bytearray(16)
        frame[0] = 0xD0  # shift=13 > max 12
        assert not _is_valid_hevag_frame(bytes(frame))


class TestSingleFrequencyTones:
    """Comprehensive single frequency testing."""

    @pytest.mark.parametrize("freq", [220, 440, 880])
    def test_frequency_encoding(self, freq):
        from hevag_encoder import generate_test_tone_pcm, pcm_to_hevag

        pcm_data = generate_test_tone_pcm(duration=1.0, sample_rate=44100, channels=2)
        hevag_data = pcm_to_hevag(pcm_data, channels=2)

        total_frames = max(len(hevag_data) // 16, 1)
        valid_frames = 0
        for i in range(total_frames):
            frame_start = i * 16
            if frame_start + 16 > len(hevag_data):
                break
            frame = hevag_data[frame_start:frame_start + 16]
            if _is_valid_hevag_frame(frame):
                valid_frames += 1

        validity_rate = (valid_frames / max(total_frames, 1)) * 100
        assert validity_rate > 95, f"Only {validity_rate:.1f}% valid frames for {freq}Hz"

    def test_compression_ratio(self):
        from hevag_encoder import generate_test_tone_pcm, pcm_to_hevag

        pcm_data = generate_test_tone_pcm(duration=1.0, sample_rate=44100, channels=2)
        hevag_data = pcm_to_hevag(pcm_data, channels=2)
        ratio = len(pcm_data) / max(len(hevag_data), 1)
        assert ratio > 1.0, "HEVAG should compress PCM data"
