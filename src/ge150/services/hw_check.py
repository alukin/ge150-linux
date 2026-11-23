"""Automatic check of the editor's writes against the real pedal (``ge150ctl hw-check``).

Each step writes through the same services the editor uses and then asks the pedal what it
really holds (the ``0xA0`` preset dump and the ``0x30`` current buffer), so nothing is taken
from the editor's own state. Only the three test slots are written; a full backup is made
first and, whatever happens, the three slots and the loaded preset are put back and the
whole pedal is compared with how it was. Covers steps 1-4 and 9 of
``docs/verificacion-hardware.md``; listening and looking at the pedal's screen stay manual.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ge150.formats import mbf
from ge150.model.gear import MODULE_TAGS
from ge150.model.preset import PRESET_COUNT, PRESET_WORDS, Preset
from ge150.protocol import messages as msg
from ge150.services import auto_backup, bulk_edit, reader
from ge150.services.editor import Editor, EditorError

DELAY = MODULE_TAGS.index("DELAY")
#: Modules tried, in order, for a numeric change (the last ones of the chain first).
NUMERIC_ORDER = ("REVERB", "DELAY", "MOD", "EQ", "NS", "AMP", "DS", "FX")
#: Modules tried for an on/off change that is easy to hear.
SWITCH_ORDER = ("DS", "MOD", "DELAY", "REVERB", "FX")


@dataclass
class Check:
    step: str
    name: str
    ok: bool | None  # None = information, not a pass/fail
    detail: str
    seconds: float = 0.0


@dataclass
class Report:
    firmware: str = ""
    slots: tuple[int, ...] = ()
    names: dict[int, str] = field(default_factory=dict)
    backup: Path | None = None
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.ok is not False for c in self.checks)

    def markdown(self) -> str:
        lines = [f"# Verificación automática con la pedalera ({time.strftime('%Y-%m-%d %H:%M')})",
                 "", f"- Firmware: {self.firmware}",
                 "- Presets de prueba: " + ", ".join(f"{s:03d} «{self.names.get(s, '')}»"
                                                     for s in self.slots),
                 f"- Backup previo: {auto_backup.short(self.backup) if self.backup else '—'}",
                 f"- Resultado: **{'TODO OK' if self.passed else 'HAY FALLAS'}**", "",
                 "| Paso | Comprobación | Resultado | Detalle | Tiempo |",
                 "|---|---|---|---|---|"]
        for c in self.checks:
            mark = "OK" if c.ok else ("FALLA" if c.ok is False else "info")
            when = f"{c.seconds:.1f} s" if c.seconds else ""
            lines.append(f"| {c.step} | {c.name} | {mark} | {c.detail} | {when} |")
        return "\n".join(lines) + "\n"


class HardwareCheck:
    """``slots``: three presets that may be written (they are restored at the end)."""

    def __init__(self, editor: Editor, slots: tuple[int, int, int],
                 log: Callable[[str], None] = print, tap_seconds: float = 0.0,
                 backups: bool = True, only_tap: bool = False) -> None:
        if len(set(slots)) != 3 or not all(1 <= s <= PRESET_COUNT for s in slots):
            raise ValueError(f"need three different presets 1..{PRESET_COUNT}")
        self.editor, self.slots, self.log = editor, slots, log
        self.tap_seconds, self.backups, self.only_tap = tap_seconds, backups, only_tap
        self.report = Report(slots=slots)
        self.originals: dict[int, Preset] = {}
        self.start_slot = 0

    # --- what the pedal really holds -----------------------------------------------------

    def dump(self) -> dict[int, Preset]:
        presets, _ = reader.read_all_presets(self.editor.session)
        if len(presets) != PRESET_COUNT:
            raise EditorError(f"the pedal sent {len(presets)} presets, expected {PRESET_COUNT}")
        return {slot: p.copy() for slot, p in presets.items()}

    def current(self) -> msg.CurrentPreset:
        return reader.read_current(self.editor.session)

    def _add(self, step: str, name: str, ok: bool | None, detail: str,
             seconds: float = 0.0) -> bool:
        self.report.checks.append(Check(step, name, ok, detail, seconds))
        mark = "OK   " if ok else ("FALLA" if ok is False else "info ")
        self.log(f"  [{mark}] {step} {name}: {detail}")
        return bool(ok)

    # --- the run ----------------------------------------------------------------------------

    def run(self) -> Report:
        editor = self.editor
        self.log("Leyendo la pedalera…")
        editor.sync()
        info = editor.state.info
        self.report.firmware = f"{info.name} {info.firmware}" if info else "?"
        self.originals = self.dump()
        self.report.names = {s: self.originals[s].name for s in self.slots}
        current = self.current()
        self.start_slot = current.slot
        stored = self.originals.get(current.slot)
        if stored is not None and current.words[:PRESET_WORDS] != stored.words:
            raise EditorError(f"the loaded preset ({current.slot}) has unsaved changes on the "
                              "pedal: save or discard them first")
        try:
            if not self.only_tap:
                self._step_backup()
                self._step_bulk()
                self._step_loaded()
                self._step_preview()
            if self.tap_seconds > 0:
                self._step_tap()
        finally:
            self._restore()
        return self.report

    def _step_backup(self) -> None:
        if not self.backups:
            self._add("1", "Backup automático", None, "omitido (--no-backup)")
            return
        start = time.monotonic()
        path = auto_backup.save_before(self.editor, "hw-check")
        took = time.monotonic() - start
        self.report.backup = path
        data = mbf.load(path)
        same = (len(data.presets) == PRESET_COUNT
                and all(p.words == self.originals[p.slot].words for p in data.presets))
        self._add("1", "Backup automático", same,
                  f"{auto_backup.short(path)}: {len(data.presets)} presets, {len(data.irs)} IR"
                  + ("" if same else "; NO coincide con la pedalera"), took)

    def _step_bulk(self) -> None:
        a, b, c = self.slots
        editor = self.editor
        editor.select(c)
        edits = bulk_edit.plan_edits(editor, [self._numeric_change(a), self._numeric_change(b)])
        start = time.monotonic()
        applied = bulk_edit.apply(editor, edits)
        took = time.monotonic() - start
        after = self.dump()
        written = all(after[e.slot].words == e.after for e in edits)
        others = all(after[s].words == self.originals[s].words
                     for s in after if s not in (a, b))
        what = ", ".join(row for e in edits for row in self._rows(e))
        self._add("2", "Edición masiva: guardado", written and not applied.skipped,
                  f"{a:03d} y {b:03d} tienen el valor nuevo ({what})"
                  if written else "la pedalera no guardó lo esperado", took)
        self._add("2", "Edición masiva: el resto intacto", others,
                  "los otros 198 presets no cambiaron" if others else "cambió otro preset")
        loaded = self.current().slot
        self._add("2", "Edición masiva: no cambia de preset", loaded == c,
                  f"la pedalera sigue en {c:03d}" if loaded == c else f"pasó a {loaded:03d}")
        bulk_edit.restore(editor, applied.previous)
        back = self.dump()
        undone = all(back[s].words == self.originals[s].words for s in (a, b))
        self._add("2", "Deshacer la edición", undone,
                  "los dos presets volvieron a como estaban" if undone else "no volvieron")

    def _step_loaded(self) -> None:
        a = self.slots[0]
        editor = self.editor
        editor.select(a)
        loaded = self.current()
        self._add("3", "Seleccionar carga lo guardado",
                  loaded.slot == a and loaded.words[:PRESET_WORDS] == self.originals[a].words,
                  f"la pedalera cargó {loaded.slot:03d}")
        # Does the pedal reload the preset it is playing when that slot is written?
        edit = bulk_edit.plan_edits(editor, [self._switch_change(a)])[0]
        editor.copy_preset_data(Preset(a, self.originals[a].name, list(edit.after)))
        raw = self.current()
        reloads = raw.words[:PRESET_WORDS] == edit.after
        self._add("3", "La pedalera recarga sola al escribir el preset que suena", None,
                  "sí: suena la versión nueva sin volver a seleccionarlo" if reloads else
                  "no: sigue sonando la versión anterior hasta volver a seleccionarlo (el "
                  "editor lo vuelve a seleccionar)")
        editor.copy_preset_data(self.originals[a].copy())
        editor.select(a)
        # What the editor does: write, then select the same slot again.
        start = time.monotonic()
        applied = bulk_edit.apply(editor, [edit])
        took = time.monotonic() - start
        now = self.current()
        plays_new = now.slot == a and now.words[:PRESET_WORDS] == edit.after
        stored = self.dump()[a].words == edit.after
        self._add("3", "Aplicar al preset que suena", plays_new and stored and not applied.skipped,
                  f"suena y queda guardada la versión nueva ({', '.join(self._rows(edit))})"
                  if plays_new and stored else
                  ("guardado, pero la pedalera sigue sonando la versión anterior" if stored
                   else "no se guardó"), took)
        bulk_edit.restore(editor, applied.previous)
        back = self.current()
        self._add("3", "Deshacer en el preset que suena",
                  back.words[:PRESET_WORDS] == self.originals[a].words,
                  "vuelve a sonar la versión original")

    def _step_preview(self) -> None:
        _, b, c = self.slots
        editor = self.editor
        editor.select(c)
        edit = bulk_edit.plan_edits(editor, [self._switch_change(b)])[0]
        bulk_edit.preview(editor, edit, True)
        after = self.current()
        self._add("4", "Escuchar: cambia al preset propuesto",
                  after.slot == b and after.words[:PRESET_WORDS] == edit.after,
                  f"la pedalera pasó de {c:03d} a {after.slot:03d} con la propuesta "
                  f"({', '.join(self._rows(edit))})")
        bulk_edit.preview(editor, edit, False)
        before = self.current()
        self._add("4", "Escuchar: «Antes»", before.words[:PRESET_WORDS] == edit.before,
                  "suena como está guardado")
        bulk_edit.preview(editor, edit, True)
        again = self.current()
        self._add("4", "Escuchar: «Después»", again.words[:PRESET_WORDS] == edit.after,
                  "vuelve a sonar la propuesta")
        editor.select(b)  # «Descartar»
        dropped = self.current()
        untouched = self.dump()[b].words == self.originals[b].words
        self._add("4", "Descartar", dropped.words[:PRESET_WORDS] == self.originals[b].words
                  and untouched, "vuelve a lo guardado y nunca se escribió en la memoria"
                  if untouched else "¡la escucha escribió en la memoria!")

    def _step_tap(self) -> None:
        editor = self.editor
        block = editor.module(DELAY)
        model = editor.catalog[DELAY].model_for_type(block.type)
        time_param = next((p for p in (model.params if model else ())
                           if p.name.upper().startswith("TIME")), None)
        if time_param is None:
            self._add("9", "TAP", None, "el modelo de delay no tiene TIME")
            return
        if not block.switch:
            editor.set_switch(DELAY, True)  # live only; undone when the preset is selected again
        before = editor.module(DELAY).words[time_param.word]
        self.log(f"  >>> Pisa TAP en la pedalera varias veces, con otro ritmo, durante "
                 f"{self.tap_seconds:.0f} s…")
        deadline = time.monotonic() + self.tap_seconds
        changed = None
        while time.monotonic() < deadline:
            now = editor.module(DELAY).words[time_param.word]
            if now != before:
                changed = now
                break
            time.sleep(0.1)
        if changed is None:  # maybe the pedal changed it without telling: ask it
            current = self.current().words
            block_words = Preset(0, "", current[:PRESET_WORDS]).module(DELAY).words
            asked = block_words[time_param.word]
            self._add("9", "TAP avisa el nuevo tiempo", False,
                      "no llegó ningún aviso de la pedalera" + (
                          f"; al preguntarle, el TIME sí cambió a "
                          f"{time_param.format(asked)} (el editor lo vería recién con F5)"
                          if asked != before else "; tampoco cambió el TIME guardado en el "
                          "preset cargado (¿se pisó TAP?)"))
            return
        self._add("9", "TAP avisa el nuevo tiempo", True,
                  f"TIME pasó de {time_param.format(before)} a {time_param.format(changed)} "
                  "al instante")

    # --- putting everything back -------------------------------------------------------------

    def _restore(self) -> None:
        editor = self.editor
        try:
            now = self.dump()
            for slot in self.slots:
                if now[slot].words != self.originals[slot].words:
                    editor.copy_preset_data(self.originals[slot].copy())
            editor.select(self.start_slot)
            final = self.dump()
            changed = [s for s in final if final[s].words != self.originals[s].words
                       or final[s].name != self.originals[s].name]
            loaded = self.current()
            ok = not changed and loaded.slot == self.start_slot
            self._add("10", "Todo como estaba", ok,
                      f"los 200 presets son idénticos y la pedalera volvió a "
                      f"{self.start_slot:03d}" if ok else
                      f"distintos: {changed} (restaura el backup)")
        except Exception as exc:  # report it; the backup is there
            self._add("10", "Todo como estaba", False, f"no se pudo comprobar: {exc}")

    # --- test changes ---------------------------------------------------------------------------

    def _numeric_change(self, slot: int) -> dict[str, Any]:
        preset = self.originals[slot]
        for tag in NUMERIC_ORDER:
            index = MODULE_TAGS.index(tag)
            block = preset.module(index)
            model = self.editor.catalog[index].model_for_type(block.type)
            for param in model.params if model else ():
                if param.kind != "number" or param.max <= param.min:
                    continue
                old = param.from_raw(block.words[param.word])
                middle = round((param.min + param.max) / 2 / param.step) * param.step
                value = param.min if old == middle else middle
                return {"slot": slot, "modules": [{"module": tag, "params": [
                    {"name": param.name, "value": str(value)}]}]}
        raise EditorError(f"preset {slot} has no numeric parameter to change")

    def _switch_change(self, slot: int) -> dict[str, Any]:
        preset = self.originals[slot]
        tag = SWITCH_ORDER[0]
        on = preset.module(MODULE_TAGS.index(tag)).switch
        return {"slot": slot, "modules": [{"module": tag, "on": not on}]}

    def _rows(self, edit: bulk_edit.PresetEdit) -> list[str]:
        return [f"{m} {b} → {a}" for m, b, a in bulk_edit.diff(self.editor, edit.before,
                                                              edit.after)]


def save_report(report: Report, directory: Path | None = None) -> Path:
    base = directory or auto_backup.backup_dir().parent / "hw-check"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"hw-check-{time.strftime('%Y%m%d-%H%M%S')}.md"
    path.write_text(report.markdown())
    return path

