"""Full backup / restore of the pedal, compatible with the vendor ``.mbf`` format.

The restore follows FUN_00437a00 of the vendor editor: ``0xBA`` (restore begin), the 200
presets as ``0xC3`` writes, rhythm (``0x8D``), system blocks (``0xA4..0xA7``), the user IRs,
then ``0xBB`` (restore end). Progress is reported in the vendor's 212 steps.
"""

from __future__ import annotations

from collections.abc import Callable

from ge150.formats.mbf import Backup, IrItem
from ge150.model.preset import PRESET_COUNT
from ge150.protocol import messages as msg
from ge150.protocol.framing import Frame
from ge150.protocol.opcodes import Op
from ge150.services import reader
from ge150.services.editor import Editor, EditorError

RESTORE_STEPS = 212
Progress = Callable[[str, int, int], None]


def create_backup(editor: Editor, progress: Progress | None = None) -> Backup:
    """Read everything a backup contains (read-only for the pedal)."""
    report = progress or (lambda *_: None)
    session = editor.session
    report("presets", 0, 3)
    presets, system = reader.read_all_presets(session)
    if len(presets) != PRESET_COUNT or system is None:
        raise EditorError("incomplete preset dump")
    report("rhythm", 1, 3)
    rhythm = reader.read_rhythm(session)
    report("IR", 2, 3)
    chunks = editor.read_ir_backup()
    report("done", 3, 3)
    return Backup(
        presets=[presets[s] for s in sorted(presets)],
        system=b"".join(system.blocks[op] for op in msg.SYSTEM_SIZES),
        rhythm=bytes(rhythm[: msg.RHYTHM_SIZE]),
        irs=[IrItem(c.slot or 0, c.name, c.data) for c in chunks],
    )


def restore_backup(editor: Editor, backup: Backup, progress: Progress | None = None,
                   include_irs: bool = True) -> None:
    """Write a whole backup to the pedal. DESTRUCTIVE: overwrites all presets."""
    if len(backup.presets) != PRESET_COUNT:
        raise EditorError(f"the backup has {len(backup.presets)} presets, expected {PRESET_COUNT}")
    report = progress or (lambda *_: None)
    session = editor.session
    session.send(Frame(Op.RESTORE_BEGIN, b"\x01"), delay=session.multipart_delay)
    for step, preset in enumerate(sorted(backup.presets, key=lambda p: p.slot)):
        report(f"preset {preset.slot}", step, RESTORE_STEPS)
        editor.copy_preset_data(preset)
    report("rhythm", 200, RESTORE_STEPS)
    editor.set_rhythm(backup.rhythm)
    report("system", 201, RESTORE_STEPS)
    pos = 0
    for op, size in msg.SYSTEM_SIZES.items():
        editor.set_system(Op(op), backup.system[pos : pos + size])
        pos += size
    if include_irs:
        for i, ir in enumerate(backup.irs):
            report(f"IR {ir.slot + 1}", 202 + i, RESTORE_STEPS)
            editor.upload_user_slot(Op.USER_IR, ir.slot, ir.name, ir.data)
    session.send(Frame(Op.RESTORE_END, b"\x01"), delay=session.multipart_delay)
    session.flush()
    report("done", RESTORE_STEPS, RESTORE_STEPS)
