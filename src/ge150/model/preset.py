"""Preset memory layout (plan.md §2.7).

A preset is a 14-byte ASCII name plus 72 little-endian u16 words: nine module blocks
followed by the expression-pedal settings. Block sizes come from FUN_0041a9c0 of the
vendor editor [V]; the module order follows the chains of preset.xml [I]. Inside a
block, word 0 is SWITCH, word 1 is TYPE and the rest are parameters [I].
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

PRESET_COUNT = 200
PRESET_WORDS = 72
NAME_LEN = 14
#: Characters accepted by the vendor editor for preset names.
NAME_PATTERN = re.compile(r"^[A-Za-z0-9\- ]*$")


@dataclass(frozen=True)
class ModuleLayout:
    index: int
    name: str
    words: int
    offset: int

    @property
    def write_op(self) -> int:
        return 0x82 + self.index

    @property
    def notify_op(self) -> int:
        return 0x02 + self.index

    @property
    def slice(self) -> slice:
        return slice(self.offset, self.offset + self.words)


def _build_layout() -> tuple[ModuleLayout, ...]:
    names = ("FX/COMP", "DS/OD", "AMP", "CAB", "NS GATE", "EQ", "MOD", "DELAY", "REVERB")
    sizes = (6, 5, 8, 7, 5, 11, 9, 9, 6)
    layout, offset = [], 0
    for index, (name, words) in enumerate(zip(names, sizes, strict=True)):
        layout.append(ModuleLayout(index, name, words, offset))
        offset += words
    return tuple(layout)


MODULES = _build_layout()
MODULE_COUNT = len(MODULES)

#: Expression pedal fields, words 66..71 (order of the .mo writer, FUN_00422e00) [V].
EXP_KEYS = ("MODULE_CTRL", "PARA_CTRL", "FUN_SWITCH", "VOL_SWITCH", "VOL_MIN", "VOL_MAX")
EXP_OFFSET = MODULES[-1].offset + MODULES[-1].words
#: Split between the two EXP messages (0x98/0x18 then 0xB3/0x33) [I].
EXP_A = slice(EXP_OFFSET, EXP_OFFSET + 3)
EXP_B = slice(EXP_OFFSET + 3, EXP_OFFSET + 6)

assert EXP_OFFSET + len(EXP_KEYS) == PRESET_WORDS


def pack_words(words: list[int] | tuple[int, ...]) -> bytes:
    """u16 little-endian packing. Values are masked to 16 bits."""
    return struct.pack(f"<{len(words)}H", *(w & 0xFFFF for w in words))


def unpack_words(data: bytes, count: int | None = None) -> list[int]:
    """Unpack u16 LE words; a trailing odd byte is ignored."""
    n = len(data) // 2 if count is None else min(count, len(data) // 2)
    return list(struct.unpack_from(f"<{n}H", data))


def encode_name(name: str, length: int = NAME_LEN) -> bytes:
    """ASCII, truncated to ``length`` and NUL padded. Non-ASCII becomes '?'."""
    raw = name.encode("ascii", errors="replace")[:length]
    return raw + bytes(length - len(raw))


def decode_name(raw: bytes) -> str:
    """Up to the first NUL; bytes >= 0x80 become spaces (as the vendor editor does)."""
    raw = raw.split(b"\x00", 1)[0]
    return "".join(chr(b) if 0x20 <= b < 0x80 else " " for b in raw).rstrip()


def is_valid_name(name: str, length: int = NAME_LEN) -> bool:
    return len(name) <= length and bool(NAME_PATTERN.match(name))


@dataclass
class ModuleBlock:
    """Words of one module. ``switch`` and ``type`` are the first two words [I]."""

    layout: ModuleLayout
    words: list[int]

    @property
    def switch(self) -> bool:
        return bool(self.words[0])

    @switch.setter
    def switch(self, on: bool) -> None:
        self.words[0] = 1 if on else 0

    @property
    def type(self) -> int:
        return self.words[1]

    @type.setter
    def type(self, value: int) -> None:
        self.words[1] = value

    @property
    def params(self) -> list[int]:
        return self.words[2:]

    def set_param(self, index: int, raw: int) -> None:
        if not 0 <= index < self.layout.words - 2:
            raise IndexError(f"{self.layout.name} has no parameter #{index}")
        self.words[2 + index] = raw & 0xFFFF


@dataclass
class Preset:
    """One preset slot. ``slot`` is 1-based as on the wire (1..200)."""

    slot: int
    name: str = ""
    words: list[int] = field(default_factory=lambda: [0] * PRESET_WORDS)

    def __post_init__(self) -> None:
        if len(self.words) < PRESET_WORDS:
            self.words = list(self.words) + [0] * (PRESET_WORDS - len(self.words))
        elif len(self.words) > PRESET_WORDS:
            self.words = list(self.words[:PRESET_WORDS])

    def module(self, index: int) -> ModuleBlock:
        """A copy of module ``index``; write it back with :meth:`set_module`."""
        layout = MODULES[index]
        return ModuleBlock(layout, list(self.words[layout.slice]))

    def set_module(self, block: ModuleBlock) -> None:
        layout = block.layout
        if len(block.words) != layout.words:
            raise ValueError(f"{layout.name} needs {layout.words} words")
        self.words[layout.slice] = block.words

    @property
    def exp(self) -> dict[str, int]:
        return dict(zip(EXP_KEYS, self.words[EXP_OFFSET:], strict=True))

    def set_exp(self, key: str, value: int) -> None:
        self.words[EXP_OFFSET + EXP_KEYS.index(key)] = value & 0xFFFF

    def copy(self, slot: int | None = None) -> Preset:
        return Preset(self.slot if slot is None else slot, self.name, list(self.words))
