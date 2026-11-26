from collections.abc import Iterator

import pytest

from ge150.mcp_server.tools import PedalTools, ToolError
from ge150.model.gear import MODULE_TAGS
from ge150.protocol.session import DeviceSession
from ge150.services import bulk_edit
from ge150.services.editor import Editor
from ge150.sim.sim_transport import SimTransport

REVERB = MODULE_TAGS.index("REVERB")


@pytest.fixture
def editor() -> Iterator[Editor]:
    session = DeviceSession(SimTransport(), frame_delay=0, multipart_delay=0)
    with session:
        editor = Editor(session)
        editor.sync()
        for slot in (22, 23, 24):
            editor.rename(slot, f"Av83 {slot}")
        yield editor


def _number_param(editor: Editor, slot: int):  # type: ignore[no-untyped-def]
    block = editor.state.presets[slot].module(REVERB)
    model = editor.catalog[REVERB].model_for_type(block.type)
    assert model is not None
    return model, next(p for p in model.params if p.kind == "number")


def test_plan_does_not_write_and_keeps_on_off(editor: Editor) -> None:
    _, param = _number_param(editor, 22)
    stored = list(editor.state.presets[22].words)
    switch = editor.state.presets[22].module(REVERB).switch
    edits = bulk_edit.plan_edits(editor, [
        {"slot": 22, "modules": [{"module": "REVERB",
                                  "params": [{"name": param.name, "value": str(param.min)}]}]}])
    assert editor.state.presets[22].words == stored  # nothing written
    edit = edits[0]
    after = editor.state.presets[22].copy()
    after.words = edit.after
    assert after.module(REVERB).switch == switch
    assert after.module(REVERB).words[param.word] == param.to_raw(param.min)
    if edit.changed:
        rows = bulk_edit.diff(editor, edit.before, edit.after)
        assert rows[0][0] == "REVERB" and param.name in rows[0][2]


def test_apply_and_restore(editor: Editor) -> None:
    editor.select(30)
    before = {s: list(editor.state.presets[s].words) for s in (22, 23, 24)}
    specs = [{"slot": s, "modules": [{"module": "REVERB", "on": not
                                      editor.state.presets[s].module(REVERB).switch}]}
             for s in (22, 23, 24)]
    edits = bulk_edit.plan_edits(editor, specs)
    assert all(e.changed and not e.blocked for e in edits)
    applied = bulk_edit.apply(editor, edits)
    assert not applied.skipped and editor.state.current_slot == 30
    for s in (22, 23, 24):
        assert editor.state.presets[s].words != before[s]
    assert bulk_edit.restore(editor, applied.previous) == [22, 23, 24]
    assert {s: editor.state.presets[s].words for s in before} == before


def test_loaded_preset_with_unsaved_changes_is_refused(editor: Editor) -> None:
    editor.select(23)
    block = editor.module(REVERB)
    block.switch = not block.switch
    editor.write_module(block)
    assert editor.state.dirty
    ds = editor.state.presets[23].module(1).switch
    spec = [{"slot": 23, "modules": [{"module": "DS", "on": not ds}]}]
    edit = bulk_edit.plan_edits(editor, spec)[0]
    assert bulk_edit.own_changes(editor, 23, edit.after)
    assert bulk_edit.apply(editor, [edit]).skipped == [(23, bulk_edit.DIRTY)]


def test_a_preview_is_not_the_users_own_change(editor: Editor) -> None:
    editor.select(30)
    on = editor.state.presets[28].module(REVERB).switch
    edit = bulk_edit.plan_edits(editor, [{"slot": 28, "modules": [{"module": "REVERB",
                                                                     "on": not on}]}])[0]
    bulk_edit.preview(editor, edit)  # the pedal goes to 28 and plays the proposal
    assert editor.state.current_slot == 28 and editor.state.dirty
    assert editor.module(REVERB).switch == (not on)
    assert not bulk_edit.own_changes(editor, 28, edit.after)
    again = bulk_edit.plan_edits(editor, [{"slot": 28, "modules": [{"module": "DS",
                                                                      "on": True}]}])[0]
    assert not again.blocked  # another option for the preset being heard
    bulk_edit.preview(editor, edit, after=False)  # «Antes»: the stored sound
    assert not editor.state.dirty
    bulk_edit.preview(editor, edit)
    applied = bulk_edit.apply(editor, [edit])
    assert not applied.skipped and not editor.state.dirty
    assert editor.state.presets[28].module(REVERB).switch == (not on)


