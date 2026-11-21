"""WAV impulse responses <-> the GE150 user-cabinet format (plan.md §2.8).

The pedal stores an IR as 512 signed 24-bit samples at 44.1 kHz, sent *planar* in
three 512-byte chunks: chunk 2 = high bytes, chunk 3 = middle bytes, chunk 4 = low
bytes (FUN_004153b0 copies byte ``4 - n`` of every 32-bit sample into chunk ``n``).
Verified by decoding the IRs of a real pedal's backup dump.

Conversion follows the vendor editor (FUN_0041e770, FUN_0041e500): first channel only,
linear-interpolation resampling to 44.1 kHz, float -> round(x * 2^23) clamped. Unlike
the vendor code, unsigned 8-bit WAV is centred (the vendor forgets to subtract 128)
and any sample rate is accepted.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

IR_SAMPLES = 512
IR_RATE = 44100
IR_BYTES = IR_SAMPLES * 3
FULL_SCALE = 1 << 23
MAX_24 = FULL_SCALE - 1
MIN_24 = -FULL_SCALE

_PCM, _FLOAT, _EXTENSIBLE = 1, 3, 0xFFFE


class WavError(ValueError):
    pass


@dataclass(frozen=True)
class WavInfo:
    rate: int
    channels: int
    bits: int
    is_float: bool
    frames: int


def _chunks(data: bytes) -> dict[bytes, bytes]:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise WavError("not a RIFF/WAVE file")
    chunks: dict[bytes, bytes] = {}
    pos = 12
    while pos + 8 <= len(data):
        cid, size = data[pos : pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
        chunks.setdefault(cid, data[pos + 8 : pos + 8 + size])
        pos += 8 + size + (size & 1)
    if b"fmt " not in chunks or b"data" not in chunks:
        raise WavError("missing fmt or data chunk")
    return chunks


def read_wav(data: bytes) -> tuple[WavInfo, list[float]]:
    """Decode the first channel of a WAV file to floats in [-1, 1)."""
    chunks = _chunks(data)
    fmt = chunks[b"fmt "]
    if len(fmt) < 16:
        raise WavError("fmt chunk too short")
    tag, channels, rate, _, block, bits = struct.unpack_from("<HHIIHH", fmt)
    if tag == _EXTENSIBLE and len(fmt) >= 26:
        tag = struct.unpack_from("<H", fmt, 24)[0]
    if tag not in (_PCM, _FLOAT) or channels < 1 or block < channels * ((bits + 7) // 8):
        raise WavError(f"unsupported WAV format (tag {tag}, {bits} bits, {channels} ch)")
    raw = chunks[b"data"]
    frames = len(raw) // block
    width = (bits + 7) // 8
    out: list[float] = []
    for i in range(frames):
        s = raw[i * block : i * block + width]
        if tag == _FLOAT:
            if width == 4:
                out.append(struct.unpack("<f", s)[0])
            elif width == 8:
                out.append(struct.unpack("<d", s)[0])
            else:
                raise WavError(f"unsupported float width {bits}")
        elif width == 1:
            out.append((s[0] - 128) / 128.0)
        else:
            value = int.from_bytes(s, "little", signed=True)
            out.append(value / float(1 << (8 * width - 1)))
    return WavInfo(rate, channels, bits, tag == _FLOAT, frames), out


def resample_linear(samples: list[float], src_rate: int, count: int = IR_SAMPLES,
                    dst_rate: int = IR_RATE) -> list[float]:
    """Linear interpolation to ``dst_rate``, returning exactly ``count`` samples."""
    if src_rate <= 0:
        raise WavError("invalid sample rate")
    if not samples:
        return [0.0] * count
    ratio = src_rate / dst_rate
    out = []
    last = len(samples) - 1
    for k in range(count):
        pos = k * ratio
        i = int(pos)
        if i >= last:
            out.append(samples[last] if i == last else 0.0)
            continue
        frac = pos - i
        out.append(samples[i] + (samples[i + 1] - samples[i]) * frac)
    return out


def to_int24(x: float) -> int:
    """Float to signed 24-bit, saturating like the vendor (±1.0 -> ±0x7FFFF7)."""
    if x >= 1.0:
        return 0x7FFFF7
    if x <= -1.0:
        return -0x7FFFF7
    return max(MIN_24, min(MAX_24, round(x * FULL_SCALE)))


def wav_to_ir(data: bytes) -> list[int]:
    """WAV file bytes -> 512 signed 24-bit samples at 44.1 kHz."""
    info, samples = read_wav(data)
    if info.rate == IR_RATE:
        floats = (samples + [0.0] * IR_SAMPLES)[:IR_SAMPLES]
    else:
        floats = resample_linear(samples, info.rate)
    return [to_int24(x) for x in floats]


def pack_planar(samples: list[int]) -> bytes:
    """512 signed 24-bit samples -> 1536 bytes (high plane, middle plane, low plane)."""
    if len(samples) != IR_SAMPLES:
        raise ValueError(f"an IR has {IR_SAMPLES} samples")
    u = [s & 0xFFFFFF for s in samples]
    return (bytes((v >> 16) & 0xFF for v in u) + bytes((v >> 8) & 0xFF for v in u)
            + bytes(v & 0xFF for v in u))


def unpack_planar(data: bytes) -> list[int]:
    """1536 planar bytes -> 512 signed 24-bit samples."""
    if len(data) < IR_BYTES:
        raise ValueError(f"an IR needs {IR_BYTES} bytes")
    out = []
    for i in range(IR_SAMPLES):
        v = data[i] << 16 | data[IR_SAMPLES + i] << 8 | data[2 * IR_SAMPLES + i]
        out.append(v - (1 << 24) if v & 0x800000 else v)
    return out


def ir_to_wav(samples: list[int], rate: int = IR_RATE) -> bytes:
    """Signed 24-bit samples -> mono 24-bit PCM WAV bytes."""
    pcm = b"".join((s & 0xFFFFFF).to_bytes(3, "little") for s in samples)
    fmt = struct.pack("<HHIIHH", _PCM, 1, rate, rate * 3, 3, 24)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


def load_ir_file(path: str | Path) -> bytes:
    """Convenience: WAV path -> 1536-byte payload ready for an IR upload."""
    return pack_planar(wav_to_ir(Path(path).read_bytes()))
