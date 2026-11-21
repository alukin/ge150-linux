import pytest

from ge150.model.preset import MODULES, PRESET_WORDS, Preset, decode_name, encode_name
from ge150.protocol import messages as msg
from ge150.protocol.framing import Frame, FrameDecoder
from ge150.protocol.opcodes import Op


def test_layout_covers_72_words() -> None:
    assert sum(m.words for m in MODULES) == 66
    assert [m.offset for m in MODULES] == [0, 6, 11, 19, 26, 31, 42, 51, 60]
    assert [m.write_op for m in MODULES] == list(range(0x82, 0x8B))
    assert PRESET_WORDS == 72


def test_write_preset_length_matches_vendor() -> None:
    frame = msg.write_preset(Preset(5, "CLEAN", list(range(72))))
    assert frame.opcode == Op.WRITE_PRESET
    assert len(frame.payload) == 0xA0  # FUN_00414d50 sets LEN = 0xA0
    assert frame.data[0] == 5
    assert frame.data[1:6] == b"CLEAN"


def test_rename_payload_is_16_bytes() -> None:
    frame = msg.rename_preset(200, "A VERY LONG NAME THAT IS CUT")
    assert len(frame.data) == 16  # slot + 15 bytes
    assert frame.data[0] == 200


def test_slot_validation() -> None:
    with pytest.raises(ValueError):
        msg.select_preset(0)
    with pytest.raises(ValueError):
        msg.select_preset(201)


def test_write_module_checks_size() -> None:
    assert msg.write_module(2, [1] * 8).opcode == 0x84
    with pytest.raises(ValueError):
        msg.write_module(2, [1] * 7)


def test_user_slot_frames_layout() -> None:
    frames = msg.user_slot_frames(Op.USER_IR, 0, "MY IR", b"\x01" * 1536)
    assert [len(f.payload) for f in frames] == [5, 0x12, 0x202, 0x202, 0x202]
    assert frames[0].data == bytes([0, 0x1A, 0, 1])
    assert frames[1].data[0] == 1 and frames[1].data[1:6] == b"MY IR"
    assert [f.data[0] for f in frames[2:]] == [2, 3, 4]
    nr = msg.user_slot_frames(Op.USER_NR, 9, "AMP", b"")
    assert nr[0].data[1] == 0x40 and len(nr) == 6


def test_delete_user_slot_uses_empty_name() -> None:
    frames = msg.delete_user_slot_frames(Op.USER_NR, 1)
    assert decode_name(frames[1].data[1:17]) == "Empty"
    assert all(f.data[1:] == bytes(512) for f in frames[2:])


def test_parse_preset_dump() -> None:
    words = list(range(100, 172))
    data = bytes([7]) + encode_name("LEAD") + b"".join(w.to_bytes(2, "little") for w in words)
    preset = msg.parse_preset_dump(Frame(Op.PRESET_DUMP, data + b"\x00\x00\x00\x00"))
    assert (preset.slot, preset.name, preset.words) == (7, "LEAD", words)


def test_parse_identify_real_device_frame() -> None:
    # Captured from a real GE150 with `ge150ctl --raw probe` (2026-11-21).
    raw = bytes.fromhex(
        "aa553f00014d4f4f45525f47453135300000000000000000000000000000000000000000"
        "0056312e302e300056312e332e380056312e332e310041005631" "2e312e30008fd9")
    frames = FrameDecoder().feed(raw)
    assert len(frames) == 1 and frames[0].opcode == Op.DEVICE_INFO
    info = msg.parse_identify(frames[0])
    assert (info.name, info.firmware, info.revision) == ("MOOER_GE150", "V1.3.8", "A")
    assert (info.field_a, info.field_c, info.field_d) == ("V1.0.0", "V1.3.1", "V1.1.0")


def test_parse_user_names_two_lists() -> None:
    names = [f"A{i}" for i in range(10)] + [f"B{i}" for i in range(10)]
    frame = Frame(Op.USER_NAMES, b"".join(encode_name(n, 16) for n in names))
    a, b = msg.parse_user_names(frame)
    assert a[3] == "A3" and b[9] == "B9"


def test_decode_name_replaces_high_bytes() -> None:
    assert decode_name(b"AB\xffC\x00junk") == "AB C"


def test_exp_split() -> None:
    words = list(range(72))
    a, b = msg.write_exp(words)
    assert a.data == b"".join(w.to_bytes(2, "little") for w in (66, 67, 68))
    assert b.data == b"".join(w.to_bytes(2, "little") for w in (69, 70, 71))


def test_preset_module_roundtrip() -> None:
    preset = Preset(1, "X")
    block = preset.module(5)
    block.switch = True
    block.type = 3
    block.set_param(0, 20)
    preset.set_module(block)
    assert preset.words[31:34] == [1, 3, 20]
    with pytest.raises(IndexError):
        block.set_param(9, 1)
