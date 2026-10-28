"""Bounded original-packet Vorbis -> FSB5, proven on PS4. No FMOD encoder/runtime.

Compression is optional: unknown profiles/codebooks or absent open-source codec
libraries fall back to the normal PCM builder. Validation failures after codec
selection are fatal, never a reason to bypass verification. Seek-table semantics
and preload settings match the hardware-tested developer candidate.
"""

from __future__ import annotations

import ctypes
import io
import struct
import zlib

MAX_BYTES = 200_000_000
PROFILE = "vorbis-passthrough-preload-v1"
PROFILE_48000 = "vorbis-passthrough-preload-48k-v1"


def _crc_table():
    result = []
    for value in range(256):
        value <<= 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04C11DB7 if value & 0x80000000 else 0)) & 0xFFFFFFFF
        result.append(value)
    return result


CRC_TABLE = _crc_table()


def page_crc(data):
    """Ogg uses a non-reflected CRC, not zlib's reflected CRC32."""
    crc = 0
    for value in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ CRC_TABLE[(crc >> 24) ^ value]
    return crc


def _rate_code(sample_rate):
    # Both rates passed separate PS4 playback/seek tests; default stays44100.
    if type(sample_rate) is not int or sample_rate not in (44100, 48000):
        raise ValueError("unsupported Vorbis sample rate")
    return 8 if sample_rate == 44100 else 9


def parse_ogg(data, *, sample_rate=44100):
    _rate_code(sample_rate)
    if not 58 <= len(data) <= MAX_BYTES:
        raise ValueError("Ogg size outside bounds")
    packets, partial = [], bytearray()
    offset, sequence, serial, final_samples, eos = 0, 0, None, None, False
    while offset < len(data):
        if eos or offset + 27 > len(data) or data[offset : offset + 5] != b"OggS\x00":
            raise ValueError("trailing/chained or malformed Ogg pages")
        flags, granule, stream, seq, crc, count = struct.unpack_from("<BQIIIB", data, offset + 5)
        if flags & ~7 or bool(flags & 1) != bool(partial):
            raise ValueError("invalid Ogg continuation/flags")
        if seq != sequence or (sequence == 0) != bool(flags & 2) or (serial is not None and serial != stream):
            raise ValueError("multiplexed/chained or out-of-order Ogg stream")
        serial = stream
        sequence += 1
        lacing = data[offset + 27 : offset + 27 + count]
        end = offset + 27 + count + sum(lacing)
        if len(lacing) != count or end > len(data):
            raise ValueError("truncated Ogg page")
        page = bytearray(data[offset:end])
        page[22:26] = bytes(4)
        if page_crc(page) != crc:
            raise ValueError("Ogg page checksum mismatch")
        start = offset + 27 + count
        for length in lacing:
            partial.extend(data[start : start + length])
            start += length
            if len(partial) > 65534:
                raise ValueError("Ogg packet exceeds FSB16 length bound")
            if length < 255:
                packets.append(bytes(partial))
                partial.clear()
        if flags & 4:
            eos, final_samples = True, granule
        offset = end
    if not eos or partial or len(packets) < 4:
        raise ValueError("incomplete Vorbis stream")
    ident, comment, setup = packets[:3]
    if (
        len(ident) != 30
        or ident[:7] != b"\x01vorbis"
        or struct.unpack_from("<I", ident, 7)[0] != 0
        or ident[11] != 2
        or struct.unpack_from("<I", ident, 12)[0] != sample_rate
        or ident[28:] != b"\xb8\x01"
        or not comment.startswith(b"\x03vorbis")
        or not setup.startswith(b"\x05vorbis")
    ):
        raise ValueError(f"compression requires Vorbis stereo {sample_rate} with 256/2048 blocks; keep PCM fallback")
    if final_samples is None or not sample_rate <= final_samples <= 600 * sample_rate:
        raise ValueError("Vorbis sample count outside supported duration")
    if any(not packet or packet[0] & 1 for packet in packets[3:]):
        raise ValueError("invalid Vorbis audio packet")
    return packets, final_samples


