"""Transport that talks to an in-process :class:`FakeGE150` through 64-byte reports.

It exercises exactly the same fragmentation / reassembly path as real hardware.
"""

from __future__ import annotations

import queue
import threading

from ge150.protocol.framing import Frame, FrameDecoder, split_reports
from ge150.sim.fake_device import FakeGE150
from ge150.usb.device_ids import REPORT_SIZE
from ge150.usb.transport import TransportDisconnected


class SimTransport:
    def __init__(self, device: FakeGE150 | None = None) -> None:
        self.device = device or FakeGE150()
        self._host_decoder = FrameDecoder()
        self._in: queue.Queue[bytes] = queue.Queue()
        self._open = False
        self._lock = threading.Lock()
        self.written_reports: list[bytes] = []

    @property
    def description(self) -> str:
        return "simulator"

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def unplug(self) -> None:
        """Simulate a disconnection: the next read raises TransportDisconnected."""
        self._open = False

    def inject(self, frames: list[Frame]) -> None:
        """Queue spontaneous device frames (footswitch, knob changes, ...)."""
        for frame in frames:
            for report in split_reports(frame.encode()):
                self._in.put(report)

    def write_report(self, report: bytes) -> None:
        if not self._open:
            raise TransportDisconnected("simulator closed")
        if len(report) != REPORT_SIZE:
            raise ValueError(f"report must be {REPORT_SIZE} bytes")
        self.written_reports.append(bytes(report))
        with self._lock:
            frames = self._host_decoder.feed_reports([report])
            for frame in frames:
                self.inject(self.device.handle(frame))

    def read_report(self, timeout: float) -> bytes | None:
        if not self._open:
            raise TransportDisconnected("simulator closed")
        try:
            return self._in.get(timeout=timeout)
        except queue.Empty:
            return None
