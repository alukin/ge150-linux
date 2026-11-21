from ge150.model.catalog import load_catalog
from ge150.model.preset import MODULES


def test_catalog_matches_layout() -> None:
    catalog = load_catalog()
    assert [m.name for m in catalog] == [m.name for m in MODULES]
    assert [len(m.models) for m in catalog] == [8, 20, 65, 36, 3, 4, 19, 9, 7]


def test_params_fit_in_module_blocks() -> None:
    for info, layout in zip(load_catalog(), MODULES, strict=True):
        for model in info.models:
            assert len(model.params) <= layout.words - 2, (info.name, model.label)


def test_param_source_inheritance() -> None:
    mod = load_catalog()[6]
    rotary = next(m for m in mod.models if m.name == "ROTARY")
    tremolo = next(m for m in mod.models if m.name == "TREMOLO")
    assert rotary.params == tremolo.params


def test_user_slots() -> None:
    cab, amp = load_catalog()[3], load_catalog()[2]
    assert [m.number for m in cab.models if m.user_slot] == list(range(27, 37))
    assert [m.number for m in amp.models if m.user_slot] == list(range(56, 66))


def test_value_encoding_fitted_to_real_presets() -> None:
    cat = load_catalog()
    eq = cat[5].models[0].params[0]  # 100Hz, -16..16: 0 dB stored as 16
    assert eq.to_raw(-16) == 0 and eq.to_raw(0) == 16 and eq.from_raw(16) == 0
    pitch = next(m for m in cat[6].models if m.name == "PITCH SHIFT").params[0]
    assert pitch.word == 7 and pitch.raw_max == 240 and pitch.format(120) == "0.0"
    detune = next(m for m in cat[6].models if m.name == "DETUNE").params[0]
    assert detune.word == 6 and detune.from_raw(200) == 0
    time = cat[7].models[0].params[2]  # TIME 40..2500 ms stored in ms
    assert time.to_raw(1332) == 1332 and time.format(40) == "40 ms"
    sub_d = cat[7].models[0].params[3]
    assert sub_d.kind == "enum" and sub_d.from_raw(1) == "1/4"


def test_fixed_words() -> None:
    cat = load_catalog()
    dynamic = next(m for m in cat[7].models if m.name == "DYNAMIC")
    assert [p.word for p in dynamic.params] == [2, 3, 4, 5, 8]
    dual = next(m for m in cat[7].models if m.name == "DUAL DELAY")
    assert [p.word for p in dual.params] == [2, 3, 4, 5, 6, 7]
    custom = next(m for m in cat[5].models if m.name == "CUSTOM EQ")
    assert [p.word for p in custom.params] == [2, 8, 4, 9, 6, 10]
    vibrato = next(m for m in cat[6].models if m.name == "VIBRATO")
    assert [p.word for p in vibrato.params] == [2, 5, 4]
    pitch = next(m for m in cat[6].models if m.name == "PITCH SHIFT")
    assert [p.word for p in pitch.params] == [7, 3, 4]
    for info, layout in zip(cat, MODULES, strict=True):
        for model in info.models:
            words = [p.word for p in model.params]
            assert len(set(words)) == len(words), (info.name, model.label)
            assert all(2 <= w < layout.words for w in words), (info.name, model.label)