def test_loaded_preset_is_selected_again(editor: Editor) -> None:
    editor.select(24)
    on = editor.state.presets[24].module(REVERB).switch
    edits = bulk_edit.plan_edits(editor, [{"slot": 24, "modules": [{"module": "REVERB",
                                                                     "on": not on}]}])
    bulk_edit.apply(editor, edits)
    assert editor.module(REVERB).switch == (not on) and not editor.state.dirty


def test_second_change_adds_to_the_first(editor: Editor) -> None:
    first = bulk_edit.plan_edits(editor, [{"slot": 22, "modules": [{"module": "DS",
                                                                     "on": True}]}])[0]
    second = bulk_edit.plan_edits(editor, [{"slot": 22, "modules": [{"module": "EQ",
                                                                      "on": True}]}],
                                  {22: first.after})[0]
    assert second.before == first.before
    tags = {row[0] for row in bulk_edit.diff(editor, second.before, second.after)}
    assert tags <= {"DS", "EQ"} and second.after != first.before


def test_unknown_preset(editor: Editor) -> None:
    assert bulk_edit.plan_edits(editor, [{"slot": 999, "modules": []}])[0].blocked


def test_ai_proposes_but_never_writes(editor: Editor) -> None:
    tools = PedalTools(editor)
    found = tools.get_presets("av83")["presets"]
    assert [p["slot"] for p in found] == [22, 23, 24] and found[0]["modules"]
    spec = [{"slot": 22, "modules": [{"module": "DS", "on": not
                                      editor.state.presets[22].module(1).switch}]}]
    with pytest.raises(ToolError, match="editor open"):
        tools.propose_preset_edits(spec)
    got: list[tuple[list, str]] = []
    tools.on_proposal = lambda edits, summary: got.append((edits, summary))
    stored = list(editor.state.presets[22].words)
    result = tools.propose_preset_edits(spec, "DS on")
    assert result["proposed"] and result["presets"][0]["changes"]
    assert got[0][1] == "DS on" and got[0][0][0].slot == 22
    assert editor.state.presets[22].words == stored


def test_rename_only(editor: Editor) -> None:
    words = list(editor.state.presets[22].words)
    edit = bulk_edit.plan_edits(editor, [{"slot": 22, "name": "OPETH CLEAN"}])[0]
    assert edit.changed and edit.renamed and not edit.blocked
    assert ("NOMBRE", "Av83 22", "OPETH CLEAN") in bulk_edit.rows(editor, edit)
    assert editor.state.presets[22].name == "Av83 22"  # nothing written yet
    applied = bulk_edit.apply(editor, [edit])
    assert editor.state.presets[22].name == "OPETH CLEAN"
    assert editor.state.presets[22].words == words
    bulk_edit.restore(editor, applied.previous)
    assert editor.state.presets[22].name == "Av83 22"


def test_invalid_name_is_blocked(editor: Editor) -> None:
    edit = bulk_edit.plan_edits(editor, [{"slot": 22, "name": "MASTER'S APPRENTICES"}])[0]
    assert "nombre no válido" in edit.blocked


def test_copy_from_swaps_presets(editor: Editor) -> None:
    editor.select(30)
    a, b = editor.state.presets[22].copy(), editor.state.presets[24].copy()
    edits = bulk_edit.plan_edits(editor, [{"slot": 22, "copy_from": 24},
                                          {"slot": 24, "copy_from": 22}])
    assert [e.source for e in edits] == [24, 22] and all(e.changed for e in edits)
    assert bulk_edit.rows(editor, edits[0])[1][0] == "CONTENIDO"
    bulk_edit.apply(editor, edits)
    presets = editor.state.presets
    assert (presets[22].name, presets[22].words) == (b.name, b.words)
    assert (presets[24].name, presets[24].words) == (a.name, a.words)


def test_copy_from_with_name_and_modules(editor: Editor) -> None:
    on = editor.state.presets[24].module(REVERB).switch
    edit = bulk_edit.plan_edits(editor, [{
        "slot": 22, "copy_from": 24, "name": "OPETH SOLO",
        "modules": [{"module": "REVERB", "on": not on}]}])[0]
    after = editor.state.presets[24].copy()
    after.words = edit.after
    assert edit.final_name == "OPETH SOLO" and after.module(REVERB).switch == (not on)


def test_copy_from_unknown_preset(editor: Editor) -> None:
    assert bulk_edit.plan_edits(editor, [{"slot": 22, "copy_from": 999}])[0].blocked


def test_ai_can_propose_names(editor: Editor) -> None:
    tools = PedalTools(editor)
    got: list[list[bulk_edit.PresetEdit]] = []
    tools.on_proposal = lambda edits, summary: got.append(edits)
    result = tools.propose_preset_edits([{"slot": 23, "name": "OPETH CRUNCH", "modules": []}])
    assert result["proposed"] and result["presets"][0]["new_name"] == "OPETH CRUNCH"
    assert got[0][0].final_name == "OPETH CRUNCH"
    assert editor.state.presets[23].name == "Av83 23"


