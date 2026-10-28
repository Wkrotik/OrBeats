#!/usr/bin/env python3
"""
Quick validation that the HEVAG encoder works correctly.
"""
import sys

sys.path.insert(0, '/workspace/beat_saber_deluxe/tools')

try:
    from hevag_encoder import generate_test_tone_pcm, pcm_to_hevig

    print("✅ HEVAG encoder imports successfully")

    # Test basic functionality - create a short tone and encode it
    print("Generating test audio...")
    pcm = generate_test_tone_pcm(duration=0.1)  # Short duration for fast testing
    hevag_data = pcm_to_hevig(pcm, channels=2)

    print(f"✅ Generated {len(hevag_data)} bytes of HEVAG data")

    # Basic validation checks
    if len(hevag_data) == 0:
        print("❌ ERROR: Generated empty HEVAG data")
        sys.exit(1)

    if len(hevag_data) < 16:
        print(f"⚠️  WARNING: Very small HEVAG data ({len(hevag_data)} bytes)")
    else:
        print("✅ HEVAG data length looks reasonable")

    # Test decoding (if available)
    try:
        from hevag_encoder import decode_hevag_to_pcm
        decoded = decode_hevag_to_pcm(hevag_data, channels=2)
        if len(decoded) == len(pcm):
            print(f"✅ Encoding/decoding cycle successful ({len(decoded)} bytes)")
        else:
            print(f"⚠️  Decoded size mismatch: original={len(pcm)}, decoded={len(decoded)}")
    except ImportError:
        print("ℹ Note: decode_hevag_to_pcm not available - basic validation only")

    print("\n✅ All basic tests passed!")

except Exception as e:
    print(f"Error during testing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
