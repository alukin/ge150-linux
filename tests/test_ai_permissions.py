import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from ge150.mcp_server.tools import GuardedTools, PedalTools, ToolError, required_permissions
from ge150.protocol.session import DeviceSession
from ge150.services import ai_permissions
from ge150.services.ai_permissions import Permissions
from ge150.services.editor import Editor
from ge150.sim.sim_transport import SimTransport


@pytest.fixture
def tools() -> Iterator[PedalTools]:
    session = DeviceSession(SimTransport(), frame_delay=0, multipart_delay=0)
    with session:
        editor = Editor(session)
        editor.sync()
        yield PedalTools(editor, on_proposal=lambda edits, summary: None)


def _guarded(tools: PedalTools, *denied: str) -> GuardedTools:
    return GuardedTools(tools, lambda: Permissions(frozenset(denied)))


def test_everything_allowed_without_a_file(tmp_path: Path) -> None:
    permissions = ai_permissions.load(tmp_path / "missing.json")
    assert all(permissions.allows(p.key) for p in ai_permissions.PERMISSIONS)


def test_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "ge150" / "ai_permissions.json"
    ai_permissions.save(Permissions(frozenset({"rename", "save"})), path)
    assert ai_permissions.load(path).denied == {"rename", "save"}


def test_default_path_follows_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ai_permissions.save(Permissions(frozenset({"live"})))
    assert (tmp_path / "ge150" / "ai_permissions.json").exists()
    assert not ai_permissions.load().allows("live")


def test_required_permissions_of_a_proposal() -> None:
    edits = [{"slot": 1, "name": "A", "copy_from": 0, "modules": []},
             {"slot": 2, "name": "", "copy_from": 3, "modules": [{"module": "DS"}]}]
    assert set(required_permissions("propose_preset_edits", edits)) == {
        "rename", "move", "edit_presets"}
    assert required_permissions("get_presets") == []
    assert required_permissions("load_tone3000_ir") == ["tone3000", "load_ir"]


def test_denied_live_change(tools: PedalTools) -> None:
    guarded = _guarded(tools, "live")
    with pytest.raises(ToolError, match="Cambiar el sonido en vivo"):
        guarded.set_module("REVERB", on=True)
    assert guarded.get_current_patch()["slot"] == 1  # reading is always allowed
    tools.undo()  # the GUI's own buttons are not limited


def test_denied_rename_but_effects_allowed(tools: PedalTools) -> None:
    guarded = _guarded(tools, "rename")
    with pytest.raises(ToolError, match="Renombrar presets"):
        guarded.propose_preset_edits([{"slot": 5, "name": "NUEVO"}])
    on = tools.editor.state.presets[5].module(8).switch
    result = guarded.propose_preset_edits([{"slot": 5, "modules": [{"module": "REVERB",
                                                                    "on": not on}]}])
    assert result["proposed"]


def test_denied_move(tools: PedalTools) -> None:
    with pytest.raises(ToolError, match="Mover y reordenar"):
        _guarded(tools, "move").propose_preset_edits(edits=[{"slot": 5, "copy_from": 6}])


def test_dialog_saves_each_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from ge150.ui.ai_permissions_dialog import AiPermissionsDialog

    QApplication.instance() or QApplication([])
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    dialog = AiPermissionsDialog()
    assert all(s.isChecked() for s in dialog.switches.values())
    dialog.switches["move"].click()
    assert ai_permissions.load().denied == {"move"}
    dialog.allow_all()
    assert ai_permissions.load().denied == frozenset()


def test_the_bridge_obeys_the_saved_permissions(tools: PedalTools, tmp_path: Path) -> None:
    from ge150.mcp_server.bridge import LocalServer, find_editor

    server = LocalServer(GuardedTools(tools), path=tmp_path / "mcp.json").start()
    try:
        remote = find_editor(server.path)
        assert remote is not None
        remote.set_module("DS", False)  # allowed: no file yet
        ai_permissions.save(Permissions(frozenset({"live"})))  # applies to the next call
        with pytest.raises(ToolError, match="gear button"):
            remote.set_module("DS", True)
        assert remote.list_presets()["presets"]
    finally:
        server.stop()
