"""Stateful fake GE150 that answers frames like the real pedal is believed to.

Behaviour comes from the vendor editor (plan.md §2). Where the real answer is
unknown the simulator stays silent; such cases are marked "[?]" below. Keep this
file in sync with plan.md when hardware captures confirm or refute something.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ge150.model.catalog import load_catalog
from ge150.model.preset import (
    EXP_A,
    EXP_B,
    MODULES,
    NAME_LEN,
    PRESET_COUNT,
    Preset,
    decode_name,
    encode_name,
    pack_words,
    unpack_words,
)
from ge150.protocol import messages as msg
from ge150.protocol.framing import Frame
from ge150.protocol.opcodes import Op


def _default_preset(slot: int) -> Preset:
    """A valid preset: factory model per module, every parameter at mid range."""
    catalog = load_catalog()
    words: list[int] = []
    for layout in MODULES:
        factory = [m for m in catalog[layout.index].models if not m.user_slot]
        type_index = (slot + layout.index) % len(factory)
        block = [slot % 2, type_index] + [0] * (layout.words - 2)
        for p in factory[type_index].params:
            block[p.word] = p.raw_max // 2 if p.kind != "number" or p.min < 0 else \
                p.to_raw((p.min + p.max) // 2)
        words.extend(block)
    words.extend([0, 0, 0, 0, 0, 100])  # EXP: MODULE_CTRL .. VOL_MAX
    return Preset(slot, f"PRESET {slot:03d}", words)


@dataclass
class _Upload:
    slot: int
    name: str = ""
    chunks: dict[int, bytes] = field(default_factory=dict)


@dataclass
class FakeGE150:
    name: str = "MOOER_GE150"
    firmware: str = "V1.3.8"
    presets: dict[int, Preset] = field(
        default_factory=lambda: {s: _default_preset(s) for s in range(1, PRESET_COUNT + 1)}
    )
    current_slot: int = 1
    page: int = 0
    system: dict[int, bytes] = field(
        default_factory=lambda: {op: bytes(size) for op, size in msg.SYSTEM_SIZES.items()}
    )
    rhythm: bytes = bytes([120, 0, 0, 0, 0, 0])
    nr_names: list[str] = field(default_factory=lambda: ["EMPTY"] * msg.USER_SLOTS)
    ir_names: list[str] = field(default_factory=lambda: ["EMPTY"] * msg.USER_SLOTS)
    user_data: dict[tuple[int, int], bytes] = field(default_factory=dict)
    received: list[Frame] = field(default_factory=list)
    unhandled: list[Frame] = field(default_factory=list)
    _edit: Preset | None = None
    _uploads: dict[int, _Upload] = field(default_factory=dict)

    # --- state helpers -------------------------------------------------------

    @property
    def edit_buffer(self) -> Preset:
        if self._edit is None:
            self._edit = self.presets[self.current_slot].copy()
        return self._edit

    def footswitch(self, slot: int) -> list[Frame]:
        """Simulate selecting a preset on the pedal: the device notifies 0x16."""
        self._select(slot)
        return [Frame(Op.PRESET_SELECTED, bytes([slot]))]

    def turn_knob(self, module: int, param: int, raw: int) -> list[Frame]:
        """Simulate a knob change on the pedal: the device sends the module block."""
        block = self.edit_buffer.module(module)
        block.set_param(param, raw)
        self.edit_buffer.set_module(block)
        return [Frame(MODULES[module].notify_op, pack_words(block.words))]

    def _select(self, slot: int) -> None:
        self.current_slot = slot
        self._edit = self.presets[slot].copy()

    # --- frame handling ------------------------------------------------------

    def handle(self, frame: Frame) -> list[Frame]:
        self.received.append(frame)
        op, d = frame.opcode, frame.data
        handler = _HANDLERS.get(op)
        if handler is not None:
            return handler(self, d)
        if Op.WRITE_MODULE_FX <= op <= Op.WRITE_MODULE_REVERB:
            return self._write_module(op - Op.WRITE_MODULE_FX, d)
        if op in msg.SYSTEM_SIZES:
            self.system[op] = bytes(d[: msg.SYSTEM_SIZES[Op(op)]])
            return []  # [?] does the pedal acknowledge?
        self.unhandled.append(frame)
        return []

    def _identify(self, d: bytes) -> list[Frame]:
        # Same layout and filler values as a real GE150 (plan.md §2.10).
        data = (encode_name(self.name, 32) + encode_name("V1.0.0", 7)
                + encode_name(self.firmware, 7) + encode_name("V1.3.1", 7)
                + encode_name("A", 2) + encode_name("V1.1.0", 7))
        return [Frame(Op.DEVICE_INFO, data)]

    def _read_all(self, d: bytes) -> list[Frame]:
        out = []
        for slot in range(1, PRESET_COUNT + 1):
            p = self.presets[slot]
            out.append(Frame(Op.PRESET_DUMP,
                             bytes([slot]) + encode_name(p.name) + pack_words(p.words)))
        # The real pedal sends the system block right after the last preset [V].
        out.append(Frame(Op.SYSTEM_ALL, b"".join(self.system[op] for op in msg.SYSTEM_SIZES)))
        return out

    def _read_current(self, d: bytes) -> list[Frame]:
        e = self.edit_buffer
        return [Frame(Op.CURRENT_PRESET, bytes([self.current_slot, self.page]) +
                      pack_words(e.words))]

    def _read_user_names(self, d: bytes) -> list[Frame]:
        data = b"".join(encode_name(n, msg.USER_NAME_LEN)
                        for n in self.nr_names + self.ir_names)
        return [Frame(Op.USER_NAMES, data)]

    def _read_rhythm(self, d: bytes) -> list[Frame]:
        return [Frame(Op.RHYTHM, self.rhythm)]

    def _write_rhythm(self, d: bytes) -> list[Frame]:
        self.rhythm = bytes(d[: msg.RHYTHM_SIZE])
        return []

    def _write_module(self, index: int, d: bytes) -> list[Frame]:
        layout = MODULES[index]
        self.edit_buffer.words[layout.slice] = unpack_words(d, layout.words)
        page = 6 + index  # the real pedal jumps to the module page (MOD 0x0C, REVERB 0x0E) [V]
        if page == self.page:
            return []
        self.page = page
        return [Frame(Op.PAGE, pack_words([page]))]

    def _select_preset(self, d: bytes) -> list[Frame]:
        if 1 <= d[0] <= PRESET_COUNT:
            self._select(d[0])
        self.page = 5
        return [Frame(Op.PAGE, pack_words([5]))]  # the real pedal answers 0x34 [05 00] [V]

    def _rename(self, d: bytes) -> list[Frame]:
        slot, name = d[0], decode_name(d[1:16])[:NAME_LEN]
        if 1 <= slot <= PRESET_COUNT:
            self.presets[slot].name = name
        return []  # the real pedal does not answer a rename [V]

    def _write_preset(self, d: bytes) -> list[Frame]:
        slot = d[0]
        if 1 <= slot <= PRESET_COUNT:
            p = Preset(slot, decode_name(d[1 : 1 + NAME_LEN]), unpack_words(d[1 + NAME_LEN :], 72))
            self.presets[slot] = p
            if slot == self.current_slot:
                self._edit = p.copy()
        return [Frame(Op.PRESET_WRITE_ACK, bytes([slot]))]  # 0x43 [slot], as the real pedal [V]

    def _write_exp(self, part: slice, d: bytes) -> list[Frame]:
        self.edit_buffer.words[part] = unpack_words(d, 3)
        return []

    def _set_page(self, d: bytes) -> list[Frame]:
        self.page = unpack_words(d, 1)[0] if len(d) >= 2 else d[0]
        return []

    def _read_backup(self, d: bytes) -> list[Frame]:
        """Like the real pedal: header + one chunk per used IR slot [V]."""
        used = [i for i, n in enumerate(self.ir_names) if not msg.is_empty_slot_name(n)]
        out = [Frame(Op.BACKUP_CHUNK, bytes([0, len(used)]))]
        for chunk, slot in enumerate(used, start=1):
            data = self.user_data.get((Op.USER_IR, slot), bytes(msg.USER_CHUNKS[Op.USER_IR] * 512))
            body = encode_name(self.ir_names[slot], msg.USER_NAME_LEN) + data
            out.append(Frame(Op.BACKUP_CHUNK, bytes([chunk, slot]) + body))
        return out

    def _user_slot(self, op: Op, d: bytes) -> list[Frame]:
        part = d[0]
        ack = [Frame(Op.USER_IR, bytes([part]))]  # B5 [part], last part = 4 for IR [I]
        if part == 0:
            self._uploads[op] = _Upload(slot=d[1])
            return ack
        upload = self._uploads.get(op)
        if upload is None:
            return []
        if part == 1:
            upload.name = decode_name(d[1 : 1 + msg.USER_NAME_LEN])
            return ack
        upload.chunks[part] = bytes(d[1:])
        if len(upload.chunks) < msg.USER_CHUNKS[op]:
            return ack
        index = upload.slot - msg.USER_FIRST_SLOT[op]
        names = self.ir_names if op == Op.USER_IR else self.nr_names
        if 0 <= index < msg.USER_SLOTS:
            names[index] = upload.name
            self.user_data[(op, index)] = b"".join(upload.chunks[k] for k in sorted(upload.chunks))
        del self._uploads[op]
        return ack

    def _factory_reset(self, d: bytes) -> list[Frame]:
        fresh = FakeGE150()
        self.presets, self._edit, self.current_slot = fresh.presets, None, 1
        return []


_Handler = Callable[[FakeGE150, bytes], list[Frame]]

_HANDLERS: dict[int, _Handler] = {
    Op.IDENTIFY: FakeGE150._identify,
    Op.READ_SYSTEM: lambda self, d: [],  # no answer on real hardware [V]
    Op.READ_ALL_PRESETS: FakeGE150._read_all,
    Op.READ_CURRENT_PRESET: FakeGE150._read_current,
    Op.READ_USER_NAMES: FakeGE150._read_user_names,
    Op.READ_RHYTHM: FakeGE150._read_rhythm,
    Op.WRITE_RHYTHM: FakeGE150._write_rhythm,
    Op.SELECT_PRESET: FakeGE150._select_preset,
    Op.RENAME_PRESET: FakeGE150._rename,
    Op.WRITE_PRESET: FakeGE150._write_preset,
    Op.WRITE_EXP_A: lambda self, d: self._write_exp(EXP_A, d),
    Op.WRITE_EXP_B: lambda self, d: self._write_exp(EXP_B, d),
    Op.SET_PAGE: FakeGE150._set_page,
    Op.READ_BACKUP: FakeGE150._read_backup,
    Op.USER_IR: lambda self, d: self._user_slot(Op.USER_IR, d),
    Op.USER_NR: lambda self, d: self._user_slot(Op.USER_NR, d),
    Op.FACTORY_RESET: FakeGE150._factory_reset,
    Op.RESTORE_BEGIN: lambda self, d: [],
    Op.RESTORE_END: lambda self, d: [],
}
