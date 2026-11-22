"""Page of one module of the edit buffer: picture of the gear, on/off, model and knobs.

Knob moves are coalesced (``DEBOUNCE_MS``) and sent as one full module block, like the
vendor editor does.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ge150.model.catalog import ModuleInfo
from ge150.model.gear import FALLBACK, describe, gear_for
from ge150.model.preset import MODULES, ModuleBlock
from ge150.services.editor import Editor
from ge150.ui.gear_art import KnobState
from ge150.ui.gear_view import GearView, load_photo, module_look
from ge150.ui.knob import EnumControl, Knob, make_control
from ge150.ui.mic_view import MicPlacement
from ge150.ui.model_gallery import ModelGallery

DEBOUNCE_MS = 40
USER_SLOT_GEAR = ("c_user", "user_nr")
COLUMNS = 4


class ModuleEditor(QFrame):
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
        self.setObjectName("modulePage")

        self.view = GearView()
        self.view.setMinimumSize(260, 260)
        self.based_on = QLabel()
        self.based_on.setObjectName("basedOn")
        self.based_on.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.based_on.setWordWrap(True)
        left = QVBoxLayout()
        left.addWidget(self.view, 1)
        left.addWidget(self.based_on)

        self.title = QLabel(MODULES[0].name)
        self.title.setObjectName("moduleTitle")
        self.switch = QPushButton("OFF")
        self.switch.setObjectName("bigPower")
        self.switch.setCheckable(True)
        self.switch.setFixedWidth(78)
        self.switch.toggled.connect(self._on_switch)
        self.model = ModelGallery()
        self.model.currentIndexChanged.connect(self._on_model)
        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.switch)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(14)
        self.note = QLabel()
        self.note.setObjectName("note")
        self.note.setWordWrap(True)
        self.mic = MicPlacement()
        self.mic.hide()
        self.mic.moved.connect(self._on_mic_moved)
        self._mic_controls: tuple[Knob, Knob, EnumControl | None] | None = None
        right = QVBoxLayout()
        right.addLayout(header)
        right.addWidget(self.model, 1)
        right.addSpacing(8)
        right.addLayout(self.grid)
        right.addSpacing(8)
        right.addWidget(self.mic)
        right.addWidget(self.note)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(22)
        layout.addLayout(left, 5)
        layout.addLayout(right, 6)
        self.params: list[Knob | EnumControl] = []

    # --- loading -------------------------------------------------------------

    @property
    def info(self) -> ModuleInfo:
        return self.editor.catalog[self.index]

    def show_module(self, index: int) -> None:
        if self._pending:
            self._flush()
        self.index = index
        self.title.setText(MODULES[index].name)
        self._loading = True
        try:
            self.model.clear()
            for i, m in enumerate(self.info.models):
                label = self.editor.model_label(index, i)
                gear = gear_for(index, m.number)
                title = label.split(":", 1)[-1].strip() if m.user_slot else m.name
                knobs = [KnobState(p.name, 0.5) for p in m.params if p.kind == "number"]
                based = "\n" + describe(gear, load_photo(gear.gid) is not None)
                self.model.add_model(label, gear, title, knobs,
                                     label + (" (ranura de usuario)" if m.user_slot else "")
                                     + based)
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
            self._show_switch(bool(block.switch))
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
        self._update_view()
        self._update_mic(animate=True)

    def _show_switch(self, on: bool) -> None:
        self.switch.setChecked(on)
        self.switch.setText("ON" if on else "OFF")

    def _update_view(self) -> None:
        gear, title, knobs, on = module_look(self.editor, self.index)
        self.view.set_gear(gear, title, knobs, on)
        has_photo = self.view.photo is not None
        caption = "" if gear is FALLBACK else describe(gear, has_photo)
        if gear.gid in USER_SLOT_GEAR:
            caption = f"{gear.name}: {title}" + self._ir_origin()
        self.based_on.setText(caption)

    def _ir_origin(self) -> str:
        """" · TONE3000: author (licence)" for a user CAB slot that came from TONE3000."""
        names = self.editor.state.user_names
        model = self.info.model_for_type(self.editor.module(self.index).type)
        if names is None or model is None or not 27 <= model.number <= 36:
            return ""
        from ge150.services.tone3000 import IrSources

        source = IrSources().matching(names.ir).get(str(model.number - 26))
        return f"  ·  TONE3000: {source['author']} ({source['license']})" if source else ""

    def _build_params(self, block: ModuleBlock) -> None:
        for widget in self.params:
            self.grid.removeWidget(widget)
            widget.hide()
            widget.setParent(None)  # detach now: deleteLater alone leaves it painted
            widget.deleteLater()
        self.params = []
        model = self.info.model_for_type(block.type)
        for i, param in enumerate(model.params if model else ()):
            widget = make_control(param, block.words[param.word])
            widget.raw_changed.connect(self._on_param)
            self.grid.addWidget(widget, i // COLUMNS, i % COLUMNS)
            self.params.append(widget)
        self._setup_mic()
        user = ""
        if model is not None and model.user_slot:
            user = ("Ranura de usuario: el IR/NR cargado en la pedalera. "
                    "Cárgalas desde la pestaña TONE3000 o en Herramientas → IR de usuario.")
        self.note.setText(user)

    # --- user actions --------------------------------------------------------

    def _send(self, block: ModuleBlock) -> None:
        try:
            self.editor.write_module(block)
        except Exception as exc:  # session closed, ...
            self.error.emit(str(exc))
        self._update_view()

    def _on_switch(self, on: bool) -> None:
        self.switch.setText("ON" if on else "OFF")
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
        self._update_view()

    def _on_param(self, word: int, raw: int) -> None:
        self._pending[word] = raw
        self._timer.start()
        if self._mic_controls and word in (c.word for c in self._mic_controls if c):
            self._update_mic(animate=True)

    # --- microphone (CAB) ------------------------------------------------------

    def _setup_mic(self) -> None:
        by_name = {w.param.name: w for w in self.params}
        center, distance = by_name.get("CENTER"), by_name.get("DISTANCE")
        mic = by_name.get("MIC")
        if isinstance(center, Knob) and isinstance(distance, Knob):
            self._mic_controls = (center, distance, mic if isinstance(mic, EnumControl) else None)
            self.mic.show()
            self._update_mic(animate=False)
        else:
            self._mic_controls = None
            self.mic.hide()

    def _update_mic(self, animate: bool) -> None:
        if self._mic_controls is None:
            return
        center, distance, mic = self._mic_controls
        self.mic.set_values(center.fraction(), distance.fraction(), animate)
        self.mic.set_labels(mic.combo.currentText() if mic else "", center.text(), distance.text())

    def _on_mic_moved(self, center: float, distance: float) -> None:
        if self._mic_controls is None:
            return
        center_knob, distance_knob, mic = self._mic_controls
        for knob, fraction in ((center_knob, center), (distance_knob, distance)):
            knob.setValue(knob.minimum + round(fraction * (knob.maximum - knob.minimum)))
        self.mic.set_labels(mic.combo.currentText() if mic else "", center_knob.text(),
                            distance_knob.text())

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
