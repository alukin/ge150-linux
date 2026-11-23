"""Gallery of the models of a module: a thumbnail of the gear (photo or drawing) and the
model name for each one, instead of a drop-down list.

Exposes the subset of the ``QComboBox`` interface the module page uses (``count``,
``currentIndex``, ``setCurrentIndex``, ``currentIndexChanged``, ``clear``): indexes count
models only, the section headers (:meth:`add_section`) are not part of them.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QHelpEvent, QIcon, QPainter, QPen, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QListView,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QWidget,
)

from ge150.model.gear import Gear
from ge150.ui.gear_art import KnobState, render_pixmap
from ge150.ui.gear_view import load_photo
from ge150.ui.theme import BORDER, MUTED

ICON = QSize(104, 78)
CELL = QSize(124, 118)
SECTION_HEIGHT = 30
SECTION_ROLE = Qt.ItemDataRole.UserRole + 1


def thumbnail(gear: Gear, title: str, knobs: list[KnobState], ratio: float) -> QPixmap:
    photo = load_photo(gear.gid)
    if photo is not None:
        scaled = photo.scaled(ICON * ratio, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(ratio)
        return scaled
    return render_pixmap(gear, ICON, title, knobs, True, ratio)


class _Delegate(QStyledItemDelegate):
    """Section headers: the title in small capitals and a line to the right."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: QModelIndex | QPersistentModelIndex) -> None:
        title = index.data(SECTION_ROLE)
        if not title:
            super().paint(painter, option, index)
            return
        painter.save()
        rect = option.rect.adjusted(4, 0, -4, 0)
        font = QFont(option.font)
        font.setPixelSize(10)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        painter.setFont(font)
        painter.setPen(QColor(MUTED))
        text = str(title).upper()
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(rect, flags, text)
        width = painter.fontMetrics().horizontalAdvance(text)
        y = rect.center().y() + 1
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(rect.left() + width + 10, y, rect.right(), y)
        painter.restore()


class ModelGallery(QListWidget):
    currentIndexChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("modelGallery")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWrapping(True)
        # No grid: a section header takes a whole row, the models flow around it.
        self.setIconSize(ICON)
        self.setSpacing(4)
        self.setItemDelegate(_Delegate(self))
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(CELL.height() * 2 + 16)
        self.currentRowChanged.connect(self._row_changed)
        self._silent = False
        self._rows: list[int] = []  # model index -> row (headers have rows too; -1 = hidden)
        #: model index -> text added to its tooltip when hovered (worked out at that moment)
        self.tooltip_extra: Callable[[int], str] | None = None

    def add_model(self, label: str, gear: Gear, title: str, knobs: list[KnobState],
                  tooltip: str = "") -> None:
        ratio = self.devicePixelRatioF() or 1.0
        item = QListWidgetItem(QIcon(thumbnail(gear, title, knobs, ratio)), label)
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        item.setToolTip(tooltip or label)
        item.setSizeHint(CELL)
        self._rows.append(self.count_rows())
        self.addItem(item)

    def skip_model(self) -> None:
        """A model that is not shown (keeps the indexes of the next ones)."""
        self._rows.append(-1)

    def add_section(self, title: str) -> None:
        """A header across the whole width, e.g. before the user IR slots."""
        item = QListWidgetItem()
        item.setData(SECTION_ROLE, title)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(self._section_size())
        self.addItem(item)

    def count_rows(self) -> int:
        return super().count()

    def _section_size(self) -> QSize:
        width = self.viewport().width() - 2 * self.spacing() - 2
        return QSize(max(width, CELL.width()), SECTION_HEIGHT)

    def sections(self) -> list[str]:
        return [str(self.item(r).data(SECTION_ROLE)) for r in range(self.count_rows())
                if self.item(r).data(SECTION_ROLE)]

    # --- QComboBox-like interface -----------------------------------------------------

    def clear(self) -> None:
        self._silent = True
        try:
            super().clear()
            self._rows = []
        finally:
            self._silent = False

    def count(self) -> int:
        return len(self._rows)

    def model_item(self, index: int) -> QListWidgetItem | None:
        return self.item(self._rows[index]) if 0 <= index < len(self._rows) else None

    def currentIndex(self) -> int:
        row = self.currentRow()
        return self._rows.index(row) if row >= 0 and row in self._rows else -1

    def setCurrentIndex(self, index: int) -> None:
        row = self._rows[index] if 0 <= index < len(self._rows) else -1
        self.setCurrentRow(row)
        item = self.item(row)
        if item is not None:
            self.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
            # Again once the grid is laid out (right after filling it the rows are unknown).
            QTimer.singleShot(0, lambda: self._scroll_to(row))

    def _scroll_to(self, row: int) -> None:
        item = self.item(row)
        if item is not None and self.currentRow() == row:
            self.doItemsLayout()  # the grid is laid out lazily: place the items first
            self.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        size = self._section_size()
        for row in range(self.count_rows()):
            item = self.item(row)
            if item.data(SECTION_ROLE) and item.sizeHint() != size:
                item.setSizeHint(size)
        QTimer.singleShot(0, lambda: self._scroll_to(self.currentRow()))

    def viewportEvent(self, event: QEvent) -> bool:
        if isinstance(event, QHelpEvent) and self.tooltip_extra is not None:
            item = self.itemAt(event.pos())
            row = self.row(item) if item is not None else -1
            if item is not None and row in self._rows:
                extra = self.tooltip_extra(self._rows.index(row))
                text = item.toolTip() + (f"\n\n{extra}" if extra else "")
                QToolTip.showText(event.globalPos(), text, self.viewport())
                return True
        return super().viewportEvent(event)

    def currentText(self) -> str:
        item = self.currentItem()
        return item.text() if item else ""

    def _row_changed(self, row: int) -> None:
        if not self._silent:
            self.currentIndexChanged.emit(
                self._rows.index(row) if row >= 0 and row in self._rows else -1)
