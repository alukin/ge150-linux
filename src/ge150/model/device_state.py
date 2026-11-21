"""Mirror of the pedal state, updated from incoming frames (single source of truth).

``DeviceState.apply(frame)`` understands every device -> host message of plan.md §2.6
and notifies listeners with a :class:`Change`. It never talks to the device itself;
:class:`ge150.services.editor.Editor` sends commands and feeds the answers back here.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from ge150.model.preset import EXP_A, EXP_B, MODULES, PRESET_COUNT, Preset, unpack_words
from ge150.protocol import messages as msg
from ge150.protocol.framing import Frame
from ge150.protocol.opcodes import Op


@dataclass(frozen=True)
class Change:
    """What changed. ``kind`` is one of the ``KIND_*`` constants below."""

    kind: str
    slot: int | None = None
    module: int | None = None


KIND_INFO = "info"
KIND_PRESET = "preset"  # one stored preset (dump, rename, save)
KIND_PRESETS = "presets"  # the whole list was refreshed
KIND_CURRENT = "current"  # edit buffer replaced (0x30 or local select)
KIND_MODULE = "module"  # one module of the edit buffer changed
KIND_EXP = "exp"
KIND_SELECTED = "selected"  # current slot changed
KIND_SYSTEM = "system"
KIND_RHYTHM = "rhythm"
KIND_USER_NAMES = "user_names"
KIND_PAGE = "page"

Listener = Callable[[Change], None]


@dataclass
class DeviceState:
    info: msg.DeviceInfo | None = None
    presets: dict[int, Preset] = field(default_factory=dict)
    current_slot: int | None = None
    page: int | None = None
    edit: Preset | None = None
    system: msg.SystemSettings | None = None
    rhythm: bytes | None = None
    user_names: msg.UserNames | None = None
    _listeners: list[Listener] = field(default_factory=list, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # --- listeners -----------------------------------------------------------

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Listener) -> None:
        self._listeners.remove(listener)

    def _emit(self, change: Change) -> None:
        for listener in list(self._listeners):
            listener(change)

    # --- queries -------------------------------------------------------------

    @property
    def complete(self) -> bool:
        """True once the 200 presets and the edit buffer are known."""
        return len(self.presets) == PRESET_COUNT and self.edit is not None

    @property
    def dirty(self) -> bool:
        """Edit buffer differs from the stored preset of the current slot."""
        with self._lock:
            if self.edit is None or self.current_slot not in self.presets:
                return False
            return self.edit.words != self.presets[self.current_slot].words

    def saved_preset(self, slot: int) -> Preset | None:
        return self.presets.get(slot)

    # --- local edits (the Editor calls these after sending a command) ------------

    def set_edit_words(self, words: list[int], module: int | None = None) -> None:
        with self._lock:
            if self.edit is None:
                return
            self.edit.words[:] = words
        self._emit(Change(KIND_MODULE if module is not None else KIND_CURRENT,
                          self.current_slot, module))

    def store_preset(self, preset: Preset) -> None:
        with self._lock:
            self.presets[preset.slot] = preset.copy()
        self._emit(Change(KIND_PRESET, preset.slot))

    def select_local(self, slot: int) -> None:
        """Assume the pedal loaded the stored preset (until 0x30 confirms)."""
        with self._lock:
            self.current_slot = slot
            stored = self.presets.get(slot)
            if stored is not None:
                self.edit = stored.copy()
        self._emit(Change(KIND_SELECTED, slot))
        self._emit(Change(KIND_CURRENT, slot))

    # --- incoming frames -----------------------------------------------------

    def apply(self, frame: Frame) -> Change | None:
        handler = _HANDLERS.get(frame.opcode)
        if handler is None:
            return None
        with self._lock:
            change = handler(self, frame)
        if change is not None:
            self._emit(change)
        return change

    def _on_info(self, frame: Frame) -> Change:
        self.info = msg.parse_identify(frame)
        return Change(KIND_INFO)

    def _on_dump(self, frame: Frame) -> Change:
        preset = msg.parse_preset_dump(frame)
        self.presets[preset.slot] = preset
        return Change(KIND_PRESETS if preset.slot == PRESET_COUNT else KIND_PRESET, preset.slot)

    def _on_current(self, frame: Frame) -> Change:
        cur = msg.parse_current(frame)
        self.current_slot, self.page = cur.slot, cur.page
        name = self.presets[cur.slot].name if cur.slot in self.presets else ""
        self.edit = Preset(cur.slot, name, cur.words)
        return Change(KIND_CURRENT, cur.slot)

    def _on_module(self, frame: Frame) -> Change | None:
        index, words = msg.parse_module(frame)
        if self.edit is None:
            return None
        self.edit.words[MODULES[index].slice] = words
        return Change(KIND_MODULE, self.current_slot, index)

    def _on_exp(self, frame: Frame) -> Change | None:
        if self.edit is None:
            return None
        part = EXP_A if frame.opcode == Op.EXP_A else EXP_B
        self.edit.words[part] = unpack_words(frame.data, 3)
        return Change(KIND_EXP, self.current_slot)

    def _on_selected(self, frame: Frame) -> Change:
        slot = frame.data[0]
        self.current_slot = slot
        if slot in self.presets:
            self.edit = self.presets[slot].copy()
        return Change(KIND_SELECTED, slot)

    def _on_renamed(self, frame: Frame) -> Change:
        slot, name = msg.parse_preset_renamed(frame)
        if slot in self.presets:
            self.presets[slot].name = name
        if self.edit is not None and slot == self.current_slot:
            self.edit.name = name
        return Change(KIND_PRESET, slot)

    def _on_system_all(self, frame: Frame) -> Change:
        self.system = msg.SystemSettings.from_all(frame)
        return Change(KIND_SYSTEM)

    def _on_system_one(self, frame: Frame) -> Change:
        if self.system is None:
            self.system = msg.SystemSettings({op: bytes(n) for op, n in msg.SYSTEM_SIZES.items()})
        write_op = frame.opcode | 0x80
        size = msg.SYSTEM_SIZES[write_op]
        self.system.blocks[write_op] = bytes(frame.data[:size]).ljust(size, b"\x00")
        return Change(KIND_SYSTEM)

    def _on_rhythm(self, frame: Frame) -> Change:
        self.rhythm = bytes(frame.data[: msg.RHYTHM_SIZE])
        return Change(KIND_RHYTHM)

    def _on_user_names(self, frame: Frame) -> Change:
        self.user_names = msg.parse_user_names(frame)
        return Change(KIND_USER_NAMES)

    def _on_page(self, frame: Frame) -> Change:
        self.page = frame.data[0]
        return Change(KIND_PAGE)


_Handler = Callable[[DeviceState, Frame], "Change | None"]

_HANDLERS: dict[int, _Handler] = {
    Op.DEVICE_INFO: DeviceState._on_info,
    Op.PRESET_DUMP: DeviceState._on_dump,
    Op.CURRENT_PRESET: DeviceState._on_current,
    Op.EXP_A: DeviceState._on_exp,
    Op.EXP_B: DeviceState._on_exp,
    Op.PRESET_SELECTED: DeviceState._on_selected,
    Op.PRESET_RENAMED: DeviceState._on_renamed,
    Op.SYSTEM_ALL: DeviceState._on_system_all,
    Op.SYSTEM_1: DeviceState._on_system_one,
    Op.SYSTEM_2: DeviceState._on_system_one,
    Op.SYSTEM_3: DeviceState._on_system_one,
    Op.SYSTEM_4: DeviceState._on_system_one,
    Op.RHYTHM: DeviceState._on_rhythm,
    Op.USER_NAMES: DeviceState._on_user_names,
    Op.PAGE: DeviceState._on_page,
    **{op: DeviceState._on_module for op in range(Op.MODULE_FX, Op.MODULE_REVERB + 1)},
}
