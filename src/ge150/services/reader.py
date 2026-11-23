"""Read-only queries. Safe to run against real hardware at any time."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ge150.model.catalog import load_catalog
from ge150.model.preset import MODULES, PRESET_COUNT, Preset
from ge150.protocol import messages as msg
from ge150.protocol.framing import Frame
from ge150.protocol.opcodes import Op
from ge150.protocol.session import DeviceSession, ResponseTimeout

FLUSH_REPORT_DATA = bytes(8)
#: 64-byte report carrying the 8 zero bytes: ``report[0]`` = useful length.
FLUSH_REPORT = (bytes([len(FLUSH_REPORT_DATA)]) + FLUSH_REPORT_DATA).ljust(64, b"\x00")


def identify(session: DeviceSession, timeout: float = 2.0) -> msg.DeviceInfo:
    return msg.parse_identify(session.request(msg.identify(), timeout=timeout))


def handshake(session: DeviceSession, attempts: int = 3, timeout: float = 2.0,
              flush: bool = True) -> msg.DeviceInfo:
    """First contact, like the vendor launcher (FUN_00408a30): 8 zero bytes, then
    identify. Retried because the pedal can ignore the first identification right after
    the node is opened (seen on hardware: timeout on the first start, fine on the next)."""
    for attempt in range(1, attempts + 1):
        if flush:
            session.send_report(FLUSH_REPORT, delay=0.05)
        try:
            return identify(session, timeout=timeout)
        except ResponseTimeout:
            if attempt == attempts:
                raise
    raise AssertionError("unreachable")


def read_rhythm(session: DeviceSession) -> bytes:
    return session.request(msg.read(Op.READ_RHYTHM)).data


def read_user_names(session: DeviceSession) -> msg.UserNames:
    return msg.parse_user_names(session.request(msg.read(Op.READ_USER_NAMES)))


def read_current(session: DeviceSession) -> msg.CurrentPreset:
    return msg.parse_current(session.request(msg.read(Op.READ_CURRENT_PRESET)))


def read_all_presets(
    session: DeviceSession, timeout: float = 2.0
) -> tuple[dict[int, Preset], msg.SystemSettings | None]:
    """0xA0 -> 200 x 0x20, then the pedal sends 0x32 (system) on its own [V].

    ``timeout`` is per frame. 0x31 gets no answer of its own on real hardware, so
    this is also the way to read the system settings.
    """

    def complete(frames: list[Frame]) -> bool:
        return any(f.opcode == Op.SYSTEM_ALL for f in frames)

    frames = session.collect(msg.read(Op.READ_ALL_PRESETS), {Op.PRESET_DUMP, Op.SYSTEM_ALL},
                             count=PRESET_COUNT + 1, timeout=timeout, until=complete)
    presets = (msg.parse_preset_dump(f) for f in frames if f.opcode == Op.PRESET_DUMP)
    system = next((msg.SystemSettings.from_all(f) for f in frames
                   if f.opcode == Op.SYSTEM_ALL), None)
    return {p.slot: p for p in presets}, system


def describe_words(words: list[int], names: msg.UserNames | None = None) -> list[dict[str, Any]]:
    """Decode the 66 module words with the catalogue. With ``names``, a user IR slot shows
    the IR loaded on the pedal ("34:1960A V30 57+906") instead of its catalogue name."""
    catalog = load_catalog()
    preset = Preset(0, "", list(words))
    out = []
    for layout in MODULES:
        block = preset.module(layout.index)
        info = catalog[layout.index]
        model = info.model_for_type(block.type)
        params, used = [], set()
        for p in model.params if model else ():
            raw = block.words[p.word]
            used.add(p.word)
            params.append({"name": p.name, "raw": raw, "value": p.format(raw)})
        extra = {i: block.words[i] for i in range(2, layout.words) if i not in used}
        out.append({
            "module": layout.name,
            "on": block.switch,
            "type": block.type,
            "model": _model_label(model, layout.name, names) if model else f"?{block.type}",
            "params": params,
            "unused_words": extra,
        })
    return out


def _model_label(model: Any, module: str, names: msg.UserNames | None) -> str:
    if not model.user_slot or names is None:
        return str(model.label)
    first, bank = (27, names.ir) if module == "CAB" else (56, names.nr)
    slot = model.number - first
    if 0 <= slot < len(bank) and not msg.is_empty_slot_name(bank[slot]):
        return f"{model.number:02d}:{bank[slot]}"
    return str(model.label)


def snapshot(session: DeviceSession) -> dict[str, Any]:
    """Everything readable, as JSON-serialisable data (keep one before any write)."""
    info = identify(session)
    presets, system = read_all_presets(session)
    names = read_user_names(session)
    current = read_current(session)
    rhythm = read_rhythm(session)
    return {
        "device": {k: v for k, v in asdict(info).items() if k != "raw"},
        "identify_raw": info.raw.hex(),
        "system": ({f"0x{op:02X}": data.hex() for op, data in system.blocks.items()}
                   if system else None),
        "rhythm": rhythm.hex(),
        "user_names": {"nr": names.nr, "ir": names.ir},
        "current": {"slot": current.slot, "page": current.page, "words": current.words},
        "presets": [{"slot": p.slot, "name": p.name, "words": p.words}
                    for p in sorted(presets.values(), key=lambda p: p.slot)],
    }
