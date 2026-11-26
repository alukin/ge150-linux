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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ge150.model.gear import MODULE_TAGS
from ge150.model.preset import MODULES, NAME_LEN, Preset, is_valid_name
from ge150.services import tone_ai
from ge150.services.editor import Editor, EditorError, Progress

DIRTY = "es el preset cargado y tiene cambios sin guardar: guárdalos o descártalos primero"


@dataclass
class PresetEdit:
    slot: int
    name: str
    before: list[int]
    after: list[int]
    warnings: list[str] = field(default_factory=list)
    blocked: str = ""  # why it cannot be written
    new_name: str = ""  # "" keeps ``name``
    source: int = 0  # the preset whose stored content this one starts from (move/reorder)
    stacked: bool = False  # planned on top of a pending change of the same preset

    @property
    def renamed(self) -> bool:
        return bool(self.new_name) and self.new_name != self.name

    @property
    def final_name(self) -> str:
        return self.new_name or self.name

    @property
    def changed(self) -> bool:
        return self.before != self.after or self.renamed


def plan_edits(editor: Editor, specs: Sequence[Mapping[str, Any]],
               bases: Mapping[int, Sequence[int]] | None = None) -> list[PresetEdit]:
    """``specs``: ``[{"slot": 22, "name"?, "copy_from"?, "modules": [{"module", "on"?,
    "model"?, "params"}]}]``.

    ``name`` renames the preset. ``copy_from`` starts from another preset's stored content
    (and name, unless ``name`` is given): that is how presets are moved or reordered, e.g.
    two specs with crossed ``copy_from`` swap them (every source is read as stored now).
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
        stacked = bases is not None and slot in bases
        start = list(bases[slot]) if bases and slot in bases else before
        new_name = str(spec.get("name") or "").strip()
        try:
            source = int(spec.get("copy_from") or 0)
        except (TypeError, ValueError):
            source = -1
        blocked = ""
        if source and source != slot:
            origin = state.presets.get(source)
            if origin is None:
                blocked = f"no existe el preset {spec.get('copy_from')!r} para copiar"
            else:
                start = list(origin.words)
                new_name = new_name or origin.name
        else:
            source = 0
        if new_name and not is_valid_name(new_name):
            blocked = blocked or (f"nombre no válido {new_name!r}: hasta {NAME_LEN} "
                                  "caracteres, letras, números, '-' y espacio")
        edit = PresetEdit(slot, stored.name, before, start, new_name=new_name, source=source,
                          stacked=stacked, blocked=blocked)
        modules = list(spec.get("modules") or [])
        if not modules and not (new_name or source):
            blocked = blocked or "no hay cambios de efectos, nombre ni contenido"
        if modules and not blocked:
            try:
                proposal = tone_ai.parse_proposal({"modules": modules}, editor,
                                                  Preset(slot, stored.name, list(start)))
            except tone_ai.ToneAIError as exc:
                edit.blocked = str(exc)
            else:
                edit.after = tone_ai.apply_to_words(start, proposal, editor.catalog)
                edit.warnings = proposal.warnings
        # The loaded preset's unsaved changes are checked when applying (a preview of a
        # pending proposal also counts as "unsaved" here).
        edits.append(edit)
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


def rows(editor: Editor, edit: PresetEdit) -> list[tuple[str, str, str]]:
    """What the review shows for one preset: name, copied content, then :func:`diff`."""
    result = []
    if edit.renamed:
        result.append(("NOMBRE", edit.name, edit.new_name))
    if edit.source:
        origin = editor.state.presets.get(edit.source)
        result.append(("CONTENIDO", "el suyo",
                       f"el del {edit.source:03d} «{origin.name if origin else '?'}»"))
    return result + diff(editor, edit.before, edit.after)


def describe(editor: Editor, edits: Sequence[PresetEdit]) -> list[dict[str, Any]]:
    """JSON-able summary (what the AI sees after proposing)."""
    return [{"slot": e.slot, "name": e.name,
             **({"new_name": e.new_name} if e.renamed else {}),
             **({"copy_from": e.source} if e.source else {}),
             "changes": [f"{m}: {a} -> {b}" for m, a, b in rows(editor, e)],
             "warnings": e.warnings, **({"blocked": e.blocked} if e.blocked else {})}
            for e in edits]


CHANGED = "el preset cambió después de la propuesta"


def to_dict(edit: PresetEdit) -> dict[str, Any]:
    """JSON-able, to keep a pending edit with its conversation."""
    return {"slot": edit.slot, "name": edit.name, "before": list(edit.before),
            "after": list(edit.after), "warnings": list(edit.warnings),
            "blocked": edit.blocked, "new_name": edit.new_name, "source": edit.source}


def from_dict(editor: Editor, data: Mapping[str, Any]) -> PresetEdit | None:
    """A kept edit checked against the pedal now: None if it is already applied (or
    unreadable), blocked if the preset changed since."""
    try:
        edit = PresetEdit(int(data["slot"]), str(data["name"]),
                          [int(w) for w in data["before"]], [int(w) for w in data["after"]],
                          [str(w) for w in data.get("warnings") or []],
                          str(data.get("blocked") or ""), str(data.get("new_name") or ""),
                          int(data.get("source") or 0))
    except (KeyError, TypeError, ValueError):
        return None
    stored = editor.state.presets.get(edit.slot)
    if stored is None:
        edit.blocked = edit.blocked or f"no existe el preset {edit.slot}"
    elif stored.words == edit.after and stored.name == edit.final_name:
        return None  # applied after the conversation was saved
    elif stored.words != edit.before or stored.name != edit.name:
        edit.blocked = edit.blocked or CHANGED
    return edit


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


#: Called once before the first write (e.g. a full backup); returns where it was saved.
Backup = Callable[[], Path]


class BackupError(RuntimeError):
    """The backup before writing failed: nothing was written."""


def _run_backup(backup: Backup) -> Path:
    try:
        return backup()
    except Exception as exc:
        raise BackupError(f"no se pudo hacer el backup automático ({exc}); no se escribió "
                          "nada en la pedalera") from exc


@dataclass
class Applied:
    previous: list[Preset]  # what to write back to undo
    skipped: list[tuple[int, str]]
    backup: Path | None = None


def apply(editor: Editor, edits: Sequence[PresetEdit], backup: Backup | None = None,
          progress: Progress | None = None) -> Applied:
    """Write the edits that are not blocked; returns the previous versions. ``backup`` runs
    before anything is written (if it raises, nothing is). ``progress`` gets
    ``("012", i, total)`` before writing each preset."""
    state = editor.state
    previous: list[Preset] = []
    skipped: list[tuple[int, str]] = []
    reload = False
    saved = _run_backup(backup) if backup is not None and any(
        e.changed and not e.blocked for e in edits) else None
    for done, edit in enumerate(edits):
        if progress is not None:
            progress(f"{edit.slot:03d}", done, len(edits))
        stored = state.presets.get(edit.slot)
        if edit.blocked or stored is None or not edit.changed:
            skipped.append((edit.slot, edit.blocked or "sin cambios"))
            continue
        if own_changes(editor, edit.slot, edit.after):  # changed since the plan
            skipped.append((edit.slot, DIRTY))
            continue
        if stored.words != edit.before or stored.name != edit.name:
            skipped.append((edit.slot, CHANGED))
            continue
        previous.append(stored.copy())
        editor.copy_preset_data(Preset(edit.slot, edit.final_name, list(edit.after)))
        reload = reload or edit.slot == state.current_slot
    if reload and state.current_slot is not None:
        editor.select(state.current_slot)
    return Applied(previous, skipped, saved)


def move_specs(source: int, target: int) -> list[dict[str, int]]:
    """Specs that move preset ``source`` to ``target`` and shift the ones in between by one
    place, as when dragging it in a list: every preset in that range is rewritten."""
    if source == target:
        return []
    step = 1 if source < target else -1
    specs = [{"slot": slot, "copy_from": slot + step} for slot in range(source, target, step)]
    specs.append({"slot": target, "copy_from": source})
    return sorted(specs, key=lambda spec: spec["slot"])


def moved_slot(slot: int, source: int, target: int) -> int:
    """Where the preset now at ``slot`` ends up after moving ``source`` to ``target``."""
    if slot == source:
        return target
    low, high = sorted((source, target))
    if not low <= slot <= high:
        return slot
    return slot - 1 if source < target else slot + 1


def move(editor: Editor, source: int, target: int, backup: Backup | None = None,
         progress: Progress | None = None) -> Applied:
    """Move preset ``source`` to ``target`` (see :func:`move_specs`). The preset loaded on
    the pedal stays loaded at its new place. Refused while it is in the range and has unsaved
    changes: skipping it would leave the order half done."""
    state = editor.state
    current = state.current_slot
    low, high = sorted((source, target))
    if current is not None and low <= current <= high and state.dirty:
        raise EditorError(f"el preset {current:03d} {DIRTY}")
    edits = plan_edits(editor, move_specs(source, target))
    blocked = [f"{e.slot:03d}: {e.blocked}" for e in edits if e.blocked]
    if blocked:
        raise EditorError("no se puede mover: " + "; ".join(blocked))
    applied = apply(editor, edits, backup, progress)
    if current is not None and (new := moved_slot(current, source, target)) != current:
        editor.select(new)
    return applied


def restore(editor: Editor, previous: Sequence[Preset],
            backup: Backup | None = None) -> list[int]:
    """Write back the versions saved by :func:`apply`; returns the slots restored."""
    state = editor.state
    if backup is not None and previous:
        _run_backup(backup)
    reload = False
    clean = not state.dirty
    for preset in previous:
        editor.copy_preset_data(preset.copy())
        reload = reload or preset.slot == state.current_slot
    if reload and clean and state.current_slot is not None:
        editor.select(state.current_slot)
    return [p.slot for p in previous]
