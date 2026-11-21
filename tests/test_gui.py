"""GUI smoke tests (offscreen Qt + simulator)."""

import os
import time
from collections.abc import Callable, Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ge150.protocol.session import DeviceSession  # noqa: E402
from ge150.services.editor import Editor  # noqa: E402
from ge150.sim.sim_transport import SimTransport  # noqa: E402
from ge150.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[MainWindow]:
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    sim = SimTransport()
    session = DeviceSession(sim, frame_delay=0, multipart_delay=0).start()
    win = MainWindow(Editor(session), session)
    win.sim = sim  # type: ignore[attr-defined]
    win.start_sync()
    assert wait(lambda: win.central.isEnabled())
    yield win
    win.close()
    session.close()


def wait(predicate: Callable[[], bool], timeout_ms: int = 3000) -> bool:
    for _ in range(timeout_ms // 10):
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    QCoreApplication.processEvents()
    return predicate()


def test_sync_populates_widgets(window: MainWindow) -> None:
    assert window.presets.list.count() == 200
    assert "PRESET 001" in window.header.text()
    assert window.chain.tiles[0].model.text().startswith("02:")
    assert window.module_editor.model.count() == 8


def test_editing_a_parameter_reaches_the_pedal(window: MainWindow) -> None:
    window.chain.select(8)  # REVERB
    widget = window.module_editor.params[1]  # LEVEL
    assert widget.slider is not None
    widget.slider.setValue(88)
    sim = window.sim  # type: ignore[attr-defined]
    assert wait(lambda: sim.device.edit_buffer.words[60 + 3] == 88)
    assert "(modificado)" in window.header.text()


def test_changing_the_model_rebuilds_parameters(window: MainWindow) -> None:
    window.chain.select(7)  # DELAY
    window.module_editor.model.setCurrentIndex(8)  # DUAL DELAY
    sim = window.sim  # type: ignore[attr-defined]
    assert wait(lambda: sim.device.edit_buffer.module(7).type == 8)
    assert [w.param.name for w in window.module_editor.params][-2:] == ["TIME B", "SUB B"]


def test_power_button_switches_module(window: MainWindow) -> None:
    tile = window.chain.tiles[1]
    before = tile.power.isChecked()
    tile.power.click()
    sim = window.sim  # type: ignore[attr-defined]
    assert wait(lambda: bool(sim.device.edit_buffer.module(1).switch) != before)


def test_load_and_save_preset(window: MainWindow) -> None:
    window.load_preset(42)
    assert wait(lambda: "PRESET 042" in window.header.text())
    assert window.state.current_slot == 42
    window.chain.select(0)
    window.module_editor.params[0].slider.setValue(1)  # type: ignore[union-attr]
    assert wait(lambda: window.state.dirty)
    window.save_current()
    assert wait(lambda: not window.state.dirty)
    sim = window.sim  # type: ignore[attr-defined]
    assert sim.device.presets[42].words == window.state.edit.words  # type: ignore[union-attr]


def test_pedal_notification_updates_list(window: MainWindow) -> None:
    sim = window.sim  # type: ignore[attr-defined]
    sim.inject(sim.device.footswitch(9))
    assert wait(lambda: window.header.text().strip().startswith("9"))


def test_settings_dialog_writes_to_pedal(window: MainWindow) -> None:
    from ge150.protocol.opcodes import Op
    from ge150.ui.settings_dialog import SettingsDialog

    device = window.sim.device  # type: ignore[attr-defined]
    dialog = SettingsDialog(window.editor, window)
    assert dialog.input_level.currentText() == "0 dB" and dialog.screen.value() == 20
    dialog.input_level.setCurrentIndex(10)  # 0.5 dB
    dialog.cab_right.setCurrentText("THRU")
    dialog.bpm.setValue(121)
    dialog.style.setValue(5)
    dialog.mode.setCurrentText("METRONOME")
    assert wait(lambda: device.rhythm[1] == 1)
    assert device.system[Op.WRITE_SYSTEM_1] == bytes([10, 0])
    assert device.system[Op.WRITE_SYSTEM_3] == bytes([1, 0, 0, 0])
    assert device.rhythm == bytes([0, 1, 0, 5, 121, 0])  # style restarts with the mode
    assert dialog.style.maximum() == 10
    dialog.close()
