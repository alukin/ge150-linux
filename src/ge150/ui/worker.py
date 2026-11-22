"""Run blocking device operations off the GUI thread."""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _Signals,
                 lock: threading.Lock) -> None:
        super().__init__()
        self.fn = fn
        self.signals = signals
        self.lock = lock

    def run(self) -> None:
        try:
            with self.lock:
                result = self.fn()
        except Exception as exc:  # reported to the GUI, never swallowed
            traceback.print_exc()
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.signals.done.emit(result)


class TaskRunner(QObject):
    """``run(fn, on_done, on_error)``: callbacks are delivered on the GUI thread."""

    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)  # device operations must not overlap
        #: Also taken by other pedal users (the AI tools, ``ai_host.py``).
        self.lock = threading.Lock()
        self._running = 0
        self._keep: list[_Signals] = []

    @property
    def busy(self) -> bool:
        return self._running > 0

    def run(self, fn: Callable[[], Any], on_done: Callable[[Any], None] | None = None,
            on_error: Callable[[str], None] | None = None) -> None:
        signals = _Signals()
        self._keep.append(signals)

        def finish() -> None:
            self._keep.remove(signals)
            self._running -= 1
            if self._running == 0:
                self.busy_changed.emit(False)

        def done(result: Any) -> None:
            finish()
            if on_done:
                on_done(result)

        def failed(message: str) -> None:
            finish()
            if on_error:
                on_error(message)

        signals.done.connect(done)
        signals.failed.connect(failed)
        self._running += 1
        if self._running == 1:
            self.busy_changed.emit(True)
        self.pool.start(_Task(fn, signals, self.lock))

    def wait(self, msecs: int = 10000) -> bool:
        return self.pool.waitForDone(msecs)
