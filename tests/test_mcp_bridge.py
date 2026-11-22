import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from ge150.mcp_server.bridge import LocalServer, RemoteTools, find_editor
from ge150.mcp_server.tools import PedalTools, ToolError
from ge150.protocol.session import DeviceSession
from ge150.services.editor import Editor
from ge150.sim.sim_transport import SimTransport


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[PedalTools, LocalServer]]:
    session = DeviceSession(SimTransport(), frame_delay=0, multipart_delay=0)
    with session:
        editor = Editor(session)
        editor.sync()
        tools = PedalTools(editor, confirm=lambda q: True)
        calls: list[str] = []
        server = LocalServer(tools, calls.append, tmp_path / "mcp.json").start()
        server.calls = calls  # type: ignore[attr-defined]
        yield tools, server
        server.stop()


def test_remote_calls_reach_the_editor(served: tuple[PedalTools, LocalServer]) -> None:
    tools, server = served
    remote = find_editor(server.path)
    assert remote is not None
    assert oct(server.path.stat().st_mode & 0o777) == "0o600"
    remote.set_module("DS", False)
    assert tools.editor.state.dirty and server.calls[-1] == "set_module"  # type: ignore[attr-defined]
    assert remote.get_current_patch()["modules"][1]["on"] is False
    assert remote.undo()["undone"] is True
    assert remote.save_preset(30, "FROM AI")["name"] == "FROM AI"
    with pytest.raises(ToolError, match="unknown module"):
        remote.set_module("NOPE")


def test_bad_token_and_unknown_tools(served: tuple[PedalTools, LocalServer]) -> None:
    _, server = served
    with pytest.raises(ToolError, match="401"):
        RemoteTools(server.url, "wrong").list_presets()
    with pytest.raises(AttributeError):
        RemoteTools(server.url, "x").factory_reset  # noqa: B018


def test_stale_discovery_file_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    assert find_editor(path) is None
    path.write_text(f'{{"url": "http://127.0.0.1:9/call", "token": "t", "pid": {os.getpid()}}}')
    assert find_editor(path) is None
    server = LocalServer(object(), path=path).start()
    server.stop()
    assert not path.exists()


def test_discovery_without_xdg_runtime_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    from ge150.mcp_server.bridge import discovery_path

    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    run = Path(f"/run/user/{os.getuid()}")
    expected = run if run.is_dir() else Path(__import__("tempfile").gettempdir())
    assert discovery_path() == expected / "ge150" / "mcp.json"


def test_editor_only_never_opens_the_pedal(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from ge150.mcp_server import server

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))  # no editor here
    monkeypatch.setattr(server, "_open_editor", lambda args: pytest.fail("opened the pedal"))
    assert server.main(["--editor-only"]) == 1


def test_panel_agents_use_editor_only() -> None:
    from ge150.services.tone_agent import ClaudeAgent, CodexAgent

    assert ClaudeAgent().server[-1] == "--editor-only"
    assert CodexAgent().server[-1] == "--editor-only"
