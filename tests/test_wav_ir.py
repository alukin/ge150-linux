import math
import struct

import pytest

from ge150.formats import wav_ir
from ge150.model.preset import encode_name
from ge150.protocol import messages as msg
from ge150.protocol.framing import Frame
from ge150.protocol.opcodes import Op


def make_wav(samples: list[float], rate: int = 44100, bits: int = 24, channels: int = 1,
             is_float: bool = False) -> bytes:
    width = bits // 8
    frames = bytearray()
    for x in samples:
        for _ in range(channels):
            if is_float:
                frames += struct.pack("<f" if bits == 32 else "<d", x)
            elif bits == 8:
                frames.append(max(0, min(255, round(x * 127) + 128)))
            else:
                full = 1 << (bits - 1)
                frames += max(-full, min(full - 1, round(x * full))).to_bytes(width, "little",
                                                                             signed=True)
    tag = 3 if is_float else 1
    fmt = struct.pack("<HHIIHH", tag, channels, rate, rate * width * channels,
                      width * channels, bits)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"LIST" + struct.pack("<I", 3) + b"abc\x00"  # odd chunk with pad byte
    body += b"data" + struct.pack("<I", len(frames)) + bytes(frames)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def decaying(n: int = 600) -> list[float]:
    return [0.9 * math.exp(-i / 40) * math.cos(i / 3) for i in range(n)]


def test_planar_roundtrip() -> None:
    samples = [(-1) ** i * (i * 16411 % (1 << 23)) for i in range(512)]
    packed = wav_ir.pack_planar(samples)
    assert len(packed) == 1536
    assert wav_ir.unpack_planar(packed) == samples


def test_planar_layout_is_high_mid_low() -> None:
    packed = wav_ir.pack_planar([0x123456] + [0] * 511)
    assert (packed[0], packed[512], packed[1024]) == (0x12, 0x34, 0x56)
    negative = wav_ir.pack_planar([-1] + [0] * 511)
    assert (negative[0], negative[512], negative[1024]) == (0xFF, 0xFF, 0xFF)


@pytest.mark.parametrize(("bits", "is_float"), [(16, False), (24, False), (32, False),
                                                (32, True), (8, False)])
def test_formats_decode_to_same_ir(bits: int, is_float: bool) -> None:
    ir = wav_ir.wav_to_ir(make_wav(decaying(), bits=bits, is_float=is_float))
    ref = [wav_ir.to_int24(x) for x in decaying()[:512]]
    tolerance = (1 << 23) // 100 if bits == 8 else (1 << 23) // 20000
    assert len(ir) == 512
    assert max(abs(a - b) for a, b in zip(ir, ref, strict=True)) <= tolerance


def test_stereo_uses_first_channel_and_short_files_are_padded() -> None:
    ir = wav_ir.wav_to_ir(make_wav([0.5] * 10, channels=2))
    assert ir[:10] == [wav_ir.to_int24(0.5)] * 10 and ir[10:] == [0] * 502


def test_resampling_48k_keeps_duration() -> None:
    src = [math.sin(2 * math.pi * 1000 * i / 48000) for i in range(1000)]
    ir = wav_ir.wav_to_ir(make_wav(src, rate=48000, is_float=True, bits=32))
    expected = [wav_ir.to_int24(math.sin(2 * math.pi * 1000 * k / 44100)) for k in range(512)]
    assert max(abs(a - b) for a, b in zip(ir, expected, strict=True)) < (1 << 23) // 50


def test_saturation_matches_vendor() -> None:
    assert wav_ir.to_int24(1.0) == 0x7FFFF7 and wav_ir.to_int24(-1.5) == -0x7FFFF7


def test_rejects_non_wav() -> None:
    with pytest.raises(wav_ir.WavError):
        wav_ir.wav_to_ir(b"not a wav file at all")


def test_ir_to_wav_roundtrip() -> None:
    samples = [wav_ir.to_int24(x) for x in decaying()[:512]]
    assert wav_ir.wav_to_ir(wav_ir.ir_to_wav(samples)) == samples


def test_backup_chunk_parsing() -> None:
    body = encode_name("VOX AC30", 16) + wav_ir.pack_planar([7] * 512)
    chunk = msg.parse_backup_chunk(Frame(Op.BACKUP_CHUNK, bytes([3, 6]) + body))
    assert (chunk.index, chunk.slot, chunk.name) == (3, 6, "VOX AC30")
    assert wav_ir.unpack_planar(chunk.data) == [7] * 512
    header = msg.parse_backup_chunk(Frame(Op.BACKUP_CHUNK, bytes([0, 7])))
    assert (header.index, header.total) == (0, 7)
