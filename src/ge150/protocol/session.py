"""DeviceSession: reader/writer threads on top of a Transport.

* The writer thread sends queued frames as 64-byte reports, pacing them like the
  vendor editor (>= 5 ms between frames, 100 ms between multipart chunks).
* The reader thread decodes incoming reports into frames and hands every frame to
  pending waiters (``request``/``collect``) and to registered listeners.

Listeners run on the reader thread: they must be quick and must not block. The GUI
bridges them to Qt signals.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from ge150.protocol.framing import Frame, FrameDecoder, split_reports
from ge150.protocol.opcodes import RESPONSES, op_name
from ge150.usb.transport import Transport, TransportDisconnected, TransportError

log = logging.getLogger(__name__)

FRAME_DELAY = 0.005
MULTIPART_DELAY = 0.1
READ_POLL = 0.2

Listener = Callable[[Frame], object]
DisconnectListener = Callable[[BaseException | None], None]
RawListener = Callable[[str, bytes], None]


class SessionError(Exception):
    pass


class ResponseTimeout(SessionError):
    pass


@dataclass
class _Waiter:
    opcodes: frozenset[int]
    frames: queue.Queue[Frame]


@dataclass
class _Outgoing:
    frame: Frame
    delay: float


@dataclass
class _Flush:
    done: threading.Event


class DeviceSession:
    def __init__(
        self,
        transport: Transport,
        *,
        frame_delay: float = FRAME_DELAY,
        multipart_delay: float = MULTIPART_DELAY,
    ) -> None:
        self.transport = transport
        self.frame_delay = frame_delay
        self.multipart_delay = multipart_delay
        self.decoder = FrameDecoder()
        self._out: queue.Queue[_Outgoing | _Flush | None] = queue.Queue()
        self._waiters: list[_Waiter] = []
        self._lock = threading.Lock()
        self._listeners: list[Listener] = []
        self._raw_listeners: list[RawListener] = []
        self._disconnect_listeners: list[DisconnectListener] = []
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._error: BaseException | None = None
        self._reset_expected = False

    # --- lifecycle -----------------------------------------------------------

    def start(self) -> DeviceSession:
        if self._threads:
            return self
        self.transport.open()
        self._stop.clear()
        self._threads = [
            threading.Thread(target=self._reader, name="ge150-reader", daemon=True),
            threading.Thread(target=self._writer, name="ge150-writer", daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        return self

    def close(self) -> None:
        if not self._threads:
            return
        self._stop.set()
        self._out.put(None)
        for thread in self._threads:
            if thread is not threading.current_thread():
                thread.join(timeout=2)
        self._threads = []
        self.transport.close()

    def expect_reset(self) -> None:
        """The next link loss is expected (restore): stop quietly, without notifying
        disconnect listeners. :meth:`reconnect` clears the flag."""
        self._reset_expected = True

    def reconnect(self, timeout: float = 20.0, settle: float = 1.0) -> None:
        """Close and reopen the transport, retrying until it opens or ``timeout`` expires.

        Used after a restore: on ``0xBB`` the pedal writes its flash and its USB link is
        reset by the host (observed on hardware), which invalidates the open node.
        """
        self.close()
        self._error = None
        self._reset_expected = False
        self._out = queue.Queue()
        self.decoder = FrameDecoder()
        time.sleep(settle)
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.start()
                return
            except TransportError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)

    def __enter__(self) -> DeviceSession:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def connected(self) -> bool:
        return bool(self._threads) and not self._stop.is_set()

    @property
    def error(self) -> BaseException | None:
        return self._error

    # --- listeners -----------------------------------------------------------

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Listener) -> None:
        self._listeners.remove(listener)

    def add_raw_listener(self, listener: RawListener) -> None:
        """Called with ("in" | "out", report) for every 64-byte report (debugging)."""
        self._raw_listeners.append(listener)

    def add_disconnect_listener(self, listener: DisconnectListener) -> None:
        self._disconnect_listeners.append(listener)

    # --- sending -------------------------------------------------------------

    def send(self, frame: Frame, delay: float | None = None) -> None:
        """Queue ``frame``; ``delay`` is the pause after it (default ``frame_delay``)."""
        if not self.connected:
            raise SessionError("session is not running") from self._error
        self._out.put(_Outgoing(frame, self.frame_delay if delay is None else delay))

    def send_multipart(self, frames: Iterable[Frame]) -> None:
        for frame in frames:
            self.send(frame, self.multipart_delay)

    def flush(self, timeout: float = 5.0) -> None:
        """Block until every queued frame has been written."""
        done = threading.Event()
        self._out.put(_Flush(done))
        if not done.wait(timeout):
            raise ResponseTimeout("timeout flushing the send queue")

    def request(
        self, frame: Frame, expect: int | Iterable[int] | None = None, timeout: float = 1.0
    ) -> Frame:
        """Send ``frame`` and return the first answer with an ``expect`` opcode."""
        frames = self.collect(frame, expect, count=1, timeout=timeout)
        return frames[0]

    def collect(
        self,
        frame: Frame | None,
        expect: int | Iterable[int] | None = None,
        *,
        count: int,
        timeout: float = 1.0,
        until: Callable[[list[Frame]], bool] | None = None,
    ) -> list[Frame]:
        """Send ``frame`` (optional) and gather ``count`` matching frames.

        ``timeout`` applies to the wait for *each* frame, so long streams (200
        preset dumps) do not need a huge global timeout.
        """
        opcodes = self._expected(frame, expect)
        with self.expecting(opcodes) as frames:
            if frame is not None:
                self.send(frame)
            got: list[Frame] = []
            while len(got) < count and not (until and until(got)):
                try:
                    got.append(frames.get(timeout=timeout))
                except queue.Empty:
                    names = ", ".join(op_name(o) for o in sorted(opcodes))
                    raise ResponseTimeout(
                        f"timeout waiting for {names} ({len(got)}/{count} received)"
                    ) from self._error
            return got

    @contextmanager
    def expecting(self, opcodes: Iterable[int]) -> Iterator[queue.Queue[Frame]]:
        """Register a waiter *before* sending several frames; yields its frame queue."""
        waiter = _Waiter(frozenset(opcodes), queue.Queue())
        with self._lock:
            self._waiters.append(waiter)
        try:
            yield waiter.frames
        finally:
            with self._lock:
                self._waiters.remove(waiter)

    @staticmethod
    def _expected(frame: Frame | None, expect: int | Iterable[int] | None) -> frozenset[int]:
        if expect is None:
            if frame is None or frame.opcode not in RESPONSES:
                raise ValueError("cannot infer the expected answer; pass expect=")
            return frozenset({RESPONSES[frame.opcode]})
        if isinstance(expect, int):
            return frozenset({expect})
        return frozenset(expect)

    # --- threads -------------------------------------------------------------

    def _fail(self, exc: BaseException | None) -> None:
        if self._stop.is_set():
            return
        self._error = exc
        self._stop.set()
        self._out.put(None)
        if self._reset_expected:
            log.info("link reset (expected): %s", exc)
            return
        log.warning("session stopped: %s", exc)
        for listener in list(self._disconnect_listeners):
            try:
                listener(exc)
            except Exception:  # pragma: no cover - listener bug
                log.exception("disconnect listener failed")

    def _writer(self) -> None:
        while not self._stop.is_set():
            item = self._out.get()
            if item is None:
                return
            if isinstance(item, _Flush):
                item.done.set()
                continue
            try:
                for report in split_reports(item.frame.encode()):
                    self.transport.write_report(report)
                    for raw in self._raw_listeners:
                        raw("out", report)
            except TransportError as exc:
                self._fail(exc)
                return
            log.debug("-> %r", item.frame)
            if item.delay:
                time.sleep(item.delay)

    def _reader(self) -> None:
        while not self._stop.is_set():
            try:
                report = self.transport.read_report(READ_POLL)
            except TransportDisconnected as exc:
                self._fail(exc)
                return
            except TransportError as exc:
                log.warning("read error: %s", exc)
                continue
            if report is None:
                continue
            for raw in self._raw_listeners:
                raw("in", report)
            for frame in self.decoder.feed_reports([report]):
                self._dispatch(frame)

    def _dispatch(self, frame: Frame) -> None:
        log.debug("<- %r", frame)
        with self._lock:
            waiters = [w for w in self._waiters if frame.opcode in w.opcodes]
        for waiter in waiters:
            waiter.frames.put(frame)
        for listener in list(self._listeners):
            try:
                listener(frame)
            except Exception:
                log.exception("listener failed for %r", frame)
