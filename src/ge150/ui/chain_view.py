"""The signal chain: one tile per module with its on/off state and model."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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


class ModuleTile(QFrame):
    clicked = Signal(int)
    toggled = Signal(int, bool)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.setObjectName("moduleTile")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(104)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.power = QPushButton(MODULES[index].name)
        self.power.setObjectName("power")
        self.power.setCheckable(True)
        self.power.setToolTip("Encender / apagar el módulo")
        self.power.toggled.connect(lambda on: self.toggled.emit(self.index, on))
        self.model = QLabel("-")
        self.model.setObjectName("modelLabel")
        self.model.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.model.setWordWrap(True)
        layout.addWidget(self.power)
        layout.addWidget(self.model)
        self.set_selected(False)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.clicked.emit(self.index)
        super().mousePressEvent(event)

    def set_state(self, on: bool, model: str) -> None:
        self.power.blockSignals(True)
        self.power.setChecked(on)
        self.power.blockSignals(False)
        self.model.setText(model)
        self.model.setEnabled(on)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


class ChainView(QWidget):
    module_selected = Signal(int)
    error = Signal(str)

    def __init__(self, editor: Editor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.selected = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tiles = [ModuleTile(i) for i in range(len(MODULES))]
        for tile in self.tiles:
            tile.clicked.connect(self.select)
            tile.toggled.connect(self._on_toggle)
            layout.addWidget(tile)
        self.tiles[0].set_selected(True)

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
            model = self.editor.catalog[tile.index].model_for_type(block.type)
            tile.set_state(block.switch, model.label if model else f"?{block.type}")

    def _on_toggle(self, index: int, on: bool) -> None:
        try:
            self.editor.set_switch(index, on)
        except Exception as exc:
            self.error.emit(str(exc))
