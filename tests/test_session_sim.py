import threading

import pytest

from ge150.protocol import messages as msg
from ge150.protocol.framing import Frame
from ge150.protocol.opcodes import Op
from ge150.protocol.session import DeviceSession, ResponseTimeout, SessionError
from ge150.services import reader
from ge150.sim.sim_transport import SimTransport


@pytest.fixture
def sim() -> SimTransport:
    return SimTransport()


@pytest.fixture
def session(sim: SimTransport):  # type: ignore[no-untyped-def]
    s = DeviceSession(sim, frame_delay=0, multipart_delay=0)
    with s:
        yield s


def test_identify(session: DeviceSession) -> None:
    info = reader.identify(session)
    assert info.name == "MOOER_GE150" and info.firmware == "V1.3.8"


def test_handshake_sends_the_flush_report(sim: SimTransport, session: DeviceSession) -> None:
    assert reader.handshake(session).name == "MOOER_GE150"
    assert sim.written_reports[0] == reader.FLUSH_REPORT


def test_handshake_retries_an_ignored_identify(sim: SimTransport,
                                               session: DeviceSession) -> None:
    handle, ignored = sim.device.handle, []

    def deaf_once(frame: Frame) -> list[Frame]:
        if frame.opcode == Op.IDENTIFY and not ignored:
            ignored.append(frame)
            return []
        return handle(frame)

    sim.device.handle = deaf_once  # type: ignore[method-assign]
    assert reader.handshake(session, timeout=0.2).name == "MOOER_GE150"
    assert ignored


def test_handshake_gives_up(sim: SimTransport, session: DeviceSession) -> None:
    sim.device.handle = lambda frame: []  # type: ignore[method-assign]
    with pytest.raises(ResponseTimeout):
        reader.handshake(session, attempts=2, timeout=0.1)


def test_read_all_presets(session: DeviceSession) -> None:
    presets, system = reader.read_all_presets(session)
    assert sorted(presets) == list(range(1, 201))
    assert system is not None
    assert presets[42].name == "PRESET 042"


def test_snapshot(session: DeviceSession) -> None:
    snap = reader.snapshot(session)
    assert len(snap["presets"]) == 200
    assert snap["device"]["name"] == "MOOER_GE150"


def test_rename_and_write_preset(session: DeviceSession, sim: SimTransport) -> None:
    session.send(msg.rename_preset(3, "CRUNCH"))
    session.flush()
    preset = sim.device.presets[10].copy()
    preset.name, preset.words[0] = "NEW", 1
    session.send(msg.write_preset(preset))
    session.flush()
    assert sim.device.presets[10].name == "NEW"
    assert reader.read_all_presets(session)[0][3].name == "CRUNCH"


def test_live_module_write_changes_edit_buffer(session: DeviceSession, sim: SimTransport) -> None:
    session.send(msg.write_module(8, [1, 2, 10, 20, 30, 40]))
    session.flush()
    assert reader.read_current(session).words[60:66] == [1, 2, 10, 20, 30, 40]


def test_notifications_reach_listeners(session: DeviceSession, sim: SimTransport) -> None:
    seen: list[Frame] = []
    got = threading.Event()

    def listener(frame: Frame) -> None:
        seen.append(frame)
        if len(seen) == 2:
            got.set()

    session.add_listener(listener)
    sim.inject(sim.device.footswitch(17) + sim.device.turn_knob(2, 0, 99))
    assert got.wait(2)
    assert seen[0] == Frame(Op.PRESET_SELECTED, bytes([17]))
    assert msg.parse_module(seen[1]) == (2, sim.device.edit_buffer.words[11:19])


def test_user_slot_upload(session: DeviceSession, sim: SimTransport) -> None:
    frames = msg.user_slot_frames(Op.USER_IR, 2, "V30", b"\x11" * 1536)
    for frame in frames[:-1]:
        session.send(frame)
    session.request(frames[-1], expect=Op.USER_IR)
    assert reader.read_user_names(session).ir[2] == "V30"
    assert sim.device.user_data[(Op.USER_IR, 2)] == b"\x11" * 1536


def test_timeout_when_device_silent(session: DeviceSession) -> None:
    with pytest.raises(ResponseTimeout):
        session.request(Frame(0x7E, b"\x01"), expect=0x7E, timeout=0.2)


def test_disconnect_is_reported(sim: SimTransport) -> None:
    session = DeviceSession(sim, frame_delay=0)
    gone = threading.Event()
    session.add_disconnect_listener(lambda exc: gone.set())
    session.start()
    sim.unplug()
    assert gone.wait(2)
    with pytest.raises(SessionError):
        session.send(msg.identify())
    session.close()


def test_describe_words_names_user_irs() -> None:
    from ge150.model.preset import Preset

    preset = Preset(1)
    block = preset.module(3)  # CAB
    block.words[1] = 33  # CAB 34 = user IR slot 8
    preset.set_module(block)
    irs = ["EMPTY"] * 7 + ["1960A V30 57+906", "EMPTY", "EMPTY"]
    names = msg.UserNames(nr=["EMPTY"] * 10, ir=irs)
    cab = reader.describe_words(preset.words, names)[3]
    assert cab["model"] == "34:1960A V30 57+906"
    assert reader.describe_words(preset.words)[3]["model"] != cab["model"]
    empty = msg.UserNames(nr=["EMPTY"] * 10, ir=["EMPTY"] * 10)
    assert reader.describe_words(preset.words, empty)[3]["model"].startswith("34:")
