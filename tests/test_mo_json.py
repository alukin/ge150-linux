import json
from pathlib import Path

import pytest

from ge150.formats import mo_json
from ge150.model.preset import Preset
from ge150.sim.fake_device import FakeGE150


def sample_preset() -> Preset:
    preset = FakeGE150().presets[19].copy()
    preset.name = "Burden Clean"
    words = preset.words
    words[51:60] = [0, 8, 50, 50, 1040, 1, 1040, 1, 50]  # DELAY: DUAL DELAY, SUB 1/4 (1/1)
    words[66:72] = [0, 6, 0, 1, 0, 100]
    return preset


def test_structure_matches_vendor_writer() -> None:
    doc = mo_json.preset_to_mo(sample_preset())
    assert set(doc) == {"fileInfo", "preset_name", "Exp", "effectModule"}
    assert doc["fileInfo"]["schema"] == "GE150 Preset"
    assert list(doc["effectModule"]) == ["FX/COMP", "DS/OD", "AMP", "CAB", "NS GATE", "EQ",
                                         "MOD", "DELAY", "REVERB"]
    delay = doc["effectModule"]["DELAY"]
    assert delay["TYPE"] == 8
    assert delay["Data"]["TIME A"] == 1000 and delay["Data"]["TIME B"] == 1000
    assert doc["Exp"] == {"MODULE_CTRL": 0, "PARA_CTRL": 6, "FUN_SWITCH": 0,
                          "VOL_SWITCH": 1, "VOL_MIN": 0, "VOL_MAX": 100}


def test_dumps_is_sorted_qt_style() -> None:
    text = mo_json.dumps(sample_preset())
    assert text.startswith('{\n    "Exp": {\n        "FUN_SWITCH"')
    assert json.loads(text)["preset_name"] == "Burden Clean"


def test_roundtrip_keeps_every_word(tmp_path: Path) -> None:
    preset = sample_preset()
    path = tmp_path / "p.mo"
    mo_json.save(path, preset)
    assert mo_json.load(path, preset).words == preset.words


def test_import_overwrites_only_known_words() -> None:
    source = sample_preset()
    base = Preset(5, "OLD", [7] * 72)
    result = mo_json.mo_to_preset(mo_json.preset_to_mo(source), base)
    assert result.slot == 5 and result.name == "Burden Clean"
    assert result.words[0:2] == source.words[0:2]
    assert result.words[66:72] == source.words[66:72]
    assert result.words[25] == 7  # CAB word 6 is not part of any model


@pytest.mark.parametrize(("raw", "sub"), [(1026, 5), (600, 4), (2000, 9), (80, 2)])
def test_delay_time_subdivisions(raw: int, sub: int) -> None:
    value = mo_json.time_to_json(raw, sub, 0)
    a, b = mo_json.SUBDIVISIONS[sub]
    assert value == max(0, min(2460, round(raw * a / b - 40 + 0.5)))
    assert abs(mo_json.time_from_json(value, sub) - raw) <= b // a + 1


def test_rejects_other_files() -> None:
    with pytest.raises(mo_json.MoError):
        mo_json.mo_to_preset({"fileInfo": {"schema": "GE200 Preset"}}, Preset(1))


def test_bad_type_is_rejected() -> None:
    doc = mo_json.preset_to_mo(sample_preset())
    doc["effectModule"]["FX/COMP"]["TYPE"] = 99
    with pytest.raises(mo_json.MoError):
        mo_json.mo_to_preset(doc, Preset(1))
