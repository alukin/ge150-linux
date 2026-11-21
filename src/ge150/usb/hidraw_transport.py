"""Linux hidraw backend: the GE150 is a HID device without report IDs.

``write()`` takes the report number (0) followed by the 64 report bytes and ``read()``
returns the 64 report bytes (Documentation/hid/hidraw.rst).
"""

from __future__ import annotations

import errno
import os
import select
from dataclasses import dataclass
from pathlib import Path

from ge150.usb.device_ids import PRODUCT_ID, REPORT_SIZE, VENDOR_ID
from ge150.usb.transport import TransportDisconnected, TransportError

SYSFS_HIDRAW = Path("/sys/class/hidraw")
#: EPROTO appears while the host resets the pedal's USB link (e.g. after a restore).
_GONE = {errno.ENODEV, errno.EIO, errno.ENXIO, errno.EPIPE, errno.EPROTO}
UDEV_HINT = (
    "install the udev rule: sudo cp udev/70-mooer-ge150.rules /etc/udev/rules.d/ && "
    "sudo udevadm control --reload && sudo udevadm trigger, then replug the pedal"
)


@dataclass(frozen=True)
class HidrawInfo:
    path: str
    name: str
    serial: str


def _uevent(path: Path) -> dict[str, str]:
    try:
        text = (path / "device" / "uevent").read_text()
    except OSError:
        return {}
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def find_hidraw_devices(
    vid: int = VENDOR_ID, pid: int = PRODUCT_ID, sysfs: Path = SYSFS_HIDRAW
) -> list[HidrawInfo]:
    """List ``/dev/hidrawN`` nodes whose HID_ID matches ``vid:pid``."""
    wanted = f"0003:{vid:08X}:{pid:08X}"
    found = []
    for entry in sorted(sysfs.glob("hidraw*")):
        info = _uevent(entry)
        if info.get("HID_ID", "").upper() == wanted:
            found.append(HidrawInfo(f"/dev/{entry.name}", info.get("HID_NAME", ""),
                                    info.get("HID_UNIQ", "")))
    return found


class HidrawTransport:
    def __init__(self, path: str | None = None) -> None:
        self._requested = path
        self._path = path
        self._fd: int | None = None

    @property
    def description(self) -> str:
        return f"hidraw {self._path or '(auto)'}"

    def open(self) -> None:
        if self._fd is not None:
            return
        if self._requested is None:
            # Re-discover on every open: the node can change after a replug or a reset.
            devices = find_hidraw_devices()
            if not devices:
                raise TransportError("GE150 not found (no hidraw node with HID_ID 0483:5703)")
            self._path = devices[0].path
        path = self._path or self._requested or ""
        try:
            self._fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as exc:
            raise TransportError(f"no permission to open {path}: {UDEV_HINT}") from exc
        except OSError as exc:
            raise TransportError(f"cannot open {path}: {exc}") from exc

    def close(self) -> None:
        if self._fd is not None:
            fd, self._fd = self._fd, None
            os.close(fd)

    def _require_fd(self) -> int:
        if self._fd is None:
            raise TransportDisconnected("transport is closed")
        return self._fd

    def write_report(self, report: bytes) -> None:
        if len(report) != REPORT_SIZE:
            raise ValueError(f"report must be {REPORT_SIZE} bytes")
        fd = self._require_fd()
        try:
            _, writable, _ = select.select([], [fd], [], 1.0)
            if not writable:
                raise TransportError("timeout writing report")
            os.write(fd, b"\x00" + report)
        except OSError as exc:
            if exc.errno in _GONE:
                raise TransportDisconnected(str(exc)) from exc
            raise TransportError(str(exc)) from exc

    def read_report(self, timeout: float) -> bytes | None:
        fd = self._require_fd()
        try:
            readable, _, _ = select.select([fd], [], [], timeout)
            if not readable:
                return None
            data = os.read(fd, REPORT_SIZE)
        except BlockingIOError:
            return None
        except (OSError, ValueError) as exc:
            if isinstance(exc, ValueError) or exc.errno in _GONE or exc.errno == errno.EBADF:
                raise TransportDisconnected(str(exc)) from exc
            raise TransportError(str(exc)) from exc
        if not data:
            raise TransportDisconnected("end of file on hidraw node")
        return data
