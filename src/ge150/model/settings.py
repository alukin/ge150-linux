"""System settings (0x24..0x27 / 0xA4..0xA7) and rhythm box (0x0C / 0x8D), decoded.

Every field was identified on hardware by changing it on the pedal and reading it back
(plan.md §2.11). Writes are not acknowledged by the pedal; reading back shows them.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from ge150.protocol.opcodes import Op

#: INPUT LEVEL and OTG LEVEL: index into this list (vendor FUN_004318d0) [V hardware:
#: 9 = 0 dB, 10 = 0.5 dB, 8 = -5 dB].
LEVELS: tuple[str, ...] = (
    "- dB", "-60 dB", "-45 dB", "-35 dB", "-30 dB", "-25 dB", "-20 dB", "-10 dB", "-5 dB",
    "0 dB", *(f"{x / 2:.1f} dB" for x in range(1, 13)),
)
CAB_THRU = ("THRU", "ON")  # CAB SIM THRU, per output: 0 = THRU, 1 = ON [V]
RHYTHM_MODES = ("RHYTHM", "METRONOME")  # [V]

SCREEN_RANGE = (0, 20)  # [V] 19 and 20 seen; lower bound [?]
BPM_RANGE = (40, 260)  # [V] confirmed on the pedal
VOLUME_RANGE = (0, 10)  # [V] 5 and 10 seen; bounds [?]
STYLE_COUNT = {0: 40, 1: 10}  # manual: 40 drum rhythms and 10 metronome options


def level_label(index: int) -> str:
    return LEVELS[index] if 0 <= index < len(LEVELS) else f"?{index}"


def level_index(text: str | int) -> int:
    """Accept an index, "0.5", "0.5 dB", "-5" or "-" (mute)."""
    if isinstance(text, int):
        index = text
    else:
        clean = text.strip().lower().removesuffix("db").strip()
        labels = [x.lower().removesuffix(" db") for x in LEVELS]
        candidates = [clean, f"{float(clean):.1f}" if _is_number(clean) else clean]
        if _is_number(clean) and float(clean) == int(float(clean)):
            candidates.append(str(int(float(clean))))
        index = next((labels.index(c) for c in candidates if c in labels), -1)
        if index < 0:
            raise ValueError(f"unknown level {text!r}; valid: {', '.join(LEVELS)}")
    if not 0 <= index < len(LEVELS):
        raise ValueError(f"level index must be 0..{len(LEVELS) - 1}")
    return index


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _u16(data: bytes, pos: int = 0) -> int:
    return int(struct.unpack_from("<H", data.ljust(pos + 2, b"\x00"), pos)[0])


@dataclass
class SystemValues:
    input_level: int = 9
    screen: int = 20
    cab_left_on: bool = True
    cab_right_on: bool = True
    otg_level: int = 9

    @classmethod
    def from_blocks(cls, blocks: dict[int, bytes]) -> SystemValues:
        cab = blocks.get(Op.WRITE_SYSTEM_3, bytes(4))
        return cls(
            input_level=_u16(blocks.get(Op.WRITE_SYSTEM_1, b"")),
            screen=_u16(blocks.get(Op.WRITE_SYSTEM_2, b"")),
            cab_left_on=bool(_u16(cab, 0)),
            cab_right_on=bool(_u16(cab, 2)),
            otg_level=_u16(blocks.get(Op.WRITE_SYSTEM_4, b"")),
        )

    def to_blocks(self) -> dict[int, bytes]:
        return {
            Op.WRITE_SYSTEM_1: struct.pack("<H", self.input_level),
            Op.WRITE_SYSTEM_2: struct.pack("<H", self.screen),
            Op.WRITE_SYSTEM_3: struct.pack("<HH", int(self.cab_left_on), int(self.cab_right_on)),
            Op.WRITE_SYSTEM_4: struct.pack("<H", self.otg_level),
        }

    def describe(self) -> list[tuple[str, str]]:
        return [
            ("INPUT LEVEL", level_label(self.input_level)),
            ("SCREEN", str(self.screen)),
            ("CAB-L", CAB_THRU[self.cab_left_on]),
            ("CAB-R", CAB_THRU[self.cab_right_on]),
            ("OTG LEVEL", level_label(self.otg_level)),
        ]

    def validate(self) -> None:
        for name, value in (("input level", self.input_level), ("OTG level", self.otg_level)):
            if not 0 <= value < len(LEVELS):
                raise ValueError(f"{name} must be 0..{len(LEVELS) - 1}, got {value}")
        if not SCREEN_RANGE[0] <= self.screen <= SCREEN_RANGE[1]:
            raise ValueError(f"screen must be {SCREEN_RANGE[0]}..{SCREEN_RANGE[1]}")


@dataclass
class RhythmValues:
    """``on, mode, style, volume, bpm (u16 LE)`` [V hardware: 01 01 00 05 79 00 =
    on, METRONOME, style 0, volume 5, 121 BPM]."""

    on: bool = False
    mode: int = 0
    style: int = 0
    volume: int = 5
    bpm: int = 120

    @classmethod
    def from_bytes(cls, data: bytes) -> RhythmValues:
        d = bytes(data).ljust(6, b"\x00")
        return cls(bool(d[0]), d[1], d[2], d[3], _u16(d, 4))

    def to_bytes(self) -> bytes:
        return struct.pack("<BBBBH", int(self.on), self.mode, self.style, self.volume, self.bpm)

    def describe(self) -> list[tuple[str, str]]:
        mode = RHYTHM_MODES[self.mode] if self.mode < len(RHYTHM_MODES) else f"?{self.mode}"
        return [
            ("STATE", "ON" if self.on else "OFF"),
            ("MODE", mode),
            ("STYLE", str(self.style + 1)),
            ("BPM", str(self.bpm)),
            ("VOL", str(self.volume)),
        ]

    def validate(self) -> None:
        checks = [
            ("mode", self.mode, 0, len(RHYTHM_MODES) - 1),
            ("style", self.style, 0, STYLE_COUNT.get(self.mode, 40) - 1),
            ("volume", self.volume, *VOLUME_RANGE),
            ("bpm", self.bpm, *BPM_RANGE),
        ]
        for name, value, low, high in checks:
            if not low <= value <= high:
                raise ValueError(f"rhythm {name} must be {low}..{high}, got {value}")