def test_kept_edits_are_checked_against_the_pedal(editor: Editor) -> None:
    on = editor.state.presets[22].module(REVERB).switch
    spec = [{"slot": 22, "name": "OPETH", "modules": [{"module": "REVERB", "on": not on}]},
            {"slot": 23, "name": "CRUNCH"}, {"slot": 24, "name": "SOLO"}]
    kept = [bulk_edit.to_dict(e) for e in bulk_edit.plan_edits(editor, spec)]
    bulk_edit.apply(editor, bulk_edit.plan_edits(editor, spec[1:2]))  # 23 applied since
    editor.rename(24, "OTRO")  # 24 changed since
    back = [bulk_edit.from_dict(editor, d) for d in kept]
    assert back[0] is not None and not back[0].blocked and back[0].final_name == "OPETH"
    assert back[1] is None
    assert back[2] is not None and back[2].blocked == bulk_edit.CHANGED
    assert bulk_edit.from_dict(editor, {"slot": "x"}) is None


def test_move_specs_shift_the_presets_in_between() -> None:
    assert bulk_edit.move_specs(5, 5) == []
    assert bulk_edit.move_specs(5, 8) == [{"slot": 5, "copy_from": 6}, {"slot": 6, "copy_from": 7},
                                          {"slot": 7, "copy_from": 8}, {"slot": 8, "copy_from": 5}]
    assert bulk_edit.move_specs(8, 6) == [{"slot": 6, "copy_from": 8}, {"slot": 7, "copy_from": 6},
                                          {"slot": 8, "copy_from": 7}]
    assert [bulk_edit.moved_slot(s, 8, 6) for s in (5, 6, 7, 8, 9)] == [5, 7, 8, 6, 9]
    assert [bulk_edit.moved_slot(s, 6, 8) for s in (5, 6, 7, 8, 9)] == [5, 8, 6, 7, 9]


def test_move_reorders_and_keeps_the_loaded_preset(editor: Editor) -> None:
    editor.select(24)
    presets = editor.state.presets
    before = {s: (presets[s].name, list(presets[s].words)) for s in range(20, 27)}
    calls: list[int] = []
    applied = bulk_edit.move(editor, 24, 21, backup=lambda: calls.append(1) or None)  # type: ignore[func-returns-value]
    assert calls == [1]
    order = [24, 21, 22, 23]  # what slots 21..24 hold now
    assert {s: (presets[s].name, presets[s].words) for s in range(21, 25)} == {
        slot: before[old] for slot, old in zip(range(21, 25), order, strict=True)}
    assert all((presets[s].name, presets[s].words) == before[s] for s in (20, 25, 26))
    assert sorted(p.slot for p in applied.previous) == [21, 22, 23, 24]
    assert editor.state.current_slot == 21  # the loaded preset followed its new place
    bulk_edit.move(editor, 21, 24)  # and back
    assert all((presets[s].name, presets[s].words) == before[s] for s in range(20, 27))


def test_move_refuses_unsaved_changes_in_the_range(editor: Editor) -> None:
    editor.select(23)
    _, param = _number_param(editor, 23)
    editor.set_param(REVERB, param.name, param.max)
    assert editor.state.dirty
    stored = {s: list(editor.state.presets[s].words) for s in (22, 23, 24)}
    with pytest.raises(bulk_edit.EditorError, match="sin guardar"):
        bulk_edit.move(editor, 24, 22)
    assert {s: list(editor.state.presets[s].words) for s in (22, 23, 24)} == stored


def test_hearing_a_copy_with_other_exp_settings_can_still_be_applied(editor: Editor) -> None:
    # The EXP settings are preset words too: hearing the planned preset must load them, or
    # the pedal looks like it has unsaved changes and applying skips it.
    editor.select(23)
    exp = list(editor.state.presets[23].words[66:72])
    editor.set_exp("MODULE_CTRL", exp[0] + 1)
    editor.save()
    editor.select(22)
    edit = bulk_edit.plan_edits(editor, [{"slot": 22, "copy_from": 23}])[0]
    bulk_edit.preview(editor, edit)
    assert editor.state.edit is not None and editor.state.edit.words == edit.after
    assert not bulk_edit.own_changes(editor, 22, edit.after)
    applied = bulk_edit.apply(editor, [edit])
    assert applied.skipped == [] and editor.state.presets[22].words == edit.after
    bulk_edit.preview(editor, edit, after=False)  # and back to the stored version
    assert editor.state.edit.words == edit.before
