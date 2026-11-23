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
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))  # guitars, TONE3000 session
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))  # AI conversations, IR sources
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


def test_user_slots_have_their_own_section(window: MainWindow) -> None:
    gallery = window.module_editor.model
    window.chain.select(3)  # CAB: 36 models, 27-36 are user IR slots
    assert gallery.count() == 36 and gallery.count_rows() == 38
    assert gallery.sections() == ["Modelos de la pedalera",
                                  "Tus IR · ranuras de usuario (TONE3000 y otras)"]
    first_user = gallery.model_item(26)
    assert first_user is not None and first_user.text().startswith("27:")
    gallery.setCurrentIndex(30)
    assert gallery.currentIndex() == 30
    sim = window.sim  # type: ignore[attr-defined]
    assert wait(lambda: sim.device.edit_buffer.module(3).type == 30)
    window.chain.select(8)  # REVERB: no user slots, no headers
    assert gallery.sections() == [] and gallery.count() == gallery.count_rows()
    window.chain.select(2)  # AMP: the NR slots 56-65 are hidden, indexes stay
    assert gallery.sections() == [] and gallery.count() == 65 and gallery.count_rows() == 55
    assert gallery.model_item(54) is not None and gallery.model_item(55) is None
    gallery.setCurrentIndex(60)
    assert gallery.currentIndex() == -1


def test_user_ir_tooltip_lists_the_presets_using_it(window: MainWindow) -> None:
    editor, page = window.editor, window.module_editor
    cab = 3
    preset = editor.state.presets[7].copy()
    block = preset.module(cab)
    block.words[1] = 27  # CAB 28: user IR slot 2
    preset.set_module(block)
    editor.copy_preset_data(preset)
    window.chain.select(cab)
    text = page._model_users(27)
    assert text.startswith("Usada en:") and "007" in text
    assert page._model_users(28) == "No la usa ningún preset."
    assert page._model_users(0) == ""  # a factory cabinet: no list


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


def test_discard_button_restores_the_saved_preset(window: MainWindow) -> None:
    assert window.discard_button.isHidden()
    saved = list(window.state.presets[1].words)
    window.chain.select(8)  # REVERB
    window.module_editor.params[1].setValue(7)
    assert wait(lambda: window.state.dirty)
    assert not window.discard_button.isHidden()
    window.discard_button.click()
    assert wait(lambda: not window.state.dirty and window.discard_button.isHidden())
    sim = window.sim  # type: ignore[attr-defined]
    assert window.state.edit.words == saved  # type: ignore[union-attr]
    assert sim.device.edit_buffer.words == saved


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


def test_ai_panel_sends_the_selected_preset_unless_unticked(window: MainWindow) -> None:
    sim = window.sim  # type: ignore[attr-defined]
    sim.inject(sim.device.footswitch(11))
    assert wait(lambda: "011" in window.ai_panel.body.context.text())
    message = window.ai_panel.body._with_context("más ganancia")
    assert message.startswith("[Contexto: preset seleccionado 11") and "AMP:" in message
    assert message.endswith("más ganancia")
    window.ai_panel.body.context.setChecked(False)
    assert "no incluido" in window.ai_panel.body.context.text()
    assert window.ai_panel.body._with_context("más ganancia") == "más ganancia"


def test_ai_panel_compares_original_and_suggested_sound(window: MainWindow) -> None:
    panel = window.ai_panel.body
    editor = window.editor
    before = list(editor.state.edit.words)  # type: ignore[union-attr]
    panel._before = list(before)
    panel.busy = True
    panel.host.tools.set_module("DS", not editor.module(1).switch)  # what the AI would do
    after = list(editor.state.edit.words)  # type: ignore[union-attr]
    panel._finished("Listo", "")
    assert panel.compare.isVisibleTo(panel) and panel.compare.suggested.isChecked()
    panel.compare.original.click()
    assert wait(lambda: editor.state.edit.words == before)  # type: ignore[union-attr]
    assert wait(lambda: panel.compare.original.isChecked() and panel.compare.isEnabled())
    panel.compare.suggested.click()
    assert wait(lambda: editor.state.edit.words == after)  # type: ignore[union-attr]
    sim = window.sim  # type: ignore[attr-defined]
    sim.inject(sim.device.footswitch(12))
    assert wait(lambda: not panel.compare.isVisibleTo(panel))