def packet_positions(packets, frames):
    from fsb5.vorbis import OggPacket, VorbisComment, VorbisInfo, vorbis

    info, comment = VorbisInfo(), VorbisComment()
    for i, payload in enumerate(packets[:3]):
        buffer = ctypes.create_string_buffer(payload)
        packet = OggPacket()
        packet.packet = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
        packet.bytes, packet.b_o_s = len(payload), int(i == 0)
        vorbis.vorbis_synthesis_headerin(info, comment, packet)
    positions, granule, previous = [], 0, 0
    for payload in packets[3:]:
        buffer = ctypes.create_string_buffer(payload)
        packet = OggPacket()
        packet.packet = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
        packet.bytes = len(payload)
        block = vorbis.vorbis_packet_blocksize(info, packet)
        if block not in (256, 2048):
            raise ValueError("invalid Vorbis block size")
        if previous:
            granule += (previous + block) // 4
        positions.append(min(granule, frames))
        previous = block
    if granule < frames:
        raise ValueError("Vorbis final granule exceeds available packet samples")
    return positions


def seek_table(packets, frames, *, sample_rate=44100):
    _rate_code(sample_rate)
    # Starting at this packet discards its own initial overlap; the NEXT packet
    # starts at this granule. Host FMOD OPENONLY and PS4 playback exercise this.
    entries, offset = [], 0
    for payload, granule in zip(packets[3:], packet_positions(packets, frames)):
        if granule < frames and (not entries or granule - entries[-1][0] >= sample_rate):
            entries.append((granule, offset))
        offset += 2 + len(payload)
    return b"".join(struct.pack("<iI", *entry) for entry in entries)


def build_fsb(data, *, sample_rate=44100):
    from fsb5.vorbis import get_header_info
    from fsb5.vorbis_headers import lookup

    packets, frames = parse_ogg(data, sample_rate=sample_rate)
    crc = zlib.crc32(packets[2])
    if crc not in lookup:
        raise ValueError("Vorbis codebook unknown to FMOD lookup; keep PCM fallback")
    # CRC alone is not proof of compatibility. Verify every setup byte and both
    # blocksizes against the independently reconstructed FMOD profile.
    short, long, setup = get_header_info(*lookup[crc])
    if (short, long) != (256, 2048) or setup != packets[2]:
        raise ValueError("Vorbis setup/codebook mismatch; keep PCM fallback")
    payload = b"".join(struct.pack("<H", len(p)) + p for p in packets[3:]) + b"\0\0"
    # Fresh seek offsets refer to our own packet stream, never the stock FSB.
    # A missing table decodes linearly but failed random access in host FMOD.
    seeks = seek_table(packets, frames, sample_rate=sample_rate)
    metadata = struct.pack("<II", crc, len(seeks)) + seeks
    descriptor = 1 | (_rate_code(sample_rate) << 1) | (1 << 5) | (frames << 34)
    sample_header = struct.pack("<QI", descriptor, (11 << 25) | (len(metadata) << 1)) + metadata
    sample_header += bytes(-(60 + len(sample_header)) % 16)
    header = struct.pack("<4s6I", b"FSB5", 1, 1, len(sample_header), 0, len(payload), 15)
    # FSB5 v1's format-version field at28 MUST be1 (0 returns FMOD_ERR_VERSION).
    header += struct.pack("<I", 1) + bytes(28)
    return header + sample_header + payload, frames, crc


