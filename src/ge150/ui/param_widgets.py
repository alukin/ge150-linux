"""One widget per catalogue parameter: slider + spin box, or a combo box for enums."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QWidget,
)

from ge150.model.catalog import Param


class ParamWidget(QWidget):
    """Edits one raw word. Emits ``raw_changed(word, raw)`` on user changes only."""

    raw_changed = Signal(int, int)

    def __init__(self, param: Param, raw: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.param = param
        self._updating = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(param.name)
        label.setMinimumWidth(90)
        layout.addWidget(label)
        self.combo: QComboBox | None = None
        self.slider: QSlider | None = None
        self.spin: QDoubleSpinBox | None = None
        if param.kind == "enum":
            self.combo = QComboBox()
            self.combo.addItems(list(param.options))
            self.combo.currentIndexChanged.connect(self._from_combo)
            layout.addWidget(self.combo, 1)
        else:
            numeric = param.kind == "number"
            self.slider = QSlider(Qt.Orientation.Horizontal)
            self.slider.setRange(param.to_raw(param.min) if numeric else 0,
                                 param.raw_max if numeric else 0xFFFF)
            self.slider.valueChanged.connect(self._from_slider)
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(param.decimals)
            self.spin.setSingleStep(param.step)
            if numeric:
                self.spin.setRange(param.min, param.max)
            else:
                self.spin.setRange(0, 0xFFFF)
            if param.unit:
                self.spin.setSuffix(f" {param.unit}")
            self.spin.setKeyboardTracking(False)
            self.spin.valueChanged.connect(self._from_spin)
            layout.addWidget(self.slider, 1)
            layout.addWidget(self.spin)
        self.set_raw(raw)

    @property
    def word(self) -> int:
        return self.param.word

    def set_raw(self, raw: int) -> None:
        """Update the display without emitting ``raw_changed``."""
        self._updating = True
        try:
            if self.combo is not None:
                self.combo.setCurrentIndex(raw if 0 <= raw < self.combo.count() else -1)
            elif self.slider is not None and self.spin is not None:
                self.slider.setValue(raw)
                value = self.param.from_raw(raw) if self.param.kind == "number" else raw
                self.spin.setValue(float(value))
        finally:
            self._updating = False

    def _emit(self, raw: int) -> None:
        if not self._updating:
            self.raw_changed.emit(self.param.word, raw)

    def _from_combo(self, index: int) -> None:
        if index >= 0:
            self._emit(index)

    def _from_slider(self, raw: int) -> None:
        if self._updating or self.spin is None:
            return
        self._updating = True
        value = self.param.from_raw(raw) if self.param.kind == "number" else raw
        self.spin.setValue(float(value))
        self._updating = False
        self._emit(raw)

    def _from_spin(self, value: float) -> None:
        if self._updating or self.slider is None:
            return
        raw = self.param.to_raw(value) if self.param.kind == "number" else int(value)
        self._updating = True
        self.slider.setValue(raw)
        self._updating = False
        self._emit(raw)
