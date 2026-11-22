from collections.abc import Iterator

import pytest

from ge150.mcp_server.tools import PedalTools, ToolError
from ge150.protocol.session import DeviceSession
from ge150.services.editor import Editor
from ge150.sim.sim_transport import SimTransport


@pytest.fixture
def tools() -> Iterator[PedalTools]:
    session = DeviceSession(SimTransport(), frame_delay=0, multipart_delay=0)
    with session:
        editor = Editor(session)
        editor.sync()
        yield PedalTools(editor)


def test_catalog_index_and_module(tools: PedalTools) -> None:
    index = tools.get_catalog()
    assert [m["module"] for m in index["modules"]][:3] == ["FX", "DS", "AMP"]
    ds = tools.get_catalog("ds")
    ts = next(m for m in ds["models"] if m["model"] == "808")
    assert ts["based_on"] == "Ibanez TS808 Tube Screamer"
    assert {"name": "GAIN", "min": 0, "max": 100} in ts["params"]
    with pytest.raises(ToolError):
        tools.get_catalog("phaser")


def test_patch_presets_and_user_slots(tools: PedalTools) -> None:
    patch = tools.get_current_patch()
    assert patch["slot"] == 1 and len(patch["modules"]) == 9
    assert patch["unsaved_changes"] is False
    assert len(tools.list_presets()["presets"]) == 200
    assert tools.list_presets("042")["presets"] == [{"slot": 42, "name": "PRESET 042"}]
    assert tools.get_preset(5)["name"] == "PRESET 005"
    assert len(tools.list_user_irs()["ir"]) == 10
    assert set(tools.get_settings()) == {"system", "rhythm"}


def test_live_changes_and_undo(tools: PedalTools) -> None:
    before = tools.get_current_patch()
    result = tools.set_module("amp", True, "J800", {"GAIN": 80, "NOPE": 1})
    assert any("J800" in row for row in result["applied"])
    assert any("NOPE" in w for w in result["warnings"])
    amp = tools.get_current_patch()["modules"][2]
    assert amp["model"] == "J800" and amp["params"]["GAIN"] == "80"
    tools.apply_patch([{"module": "MOD", "on": False, "model": "", "params": []}])
    assert tools.undo()["undone"] and tools.undo()["undone"]
    assert tools.get_current_patch()["modules"] == before["modules"]
    assert tools.undo() == {"undone": False, "reason": "nothing to undo"}


def test_select_preset_protects_unsaved_changes(tools: PedalTools) -> None:
    tools.set_module("DS", False)
    with pytest.raises(ToolError, match="unsaved"):
        tools.select_preset(7)
    assert tools.select_preset(7, discard_changes=True)["slot"] == 7
    with pytest.raises(ToolError):
        tools.select_preset(500)


def test_no_tool_stores_anything() -> None:
    names = {n for n in dir(PedalTools) if not n.startswith("_")}
    assert not names & {"save", "save_preset", "rename", "factory_reset", "restore", "load_ir"}
