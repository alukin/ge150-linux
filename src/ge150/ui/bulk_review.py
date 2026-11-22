"""«Cambios pendientes»: stored-preset changes (from the AI or the form) waiting for review.

One row per preset with a check box, its changes per module (before → after) and any
warning underneath. «Aplicar» writes the ticked presets on the runner thread; «Deshacer
última edición» writes back the versions saved before (the click is the confirmation).
"""

from __future__ import annotations

import html
from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ge150.model.preset import Preset
from ge150.services import bulk_edit
from ge150.services.bulk_edit import PresetEdit
from ge150.services.editor import Editor
from ge150.ui.worker import TaskRunner

WARN, BLOCKED, MUTED = "#f0c860", "#ff8a80", "#8b95a3"


class BulkReview(QWidget):
    #: a message for the user (status line of the tab)
    message = Signal(str)

    def __init__(self, editor: Editor, runner: TaskRunner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor, self.runner = editor, runner
        self.edits: dict[int, PresetEdit] = {}
        self.previous: list[Preset] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        title = QLabel("Cambios pendientes")
        title.setObjectName("cardTitle")
        self.badge = QLabel()
        self.badge.setObjectName("countBadge")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.badge)
        layout.addLayout(head)
        self.summary = QLabel()
        self.summary.setObjectName("note")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tree = QTreeWidget()
        self.tree.setObjectName("bulkTree")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Preset / módulo", "Antes", "Después"])
        self.tree.setIndentation(0)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(False)
        self.tree.setWordWrap(True)
        header = self.tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.itemChanged.connect(lambda *_: self._count())
        layout.addWidget(self.tree, 1)
        self.empty = QLabel("<p style='font-size:28px; margin:0'>⇄</p>"
                            "<p><b>Sin cambios pendientes</b></p>"
                            "<p>Lo que propone la IA o armas en la edición manual aparece aquí, "
                            "preset por preset, con el valor de antes y el de después.</p>"
                            "<p>Nada se escribe en la pedalera hasta que aprietes "
                            "<b>Aplicar</b>.</p>")
        self.empty.setObjectName("emptyState")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty, 1)
        row = QHBoxLayout()
        self.discard = QPushButton("Descartar")
        self.discard.clicked.connect(self.clear)
        self.apply_button = QPushButton("Aplicar")
        self.apply_button.setObjectName("saveButton")
        self.apply_button.clicked.connect(self.apply)
        row.addWidget(self.discard)
        row.addStretch(1)
        row.addWidget(self.apply_button)
        layout.addLayout(row)
        self.undo_button = QPushButton("↶  Deshacer la última edición aplicada")
        self.undo_button.setObjectName("linkButton")
        self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_button.setToolTip("Vuelve a escribir los presets como estaban antes de aplicar")
        self.undo_button.clicked.connect(self.undo)
        layout.addWidget(self.undo_button, 0, Qt.AlignmentFlag.AlignRight)
        runner.busy_changed.connect(lambda _: self._count())
        self._render()

    # --- content ----------------------------------------------------------------------

    def bases(self) -> dict[int, list[int]]:
        """Planned words per preset: a new change for the same preset adds to these."""
        return {slot: edit.after for slot, edit in self.edits.items() if not edit.blocked}

    def add(self, edits: Sequence[PresetEdit], summary: str = "") -> None:
        for edit in edits:
            if edit.changed or edit.blocked:
                self.edits[edit.slot] = edit
        if summary:
            self.summary.setText(html.escape(summary))
        self._render()

    def clear(self) -> None:
        self.edits.clear()
        self.summary.setText("")
        self._render()

    def chosen(self) -> list[PresetEdit]:
        result = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            edit = self.edits.get(int(item.data(0, Qt.ItemDataRole.UserRole)))
            if (edit is not None and not edit.blocked
                    and item.checkState(0) == Qt.CheckState.Checked):
                result.append(edit)
        return result

    def _render(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        for slot in sorted(self.edits):
            edit = self.edits[slot]
            top = QTreeWidgetItem([f"{slot:03d}  {edit.name}"])
            top.setData(0, Qt.ItemDataRole.UserRole, slot)
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            top.setFirstColumnSpanned(True)
            if edit.blocked:
                top.setDisabled(True)
            else:
                top.setFlags(top.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                top.setCheckState(0, Qt.CheckState.Checked)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            for module, before, after in bulk_edit.diff(self.editor, edit.before, edit.after):
                child = QTreeWidgetItem(["    " + module, before, after])
                child.setForeground(1, QBrush(QColor(MUTED)))
                self.tree.addTopLevelItem(child)
                child.setData(0, Qt.ItemDataRole.UserRole, slot)
                child.setFlags(Qt.ItemFlag.ItemIsEnabled)
            notes = ([(edit.blocked, BLOCKED)] if edit.blocked else []) + \
                [(w, WARN) for w in edit.warnings]
            for text, colour in notes:
                child = QTreeWidgetItem(["    ⚠ " + text])
                child.setForeground(0, QBrush(QColor(colour)))
                child.setData(0, Qt.ItemDataRole.UserRole, slot)
                child.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.tree.addTopLevelItem(child)
                child.setFirstColumnSpanned(True)
        self.tree.blockSignals(False)
        self.empty.setVisible(not self.edits)
        self.tree.setVisible(bool(self.edits))
        self._count()

    def _count(self) -> None:
        chosen = len(self.chosen())
        busy = self.runner.busy
        self.apply_button.setText(f"Aplicar a {chosen} preset{'s' * (chosen != 1)}")
        self.apply_button.setEnabled(chosen > 0 and not busy)
        self.badge.setText(f"{len(self.edits)} preset{'s' * (len(self.edits) != 1)}"
                           if self.edits else "")
        self.badge.setProperty("on", bool(self.edits))
        self.badge.setVisible(bool(self.edits))
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.undo_button.setVisible(bool(self.previous))
        self.discard.setEnabled(bool(self.edits) and not busy)
        self.undo_button.setEnabled(bool(self.previous) and not busy)

    # --- writing ----------------------------------------------------------------------

    def apply(self) -> None:
        chosen = self.chosen()
        if not chosen:
            return
        self.message.emit(f"Escribiendo {len(chosen)} presets…")

        def done(result: bulk_edit.Applied) -> None:
            self.previous = result.previous
            for preset in result.previous:
                self.edits.pop(preset.slot, None)
            skipped = "; ".join(f"{slot:03d}: {why}" for slot, why in result.skipped)
            self.message.emit(f"Listo: {len(result.previous)} presets escritos."
                              + (f" No se escribieron: {skipped}" if skipped else ""))
            self._render()

        self.runner.run(lambda: bulk_edit.apply(self.editor, chosen), done, self._failed)

    def undo(self) -> None:
        previous = self.previous
        if not previous:
            return

        def done(slots: list[int]) -> None:
            self.previous = []
            self.message.emit(f"Restaurados: {', '.join(f'{s:03d}' for s in slots)}.")
            self._count()

        self.runner.run(lambda: bulk_edit.restore(self.editor, previous), done, self._failed)

    def _failed(self, error: str) -> None:
        self.message.emit(f"Error: {error}")
        self._count()
