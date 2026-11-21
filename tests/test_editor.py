import threading
from collections.abc import Iterator

import pytest

from ge150.formats import wav_ir
from ge150.model import device_state as ds
from ge150.protocol.opcodes import Op
from ge150.protocol.session import DeviceSession
from ge150.services.editor import Editor, EditorError
from ge150.sim.sim_transport import SimTransport


@pytest.fixture
def sim() -> SimTransport:
    return SimTransport()


@pytest.fixture
def editor(sim: SimTransport) -> Iterator[Editor]:
    session = DeviceSession(sim, frame_delay=0, multipart_delay=0)
    with session:
        ed = Editor(session)
        ed.sync()
        yield ed


def wait_for(predicate, timeout: float = 2.0) -> bool:  # type: ignore[no-untyped-def]
    done = threading.Event()
    for _ in range(int(timeout / 0.01)):
        if predicate():
            return True
        done.wait(0.01)
    return predicate()


def test_sync_fills_state(editor: Editor) -> None:
    state = editor.state
    assert state.complete and state.info is not None and state.info.name == "MOOER_GE150"
    assert state.current_slot == 1 and not state.dirty
    assert state.user_names is not None and state.system is not None


def test_set_param_by_name_and_value(editor: Editor, sim: SimTransport) -> None:
    editor.set_type(8, 1)  # REVERB 02:HALL
    raw = editor.set_param(8, "level", 77)
    editor.session.flush()
    reverb = sim.device.edit_buffer.module(8)
    assert raw == 77 and reverb.type == 1 and reverb.words[3] == 77  # LEVEL = param 1 -> word 3
    assert editor.state.edit is not None
    assert editor.state.edit.module(8).words == reverb.words
    assert editor.state.dirty


def test_param_words_follow_vendor_map(editor: Editor, sim: SimTransport) -> None:
    editor.set_type(6, 8)  # MOD 09:PITCH SHIFT -> PITCH lives in word 7
    editor.set_param(6, "PITCH", -12)
    editor.session.flush()
    assert sim.device.edit_buffer.words[42 + 7] == 0
    with pytest.raises(EditorError):
        editor.set_param(6, "DEPTH", 10)
    with pytest.raises(ValueError):
        editor.set_param(6, "MIX", 101)


def test_switch_and_module_names(editor: Editor, sim: SimTransport) -> None:
    for name, index in (("fx", 0), ("DS/OD", 1), ("ns", 4), ("reverb", 8), ("Delay", 7)):
        assert Editor.module_index(name) == index
    editor.set_switch(Editor.module_index("eq"), False)
    editor.session.flush()
    assert sim.device.edit_buffer.words[31] == 0


def test_save_sends_page_then_preset(editor: Editor, sim: SimTransport) -> None:
    editor.set_param(0, editor.model_params(0)[0].name, 3)
    sim.device.received.clear()
    editor.save(name="MY TONE")
    ops = [f.opcode for f in sim.device.received]
    assert ops[-2:] == [Op.SET_PAGE, Op.WRITE_PRESET]
    assert sim.device.received[-2].data == b"\x05\x00"
    assert sim.device.presets[1].name == "MY TONE"
    assert sim.device.presets[1].words == editor.state.edit.words  # type: ignore[union-attr]
    assert not editor.state.dirty


def test_save_rejects_bad_names(editor: Editor) -> None:
    with pytest.raises(EditorError):
        editor.save(name="ñandú")
    with pytest.raises(EditorError):
        editor.save(name="x" * 15)


def test_rename_and_copy(editor: Editor, sim: SimTransport) -> None:
    editor.rename(5, "CRUNCH")
    assert wait_for(lambda: sim.device.presets[5].name == "CRUNCH")
    assert editor.state.presets[5].name == "CRUNCH"
    editor.copy_preset(5, 199)
    assert sim.device.presets[199].name == "CRUNCH"
    assert sim.device.presets[199].words == sim.device.presets[5].words


def test_select_loads_stored_preset(editor: Editor) -> None:
    editor.select(42)
    assert editor.state.current_slot == 42
    assert editor.state.edit is not None
    assert editor.state.edit.words == editor.state.presets[42].words


def test_pedal_notifications_update_state(editor: Editor, sim: SimTransport) -> None:
    changes: list[ds.Change] = []
    editor.state.add_listener(changes.append)
    sim.inject(sim.device.footswitch(7))
    assert wait_for(lambda: editor.state.current_slot == 7)
    sim.inject(sim.device.turn_knob(2, 1, 66))
    assert wait_for(lambda: editor.module(2).words[3] == 66)
    kinds = [c.kind for c in changes]
    assert ds.KIND_SELECTED in kinds and ds.KIND_MODULE in kinds


def test_exp_goes_to_the_right_message(editor: Editor, sim: SimTransport) -> None:
    sim.device.received.clear()
    editor.set_exp("VOL_MIN", 12)
    editor.set_exp("MODULE_CTRL", 3)
    editor.session.flush()
    assert [f.opcode for f in sim.device.received] == [Op.WRITE_EXP_B, Op.WRITE_EXP_A]
    assert sim.device.edit_buffer.exp["VOL_MIN"] == 12
    assert sim.device.edit_buffer.exp["MODULE_CTRL"] == 3


def test_ir_upload_backup_and_delete(editor: Editor, sim: SimTransport) -> None:
    samples = [(i * 7919) % 100000 - 50000 for i in range(512)]
    payload = wav_ir.pack_planar(samples)
    editor.upload_user_slot(Op.USER_IR, 3, "MY CAB", payload)
    assert editor.state.user_names is not None and editor.state.user_names.ir[3] == "MY CAB"
    chunks = editor.read_ir_backup()
    assert [(c.slot, c.name) for c in chunks] == [(3, "MY CAB")]
    assert wav_ir.unpack_planar(chunks[0].data) == samples
    editor.delete_user_slot(Op.USER_IR, 3)
    assert editor.state.user_names.ir[3] == "Empty"
    assert editor.read_ir_backup() == []


def test_model_label_uses_user_slot_names(editor: Editor) -> None:
    editor.upload_user_slot(Op.USER_IR, 6, "VOX AC30", b"")
    assert editor.model_label(3, 32) == "33:VOX AC30"  # CAB 33 = IR slot 7
    assert editor.model_label(3, 33) == "34:EMPTY"
    assert editor.model_label(3, 0) == "01:US DLX 112"
