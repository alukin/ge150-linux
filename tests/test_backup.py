import struct
from collections.abc import Iterator
from pathlib import Path

import pytest

from ge150.formats import mbf, wav_ir
from ge150.protocol.opcodes import Op
from ge150.protocol.session import DeviceSession
from ge150.services.backup import create_backup, restore_backup
from ge150.services.editor import Editor
from ge150.sim.fake_device import FakeGE150
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


def sample_backup() -> mbf.Backup:
    presets = list(FakeGE150().presets.values())
    irs = [mbf.IrItem(2, "MY CAB", wav_ir.pack_planar([i - 256 for i in range(512)]))]
    return mbf.Backup(presets, bytes(range(10)), bytes([1, 2, 3, 4, 5, 6]), irs)


def test_build_layout_matches_vendor() -> None:
    data = mbf.build(sample_backup())
    assert data[0:5] == b"MOOER" and data[8:19] == b"MOOER_GE150" and data[0x48:0x4C] == b"BUFF"
    assert data[0x2F:0x35] == b"V1.0.2"
    assert struct.unpack_from("<I", data, 0x4C)[0] == 4
    first, second = struct.unpack_from("<QQ", data, 0x50)
    assert first == 0x400 and second == 0x400 + 0x100 + 200 * (0x22 + 0xA0)
    assert data[first : first + 12] == b"GE150_PRESET" and data[first + 0x20] == 0xC3
    assert struct.unpack_from("<II", data, first + 0x28) == (200, 0xA0)
    stored = struct.unpack_from("<Q", data, 0x3F8)[0]
    assert stored == sum(data[:0x3F8]) + sum(data[0x400:])


def test_roundtrip(tmp_path: Path) -> None:
    backup = sample_backup()
    path = tmp_path / "GE150.mbf"
    mbf.save(path, backup)
    loaded = mbf.load(path)
    assert [p.words for p in loaded.presets] == [p.words for p in backup.presets]
    assert [p.name for p in loaded.presets] == [p.name for p in backup.presets]
    assert (loaded.system, loaded.rhythm) == (backup.system, backup.rhythm)
    assert [(i.slot, i.name, i.data) for i in loaded.irs] == [(2, "MY CAB", backup.irs[0].data)]


def test_corruption_is_detected() -> None:
    data = bytearray(mbf.build(sample_backup()))
    data[0x500] ^= 0x01
    with pytest.raises(mbf.MbfError, match="checksum"):
        mbf.parse(bytes(data))
    with pytest.raises(mbf.MbfError, match="magic"):
        mbf.parse(b"X" * 0x400)


def test_create_backup_from_device(editor: Editor, sim: SimTransport) -> None:
    editor.upload_user_slot(Op.USER_IR, 4, "V30", wav_ir.pack_planar([7] * 512))
    backup = create_backup(editor)
    assert len(backup.presets) == 200 and backup.presets[0].name == "PRESET 001"
    assert [(i.slot, i.name) for i in backup.irs] == [(4, "V30")]
    assert mbf.parse(mbf.build(backup)).irs[0].data == wav_ir.pack_planar([7] * 512)


def test_restore_writes_everything(editor: Editor, sim: SimTransport) -> None:
    backup = sample_backup()
    backup.presets[9].name = "RESTORED"
    steps: list[int] = []
    sim.device.received.clear()
    restore_backup(editor, backup, lambda _, step, total: steps.append(step))
    ops = [f.opcode for f in sim.device.received]
    assert ops[0] == Op.RESTORE_BEGIN and ops[-1] == Op.RESTORE_END
    assert ops.count(Op.WRITE_PRESET) == 200
    assert sim.device.presets[10].name == "RESTORED"
    assert sim.device.rhythm == bytes([1, 2, 3, 4, 5, 6])
    assert sim.device.system[Op.WRITE_SYSTEM_3] == bytes([4, 5, 6, 7])
    assert sim.device.ir_names[2] == "MY CAB"
    assert steps[-1] == 212
