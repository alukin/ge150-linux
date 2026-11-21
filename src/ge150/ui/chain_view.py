"""The signal chain, always visible at the bottom: one tile per module with a picture of
its gear, its model and an on/off button. Clicking a tile opens that module."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ge150.model.preset import MODULES
from ge150.services.editor import Editor
from ge150.ui.gear_view import GearView, module_look

SHORT = ("FX", "DS", "AMP", "CAB", "NS", "EQ", "MOD", "DLY", "REV")


class ModuleTile(QFrame):
    clicked = Signal(int)
    toggled = Signal(int, bool)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.setObjectName("moduleTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{MODULES[index].name}: clic para editar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(4)
        self.name = QLabel(SHORT[index])
        self.name.setObjectName("tileName")
        self.power = QPushButton("⏻")
        self.power.setObjectName("power")
        self.power.setCheckable(True)
        self.power.setFixedSize(24, 24)
        self.power.setToolTip("Encender / apagar el módulo")
        self.power.toggled.connect(lambda on: self.toggled.emit(self.index, on))
        top.addWidget(self.name)
        top.addStretch(1)
        top.addWidget(self.power)
        self.view = GearView(compact=True)
        self.view.setMinimumHeight(70)
        self.model = QLabel("-")
        self.model.setObjectName("modelLabel")
        self.model.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(top)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.model)
        self.setMinimumWidth(96)
        self.set_selected(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit(self.index)
        super().mousePressEvent(event)

    def set_state(self, on: bool, model: str) -> None:
        self.power.blockSignals(True)
        self.power.setChecked(on)
        self.power.blockSignals(False)
        self.model.setText(model)
        self.model.setToolTip(model)
        self.model.setEnabled(on)
        self.setProperty("on", on)
        self._repolish()

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self._repolish()

    def _repolish(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)


class _Wire(QWidget):
    """The cable between two tiles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(14)

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = self.height() / 2
        p.setPen(QPen(QColor("#5b636e"), 2))
        p.drawLine(QPointF(0, y), QPointF(self.width() - 4, y))
        p.drawLine(QPointF(self.width() - 8, y - 4), QPointF(self.width() - 3, y))
        p.drawLine(QPointF(self.width() - 8, y + 4), QPointF(self.width() - 3, y))
        p.end()


class ChainView(QFrame):
    module_selected = Signal(int)
    error = Signal(str)

    def __init__(self, editor: Editor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.selected = 0
        self.setObjectName("chainBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)
        self.tiles = [ModuleTile(i) for i in range(len(MODULES))]
        for i, tile in enumerate(self.tiles):
            if i:
                layout.addWidget(_Wire())
            tile.clicked.connect(self.select)
            tile.toggled.connect(self._on_toggle)
            layout.addWidget(tile, 1)
        self.tiles[0].set_selected(True)
        self.setMinimumHeight(150)
        self.setMaximumHeight(190)

    def select(self, index: int) -> None:
        self.tiles[self.selected].set_selected(False)
        self.selected = index
        self.tiles[index].set_selected(True)
        self.module_selected.emit(index)

    def refresh(self) -> None:
        if self.editor.state.edit is None:
            return
        for tile in self.tiles:
            block = self.editor.module(tile.index)
            tile.set_state(block.switch, self.editor.model_label(tile.index, block.type))
            tile.view.set_gear(*module_look(self.editor, tile.index))

    def _on_toggle(self, index: int, on: bool) -> None:
        try:
            self.editor.set_switch(index, on)
        except Exception as exc:
            self.error.emit(str(exc))
