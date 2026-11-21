"""Transports that move 64-byte HID reports to and from the pedal."""

from ge150.usb.transport import Transport, TransportDisconnected, TransportError

__all__ = ["Transport", "TransportDisconnected", "TransportError", "open_transport"]


def open_transport(backend: str = "auto", device: str | None = None) -> Transport:
    """Create (not yet opened) transport. ``backend``: auto | hidraw | usb."""
    if backend in ("auto", "hidraw"):
        from ge150.usb.hidraw_transport import HidrawTransport, find_hidraw_devices

        if backend == "hidraw" or device or find_hidraw_devices():
            return HidrawTransport(device)
    if backend in ("auto", "usb"):
        from ge150.usb.usb_transport import UsbTransport

        return UsbTransport()
    raise ValueError(f"unknown backend: {backend}")
