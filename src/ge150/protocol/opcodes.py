"""Opcode catalogue (plan.md §2.5 and §2.6).

Host requests generally set bit 7; the device answers / notifies with the same
opcode without it (e.g. 0xA4 -> 0x24). Evidence tags follow plan.md: names marked
"unknown" still need hardware confirmation.
"""

from __future__ import annotations

from enum import IntEnum


class Op(IntEnum):
    # --- shared ------------------------------------------------------------
    IDENTIFY = 0x00  # host -> device: [00]

    # --- device -> host ----------------------------------------------------
    DEVICE_INFO = 0x01  # answer to IDENTIFY, verified on hardware (plan.md §2.10)
    MODULE_FX = 0x02
    MODULE_DS = 0x03
    MODULE_AMP = 0x04
    MODULE_CAB = 0x05
    MODULE_NS = 0x06
    MODULE_EQ = 0x07
    MODULE_MOD = 0x08
    MODULE_DELAY = 0x09
    MODULE_REVERB = 0x0A
    RHYTHM = 0x0C
    PRESET_SELECTED = 0x16
    PRESET_RENAMED = 0x17
    EXP_A = 0x18
    PRESET_DUMP = 0x20
    SYSTEM_1 = 0x24
    SYSTEM_2 = 0x25
    SYSTEM_3 = 0x26
    SYSTEM_4 = 0x27
    CURRENT_PRESET = 0x30
    SYSTEM_ALL = 0x32
    EXP_B = 0x33
    PAGE = 0x34
    USER_NAMES = 0x41
    PRESET_WRITE_ACK = 0x43  # answer to 0xC3: [slot], verified on hardware
    BACKUP_CHUNK = 0x44

    # --- host -> device ----------------------------------------------------
    READ_SYSTEM = 0x31  # no answer on real hardware; maybe 'editor connected' [?]
    WRITE_MODULE_FX = 0x82
    WRITE_MODULE_DS = 0x83
    WRITE_MODULE_AMP = 0x84
    WRITE_MODULE_CAB = 0x85
    WRITE_MODULE_NS = 0x86
    WRITE_MODULE_EQ = 0x87
    WRITE_MODULE_MOD = 0x88
    WRITE_MODULE_DELAY = 0x89
    WRITE_MODULE_REVERB = 0x8A
    FACTORY_RESET = 0x8B  # destructive
    READ_RHYTHM = 0x8C
    WRITE_RHYTHM = 0x8D
    SELECT_PRESET = 0x96
    RENAME_PRESET = 0x97
    WRITE_EXP_A = 0x98
    READ_ALL_PRESETS = 0xA0
    WRITE_SYSTEM_1 = 0xA4
    WRITE_SYSTEM_2 = 0xA5
    WRITE_SYSTEM_3 = 0xA6
    WRITE_SYSTEM_4 = 0xA7
    FIRMWARE_UPDATE = 0xAA  # destructive (launcher only)
    READ_CURRENT_PRESET = 0xB0
    WRITE_EXP_B = 0xB3
    SET_PAGE = 0xB4
    USER_IR = 0xB5  # multipart upload/delete; the pedal acks each part: B5 [part] [V]
    USER_NR = 0xB7  # multipart upload/delete; the pedal acks each part: B7 [part] [V]
    RESTORE_BEGIN = 0xBA  # destructive
    RESTORE_END = 0xBB
    READ_USER_NAMES = 0xC1
    WRITE_PRESET = 0xC3
    READ_BACKUP = 0xC4


#: Opcodes that change persistent device state in a way that may lose user data.
DESTRUCTIVE = frozenset(
    {Op.FACTORY_RESET, Op.FIRMWARE_UPDATE, Op.RESTORE_BEGIN, Op.USER_IR, Op.USER_NR}
)

#: Opcodes that only read state. Safe to send at any time.
READ_ONLY = frozenset(
    {
        Op.IDENTIFY,
        Op.READ_SYSTEM,
        Op.READ_RHYTHM,
        Op.READ_ALL_PRESETS,
        Op.READ_CURRENT_PRESET,
        Op.READ_USER_NAMES,
        Op.READ_BACKUP,
    }
)

#: Module index (0..8) -> write opcode. Table 0x44d880 of MOOER_GE150.exe.
MODULE_WRITE_OPS = tuple(Op(0x82 + i) for i in range(9))
#: Module index (0..8) -> notification opcode.
MODULE_NOTIFY_OPS = tuple(Op(0x02 + i) for i in range(9))


def op_name(opcode: int) -> str:
    """Human readable name for logs (``0x20 PRESET_DUMP``)."""
    try:
        return f"0x{opcode:02X} {Op(opcode).name}"
    except ValueError:
        return f"0x{opcode:02X} ?"


#: Request -> opcode of the answer the vendor editor waits for (plan.md §2.9).
#: 0x31 gets no direct answer on real hardware; 0x32 follows the 0xA0 dump.
RESPONSES: dict[int, int] = {
    Op.IDENTIFY: Op.DEVICE_INFO,
    Op.READ_RHYTHM: Op.RHYTHM,
    Op.READ_ALL_PRESETS: Op.PRESET_DUMP,
    Op.READ_CURRENT_PRESET: Op.CURRENT_PRESET,
    Op.READ_USER_NAMES: Op.USER_NAMES,
    Op.READ_BACKUP: Op.BACKUP_CHUNK,
}
