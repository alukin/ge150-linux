"""CRC-16/GSM as used by the GE150 frames.

poly 0x1021, init 0x0000, no reflection, xorout 0xFFFF. The vendor editor keeps the
same table at 0x44dd60 (MOOER_GE150.exe) and computes it over LEN(2 bytes) + PAYLOAD.
"""

from __future__ import annotations


def _make_table() -> tuple[int, ...]:
    table = []
    for i in range(256):
        crc = i << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
        table.append(crc & 0xFFFF)
    return tuple(table)


_TABLE = _make_table()


def crc16_gsm(data: bytes | bytearray | memoryview) -> int:
    """Return the CRC-16/GSM of ``data``."""
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFF) ^ _TABLE[((crc >> 8) ^ byte) & 0xFF]
    return crc ^ 0xFFFF