def test_original_sound_is_the_saved_preset(window: MainWindow) -> None:
    panel, editor = window.ai_panel.body, window.editor
    saved = list(window.state.presets[window.state.current_slot].words)  # type: ignore[index]

    def ai_turn(module: str) -> None:  # what the panel does around one AI request
        panel.prompt.setPlainText("algo")
        panel._agent = lambda: type("A", (), {"name": "X", "ask": lambda s, m: "ok"})()  # type: ignore[method-assign,assignment]
        panel.ask()
        panel.host.tools.set_module(module, not editor.module(MODULES_INDEX[module]).switch)
        assert wait(lambda: not panel.busy)

    ai_turn("DS")
    ai_turn("MOD")  # a second suggestion on top of the first one
    assert panel.compare.isVisibleTo(panel)
    panel.compare.original.click()
    assert wait(lambda: editor.state.edit.words == saved)  # type: ignore[union-attr]
    assert wait(panel.compare.isEnabled)  # the switch has finished
    panel.compare.suggested.click()
    assert wait(lambda: editor.state.edit.words != saved)  # type: ignore[union-attr]
    assert wait(panel.compare.isEnabled)
    editor.save()  # keeping the suggestion: nothing left to compare
    assert wait(lambda: not panel.compare.isVisibleTo(panel))


MODULES_INDEX = {"DS": 1, "MOD": 6}


def test_assistant_tab_plans_reviews_and_applies(window: MainWindow) -> None:
    page = window.assistant
    state = window.editor.state
    assert page.list.count() == 200
    page.filter.setText("PRESET 02")  # 020..029 visible
    assert wait(lambda: not page.list.item(21).isHidden() and page.list.item(40).isHidden())
    page.tick([22, 23])
    assert page.ticked() == [22, 23] and "22" in page._context()
    page.form.select_module(8)  # REVERB
    page.form.select_state("off")
    assert "Apagar REVERB" in page.form.summary.text() and page.form.add_button.isEnabled()
    before = {s: list(state.presets[s].words) for s in (22, 23)}
    on = {s: state.presets[s].module(8).switch for s in (22, 23)}
    page.form.plan()
    planned = [s for s in (22, 23) if on[s]]  # only presets with the REVERB on change
    assert sorted(page.review.edits) == planned
    assert all(state.presets[s].words == before[s] for s in (22, 23))  # nothing written yet
    if not planned:
        return
    page.review.apply()
    assert wait(lambda: not page.review.edits and page.review.undo_button.isEnabled())
    assert "Backup previo: " in page.status.text()
    from ge150.services.auto_backup import backup_dir
    assert len(list(backup_dir().glob("auto-*-aplicar.mbf"))) == 1
    assert all(not state.presets[s].module(8).switch for s in planned)
    page.review.undo()
    assert wait(lambda: all(state.presets[s].words == before[s] for s in (22, 23)))


def test_ai_proposal_opens_the_assistant_tab(window: MainWindow) -> None:
    tools = window.ai_host.tools
    on = window.editor.state.presets[30].module(1).switch
    tools.propose_preset_edits([{"slot": 30, "modules": [{"module": "DS", "on": not on}]}],
                               "DS al revés")
    assert wait(lambda: window.tabs.currentWidget() is window.assistant)
    assert 30 in window.assistant.review.edits and 30 in window.assistant.ticked()


def test_reopened_conversation_brings_back_ticks_and_pending(window: MainWindow) -> None:
    page, tools = window.assistant, window.ai_host.tools
    chat = page.chat
    chat.chat_id, chat.chat_title = "opeth-1", "Opeth"
    page.tick([18, 19, 20, 21], only=True)
    tools.propose_preset_edits([{"slot": 18, "name": "OPETH CLEAN"}], "Opeth")
    assert wait(lambda: 18 in page.review.edits)
    chat._save()
    chat.new_conversation()  # what changes now is not kept with «opeth-1»
    page.review.clear()
    page.tick([5], only=True)
    chat.open_chat("opeth-1")
    assert page.ticked() == [18, 19, 20, 21]
    assert page.review.edits[18].final_name == "OPETH CLEAN"
    assert page.review.summary_text == "Opeth"


def test_agent_steps_and_working_indicator(window: MainWindow) -> None:
    chat = window.assistant.chat
    chat._set_busy(True, "Claude está trabajando…")
    assert chat.working.isVisibleTo(chat) and chat.working.running
    for tool in ("get_catalog", "get_catalog", "get_catalog", "get_presets"):
        chat._tool_called(tool)
    assert "revisa el catálogo \u00d73" in chat.blocks[-2] and "\u2713" in chat.blocks[-2]
    assert "lee varios presets" in chat.blocks[-1] and "\u2713" not in chat.blocks[-1]
    assert "lee varios presets" in chat.working.label.text()
    chat._finished("| A | B |\n|---|---|\n| 1 | **2** |", "")
    assert not chat.working.running and "\u2713" in chat.blocks[-2]
    assert "<table" in chat.blocks[-1] and "<strong>2</strong>" in chat.blocks[-1]


