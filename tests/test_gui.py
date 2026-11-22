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
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch,
           tmp_path: "os.PathLike[str]") -> Iterator[MainWindow]:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))  # the AI bridge discovery file
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
    widget.setValue(88)
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
    window.module_editor.params[0].setValue(1)
    assert wait(lambda: window.state.dirty)
    window.save_current()
    assert wait(lambda: not window.state.dirty)
    sim = window.sim  # type: ignore[attr-defined]
    assert sim.device.presets[42].words == window.state.edit.words  # type: ignore[union-attr]


def test_pedal_notification_updates_list(window: MainWindow) -> None:
    sim = window.sim  # type: ignore[attr-defined]
    window.presets.select_slot(10)
    sim.inject(sim.device.footswitch(11))
    assert wait(lambda: window.header.text().strip().startswith("11"))
    assert window.number.text() == "011"
    current = window.presets.list.currentItem()
    from ge150.ui.preset_list import SLOT_ROLE

    assert current is not None and current.data(SLOT_ROLE) == 11
    assert window.state.edit.words == sim.device.presets[11].words  # type: ignore[union-attr]


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


def test_cab_microphone_drag_sets_center_and_distance(window: MainWindow) -> None:
    window.chain.select(3)  # CAB
    page = window.module_editor
    assert page.mic.isVisibleTo(page)
    page.mic.moved.emit(0.2, 0.8)
    sim = window.sim  # type: ignore[attr-defined]
    assert wait(lambda: sim.device.edit_buffer.words[19 + 4] == 20)
    assert sim.device.edit_buffer.words[19 + 5] == 80
    window.chain.select(1)  # DS has no microphone
    assert not page.mic.isVisibleTo(page)


def test_gear_pictures_follow_the_model(window: MainWindow) -> None:
    window.chain.select(1)
    window.module_editor.model.setCurrentIndex(1)  # 808
    assert wait(lambda: window.module_editor.view.gear.gid == "ts808")
    assert "TS808" in window.module_editor.based_on.text()
    assert window.chain.tiles[1].view.gear.gid == "ts808"


def test_single_click_loads_preset_and_asks_when_dirty(
        window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    presets = window.presets.list

    def click(slot: int) -> None:
        item = presets.item(slot - 1)
        QTest.mouseClick(presets.viewport(), Qt.MouseButton.LeftButton,
                         pos=presets.visualItemRect(item).center())

    click(5)
    assert wait(lambda: window.state.current_slot == 5)
    window.module_editor.params[0].setValue(3)
    assert wait(lambda: window.state.dirty)
    asked: list[str] = []

    def cancel(*args: object, **kwargs: object) -> QMessageBox.StandardButton:
        asked.append(str(args[2]))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", cancel)
    click(9)
    assert asked and "sin guardar" in asked[0]
    assert window.state.current_slot == 5
    assert window.presets.selected_slot() == 5


def test_ai_clients_drive_the_open_editor(window: MainWindow) -> None:
    import threading

    from ge150.mcp_server.bridge import find_editor

    remote = find_editor()
    assert remote is not None
    results: dict[str, object] = {}

    def client() -> None:  # an AI client, on its own thread like ge150-mcp
        remote.set_module("AMP", True, "PLX100", {"GAIN": "77"})
        results["saved"] = remote.save_preset(30, "AI PLEXI")  # dialog answered "Yes"

    thread = threading.Thread(target=client)
    thread.start()
    assert wait(lambda: not thread.is_alive(), 8000)
    assert results["saved"] == {"saved": True, "slot": 30, "name": "AI PLEXI"}
    assert wait(lambda: "PLX100" in window.chain.tiles[2].model.text())
    assert window.state.presets[30].name == "AI PLEXI"
    window.close()
    assert find_editor() is None
