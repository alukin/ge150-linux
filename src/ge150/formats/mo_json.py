"""``.mo`` preset files of the vendor editor (JSON, plan.md §3).

Writer FUN_00423300 / reader FUN_00421000 + FUN_00420910 of MOOER_GE150.exe [V]::

    {
        "Exp": {"FUN_SWITCH": 0, "MODULE_CTRL": 0, "PARA_CTRL": 0,
                "VOL_MAX": 100, "VOL_MIN": 0, "VOL_SWITCH": 0},
        "effectModule": {
            "AMP": {"Data": {"BASS": 40, "GAIN": 29, ...}, "SWITCH": 1, "TYPE": 1},
            ...
        },
        "fileInfo": {"app": "GE150 Edit", "app_version": "V1.3.0",
                     "device": "MOOER GE150", "device_version": "V1.3.0",
                     "schema": "GE150 Preset"},
        "preset_name": "Burden Clean"
    }

QJsonObject keeps keys sorted and QJsonDocument indents with 4 spaces, so the output
uses ``sort_keys=True, indent=4``. ``Data`` values are the raw words, except the DELAY
times, which the vendor stores as ``round(raw * a / b - 40)`` (0..2460) where ``a/b``
is the subdivision ratio selected by the matching SUB word (FUN_0041d470) [V]. The
inverse used on import is mathematical; it is exact for ratio 1/1 (SUB-D OFF or 1/4)
and still has to be checked against a vendor export for other subdivisions [?].
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from ge150.model.catalog import ModuleInfo, load_catalog
from ge150.model.preset import EXP_KEYS, MODULES, NAME_LEN, Preset, is_valid_name

FILE_INFO = {
    "app": "GE150 Edit",
    "app_version": "V1.3.0",
    "device": "MOOER GE150",
    "device_version": "V1.3.0",
    "schema": "GE150 Preset",
}
#: Subdivision ratios indexed by the delay SUB word (list built in FUN_00446a70).
SUBDIVISIONS = ((1, 1), (1, 1), (2, 3), (3, 2), (1, 2), (1, 3), (3, 4), (1, 4), (1, 6), (3, 8))
TIME_OFFSET = 40
TIME_MAX = 0x99C
#: DELAY time parameter -> word of the SUB selector that scales it.
DELAY_TIME_SUB_WORD = {"TIME": 5, "TIME A": 5, "TIME B": 7}
#: Models whose exported TIME is not rounded up by +0.5 (DYNAMIC, DUAL DELAY).
_NO_HALF_UP = (7, 8)
DELAY_INDEX = 7


class MoError(ValueError):
    pass


def _ratio(sub_word: int) -> tuple[int, int]:
    return SUBDIVISIONS[sub_word] if 0 <= sub_word < len(SUBDIVISIONS) else (1, 1)


def time_to_json(raw: int, sub_word: int, model_index: int) -> int:
    a, b = _ratio(sub_word)
    value = raw * a / b - TIME_OFFSET
    if model_index not in _NO_HALF_UP:
        value += 0.5
    return max(0, min(TIME_MAX, round(value)))


def time_from_json(value: int, sub_word: int) -> int:
    a, b = _ratio(sub_word)
    return max(0, min(0xFFFF, math.floor((value + TIME_OFFSET) * b / a + 0.5)))


def preset_to_mo(preset: Preset, catalog: tuple[ModuleInfo, ...] | None = None) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    modules: dict[str, Any] = {}
    for layout in MODULES:
        block = preset.module(layout.index)
        model = catalog[layout.index].model_for_type(block.type)
        data: dict[str, int] = {}
        for p in model.params if model else ():
            raw = block.words[p.word]
            if layout.index == DELAY_INDEX and p.name in DELAY_TIME_SUB_WORD:
                raw = time_to_json(raw, block.words[DELAY_TIME_SUB_WORD[p.name]], block.type)
            data[p.name] = raw
        modules[layout.name] = {"SWITCH": block.words[0], "TYPE": block.type, "Data": data}
    return {
        "fileInfo": dict(FILE_INFO),
        "preset_name": preset.name,
        "Exp": preset.exp,
        "effectModule": modules,
    }


def dumps(preset: Preset) -> str:
    return json.dumps(preset_to_mo(preset), sort_keys=True, indent=4, ensure_ascii=True) + "\n"


def mo_to_preset(doc: dict[str, Any], base: Preset,
                 catalog: tuple[ModuleInfo, ...] | None = None) -> Preset:
    """Apply a parsed ``.mo`` document on top of ``base`` (like the vendor import).

    Words not mentioned in the file keep the value of ``base``.
    """
    catalog = catalog or load_catalog()
    if doc.get("fileInfo", {}).get("schema") != FILE_INFO["schema"]:
        raise MoError("not a GE150 preset file (fileInfo.schema)")
    preset = base.copy()
    name = str(doc.get("preset_name", preset.name))[:NAME_LEN]
    preset.name = name if is_valid_name(name) else "".join(
        c if c.isascii() and (c.isalnum() or c in "- ") else " " for c in name)
    exp = doc.get("Exp", {})
    for key in EXP_KEYS:
        if key in exp:
            preset.set_exp(key, int(exp[key]))
    modules = doc.get("effectModule", {})
    for layout in MODULES:
        entry = modules.get(layout.name)
        if not isinstance(entry, dict):
            continue
        block = preset.module(layout.index)
        if "SWITCH" in entry:
            block.words[0] = 1 if int(entry["SWITCH"]) else 0
        if "TYPE" in entry:
            type_index = int(entry["TYPE"])
            if not 0 <= type_index < len(catalog[layout.index].models):
                raise MoError(f"{layout.name}: TYPE {type_index} out of range")
            block.words[1] = type_index
        model = catalog[layout.index].model_for_type(block.type)
        data = entry.get("Data", {})
        params = model.params if model else ()
        # SUB selectors first, so the delay times are converted with the new ratio.
        ordered = sorted(params, key=lambda p: p.name in DELAY_TIME_SUB_WORD)
        for p in ordered:
            if p.name not in data:
                continue
            value = int(data[p.name])
            if layout.index == DELAY_INDEX and p.name in DELAY_TIME_SUB_WORD:
                value = time_from_json(value, block.words[DELAY_TIME_SUB_WORD[p.name]])
            block.words[p.word] = value & 0xFFFF
        preset.set_module(block)
    return preset


def load(path: str | Path, base: Preset) -> Preset:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MoError(f"invalid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise MoError("invalid .mo file")
    return mo_to_preset(doc, base)


def save(path: str | Path, preset: Preset) -> None:
    Path(path).write_text(dumps(preset), encoding="utf-8")