def _ogg_pages(packets, positions):
    """Deterministic bounded Ogg mux for independent libsndfile verification."""
    pages = []
    sequence = 0
    for index, (packet, position) in enumerate(zip(packets, positions)):
        lacing = [255] * (len(packet) // 255) + [len(packet) % 255]
        offset = 0
        for first in range(0, len(lacing), 255):
            segment = bytes(lacing[first : first + 255])
            final = first + 255 >= len(lacing)
            flags = int(first != 0) | (2 if index == 0 and first == 0 else 0)
            if index == len(packets) - 1 and final:
                flags |= 4
            header = struct.pack(
                "<4sBBQIIIB", b"OggS", 0, flags, position if final else (1 << 64) - 1, 1, sequence, 0, len(segment)
            )
            count = sum(segment)
            page = bytearray(header + segment + packet[offset : offset + count])
            struct.pack_into("<I", page, 22, page_crc(page))
            pages.append(bytes(page))
            sequence += 1
            offset += count
    return b"".join(pages)


def reconstruct_ogg(fsb, *, sample_rate=44100):
    """Strict inverse of our one-subsound FSB; check all headers/padding/seeks."""
    rate_code = _rate_code(sample_rate)
    from fsb5.vorbis import get_header_info
    from fsb5.vorbis_headers import lookup

    if not 82 <= len(fsb) <= MAX_BYTES or fsb[:4] != b"FSB5":
        raise ValueError("invalid compressed FSB size/signature")
    version, count, header_size, names_size, payload_size, codec = struct.unpack_from("<6I", fsb, 4)
    if (version, count, names_size, codec) != (1, 1, 0, 15):
        raise ValueError("unsupported compressed FSB header")
    start = 60 + header_size
    if not 80 <= start <= len(fsb) - 2 or start % 16 or start + payload_size != len(fsb):
        raise ValueError("compressed FSB section bounds mismatch")
    if fsb[28:60] != struct.pack("<I", 1) + bytes(28):
        raise ValueError("compressed FSB format version mismatch")
    descriptor, chunk, crc, table_size = struct.unpack_from("<QIII", fsb, 60)
    frames = descriptor >> 34
    if not sample_rate <= frames <= 600 * sample_rate or descriptor != 1 | (rate_code << 1) | (1 << 5) | (frames << 34):
        raise ValueError("compressed FSB sample descriptor mismatch")
    if table_size % 8 or not 8 <= table_size <= 8 * 601 or 80 + table_size > start:
        raise ValueError("compressed FSB seek bounds mismatch")
    if chunk != (11 << 25) | ((8 + table_size) << 1) or any(fsb[80 + table_size : start]):
        raise ValueError("compressed FSB metadata/padding mismatch")
    if crc not in lookup:
        raise ValueError("unknown compressed Vorbis setup")
    short, long, setup = get_header_info(*lookup[crc])
    if (short, long) != (256, 2048) or zlib.crc32(setup) != crc:
        raise ValueError("compressed Vorbis setup mismatch")
    ident = b"\x01vorbis" + struct.pack("<IBIiiiBB", 0, 2, sample_rate, 0, 0, 0, 0xB8, 1)
    vendor = b"OrBeats verification"
    comment = b"\x03vorbis" + struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0) + b"\x01"
    packets = [ident, comment, setup]
    offset = start
    while offset + 2 <= len(fsb):
        length = struct.unpack_from("<H", fsb, offset)[0]
        offset += 2
        if not length:
            break
        if length > 65534 or offset + length > len(fsb):
            raise ValueError("compressed FSB packet length mismatch")
        packets.append(fsb[offset : offset + length])
        offset += length
    else:
        raise ValueError("missing compressed FSB packet terminator")
    if offset != len(fsb) or len(packets) < 4:
        raise ValueError("compressed FSB trailing data or empty audio")
    positions = [0, 0, 0] + packet_positions(packets, frames)
    positions[-1] = frames  # Preserve original non-block-aligned final trim.
    ogg = _ogg_pages(packets, positions)
    canonical, rebuilt_frames, _ = build_fsb(ogg, sample_rate=sample_rate)
    if rebuilt_frames != frames or canonical != fsb:
        raise ValueError("compressed FSB seek table or packet roundtrip mismatch")
    return ogg, frames


def verify_fsb(fsb, expected_frames, expected_pcm=None, *, sample_rate=44100):
    """Reopen packets with libsndfile, not proprietary FMOD, before publication."""
    import numpy as np
    import soundfile as sf

    ogg, frames = reconstruct_ogg(fsb, sample_rate=sample_rate)
    actual, rate = sf.read(io.BytesIO(ogg), dtype="float32", always_2d=True)
    if rate != sample_rate or frames != expected_frames or actual.shape != (frames, 2) or not np.isfinite(actual).all():
        raise ValueError("compressed audio rate/channels/sample count mismatch")
    if expected_pcm is not None:
        source = np.frombuffer(expected_pcm, dtype="<i2").reshape(-1, 2).astype(np.int32)
        # FFmpeg's normalized PCM clips Vorbis overshoots; retain those same
        # sample coordinates while comparing against the original packet decode.
        if sample_rate == 44100:
            decoded = np.clip(actual, -1, 32767 / 32768) * 32768
        else:
            # Compare to the importer's44.1kHz baseline in its own coordinates.
            # Only temporary verification PCM is resampled; stored packets stay
            # byte-identical at48kHz. Use the same FFmpeg decoder/resampler as
            # normalization, rather than comparing unlike sample positions.
            import subprocess

            result = subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    "pipe:0",
                    "-vn",
                    "-ac",
                    "2",
                    "-ar",
                    "44100",
                    "-c:a",
                    "pcm_s16le",
                    "-f",
                    "s16le",
                    "pipe:1",
                ],
                input=ogg,
                capture_output=True,
                check=True,
                timeout=120,
            )
            decoded = np.frombuffer(result.stdout, dtype="<i2").reshape(-1, 2).astype(np.int32)
        if source.shape != decoded.shape or np.max(np.abs(source - decoded)) > 4:
            raise ValueError("independent compressed audio roundtrip mismatch")
    return {"codec": "vorbis", "frames": frames, "packets_reencoded": False}
