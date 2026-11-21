"""``.mbf`` full backups of the vendor editor (plan.md §3).

Layout reconstructed from the writer FUN_004389d0 / FUN_00435a80 / FUN_00436a40 and the
reader FUN_00437330 / FUN_00434c20 / FUN_00437a00 of MOOER_GE150.exe [V]::

    0x000  file header, 0x400 bytes
           +0x00 "MOOER"   +0x08 "MOOER_GE150"   +0x28 "V1.0.0"   +0x2F "V1.0.2"
           +0x36 "V1.0.0"  +0x48 "BUFF"          +0x4C u32 number of sections
           +0x50 u64 absolute file offset of each section
           +0x3F8 u64 checksum = sum(header[0:0x3F8]) + sum(every byte after 0x400)
    section header, 0x100 bytes: +0x00 name, +0x20 u8 restore opcode,
           +0x28 u32 item count, +0x2C u32 item size
    item: 0x22-byte header (only +0x20 u16 = index/slot is used) + ``size`` data bytes

Sections written by the vendor, in order: GE150_PRESET (0xC3, 200 x 0xA0 = name 14 B +
2 B + 72 words), GE150_SYSTEM (0xFF, 1 x 10 B), GE150_RHYTHM (0x8D, 1 x 6 B) and
GE150_IR (0xB5, one 0x610-byte item per used IR slot = 16-byte name + 1536 planar bytes,
exactly the body of a 0x44 backup chunk).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

from ge150.model.preset import (
    NAME_LEN,
    PRESET_COUNT,
    PRESET_WORDS,
    Preset,
    decode_name,
    encode_name,
    pack_words,
    unpack_words,
)

HEADER_SIZE = 0x400
SECTION_HEADER = 0x100
ITEM_HEADER = 0x22
CHECKSUM_AT = 0x3F8
PRESET_ITEM = 0xA0
SYSTEM_SIZE = 10
RHYTHM_SIZE = 6
IR_ITEM = 0x610

SECTION_PRESET = "GE150_PRESET"
SECTION_SYSTEM = "GE150_SYSTEM"
SECTION_RHYTHM = "GE150_RHYTHM"
SECTION_IR = "GE150_IR"


class MbfError(ValueError):
    pass


@dataclass
class IrItem:
    slot: int  # 0-based user IR slot
    name: str
    data: bytes  # 1536 planar bytes


@dataclass
class Backup:
    presets: list[Preset] = field(default_factory=list)
    system: bytes = bytes(SYSTEM_SIZE)
    rhythm: bytes = bytes(RHYTHM_SIZE)
    irs: list[IrItem] = field(default_factory=list)


# --- encoding ----------------------------------------------------------------


def _byte_sum(data: bytes | bytearray) -> int:
    return sum(data)


def _section(name: str, opcode: int, size: int, items: list[tuple[int, bytes]]) -> bytes:
    header = bytearray(SECTION_HEADER)
    raw_name = name.encode("ascii")
    header[: len(raw_name)] = raw_name
    header[0x20] = opcode
    struct.pack_into("<II", header, 0x28, len(items), size)
    body = bytearray(header)
    for index, data in items:
        if len(data) != size:
            raise MbfError(f"{name}: item of {len(data)} bytes, expected {size}")
        item_header = bytearray(ITEM_HEADER)
        struct.pack_into("<H", item_header, 0x20, index)
        body += item_header + data
    return bytes(body)


def preset_item(preset: Preset) -> bytes:
    return encode_name(preset.name) + bytes(2) + pack_words(preset.words)


def build(backup: Backup) -> bytes:
    if len(backup.presets) != PRESET_COUNT:
        raise MbfError(f"a backup needs {PRESET_COUNT} presets")
    presets = sorted(backup.presets, key=lambda p: p.slot)
    sections = [
        _section(SECTION_PRESET, 0xC3, PRESET_ITEM,
                 [(p.slot - 1, preset_item(p)) for p in presets]),
        _section(SECTION_SYSTEM, 0xFF, SYSTEM_SIZE, [(0, bytes(backup.system[:SYSTEM_SIZE]))]),
        _section(SECTION_RHYTHM, 0x8D, RHYTHM_SIZE, [(0, bytes(backup.rhythm[:RHYTHM_SIZE]))]),
        _section(SECTION_IR, 0xB5, IR_ITEM,
                 [(ir.slot, encode_name(ir.name, 16) + bytes(ir.data)) for ir in backup.irs]),
    ]
    header = bytearray(HEADER_SIZE)
    for offset, text in ((0x00, "MOOER"), (0x08, "MOOER_GE150"), (0x28, "V1.0.0"),
                         (0x2F, "V1.0.2"), (0x36, "V1.0.0"), (0x48, "BUFF")):
        header[offset : offset + len(text)] = text.encode("ascii")
    struct.pack_into("<I", header, 0x4C, len(sections))
    offset = HEADER_SIZE
    for i, section in enumerate(sections):
        struct.pack_into("<Q", header, 0x50 + 8 * i, offset)
        offset += len(section)
    body = b"".join(sections)
    checksum = _byte_sum(header[:CHECKSUM_AT]) + _byte_sum(body)
    struct.pack_into("<Q", header, CHECKSUM_AT, checksum)
    return bytes(header) + body


# --- decoding ----------------------------------------------------------------


def _cstr(data: bytes) -> str:
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def parse(data: bytes, verify: bool = True) -> Backup:
    if len(data) < HEADER_SIZE:
        raise MbfError("file too short")
    header = data[:HEADER_SIZE]
    if _cstr(header[0:8]) != "MOOER" or _cstr(header[8:0x28]) != "MOOER_GE150" \
            or header[0x48:0x4C] != b"BUFF":
        raise MbfError("not a GE150 backup (MOOER / MOOER_GE150 / BUFF magic)")
    if verify:
        stored = struct.unpack_from("<Q", header, CHECKSUM_AT)[0]
        actual = _byte_sum(header[:CHECKSUM_AT]) + _byte_sum(data[HEADER_SIZE:])
        if stored != actual:
            raise MbfError(f"checksum mismatch ({stored} != {actual})")
    count = struct.unpack_from("<I", header, 0x4C)[0]
    if count > (CHECKSUM_AT - 0x50) // 8:
        raise MbfError("invalid section count")
    backup = Backup()
    for i in range(count):
        offset = struct.unpack_from("<Q", header, 0x50 + 8 * i)[0]
        if offset + SECTION_HEADER > len(data):
            raise MbfError(f"section {i} outside the file")
        name = _cstr(data[offset : offset + 0x20])
        items_count, size = struct.unpack_from("<II", data, offset + 0x28)
        end = offset + SECTION_HEADER + items_count * (ITEM_HEADER + size)
        if end > len(data):
            raise MbfError(f"{name}: truncated")
        pos = offset + SECTION_HEADER
        for _ in range(items_count):
            index = struct.unpack_from("<H", data, pos + 0x20)[0]
            item = data[pos + ITEM_HEADER : pos + ITEM_HEADER + size]
            pos += ITEM_HEADER + size
            _apply(backup, name, index, item)
    return backup


def _apply(backup: Backup, section: str, index: int, item: bytes) -> None:
    if section == SECTION_PRESET:
        name = decode_name(item[:NAME_LEN])
        words = unpack_words(item[16:], PRESET_WORDS)
        backup.presets.append(Preset(index + 1, name, words))
    elif section == SECTION_SYSTEM:
        backup.system = bytes(item[:SYSTEM_SIZE])
    elif section == SECTION_RHYTHM:
        backup.rhythm = bytes(item[:RHYTHM_SIZE])
    elif section == SECTION_IR:
        backup.irs.append(IrItem(index, decode_name(item[:16]), bytes(item[16:IR_ITEM])))


def load(path: str | Path) -> Backup:
    return parse(Path(path).read_bytes())


def save(path: str | Path, backup: Backup) -> None:
    Path(path).write_bytes(build(backup))
