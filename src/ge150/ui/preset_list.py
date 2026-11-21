"""List of the 200 stored presets with search and a context menu."""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from ge150.model.device_state import DeviceState

SLOT_ROLE = Qt.ItemDataRole.UserRole
DOUBLE_CLICK_S = 0.6


class PresetList(QWidget):
    activated = Signal(int)  # load preset on the pedal
    action_requested = Signal(str, int)  # (action name, slot)

    ACTIONS = (("rename", "Renombrar…"), ("copy", "Copiar"), ("paste", "Pegar aquí"),
               ("export", "Exportar .mo…"), ("import", "Importar .mo aquí…"))

    def __init__(self, state: DeviceState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar preset…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.list = QListWidget()
        self.list.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        # One click loads the preset; Enter too. A double click must not load it twice.
        self.list.itemClicked.connect(self._chosen)
        self.list.itemActivated.connect(self._chosen)
        self._last_choice: tuple[int, float] = (0, 0.0)
        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)
        self.clipboard: int | None = None

    def _chosen(self, item: QListWidgetItem) -> None:
        slot = int(item.data(SLOT_ROLE))
        now = time.monotonic()
        last_slot, last_time = self._last_choice
        self._last_choice = (slot, now)
        if slot == last_slot and now - last_time < DOUBLE_CLICK_S:
            return
        self.activated.emit(slot)

    def select_slot(self, slot: int | None) -> None:
        """Highlight ``slot`` (e.g. back to the current preset after a cancelled change)."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(SLOT_ROLE) == slot:
                self.list.setCurrentItem(item)
                self.list.scrollToItem(item)
                return

    def selected_slot(self) -> int | None:
        item = self.list.currentItem()
        return None if item is None else int(item.data(SLOT_ROLE))

    def reload(self) -> None:
        current = self.selected_slot()
        self.list.clear()
        for slot in sorted(self.state.presets):
            item = QListWidgetItem()
            item.setData(SLOT_ROLE, slot)
            self.list.addItem(item)
            self._paint(item)
            if slot == (current or self.state.current_slot):
                self.list.setCurrentItem(item)
        self._filter(self.search.text())

    def update_slot(self, slot: int) -> None:
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(SLOT_ROLE) == slot:
                self._paint(item)
        if self.list.count() == 0 and self.state.presets:
            self.reload()

    def mark_current(self) -> None:
        for row in range(self.list.count()):
            item = self.list.item(row)
            self._paint(item)
            if item.data(SLOT_ROLE) == self.state.current_slot:
                self.list.scrollToItem(item)

    def _paint(self, item: QListWidgetItem) -> None:
        slot = int(item.data(SLOT_ROLE))
        preset = self.state.presets.get(slot)
        current = slot == self.state.current_slot
        dirty = current and self.state.dirty
        name = preset.name if preset else "?"
        item.setText(f"{slot:3d}  {name}{'  *' if dirty else ''}")
        font = QFont(item.font())
        font.setBold(current)
        item.setFont(font)

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.list.count()):
            item = self.list.item(row)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _menu(self, pos: QPoint) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        slot = int(item.data(SLOT_ROLE))
        menu = QMenu(self)
        load = QAction("Cargar en la pedalera", menu)
        load.triggered.connect(lambda: self.activated.emit(slot))
        menu.addAction(load)
        menu.addSeparator()
        for name, label in self.ACTIONS:
            action = QAction(label, menu)
            action.setEnabled(name != "paste" or self.clipboard is not None)
            action.triggered.connect(lambda _=False, n=name: self.action_requested.emit(n, slot))
            menu.addAction(action)
        menu.exec(self.list.mapToGlobal(pos))
