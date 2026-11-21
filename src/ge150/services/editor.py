"""High level editing operations on top of DeviceSession + DeviceState.

Live edits (module words, EXP) only touch the pedal's edit buffer and are lost when
another preset is selected. ``save``/``rename``/``copy_preset``/user-slot uploads are
persistent: callers (CLI, GUI) must ask the user before calling them.
"""

from __future__ import annotations

import contextlib
import queue
import time
from collections.abc import Callable

from ge150.model.catalog import ModuleInfo, Param, load_catalog
from ge150.model.device_state import DeviceState
from ge150.model.preset import (
    EXP_A,
    EXP_KEYS,
    EXP_OFFSET,
    MODULES,
    PRESET_COUNT,
    ModuleBlock,
    Preset,
    is_valid_name,
)
from ge150.protocol import messages as msg
from ge150.protocol.framing import Frame
from ge150.protocol.opcodes import Op
from ge150.protocol.session import DeviceSession, ResponseTimeout
from ge150.services import reader

#: Page the vendor editor announces (0xB4) before every 0xC3 preset write.
SAVE_PAGE = 5

Progress = Callable[[str, int, int], None]


class EditorError(Exception):
    pass


class Editor:
    def __init__(self, session: DeviceSession, state: DeviceState | None = None) -> None:
        self.session = session
        self.state = state or DeviceState()
        self.catalog: tuple[ModuleInfo, ...] = load_catalog()
        session.add_listener(self.state.apply)

    # --- synchronisation -----------------------------------------------------

    def sync(self, progress: Progress | None = None) -> DeviceState:
        """Read everything the editor needs (same order as the vendor app)."""
        steps = ("identify", "presets", "user names", "rhythm", "current preset")
        report = progress or (lambda *_: None)
        report(steps[0], 0, len(steps))
        reader.identify(self.session)
        report(steps[1], 1, len(steps))
        reader.read_all_presets(self.session)
        report(steps[2], 2, len(steps))
        reader.read_user_names(self.session)
        report(steps[3], 3, len(steps))
        reader.read_rhythm(self.session)
        report(steps[4], 4, len(steps))
        reader.read_current(self.session)
        report("done", len(steps), len(steps))
        return self.state

    def refresh_current(self) -> None:
        reader.read_current(self.session)

    # --- helpers ---------------------------------------------------------------

    def _edit(self) -> Preset:
        if self.state.edit is None:
            raise EditorError("edit buffer unknown: call sync() first")
        return self.state.edit

    def module(self, index: int) -> ModuleBlock:
        return self._edit().module(index)

    def model_params(self, index: int) -> tuple[Param, ...]:
        model = self.catalog[index].model_for_type(self.module(index).type)
        return model.params if model else ()

    def find_param(self, index: int, name: str) -> Param:
        for p in self.model_params(index):
            if p.name.lower() == name.lower():
                return p
        names = ", ".join(p.name for p in self.model_params(index))
        raise EditorError(f"{MODULES[index].name} has no parameter {name!r} (have: {names})")

    def model_label(self, index: int, type_index: int) -> str:
        """``NN:NAME``; user IR/NR slots show the name loaded on the pedal."""
        model = self.catalog[index].model_for_type(type_index)
        if model is None:
            return f"?{type_index}"
        names = self.state.user_names
        if model.user_slot and names is not None:
            # CAB 27-36 = IR slots 0-9, AMP 56-65 = NR slots 0-9 (plan.md §2.8).
            first, bank = (27, names.ir) if MODULES[index].name == "CAB" else (56, names.nr)
            slot = model.number - first
            if 0 <= slot < len(bank) and not msg.is_empty_slot_name(bank[slot]):
                return f"{model.number:02d}:{bank[slot]}"
        return model.label

    @staticmethod
    def module_index(name: str) -> int:
        key = name.upper().replace("_", " ")
        for layout in MODULES:
            if key in (layout.name, layout.name.split("/")[0], layout.name.split()[0]):
                return layout.index
        raise EditorError(f"unknown module {name!r}")

    # --- live edits ------------------------------------------------------------

    def write_module(self, block: ModuleBlock) -> None:
        self.session.send(msg.write_module(block.layout.index, block.words))
        words = list(self._edit().words)
        words[block.layout.slice] = block.words
        self.state.set_edit_words(words, block.layout.index)

    def set_switch(self, index: int, on: bool) -> None:
        block = self.module(index)
        block.switch = on
        self.write_module(block)

    def set_type(self, index: int, type_index: int) -> None:
        count = len(self.catalog[index].models)
        if not 0 <= type_index < count:
            raise EditorError(f"{MODULES[index].name}: model index must be 0..{count - 1}")
        block = self.module(index)
        block.type = type_index
        self.write_module(block)

    def set_param(self, index: int, name: str, value: float | str) -> int:
        """Set a parameter by name and display value; returns the raw word written."""
        param = self.find_param(index, name)
        raw = param.to_raw(value)
        self.set_word(index, param.word, raw)
        return raw

    def set_word(self, index: int, word: int, raw: int) -> None:
        layout = MODULES[index]
        if not 0 <= word < layout.words:
            raise EditorError(f"{layout.name} has words 0..{layout.words - 1}")
        block = self.module(index)
        block.words[word] = raw & 0xFFFF
        self.write_module(block)

    def set_exp(self, key: str, value: int) -> None:
        edit = self._edit()
        position = EXP_OFFSET + EXP_KEYS.index(key)
        words = list(edit.words)
        words[position] = value & 0xFFFF
        frame_a, frame_b = msg.write_exp(words)
        self.session.send(frame_a if EXP_A.start <= position < EXP_A.stop else frame_b)
        self.state.set_edit_words(words)

    def select(self, slot: int, refresh: bool = True) -> None:
        self.session.send(msg.select_preset(slot))
        self.state.select_local(slot)
        if refresh:
            with contextlib.suppress(ResponseTimeout):
                self.refresh_current()

    # --- persistent operations -------------------------------------------------

    def _write_preset(self, preset: Preset, ack_timeout: float = 2.0) -> None:
        """``0xB4 5`` + ``0xC3``, then wait for the ``0x43 [slot]`` acknowledgement
        (verified on hardware; a missing ack is tolerated)."""
        self.session.send(msg.set_page(SAVE_PAGE))
        with self.session.expecting({Op.PRESET_WRITE_ACK}) as acks:
            self.session.send(msg.write_preset(preset), delay=self.session.multipart_delay)
            self.session.flush()
            with contextlib.suppress(queue.Empty):
                acks.get(timeout=ack_timeout)
        self.state.store_preset(preset)

    def save(self, slot: int | None = None, name: str | None = None) -> Preset:
        """Store the edit buffer into ``slot`` (default: current slot)."""
        edit = self._edit()
        target = slot or self.state.current_slot
        if target is None or not 1 <= target <= PRESET_COUNT:
            raise EditorError("no target slot")
        stored = self.state.presets.get(target)
        new_name = name if name is not None else (stored.name if stored else edit.name)
        if not is_valid_name(new_name):
            raise EditorError("names: up to 14 characters, letters, digits, '-' and space")
        preset = Preset(target, new_name, list(edit.words))
        self._write_preset(preset)
        if target == self.state.current_slot and self.state.edit is not None:
            self.state.edit.name = new_name
        return preset

    def rename(self, slot: int, name: str) -> None:
        if not is_valid_name(name):
            raise EditorError("names: up to 14 characters, letters, digits, '-' and space")
        self.session.send(msg.rename_preset(slot, name))
        self.session.flush()
        stored = self.state.presets.get(slot)
        if stored is not None:
            renamed = stored.copy()
            renamed.name = name
            self.state.store_preset(renamed)

    def copy_preset(self, source: int, target: int) -> Preset:
        stored = self.state.presets.get(source)
        if stored is None:
            raise EditorError(f"preset {source} not loaded")
        preset = stored.copy(target)
        self._write_preset(preset)
        return preset

    def copy_preset_data(self, preset: Preset) -> None:
        """Store an arbitrary preset (e.g. imported from a file) into ``preset.slot``."""
        if not is_valid_name(preset.name):
            raise EditorError("invalid preset name")
        self._write_preset(preset)

    def set_system(self, op: Op, data: bytes) -> None:
        self.session.send(msg.write_system(op, data))
        self.state.apply(Frame(op & 0x7F, data))

    def set_rhythm(self, data: bytes) -> None:
        self.session.send(msg.write_rhythm(data))
        self.state.apply(Frame(Op.RHYTHM, data))

    # --- user IR / NR slots ----------------------------------------------------

    def upload_user_slot(self, op: Op, slot_index: int, name: str, payload: bytes,
                         timeout: float = 3.0) -> None:
        frames = msg.user_slot_frames(op, slot_index, name, payload)
        self._send_multipart_and_wait(frames, timeout)

    def delete_user_slot(self, op: Op, slot_index: int, timeout: float = 3.0) -> None:
        self._send_multipart_and_wait(msg.delete_user_slot_frames(op, slot_index), timeout)

    def _send_multipart_and_wait(self, frames: list[Frame], timeout: float) -> None:
        """Send every part, then wait for the acknowledgement of the last one.

        Verified on hardware: the pedal answers every part with the same opcode and the
        part number (``B5 00..04`` for an IR, ``B7 00..05`` for an NR); a timeout is
        tolerated.
        """
        last = frames[-1].data[0]
        with self.session.expecting({frames[-1].opcode}) as acks:
            self.session.send_multipart(frames)
            deadline = time.monotonic() + timeout
            while (remaining := deadline - time.monotonic()) > 0:
                try:
                    if acks.get(timeout=remaining).data[:1] == bytes([last]):
                        break
                except queue.Empty:
                    break
        reader.read_user_names(self.session)

    def read_ir_backup(self, timeout: float = 3.0) -> list[msg.BackupChunk]:
        """0xC4 dump: one chunk per used IR slot (read-only)."""
        def complete(frames: list[Frame]) -> bool:
            return bool(frames) and len(frames) >= frames[0].data[1] + 1

        frames = self.session.collect(msg.read(Op.READ_BACKUP), Op.BACKUP_CHUNK,
                                      count=msg.USER_SLOTS + 1, timeout=timeout, until=complete)
        return [c for c in map(msg.parse_backup_chunk, frames) if c.index > 0]
