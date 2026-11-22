"""The GE150 as a set of tools for AI clients (transport-agnostic, see ``server.py``).

Rules (docs/plan-ia-tone3000.md §3.2, §10): reads are free; changes go to the edit
buffer only (live, reversible with ``undo``); the AI never stores presets, never resets,
restores or flashes the pedal. Every method returns plain JSON-able data.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from ge150.model.gear import MODULE_TAGS, describe, gear_for
from ge150.model.preset import EXP_KEYS, EXP_OFFSET, MODULES, PRESET_COUNT
from ge150.services import tone_ai
from ge150.services.editor import Editor

T = TypeVar("T")

INSTRUCTIONS = """Controls a MOOER GE150 guitar multi-effects pedal connected to this computer.
Signal chain (fixed order): FX -> DS -> AMP -> CAB -> NS -> EQ -> MOD -> DELAY -> REVERB.
Workflow: read get_current_patch, look up models with get_catalog(module), then change the
sound with set_module or apply_patch. Changes are LIVE in the edit buffer and are NOT saved:
tell the user to press Save in the GE150 editor when they like it (you cannot save). Use undo
to go back. Use only model and parameter names from get_catalog; values outside a range are
clamped and reported."""


class ToolError(Exception):
    """A request the pedal cannot honour (the message is shown to the AI)."""


def _module_index(module: str) -> int:
    key = module.strip().upper()
    aliases = {"COMP": "FX", "OD": "DS", "DIST": "DS", "DLY": "DELAY", "REV": "REVERB",
               "GATE": "NS", "NOISE": "NS"}
    key = aliases.get(key, key)
    if key not in MODULE_TAGS:
        raise ToolError(f"unknown module {module!r}; use one of {', '.join(MODULE_TAGS)}")
    return MODULE_TAGS.index(key)


class PedalTools:
    """Thread-safe facade over an :class:`Editor` (one lock for every pedal access)."""

    def __init__(self, editor: Editor, lock: threading.Lock | None = None) -> None:
        self.editor = editor
        self.lock = lock or threading.Lock()
        self.history: list[list[int]] = []

    def _locked(self, fn: Callable[[], T]) -> T:
        with self.lock:
            if self.editor.state.edit is None:
                raise ToolError("the pedal has not been read yet")
            return fn()

    # --- reading ----------------------------------------------------------------------

    def get_catalog(self, module: str = "") -> dict[str, Any]:
        if not module:
            return {"modules": [
                {"module": tag, "name": info.name,
                 "models": len([m for m in info.models if not m.hidden])}
                for tag, info in zip(MODULE_TAGS, self.editor.catalog, strict=True)]}
        index = _module_index(module)
        info = self.editor.catalog[index]
        names = self.editor.state.user_names
        models = []
        for model in info.models:
            if model.hidden:
                continue
            entry: dict[str, Any] = {"model": model.name, "number": model.number}
            gear = gear_for(index, model.number)
            if gear.name:
                entry["based_on" if not gear.generic else "kind"] = gear.name
            if model.user_slot:
                bank = (names.ir if MODULE_TAGS[index] == "CAB" else names.nr) if names else []
                slot = model.number - (27 if MODULE_TAGS[index] == "CAB" else 56)
                entry["user_slot"] = bank[slot] if 0 <= slot < len(bank) else "?"
            entry["params"] = [_param_info(p) for p in model.params]
            models.append(entry)
        return {"module": MODULE_TAGS[index], "name": info.name, "models": models}

    def get_current_patch(self) -> dict[str, Any]:
        return self._locked(self._patch)

    def _patch(self) -> dict[str, Any]:
        state = self.editor.state
        stored = state.presets.get(state.current_slot or 0)
        edit = state.edit
        modules = []
        for index in range(len(MODULES)):
            block = self.editor.module(index)
            model = self.editor.catalog[index].model_for_type(block.type)
            entry: dict[str, Any] = {"module": MODULE_TAGS[index], "on": block.switch,
                                     "model": model.name if model else f"?{block.type}"}
            if model is not None:
                gear = gear_for(index, model.number)
                entry["based_on"] = describe(gear, False)
                entry["params"] = {p.name: p.format(block.words[p.word]) for p in model.params}
            modules.append(entry)
        exp = {key: edit.words[EXP_OFFSET + i] for i, key in enumerate(EXP_KEYS)} if edit else {}
        return {"slot": state.current_slot, "name": stored.name if stored else "",
                "unsaved_changes": state.dirty, "modules": modules, "expression_pedal": exp}

    def list_presets(self, query: str = "") -> dict[str, Any]:
        needle = query.strip().lower()
        presets = [{"slot": slot, "name": preset.name}
                   for slot, preset in sorted(self.editor.state.presets.items())
                   if needle in preset.name.lower()]
        return {"current": self.editor.state.current_slot, "presets": presets}

    def get_preset(self, slot: int) -> dict[str, Any]:
        preset = self.editor.state.presets.get(slot)
        if preset is None:
            raise ToolError(f"preset {slot} not loaded (1..{PRESET_COUNT})")
        modules = []
        for index in range(len(MODULES)):
            block = preset.module(index)
            model = self.editor.catalog[index].model_for_type(block.type)
            modules.append({"module": MODULE_TAGS[index], "on": block.switch,
                            "model": model.name if model else f"?{block.type}",
                            "params": {p.name: p.format(block.words[p.word])
                                       for p in (model.params if model else ())}})
        return {"slot": slot, "name": preset.name, "modules": modules}

    def list_user_irs(self) -> dict[str, Any]:
        names = self.editor.state.user_names
        if names is None:
            return {"ir": [], "nr": []}
        return {"ir": [{"slot": i + 1, "model": f"CAB {27 + i}", "name": n}
                       for i, n in enumerate(names.ir)],
                "nr": [{"slot": i + 1, "model": f"AMP {56 + i}", "name": n}
                       for i, n in enumerate(names.nr)]}

    def get_settings(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        system, rhythm = self.editor.system_values(), self.editor.rhythm_values()
        if system is not None:
            result["system"] = dict(system.describe())
        if rhythm is not None:
            result["rhythm"] = dict(rhythm.describe())
        return result

    # --- live changes -----------------------------------------------------------------

    def set_module(self, module: str, on: bool | None = None, model: str = "",
                   params: Mapping[str, str | float] | None = None) -> dict[str, Any]:
        index = _module_index(module)
        current = self.editor.module(index)
        entry = {"module": MODULE_TAGS[index],
                 "on": current.switch if on is None else on, "model": model,
                 "params": [{"name": k, "value": str(v)} for k, v in (params or {}).items()]}
        return self.apply_patch([entry])

    def apply_patch(self, modules: list[dict[str, Any]], name: str = "") -> dict[str, Any]:
        def run() -> dict[str, Any]:
            proposal = tone_ai.parse_proposal(
                {"name": name, "explanation": "", "modules": modules}, self.editor)
            edit = self.editor.state.edit
            if edit is not None:
                self.history.append(list(edit.words))
            tone_ai.apply_proposal(self.editor, proposal)
            return {"applied": proposal.describe(self.editor.catalog),
                    "warnings": proposal.warnings,
                    "note": "live only: the user saves it from the GE150 editor"}

        try:
            return self._locked(run)
        except tone_ai.ToneAIError as exc:
            raise ToolError(str(exc)) from exc

    def undo(self) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            if not self.history:
                return {"undone": False, "reason": "nothing to undo"}
            tone_ai.restore_words(self.editor, self.history.pop())
            return {"undone": True, "remaining": len(self.history)}

        return self._locked(run)

    def select_preset(self, slot: int, discard_changes: bool = False) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            if not 1 <= slot <= PRESET_COUNT:
                raise ToolError(f"slot must be 1..{PRESET_COUNT}")
            if self.editor.state.dirty and not discard_changes:
                raise ToolError("the current preset has unsaved changes: ask the user whether "
                                "to discard them, then call again with discard_changes=true")
            self.editor.select(slot)
            self.history.clear()
            return self._patch()

        return self._locked(run)


def _param_info(param: Any) -> dict[str, Any]:
    if param.kind == "enum":
        return {"name": param.name, "options": list(param.options)}
    if param.kind == "number":
        info: dict[str, Any] = {"name": param.name, "min": param.min, "max": param.max}
        if param.step != 1:
            info["step"] = param.step
        if param.unit:
            info["unit"] = param.unit
        return info
    return {"name": param.name}
