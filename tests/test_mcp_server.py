import json
from collections.abc import Iterator

import anyio
import pytest

pytest.importorskip("mcp")

from mcp.client.client import Client

from ge150.mcp_server import install
from ge150.mcp_server.server import build_server
from ge150.mcp_server.tools import PedalTools
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


def _data(result: object) -> dict:
    structured = getattr(result, "structured_content", None) or getattr(
        result, "structuredContent", None)
    if structured:
        return structured.get("result", structured)
    text = result.content[0].text  # type: ignore[attr-defined]
    return json.loads(text)


def test_server_lists_and_runs_tools(tools: PedalTools) -> None:
    server = build_server(tools)

    async def scenario() -> None:
        async with Client(server) as client:
            listed = await client.list_tools()
            names = {t.name for t in listed.tools}
            assert names == {"get_catalog", "get_current_patch", "list_presets", "get_preset",
                             "list_user_irs", "get_settings", "set_module", "apply_patch",
                             "undo", "select_preset", "save_preset", "get_guitar",
                             "tone3000_search", "tone3000_get", "load_tone3000_ir",
                             "get_presets", "propose_preset_edits"}
            read_only = {t.name for t in listed.tools if t.annotations
                         and t.annotations.read_only_hint}
            assert "get_current_patch" in read_only and "set_module" not in read_only
            result = await client.call_tool("apply_patch", {"modules": [
                {"module": "AMP", "on": True, "model": "PLX100",
                 "params": [{"name": "GAIN", "value": "65"}]}]})
            assert not getattr(result, "is_error", getattr(result, "isError", False))
            patch = _data(await client.call_tool("get_current_patch", {}))
            assert patch["modules"][2]["model"] == "PLX100"
            bad = await client.call_tool("get_catalog", {"module": "nope"})
            assert getattr(bad, "is_error", getattr(bad, "isError", False))

    anyio.run(scenario)


def test_install_commands_use_the_server_script() -> None:
    remove, add = install.install_commands("claude", sim=True)
    assert remove[:3] == ["claude", "mcp", "remove"]
    assert add[:6] == ["claude", "mcp", "add", "--scope", "user", "ge150"]
    assert add[-1] == "--sim" and "ge150" in " ".join(add[7:])
    assert install.install_commands("codex")[1][:4] == ["codex", "mcp", "add", "ge150"]
