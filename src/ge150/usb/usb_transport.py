"""pyusb (libusb) fallback backend, mirroring what the vendor editor does.

Detaches the kernel HID driver from interface 0 while open and reattaches it on close.
"""

from __future__ import annotations

from typing import Any

from ge150.usb.device_ids import EP_IN, EP_OUT, INTERFACE, PRODUCT_ID, REPORT_SIZE, VENDOR_ID
from ge150.usb.transport import TransportDisconnected, TransportError


class UsbTransport:
    def __init__(self, vid: int = VENDOR_ID, pid: int = PRODUCT_ID) -> None:
        self._vid, self._pid = vid, pid
        self._dev: Any = None
        self._reattach = False
        self._usb: Any = None

    @property
    def description(self) -> str:
        return f"libusb {self._vid:04x}:{self._pid:04x}"

    def open(self) -> None:
        if self._dev is not None:
            return
        try:
            import usb.core
            import usb.util
        except ImportError as exc:
            raise TransportError("pyusb is not installed (pip install pyusb)") from exc
        self._usb = usb
        dev = usb.core.find(idVendor=self._vid, idProduct=self._pid)
        if dev is None:
            raise TransportError(f"device {self._vid:04x}:{self._pid:04x} not found")
        try:
            if dev.is_kernel_driver_active(INTERFACE):
                dev.detach_kernel_driver(INTERFACE)
                self._reattach = True
            dev.set_configuration()
            usb.util.claim_interface(dev, INTERFACE)
        except usb.core.USBError as exc:
            raise TransportError(f"cannot claim interface {INTERFACE}: {exc}") from exc
        self._dev = dev

    def close(self) -> None:
        dev, self._dev = self._dev, None
        if dev is None:
            return
        usb = self._usb
        try:
            usb.util.release_interface(dev, INTERFACE)
            if self._reattach:
                dev.attach_kernel_driver(INTERFACE)
        except usb.core.USBError:
            pass
        finally:
            usb.util.dispose_resources(dev)
            self._reattach = False

    def write_report(self, report: bytes) -> None:
        if len(report) != REPORT_SIZE:
            raise ValueError(f"report must be {REPORT_SIZE} bytes")
        if self._dev is None:
            raise TransportDisconnected("transport is closed")
        try:
            self._dev.write(EP_OUT, report, timeout=500)
        except self._usb.core.USBTimeoutError as exc:
            raise TransportError("timeout writing report") from exc
        except self._usb.core.USBError as exc:
            raise TransportDisconnected(str(exc)) from exc

    def read_report(self, timeout: float) -> bytes | None:
        if self._dev is None:
            raise TransportDisconnected("transport is closed")
        try:
            data = self._dev.read(EP_IN, REPORT_SIZE, timeout=max(1, int(timeout * 1000)))
        except self._usb.core.USBTimeoutError:
            return None
        except self._usb.core.USBError as exc:
            raise TransportDisconnected(str(exc)) from exc
        return bytes(data)
