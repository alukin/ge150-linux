"""Typed builders for host requests and parsers for device messages.

Byte offsets refer to plan.md §2.5-§2.10. ``Frame.data`` excludes the opcode, so a
vendor offset ``frame+N`` maps to ``data[N-5]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ge150.model.preset import (
    EXP_A,
    EXP_B,
    MODULES,
    NAME_LEN,
    PRESET_COUNT,
    Preset,
    decode_name,
    encode_name,
    pack_words,
    unpack_words,
)
from ge150.protocol.framing import Frame
from ge150.protocol.opcodes import MODULE_WRITE_OPS, Op

READ_FLAG = b"\x01"

# --- sizes ------------------------------------------------------------------
SYSTEM_SIZES = {Op.WRITE_SYSTEM_1: 2, Op.WRITE_SYSTEM_2: 2, Op.WRITE_SYSTEM_3: 4,
                Op.WRITE_SYSTEM_4: 2}
RHYTHM_SIZE = 6
USER_NAME_LEN = 16
USER_SLOTS = 10
USER_CHUNK = 512
#: Data chunks per upload: IR = 1536 B (512 x 24-bit samples), NR = 2048 B.
USER_CHUNKS = {Op.USER_IR: 3, Op.USER_NR: 4}
#: First wire slot of each user bank (0-based model index: CAB 27 / AMP 56).
USER_FIRST_SLOT = {Op.USER_IR: 0x1A, Op.USER_NR: 0x37}
BACKUP_CHUNK_SIZE = 0x610


def _check_slot(slot: int) -> int:
    if not 1 <= slot <= PRESET_COUNT:
        raise ValueError(f"preset slot must be 1..{PRESET_COUNT}, got {slot}")
    return slot


# =============================================================================
# Host -> device
# =============================================================================


def identify() -> Frame:
    return Frame(Op.IDENTIFY, b"\x00")


def read(op: Op) -> Frame:
    """Generic read request (``[op] 01``): 0x31, 0x8C, 0xA0, 0xB0, 0xC1, 0xC4."""
    return Frame(op, READ_FLAG)


def write_module(index: int, words: list[int]) -> Frame:
    layout = MODULES[index]
    if len(words) != layout.words:
        raise ValueError(f"{layout.name} needs {layout.words} words, got {len(words)}")
    return Frame(MODULE_WRITE_OPS[index], pack_words(words))


def select_preset(slot: int) -> Frame:
    return Frame(Op.SELECT_PRESET, bytes([_check_slot(slot)]))


def rename_preset(slot: int, name: str) -> Frame:
    """0x97: slot + 15 name bytes (the vendor truncates the QString to 15 chars)."""
    return Frame(Op.RENAME_PRESET, bytes([_check_slot(slot)]) + encode_name(name, 15))


def write_preset(preset: Preset) -> Frame:
    """0xC3: slot + 14-byte name + 72 words (LEN = 0xA0)."""
    data = bytes([_check_slot(preset.slot)]) + encode_name(preset.name) + pack_words(preset.words)
    return Frame(Op.WRITE_PRESET, data)


def write_exp(preset_words: list[int]) -> tuple[Frame, Frame]:
    """EXP block A (0x98) and block B (0xB3) from the 72 preset words."""
    return (Frame(Op.WRITE_EXP_A, pack_words(preset_words[EXP_A])),
            Frame(Op.WRITE_EXP_B, pack_words(preset_words[EXP_B])))


def write_system(op: Op, data: bytes) -> Frame:
    size = SYSTEM_SIZES.get(op)
    if size is None or len(data) != size:
        raise ValueError(f"{op!r} expects {size} bytes")
    return Frame(op, data)


def write_rhythm(data: bytes) -> Frame:
    if len(data) != RHYTHM_SIZE:
        raise ValueError(f"rhythm block is {RHYTHM_SIZE} bytes")
    return Frame(Op.WRITE_RHYTHM, data)


def set_page(page: int) -> Frame:
    return Frame(Op.SET_PAGE, pack_words([page]))


def user_slot_frames(op: Op, slot_index: int, name: str, payload: bytes) -> list[Frame]:
    """Multipart upload of an IR (0xB5) or NR (0xB7) into user slot 0..9.

    Sequence (FUN_004153b0): header, name, then 512-byte chunks. Send with 100 ms
    between frames. ``payload`` shorter than the bank size is zero padded.
    """
    if op not in USER_CHUNKS:
        raise ValueError("op must be Op.USER_IR or Op.USER_NR")
    if not 0 <= slot_index < USER_SLOTS:
        raise ValueError(f"user slot must be 0..{USER_SLOTS - 1}")
    size = USER_CHUNKS[op] * USER_CHUNK
    if len(payload) > size:
        raise ValueError(f"payload too long: {len(payload)} > {size}")
    payload = payload + bytes(size - len(payload))
    wire_slot = USER_FIRST_SLOT[op] + slot_index
    frames = [Frame(op, bytes([0, wire_slot, 0, 1])),
              Frame(op, bytes([1]) + encode_name(name, USER_NAME_LEN))]
    for part in range(USER_CHUNKS[op]):
        chunk = payload[part * USER_CHUNK : (part + 1) * USER_CHUNK]
        frames.append(Frame(op, bytes([part + 2]) + chunk))
    return frames


def delete_user_slot_frames(op: Op, slot_index: int) -> list[Frame]:
    """Deleting = uploading the name ``Empty`` with zeroed data (FUN_004149b0)."""
    return user_slot_frames(op, slot_index, "Empty", b"")


# =============================================================================
# Device -> host
# =============================================================================


@dataclass(frozen=True)
class DeviceInfo:
    """Answer to IDENTIFY (opcode 0x01). ``firmware`` is the field the vendor launcher
    compares with config.ini AppVersion. The other version fields are unidentified [?]."""

    name: str
    firmware: str
    field_a: str = ""
    field_c: str = ""
    revision: str = ""
    field_d: str = ""
    raw: bytes = b""


#: Identification answer layout, verified on a real GE150 (2026-11-21) [V]:
#: name[32] | field_a[7] | firmware[7] | field_c[7] | revision[2] | field_d[7]  (62 bytes)
#: Observed: "MOOER_GE150", "V1.0.0", "V1.3.8", "V1.3.1", "A", "V1.1.0".
_ID_FIELDS = (("name", 32), ("field_a", 7), ("firmware", 7), ("field_c", 7),
              ("revision", 2), ("field_d", 7))


def parse_identify(frame: Frame) -> DeviceInfo:
    d, pos, values = frame.data, 0, {}
    for key, size in _ID_FIELDS:
        values[key] = decode_name(d[pos : pos + size])
        pos += size
    return DeviceInfo(raw=d, **values)


def parse_preset_dump(frame: Frame) -> Preset:
    """0x20: slot, 14-byte name, parameter words (72 used)."""
    d = frame.data
    return Preset(d[0], decode_name(d[1 : 1 + NAME_LEN]), unpack_words(d[1 + NAME_LEN :], 72))


@dataclass(frozen=True)
class CurrentPreset:
    slot: int
    page: int
    words: list[int]


def parse_current(frame: Frame) -> CurrentPreset:
    """0x30: slot, page byte, parameter words."""
    d = frame.data
    return CurrentPreset(d[0], d[1], unpack_words(d[2:], 72))


def parse_module(frame: Frame) -> tuple[int, list[int]]:
    """0x02..0x0A: (module index, words)."""
    index = frame.opcode - Op.MODULE_FX
    if not 0 <= index < len(MODULES):
        raise ValueError(f"not a module frame: {frame!r}")
    return index, unpack_words(frame.data, MODULES[index].words)


def parse_preset_renamed(frame: Frame) -> tuple[int, str]:
    return frame.data[0], decode_name(frame.data[1 : 1 + NAME_LEN])


@dataclass
class SystemSettings:
    """Raw system blocks 0x24..0x27 (meaning of each block still unknown [?])."""

    blocks: dict[int, bytes] = field(default_factory=dict)

    @classmethod
    def from_all(cls, frame: Frame) -> SystemSettings:
        d, pos = frame.data, 0
        blocks: dict[int, bytes] = {}
        for op, size in SYSTEM_SIZES.items():
            blocks[op] = bytes(d[pos : pos + size]).ljust(size, b"\x00")
            pos += size
        return cls(blocks)


@dataclass(frozen=True)
class UserNames:
    """0x41 answer: first list = NR (amp captures), second list = IR (cabinets) [V].

    Verified on hardware: the second list matches the IR names of the backup dump and the
    CAB user model selected by the current preset. Factory blank = "EMPTY"; slots deleted
    by the vendor editor read "Empty".
    """

    nr: list[str]
    ir: list[str]


def parse_user_names(frame: Frame) -> UserNames:
    d = frame.data

    def names(base: int) -> list[str]:
        return [decode_name(d[base + i * USER_NAME_LEN : base + (i + 1) * USER_NAME_LEN])
                for i in range(USER_SLOTS)]

    return UserNames(nr=names(0), ir=names(USER_SLOTS * USER_NAME_LEN))


def is_empty_slot_name(name: str) -> bool:
    return name.strip().upper() in ("", "EMPTY")


@dataclass(frozen=True)
class BackupChunk:
    """0x44 frame of the 0xC4 dump [V]: header (``index`` 0, ``total`` chunks) or one used
    IR slot: ``index`` (1-based), ``slot`` (0-based IR slot), 16-byte name, 1536 B data."""

    index: int
    total: int | None = None
    slot: int | None = None
    name: str = ""
    data: bytes = b""


def parse_backup_chunk(frame: Frame) -> BackupChunk:
    d = frame.data
    if d[0] == 0:
        return BackupChunk(0, total=d[1])
    body = bytes(d[2 : 2 + BACKUP_CHUNK_SIZE])
    return BackupChunk(d[0], slot=d[1], name=decode_name(body[:USER_NAME_LEN]),
                       data=body[USER_NAME_LEN:])
