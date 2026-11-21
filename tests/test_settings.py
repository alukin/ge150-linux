import pytest

from ge150.cli import main
from ge150.cli_settings import apply_rhythm_field, apply_system_field
from ge150.model import settings
from ge150.model.settings import RhythmValues, SystemValues
from ge150.protocol.opcodes import Op
from ge150.services.editor import EditorError

# Read from the real pedal before and after changing each setting by hand.
REAL_SYSTEM = {Op.WRITE_SYSTEM_1: bytes.fromhex("0900"), Op.WRITE_SYSTEM_2: bytes.fromhex("1400"),
               Op.WRITE_SYSTEM_3: bytes.fromhex("01000000"),
               Op.WRITE_SYSTEM_4: bytes.fromhex("0800")}


def test_system_matches_pedal_screen() -> None:
    values = SystemValues.from_blocks(REAL_SYSTEM)
    assert values.describe() == [("INPUT LEVEL", "0 dB"), ("SCREEN", "20"), ("CAB-L", "ON"),
                                 ("CAB-R", "THRU"), ("OTG LEVEL", "-5 dB")]
    assert values.to_blocks() == REAL_SYSTEM


def test_levels() -> None:
    assert len(settings.LEVELS) == 22
    assert settings.level_label(10) == "0.5 dB" and settings.level_label(21) == "6.0 dB"
    for text, index in (("0", 9), ("0 dB", 9), ("0.5", 10), ("6", 21), ("-5dB", 8), ("-", 0),
                        ("-60", 1)):
        assert settings.level_index(text) == index
    with pytest.raises(ValueError):
        settings.level_index("7")


def test_rhythm_matches_pedal_screen() -> None:
    assert RhythmValues.from_bytes(bytes.fromhex("0000000a0401")) == RhythmValues(
        False, 0, 0, 10, 260)
    metronome = RhythmValues.from_bytes(bytes.fromhex("010100057900"))
    assert metronome == RhythmValues(True, 1, 0, 5, 121)
    assert metronome.to_bytes() == bytes.fromhex("010100057900")
    assert dict(metronome.describe())["MODE"] == "METRONOME"


def test_validation() -> None:
    with pytest.raises(ValueError, match="bpm"):
        RhythmValues(bpm=300).validate()
    with pytest.raises(ValueError, match="style"):
        RhythmValues(mode=1, style=10).validate()
    with pytest.raises(ValueError, match="screen"):
        SystemValues(screen=21).validate()


def test_field_parsing() -> None:
    base = SystemValues()
    assert apply_system_field(base, "input", "0.5").input_level == 10
    assert apply_system_field(base, "cab-right", "thru").cab_right_on is False
    assert apply_system_field(base, "screen", "15").screen == 15
    with pytest.raises(EditorError):
        apply_system_field(base, "cab-left", "off")
    rhythm = apply_rhythm_field(RhythmValues(style=5), "mode", "metronome")
    assert (rhythm.mode, rhythm.style) == (1, 0)
    assert apply_rhythm_field(rhythm, "style", "3").style == 2
    assert apply_rhythm_field(rhythm, "state", "on").on is True


def test_cli_settings_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--sim", "system-set", "cab-left", "thru"]) == 0
    assert "CAB-L        THRU" in capsys.readouterr().out
    assert main(["--sim", "rhythm-set", "bpm", "121"]) == 0
    assert "BPM          121" in capsys.readouterr().out
    assert main(["--sim", "rhythm-set", "bpm", "9"]) == 2
