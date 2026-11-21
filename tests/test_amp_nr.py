import pytest

from ge150.formats import amp_nr
from ge150.protocol import messages as msg
from ge150.protocol.opcodes import Op


def words() -> list[int]:
    return [(i * 2654435761) % (1 << 32) - (1 << 31) for i in range(512)]


def test_amp_roundtrip_and_validation() -> None:
    data = amp_nr.build_amp(words())
    assert data.endswith(b"2.0") and len(data) == 2048 + 4 + 3
    assert amp_nr.parse_amp(data) == words()
    with pytest.raises(amp_nr.AmpError, match="checksum"):
        amp_nr.parse_amp(b"\x01" + data[1:])
    with pytest.raises(amp_nr.AmpError, match="trailer"):
        amp_nr.parse_amp(data[:-1] + b"1")


def test_planar_layout_msb_first() -> None:
    packed = amp_nr.pack_planar([0x11223344] + [0] * 511)
    assert (packed[0], packed[512], packed[1024], packed[1536]) == (0x11, 0x22, 0x33, 0x44)
    assert amp_nr.unpack_planar(amp_nr.pack_planar(words())) == words()


def test_nr_upload_frames_use_four_parts() -> None:
    payload = amp_nr.pack_planar(words())
    frames = msg.user_slot_frames(Op.USER_NR, 0, "MY AMP", payload)
    assert frames[0].data[1] == 0  # 0-based user slot (AMP 56)
    assert [f.data[0] for f in frames[2:]] == [2, 3, 4, 5]
    assert b"".join(f.data[1:] for f in frames[2:]) == payload
