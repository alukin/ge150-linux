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
    spec = [{"slot": 23, "modules": [{"module": "DS", "on": True}]}]
    edit = bulk_edit.plan_edits(editor, spec)[0]
    assert edit.blocked == bulk_edit.DIRTY
    assert bulk_edit.apply(editor, [edit]).skipped[0][0] == 23


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