def test_assistant_preset_rows_tick_on_click(window: MainWindow) -> None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    page = window.assistant
    window.tabs.setCurrentWidget(page)
    page.list.scrollToTop()
    item = page.list.item(4)
    rect = page.list.visualItemRect(item)
    name = QPoint(rect.center().x(), rect.center().y())  # on the name, not the box
    QTest.mouseClick(page.list.viewport(), Qt.MouseButton.LeftButton, pos=name)
    assert item.checkState() == Qt.CheckState.Checked and page.ticked() == [5]
    QTest.mouseClick(page.list.viewport(), Qt.MouseButton.LeftButton, pos=name)
    assert item.checkState() == Qt.CheckState.Unchecked and page.ticked() == []
    assert not page.list.selectedItems()
    box = QPoint(rect.left() + 14, rect.center().y())  # on the check box itself: once
    QTest.mouseClick(page.list.viewport(), Qt.MouseButton.LeftButton, pos=box)
    assert item.checkState() == Qt.CheckState.Checked


def test_assistant_chat_shows_the_ticked_presets(window: MainWindow) -> None:
    page = window.assistant
    assert page.ticks_chip.text() == "Sin presets marcados"
    page.tick([22, 23, 24, 26])
    assert page.ticks_chip.text() == "Presets marcados: 022, 023, 024 +1"
    assert "026" in page.ticks_chip.toolTip() and "26" in page._context()
    page.ticks_chip.setChecked(False)
    assert "no incluidos" in page.ticks_chip.text() and page._context() == ""
    assert "Presets marcados" not in page.chat._with_context("hola")


def test_chat_history_reopens_a_conversation_and_its_preset(window: MainWindow,
                                                             monkeypatch: pytest.MonkeyPatch,
                                                             tmp_path: "os.PathLike[str]") -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    from ge150.services.chat_history import ChatStore

    chat = window.ai_panel.body
    chat.store = chat.history.store = ChatStore()
    agent = type("A", (), {"name": "Claude", "session": "sess-1", "reset": lambda s: None,
                           "ask": lambda s, m: "Listo, más ganancia."})()
    chat.agents = {"claude": agent}  # type: ignore[dict-item]
    chat._agent = lambda: agent  # type: ignore[method-assign,assignment]
    window.presets.activated.emit(11)
    assert wait(lambda: window.editor.state.current_slot == 11)
    chat.prompt.setPlainText("más ganancia")
    chat.ask()
    assert wait(lambda: not chat.busy)
    saved = chat.store.entries("panel")
    assert len(saved) == 1 and saved[0].title == "más ganancia" and saved[0].slot == 11
    assert chat.store.entries("asistente") == []  # the tab has its own history

    window.presets.activated.emit(30)  # elsewhere, then reopen it
    assert wait(lambda: window.editor.state.current_slot == 30)
    chat.new_conversation()
    assert "más ganancia" not in chat.chat.toPlainText()
    chat.history_button.setChecked(True)
    assert chat.pages.currentWidget() is chat.history
    chat.open_chat(saved[0].id)
    assert "Listo, más ganancia." in chat.chat.toPlainText()
    assert chat.chat_id == saved[0].id and chat.agents["claude"].session == "sess-1"
    assert chat.pages.currentIndex() == 0
    assert wait(lambda: window.editor.state.current_slot == 11)


def test_chat_history_asks_before_dropping_unsaved_changes(window: MainWindow) -> None:
    from ge150.services.chat_history import ChatEntry

    chat = window.ai_panel.body
    editor = window.editor
    block = editor.module(1)
    block.switch = not block.switch
    editor.write_module(block)
    assert editor.state.dirty
    asked: list[str] = []

    def answer(box: QMessageBox) -> int:
        asked.append(box.text())
        box.setProperty("clicked", "cancel")
        return 0

    monkeypatch_exec = QMessageBox.exec
    try:
        QMessageBox.exec = answer  # type: ignore[method-assign,assignment]
        entry = ChatEntry("x", "panel", "t", "claude", 1, 1, 40, "Otro")
        assert chat._ask_switch(entry) is None  # nothing clicked = cancel
    finally:
        QMessageBox.exec = monkeypatch_exec  # type: ignore[method-assign]
    assert "cambios sin guardar" in asked[0] and "040" in asked[0]


