"""Change several stored presets at once (the AI or the «Asistente» tab's form).

Nothing is written when planning: :func:`plan_edits` turns per-preset changes (the same
module entries as ``apply_patch``) into before/after words that the user reviews; only
:func:`apply` writes the presets the user kept. The preset loaded on the pedal is refused
while it has unsaved changes (writing it would make them unreachable), and is selected
again after being rewritten, so the pedal plays the new version. :func:`restore` writes the
previous versions back. :func:`preview` loads a planned preset on the pedal (live, not
saved) so the user can hear it before applying.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ge150.model.gear import MODULE_TAGS
from ge150.model.preset import MODULES, Preset
from ge150.services import tone_ai
from ge150.services.editor import Editor

DIRTY = "es el preset cargado y tiene cambios sin guardar: guárdalos o descártalos primero"


@dataclass
class PresetEdit:
    slot: int
    name: str
    before: list[int]
    after: list[int]
    warnings: list[str] = field(default_factory=list)
    blocked: str = ""  # why it cannot be written

    @property
    def changed(self) -> bool:
        return self.before != self.after


def plan_edits(editor: Editor, specs: Sequence[Mapping[str, Any]],
               bases: Mapping[int, Sequence[int]] | None = None) -> list[PresetEdit]:
    """``specs``: ``[{"slot": 22, "modules": [{"module", "on"?, "model"?, "params"}]}]``.

    ``bases``: words already planned for a slot (a second change adds to the first)."""
    state = editor.state
    edits: list[PresetEdit] = []
    for spec in specs:
        try:
            slot = int(spec.get("slot", 0))
        except (TypeError, ValueError):
            slot = 0
        stored = state.presets.get(slot)
        if stored is None:
            edits.append(PresetEdit(slot, "", [], [], blocked=f"no existe el preset {slot}"))
            continue
        before = list(stored.words)
        start = list(bases[slot]) if bases and slot in bases else before
        base = Preset(slot, stored.name, list(start))
        try:
            proposal = tone_ai.parse_proposal({"modules": list(spec.get("modules") or [])},
                                              editor, base)
        except tone_ai.ToneAIError as exc:
            edits.append(PresetEdit(slot, stored.name, before, start, blocked=str(exc)))
            continue
        after = tone_ai.apply_to_words(start, proposal, editor.catalog)
        # The loaded preset's unsaved changes are checked when applying (a preview of a
        # pending proposal also counts as "unsaved" here).
        edits.append(PresetEdit(slot, stored.name, before, after, proposal.warnings))
    return edits


def diff(editor: Editor, before: Sequence[int], after: Sequence[int]
         ) -> list[tuple[str, str, str]]:
    """``(module, before, after)`` for every module that changes, in display terms."""
    old_preset, new_preset = Preset(1, "", list(before)), Preset(1, "", list(after))
    rows = []
    for index in range(len(MODULES)):
        old, new = old_preset.module(index), new_preset.module(index)
        if old.words == new.words:
            continue
        was, now = [], []
        if old.switch != new.switch:
            was.append("ON" if old.switch else "OFF")
            now.append("ON" if new.switch else "OFF")
        if old.type != new.type:
            was.append(editor.model_display(index, old.type))
            now.append(editor.model_display(index, new.type))
        model = editor.catalog[index].model_for_type(new.type)
        same_model = old.type == new.type
        for param in model.params if model else ():
            if same_model and old.words[param.word] == new.words[param.word]:
                continue
            if same_model:
                was.append(f"{param.name} {param.format(old.words[param.word])}")
            now.append(f"{param.name} {param.format(new.words[param.word])}")
        rows.append((MODULE_TAGS[index], " · ".join(was) or "—", " · ".join(now) or "—"))
    return rows


def describe(editor: Editor, edits: Sequence[PresetEdit]) -> list[dict[str, Any]]:
    """JSON-able summary (what the AI sees after proposing)."""
    return [{"slot": e.slot, "name": e.name,
             "changes": [f"{m}: {a} -> {b}" for m, a, b in diff(editor, e.before, e.after)],
             "warnings": e.warnings, **({"blocked": e.blocked} if e.blocked else {})}
            for e in edits]


def own_changes(editor: Editor, slot: int, planned: Sequence[int]) -> bool:
    """The loaded preset has unsaved changes of the user's (not just a preview of
    ``planned``, the words this edit is heard with)."""
    state = editor.state
    if slot != state.current_slot or not state.dirty or state.edit is None:
        return False
    return list(state.edit.words) != list(planned)


def preview(editor: Editor, edit: PresetEdit, after: bool = True) -> None:
    """Load the edit's preset on the pedal and play its planned (or stored) version, live:
    nothing is stored."""
    if editor.state.current_slot != edit.slot:
        editor.select(edit.slot)
    tone_ai.restore_words(editor, edit.after if after else edit.before)


@dataclass
class Applied:
    previous: list[Preset]  # what to write back to undo
    skipped: list[tuple[int, str]]


def apply(editor: Editor, edits: Sequence[PresetEdit]) -> Applied:
    """Write the edits that are not blocked; returns the previous versions."""
    state = editor.state
    previous: list[Preset] = []
    skipped: list[tuple[int, str]] = []
    reload = False
    for edit in edits:
        stored = state.presets.get(edit.slot)
        if edit.blocked or stored is None or not edit.changed:
            skipped.append((edit.slot, edit.blocked or "sin cambios"))
            continue
        if own_changes(editor, edit.slot, edit.after):  # changed since the plan
            skipped.append((edit.slot, DIRTY))
            continue
        if stored.words != edit.before:
            skipped.append((edit.slot, "el preset cambió después de la propuesta"))
            continue
        previous.append(stored.copy())
        editor.copy_preset_data(Preset(edit.slot, stored.name, list(edit.after)))
        reload = reload or edit.slot == state.current_slot
    if reload and state.current_slot is not None:
        editor.select(state.current_slot)
    return Applied(previous, skipped)


def restore(editor: Editor, previous: Sequence[Preset]) -> list[int]:
    """Write back the versions saved by :func:`apply`; returns the slots restored."""
    state = editor.state
    reload = False
    clean = not state.dirty
    for preset in previous:
        editor.copy_preset_data(preset.copy())
        reload = reload or preset.slot == state.current_slot
    if reload and clean and state.current_slot is not None:
        editor.select(state.current_slot)
    return [p.slot for p in previous]
