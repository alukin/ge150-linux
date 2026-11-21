"""Gallery of the models of a module: a thumbnail of the gear (photo or drawing) and the
model name for each one, instead of a drop-down list.

Exposes the subset of the ``QComboBox`` interface the module page uses (``count``,
``currentIndex``, ``setCurrentIndex``, ``currentIndexChanged``, ``clear``).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap, QResizeEvent
from PySide6.QtWidgets import QListView, QListWidget, QListWidgetItem, QWidget

from ge150.model.gear import Gear
from ge150.ui.gear_art import KnobState, render_pixmap
from ge150.ui.gear_view import load_photo

ICON = QSize(104, 78)
CELL = QSize(124, 118)


def thumbnail(gear: Gear, title: str, knobs: list[KnobState], ratio: float) -> QPixmap:
    photo = load_photo(gear.gid)
    if photo is not None:
        scaled = photo.scaled(ICON * ratio, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(ratio)
        return scaled
    return render_pixmap(gear, ICON, title, knobs, True, ratio)


class ModelGallery(QListWidget):
    currentIndexChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("modelGallery")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setIconSize(ICON)
        self.setGridSize(CELL)
        self.setSpacing(4)
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(CELL.height() * 2 + 16)
        self.currentRowChanged.connect(self._row_changed)
        self._silent = False

    def add_model(self, label: str, gear: Gear, title: str, knobs: list[KnobState],
                  tooltip: str = "") -> None:
        ratio = self.devicePixelRatioF() or 1.0
        item = QListWidgetItem(QIcon(thumbnail(gear, title, knobs, ratio)), label)
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        item.setToolTip(tooltip or label)
        item.setSizeHint(CELL)
        self.addItem(item)

    # --- QComboBox-like interface -----------------------------------------------------

    def clear(self) -> None:
        self._silent = True
        try:
            super().clear()
        finally:
            self._silent = False

    def currentIndex(self) -> int:
        return self.currentRow()

    def setCurrentIndex(self, index: int) -> None:
        self.setCurrentRow(index)
        item = self.item(index)
        if item is not None:
            self.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
            # Again once the grid is laid out (right after filling it the rows are unknown).
            QTimer.singleShot(0, lambda: self._scroll_to(index))

    def _scroll_to(self, index: int) -> None:
        item = self.item(index)
        if item is not None and self.currentRow() == index:
            self.doItemsLayout()  # the grid is laid out lazily: place the items first
            self.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, lambda: self._scroll_to(self.currentRow()))

    def currentText(self) -> str:
        item = self.currentItem()
        return item.text() if item else ""

    def _row_changed(self, row: int) -> None:
        if not self._silent:
            self.currentIndexChanged.emit(row)
