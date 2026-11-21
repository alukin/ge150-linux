"""Frame encoding, 64-byte report fragmentation and a resynchronising stream decoder.

Frame layout (plan.md §2.3)::

    AA 55 | LEN (u16 LE) | OPCODE | DATA (LEN-1 bytes) | CRC16 (big-endian)

The CRC covers the LEN field and the payload. On the wire every frame is cut into
63-byte chunks, each carried by one 64-byte interrupt report whose first byte is the
number of useful bytes that follow.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from ge150.protocol.crc import crc16_gsm

HEADER = b"\xaa\x55"
REPORT_SIZE = 64
CHUNK_SIZE = REPORT_SIZE - 1
#: Largest payload seen in the vendor code (multipart IR/NR chunks: 0x202 bytes).
MAX_PAYLOAD = 0x0800


class FrameError(ValueError):
    """Raised when building an invalid frame."""


@dataclass(frozen=True)
class Frame:
    """One decoded frame. ``data`` excludes the opcode byte."""

    opcode: int
    data: bytes = b""

    @property
    def payload(self) -> bytes:
        return bytes([self.opcode]) + self.data

    def encode(self) -> bytes:
        return encode_frame(self.opcode, self.data)

    def __repr__(self) -> str:
        return f"Frame(0x{self.opcode:02X}, {self.data.hex(' ') or '-'})"


def encode_frame(opcode: int, data: bytes = b"") -> bytes:
    """Build the full byte frame for ``opcode`` + ``data`` including CRC."""
    if not 0 <= opcode <= 0xFF:
        raise FrameError(f"opcode out of range: {opcode}")
    payload = bytes([opcode]) + bytes(data)
    if len(payload) > MAX_PAYLOAD:
        raise FrameError(f"payload too long: {len(payload)} bytes")
    length = struct.pack("<H", len(payload))
    crc = crc16_gsm(length + payload)
    return HEADER + length + payload + struct.pack(">H", crc)


def split_reports(frame: bytes) -> list[bytes]:
    """Cut a frame into 64-byte output reports (``[n] + n bytes + zero padding``)."""
    reports = []
    for start in range(0, len(frame), CHUNK_SIZE):
        chunk = frame[start : start + CHUNK_SIZE]
        reports.append(bytes([len(chunk)]) + chunk + bytes(CHUNK_SIZE - len(chunk)))
    return reports


def report_data(report: bytes) -> bytes:
    """Extract the useful bytes of an input report.

    Assumption [I] (plan.md §2.2): ``report[0]`` is the number of useful bytes, as in
    output reports. If that byte is not a plausible length we fall back to the vendor
    behaviour (everything after byte 0); the decoder resynchronises on ``AA 55`` anyway.
    """
    if not report:
        return b""
    n = report[0]
    if 1 <= n <= len(report) - 1:
        return bytes(report[1 : 1 + n])
    return bytes(report[1:])


@dataclass
class DecoderStats:
    frames: int = 0
    crc_errors: int = 0
    discarded_bytes: int = 0


@dataclass
class FrameDecoder:
    """Incremental decoder: feed raw bytes, get complete CRC-valid frames.

    Garbage before a header, truncated frames and CRC errors are skipped by
    discarding one byte and searching for the next ``AA 55``.
    """

    max_buffer: int = 0x4000
    stats: DecoderStats = field(default_factory=DecoderStats)
    _buf: bytearray = field(default_factory=bytearray)

    def feed(self, data: bytes) -> list[Frame]:
        self._buf.extend(data)
        frames = list(self._drain())
        if len(self._buf) > self.max_buffer:
            self.stats.discarded_bytes += len(self._buf)
            self._buf.clear()
        return frames

    def feed_reports(self, reports: Iterable[bytes]) -> list[Frame]:
        frames: list[Frame] = []
        for report in reports:
            frames.extend(self.feed(report_data(report)))
        return frames

    @property
    def pending(self) -> int:
        return len(self._buf)

    def _discard(self, count: int) -> None:
        del self._buf[:count]
        self.stats.discarded_bytes += count

    def _drain(self) -> Iterator[Frame]:
        buf = self._buf
        while True:
            start = buf.find(HEADER)
            if start < 0:
                # Keep a trailing 0xAA: it may be the first half of a header.
                keep = 1 if buf.endswith(HEADER[:1]) else 0
                self._discard(len(buf) - keep)
                return
            if start:
                self._discard(start)
            if len(buf) < 4:
                return
            (length,) = struct.unpack_from("<H", buf, 2)
            if length == 0 or length > MAX_PAYLOAD:
                self._discard(1)
                continue
            total = length + 6
            if len(buf) < total:
                return
            body = bytes(buf[2 : 4 + length])
            (crc,) = struct.unpack_from(">H", buf, 4 + length)
            if crc16_gsm(body) != crc:
                self.stats.crc_errors += 1
                self._discard(1)
                continue
            del buf[:total]
            self.stats.frames += 1
            yield Frame(body[2], body[3:])
