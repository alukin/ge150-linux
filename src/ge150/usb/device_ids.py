"""USB identifiers (plan.md §2.1)."""

from __future__ import annotations

VENDOR_ID = 0x0483  # STMicroelectronics
#: GE150 in normal mode, verified with lsusb on real hardware (bcdDevice 0x00C8).
PRODUCT_ID = 0x5703
#: Candidate bootloader / update mode seen in the launcher (mode 3) [I].
BOOTLOADER_PRODUCT_ID = 0x5750

EP_IN = 0x81
EP_OUT = 0x02
INTERFACE = 0
REPORT_SIZE = 64

#: Launcher classification (GE150.exe FUN_004086a0): (pid, bcdDevice) -> mode.
LAUNCHER_MODES = {
    (0x5750, 0x00C8): 1,
    (0x5750, 0x00CA): 3,
    (0x5703, 0x00CA): 4,
    (0x5703, 0x00C8): 5,
    (0x1412, 0x00C8): 6,
    (0x1512, 0x00C8): 7,
    (0x1522, 0x00C8): 8,
}

#: Model name returned by the identification frame.
DEVICE_NAME = "MOOER_GE150"
