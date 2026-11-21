"""Qt bridge: DeviceState / DeviceSession callbacks (USB threads) -> Qt signals."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ge150.model.device_state import Change, DeviceState
from ge150.protocol.session import DeviceSession


class StateBridge(QObject):
    #: kind, slot (-1 if none), module (-1 if none). Delivered on the GUI thread.
    changed = Signal(str, int, int)
    disconnected = Signal(str)

    def __init__(self, state: DeviceState, session: DeviceSession,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.state = state
        state.add_listener(self._on_change)
        session.add_disconnect_listener(self._on_disconnect)

    def _on_change(self, change: Change) -> None:
        slot = -1 if change.slot is None else change.slot
        module = -1 if change.module is None else change.module
        self.changed.emit(change.kind, slot, module)

    def _on_disconnect(self, exc: BaseException | None) -> None:
        self.disconnected.emit(str(exc) if exc else "device disconnected")

    def detach(self) -> None:
        self.state.remove_listener(self._on_change)
