from ge150.model import exp
from ge150.model.catalog import load_catalog
from ge150.model.exp import ExpSettings
from ge150.model.preset import EXP_OFFSET, MODULES


def test_each_module_lists_its_number_parameters() -> None:
    catalog = load_catalog()
    for index in range(len(MODULES)):
        names = {p.name.upper() for m in catalog[index].models for p in m.params
                 if p.kind == "number"}
        assert set(exp.PARAMS[index]) <= names, MODULES[index].name


def test_indexes_match_the_vendor_menu_and_real_presets() -> None:
    assert (exp.para_index(0, "POSITION"), exp.para_name(0, 0)) == (0, "POSITION")
    # (module, PARA_CTRL, parameter) stored in a real GE150's presets.
    seen = [(6, 43, "MIX"), (6, 44, "DEPTH"), (6, 46, "FEEDBACK"), (6, 39, "RATE"),
            (6, 41, "RISE"), (2, 13, "GAIN"), (1, 10, "VOLUME"), (7, 51, "LEVEL"),
            (8, 58, "LEVEL"), (8, 59, "DECAY"), (0, 6, "THRES")]
    for module, para, name in seen:
        assert exp.para_name(module, para) == name
        assert exp.para_index(module, name) == para
    assert exp.para_index(5, "80Hz") == 25  # catalog spelling
    assert exp.para_name(6, 51) is None  # DELAY's first, not MOD's
    assert exp.para_index(3, "MIC") is None


def test_controllable_keeps_the_model_order() -> None:
    catalog = load_catalog()
    chorus = next(m for m in catalog[6].models if m.name == "ANA-CHORUS")
    assert [p.name for p in exp.controllable(6, chorus)] == ["RATE", "MIX", "TONE", "DEPTH"]


def test_settings_round_trip() -> None:
    words = list(range(72))
    settings = ExpSettings(6, 43, True, False, 10, 90)
    new = settings.to_words(words)
    assert new[:EXP_OFFSET] == words[:EXP_OFFSET]
    assert new[EXP_OFFSET:] == [6, 43, 1, 0, 10, 90]
    assert ExpSettings.from_words(new) == settings
    assert settings.param_name == "MIX"
