"""``.amp`` NR (amp capture) files <-> the pedal's user AMP slot format (plan.md §2.8).

File layout read by FUN_0041f700 of MOOER_GE150.exe [V]::

    512 x int32 LE   data words
    int32 LE         checksum = sum of the 512 words (32-bit wrap-around)
    ...              (anything)
    "2.0"            the last three bytes of the file

Upload (FUN_004153b0, opcode 0xB7): four 512-byte parts; part ``n`` (2..5) carries byte
``5 - n`` of every 32-bit word, i.e. planes from the most to the least significant byte.
"""

from __future__ import annotations

import struct
from pathlib import Path

NR_WORDS = 512
NR_BYTES = NR_WORDS * 4
TRAILER = b"2.0"


class AmpError(ValueError):
    pass


def parse_amp(data: bytes) -> list[int]:
    """Validate an ``.amp`` file and return its 512 signed 32-bit words."""
    if len(data) < NR_BYTES + 4 + len(TRAILER):
        raise AmpError("file too short for an NR capture")
    if not data.endswith(TRAILER):
        raise AmpError("missing '2.0' trailer: not a GE150 NR file")
    words = list(struct.unpack_from(f"<{NR_WORDS}i", data))
    stored = struct.unpack_from("<I", data, NR_BYTES)[0]
    if stored != sum(words) & 0xFFFFFFFF:
        raise AmpError("checksum mismatch")
    return words


def build_amp(words: list[int]) -> bytes:
    """Inverse of :func:`parse_amp` (useful to export captures from a backup)."""
    if len(words) != NR_WORDS:
        raise AmpError(f"an NR capture has {NR_WORDS} words")
    body = struct.pack(f"<{NR_WORDS}i", *words)
    return body + struct.pack("<I", sum(words) & 0xFFFFFFFF) + TRAILER


def pack_planar(words: list[int]) -> bytes:
    """512 words -> 2048 bytes: byte 3 plane, byte 2 plane, byte 1 plane, byte 0 plane."""
    if len(words) != NR_WORDS:
        raise AmpError(f"an NR capture has {NR_WORDS} words")
    u = [w & 0xFFFFFFFF for w in words]
    return b"".join(bytes((v >> shift) & 0xFF for v in u) for shift in (24, 16, 8, 0))


def unpack_planar(data: bytes) -> list[int]:
    if len(data) < NR_BYTES:
        raise AmpError(f"an NR payload needs {NR_BYTES} bytes")
    out = []
    for i in range(NR_WORDS):
        v = (data[i] << 24 | data[NR_WORDS + i] << 16 | data[2 * NR_WORDS + i] << 8
             | data[3 * NR_WORDS + i])
        out.append(v - (1 << 32) if v & 0x80000000 else v)
    return out


def load_nr_file(path: str | Path) -> bytes:
    """``.amp`` path -> 2048-byte payload ready for an NR upload (opcode 0xB7)."""
    return pack_planar(parse_amp(Path(path).read_bytes()))
