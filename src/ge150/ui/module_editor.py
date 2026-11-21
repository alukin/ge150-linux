"""Editor for one module of the edit buffer: on/off, model and parameters.

Slider moves are coalesced (``DEBOUNCE_MS``) and sent as one full module block, like
the vendor editor does.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ge150.model.catalog import ModuleInfo
from ge150.model.preset import MODULES, ModuleBlock
from ge150.services.editor import Editor
from ge150.ui.param_widgets import ParamWidget

DEBOUNCE_MS = 40


class ModuleEditor(QGroupBox):
    """Emits ``error(str)`` when a command cannot be sent."""

    error = Signal(str)

    def __init__(self, editor: Editor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.index = 0
        self._pending: dict[int, int] = {}
        self._loading = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self._flush)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.switch = QCheckBox("ON")
        self.switch.toggled.connect(self._on_switch)
        self.model = QComboBox()
        self.model.setMinimumWidth(220)
        self.model.currentIndexChanged.connect(self._on_model)
        top.addWidget(self.switch)
        top.addWidget(QLabel("Modelo:"))
        top.addWidget(self.model, 1)
        layout.addLayout(top)
        self.form = QFormLayout()
        layout.addLayout(self.form)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        layout.addStretch(1)
        self.params: list[ParamWidget] = []

    # --- loading -------------------------------------------------------------

    @property
    def info(self) -> ModuleInfo:
        return self.editor.catalog[self.index]

    def show_module(self, index: int) -> None:
        if self._pending:
            self._flush()
        self.index = index
        self.setTitle(MODULES[index].name)
        self._loading = True
        try:
            self.model.clear()
            for i, m in enumerate(self.info.models):
                label = self.editor.model_label(index, i)
                self.model.addItem(label + ("  (usuario)" if m.user_slot else ""))
        finally:
            self._loading = False
        self.refresh()

    def refresh(self) -> None:
        """Re-read the module from the edit buffer (after a notification)."""
        if self.editor.state.edit is None or self._pending:
            return
        block = self.editor.module(self.index)
        self._loading = True
        try:
            self.switch.setChecked(block.switch)
            if self.model.currentIndex() != block.type:
                self.model.setCurrentIndex(block.type if block.type < self.model.count() else -1)
                self._build_params(block)
            elif len(self.params) != len(self.editor.model_params(self.index)):
                self._build_params(block)
            else:
                for widget in self.params:
                    widget.set_raw(block.words[widget.word])
        finally:
            self._loading = False

    def _build_params(self, block: ModuleBlock) -> None:
        for widget in self.params:
            self.form.removeRow(widget)
        self.params = []
        model = self.info.model_for_type(block.type)
        for param in model.params if model else ():
            widget = ParamWidget(param, block.words[param.word])
            widget.raw_changed.connect(self._on_param)
            self.form.addRow(widget)
            self.params.append(widget)
        user = ""
        if model is not None and model.user_slot:
            user = ("Ranura de usuario: el IR/NR cargado en la pedalera. "
                    "Gestiónalas en Herramientas → IR de usuario.")
        self.note.setText(user)

    # --- user actions --------------------------------------------------------

    def _send(self, block: ModuleBlock) -> None:
        try:
            self.editor.write_module(block)
        except Exception as exc:  # session closed, ...
            self.error.emit(str(exc))

    def _on_switch(self, on: bool) -> None:
        if self._loading or self.editor.state.edit is None:
            return
        self._flush()
        block = self.editor.module(self.index)
        block.switch = on
        self._send(block)

    def _on_model(self, type_index: int) -> None:
        if self._loading or type_index < 0 or self.editor.state.edit is None:
            return
        self._pending.clear()
        block = self.editor.module(self.index)
        block.type = type_index
        self._send(block)
        self._loading = True
        try:
            self._build_params(self.editor.module(self.index))
        finally:
            self._loading = False

    def _on_param(self, word: int, raw: int) -> None:
        self._pending[word] = raw
        self._timer.start()

    def _flush(self) -> None:
        self._timer.stop()
        if not self._pending or self.editor.state.edit is None:
            self._pending.clear()
            return
        block = self.editor.module(self.index)
        for word, raw in self._pending.items():
            block.words[word] = raw & 0xFFFF
        self._pending.clear()
        self._send(block)
