"""The expression pedal settings of a preset (words 66..71, plan.md §2.6).

``MODULE_CTRL`` is the module the pedal controls (0 = FX … 8 = REVERB) and ``PARA_CTRL`` an
index into one flat list of the parameters it can control, module after module: the list the
vendor app builds for its EXP menu (``FUN_00424c90``; its default "EXP:FX/COMP - POSITION" is
0/0). Each module's part is exactly its models' number parameters, and the indexes stored in a
real pedal's 200 presets all land on a parameter of that preset's model (MIX of ANA-CHORUS,
DEPTH of VIBRATO, DECAY of CHURCH…). ``FUN_SWITCH`` turns that control on; ``VOL_SWITCH``,
``VOL_MIN`` and ``VOL_MAX`` are the volume pedal, independent of it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ge150.model.catalog import Model, Param
from ge150.model.preset import EXP_OFFSET, MODULES

#: Per module, in the vendor's order (names upper-case: the EQ bands are "80Hz" in the catalog).
PARAMS: tuple[tuple[str, ...], ...] = (
    ("POSITION", "Q", "RATE", "ATTACK", "RANGE", "SENS", "THRES", "PEAK", "RATIO", "LEVEL"),
    ("VOLUME", "TONE", "GAIN"),
    ("GAIN", "BASS", "MID", "TREBLE", "PRES", "MST"),
    ("CENTER", "DISTANCE"),
    ("THRES", "SENS", "ATTACK", "RELEASE"),
    ("80HZ", "100HZ", "200HZ", "240HZ", "250HZ", "400HZ", "630HZ", "750HZ", "800HZ", "1.6KHZ",
     "2.2KHZ", "3.2KHZ", "4KHZ", "6.6KHZ"),
    ("RATE", "PITCH", "RISE", "SAMPLE", "MIX", "DEPTH", "LEVEL", "FEEDBACK", "TONE", "Q", "RANGE",
     "BIT"),
    ("LEVEL", "FEEDBACK", "TIME", "TIME A", "THRES", "TIME B"),
    ("PRE DELAY", "LEVEL", "DECAY", "TONE"),
)
assert len(PARAMS) == len(MODULES)

VOLUME_RANGE = (0, 100)


def first_index(module: int) -> int:
    """``PARA_CTRL`` of the module's first parameter."""
    return sum(len(names) for names in PARAMS[:module])


def para_index(module: int, name: str) -> int | None:
    """``PARA_CTRL`` for a parameter of ``module``, or None if the pedal cannot control it."""
    names = PARAMS[module]
    key = name.upper()
    return first_index(module) + names.index(key) if key in names else None


def para_name(module: int, para: int) -> str | None:
    """The parameter ``para`` points at, if it belongs to ``module``."""
    offset = para - first_index(module)
    names = PARAMS[module] if 0 <= module < len(PARAMS) else ()
    return names[offset] if 0 <= offset < len(names) else None


def controllable(module: int, model: Model | None) -> list[Param]:
    """The model's parameters the pedal can control, in the model's own order."""
    names = PARAMS[module]
    return [p for p in (model.params if model else ()) if p.name.upper() in names]


@dataclass
class ExpSettings:
    module: int = 0
    para: int = 0
    function_on: bool = False
    volume_on: bool = False
    vol_min: int = 0
    vol_max: int = 100

    @classmethod
    def from_words(cls, words: Sequence[int]) -> ExpSettings:
        m, p, f, v, lo, hi = words[EXP_OFFSET:EXP_OFFSET + 6]
        return cls(m, p, bool(f), bool(v), lo, hi)

    def to_words(self, words: Sequence[int]) -> list[int]:
        """``words`` (a whole preset) with these settings."""
        result = list(words)
        result[EXP_OFFSET:EXP_OFFSET + 6] = [
            self.module, self.para, int(self.function_on), int(self.volume_on),
            self.vol_min, self.vol_max]
        return result

    @property
    def param_name(self) -> str | None:
        return para_name(self.module, self.para)