def test_a_proposal_is_heard_on_its_own_preset(window: MainWindow) -> None:
    """Pedal on «Solo» (22), the AI changes «Clean» (28): the pedal must play the Clean."""
    editor, review = window.editor, window.assistant.review
    window.presets.activated.emit(22)
    assert wait(lambda: editor.state.current_slot == 22 and not window.runner.busy)
    on = editor.state.presets[28].module(8).switch
    window.ai_host.tools.propose_preset_edits(
        [{"slot": 28, "modules": [{"module": "REVERB", "on": not on}]}], "Clean")
    assert wait(lambda: editor.state.current_slot == 28 and review.playing == 28)
    assert editor.module(8).switch == (not on) and review.bar.isVisibleTo(review)
    assert "028" in review.playing_label.text()
    review.sides.button(0).click()  # «Antes»
    assert wait(lambda: editor.module(8).switch == on and not review.playing_after)
    review.sides.button(1).click()  # «Después»
    assert wait(lambda: editor.module(8).switch == (not on))
    review.clear()  # «Descartar»: back to the saved Clean
    assert wait(lambda: not editor.state.dirty and editor.module(8).switch == on)
    assert not review.bar.isVisibleTo(review)


def test_hearing_a_proposal_asks_before_dropping_own_changes(window: MainWindow,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    editor, review = window.editor, window.assistant.review
    window.presets.activated.emit(22)
    assert wait(lambda: editor.state.current_slot == 22 and not window.runner.busy)
    block = editor.module(1)
    block.switch = not block.switch
    editor.write_module(block)  # the user's own unsaved change on 22
    assert editor.state.dirty
    on = editor.state.presets[28].module(8).switch
    window.ai_host.tools.propose_preset_edits(
        [{"slot": 28, "modules": [{"module": "REVERB", "on": not on}]}])
    assert wait(lambda: 28 in review.edits)
    wait(lambda: False, 200)
    assert editor.state.current_slot == 22 and review.playing is None  # not auto-played
    asked: list[str] = []

    def no(*args: object, **kwargs: object) -> QMessageBox.StandardButton:
        asked.append(str(args[2]))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", no)
    assert not review.listen(28)
    assert "cambios sin guardar" in asked[0] and editor.state.current_slot == 22


def test_chain_tap_led_follows_the_delay_time(window: MainWindow) -> None:
    from ge150.model.gear import MODULE_TAGS

    delay = MODULE_TAGS.index("DELAY")
    editor, chain = window.editor, window.chain
    tap = chain.tiles[delay].tap
    assert tap is not None
    if not editor.module(delay).switch:
        chain.tiles[delay].power.click()
        assert wait(lambda: editor.module(delay).switch)
    window.ai_host.tools.set_module("DELAY", True, "DIGITAL", {"TIME": "500"})
    assert wait(lambda: tap.period == 500)
    assert "120 BPM" in tap.toolTip()
    chain.tiles[delay].power.click()  # delay off: no blinking
    assert wait(lambda: tap.period == 0)


def test_chain_hover_lights_the_cables_of_that_pedal(window: MainWindow) -> None:
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QEnterEvent

    chain = window.chain
    tile = chain.tiles[2]
    QApplication.sendEvent(tile, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    assert wait(lambda: chain.wires[2].lit > 0.9 and chain.wires[3].lit > 0.9)
    assert wait(lambda: tile.view.zoom > 1.0) and chain.wires[1].lit == 0.0
    QApplication.sendEvent(tile, QEvent(QEvent.Type.Leave))
    assert wait(lambda: chain.wires[2].lit < 0.01 and tile.view.zoom == 1.0)


def test_about_dialog_shows_the_project_and_the_system(window: MainWindow) -> None:
    from ge150 import __version__
    from ge150.ui.about_dialog import REPO, AboutDialog, folders

    dialog = AboutDialog(window.state, "simulator", window)
    info = dict(dialog.system_info())
    assert info["Editor"] == __version__ and "V1.3.8" in info["Pedalera"]
    assert info["Conexión"] == "simulator"
    text = dialog.report_text()
    assert __version__ in text and "Qt / PySide6" in text
    assert {name for name, _, _ in folders()} >= {"Backups automáticos", "Conversaciones con la IA"}
    assert "github.com/wh01s17/ge150-linux" in REPO
    dialog.deleteLater()
