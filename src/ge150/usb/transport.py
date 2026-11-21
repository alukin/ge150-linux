"""Transport interface shared by the hidraw, pyusb and simulator backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class TransportError(Exception):
    """Cannot open or use the device (permissions, not found, ...)."""


class TransportDisconnected(TransportError):
    """The device went away while in use."""


@runtime_checkable
class Transport(Protocol):
    """Moves raw 64-byte interrupt reports. No protocol knowledge here."""

    @property
    def description(self) -> str: ...

    def open(self) -> None: ...

    def close(self) -> None: ...

    def write_report(self, report: bytes) -> None:
        """Send one 64-byte output report."""
        ...

    def read_report(self, timeout: float) -> bytes | None:
        """Return one 64-byte input report, or ``None`` after ``timeout`` seconds."""
        ...
