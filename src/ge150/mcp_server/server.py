"""``ge150-mcp``: MCP server (stdio) that lets Claude Code, Codex or any MCP client drive
the pedal through :class:`~ge150.mcp_server.tools.PedalTools`.

    ge150-mcp            # the pedal on USB
    ge150-mcp --sim      # the built-in simulator

Only one program may own the pedal: close the GE150 editor while this server runs (the
editor will host the server itself in phase 11.2, docs/plan-ia-tone3000.md).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from typing import Any, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ge150 import __version__
from ge150.mcp_server.tools import INSTRUCTIONS, PedalTools, ToolError

T = TypeVar("T")
READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)
LIVE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)


class ParamValue(BaseModel):
    name: str = Field(description="parameter name from get_catalog, e.g. GAIN")
    value: str = Field(description="display value, e.g. 65, -3.5, 380 or an enum option")


class ModuleSetting(BaseModel):
    module: str = Field(description="FX, DS, AMP, CAB, NS, EQ, MOD, DELAY or REVERB")
    on: bool
    model: str = Field("", description="model name from get_catalog; empty keeps the current")
    params: list[ParamValue] = Field(default_factory=list)


def _call(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except ToolError as exc:
        raise MCPToolError(str(exc)) from exc


def build_server(tools: PedalTools) -> MCPServer:
    server: MCPServer = MCPServer("ge150", title="MOOER GE150", version=__version__,
                                  instructions=INSTRUCTIONS)

    @server.tool(annotations=READ)
    def get_catalog(module: str = "") -> dict[str, Any]:
        """Modules of the pedal, or the models of one module (with the real gear each one
        is based on and the name, range and options of every parameter)."""
        return _call(lambda: tools.get_catalog(module))

    @server.tool(annotations=READ)
    def get_current_patch() -> dict[str, Any]:
        """The sound loaded now: every module (on/off, model, parameter values), the preset
        slot and name, and whether it has unsaved changes."""
        return _call(tools.get_current_patch)

    @server.tool(annotations=READ)
    def list_presets(query: str = "") -> dict[str, Any]:
        """The 200 stored presets (slot and name), optionally filtered by text."""
        return _call(lambda: tools.list_presets(query))

    @server.tool(annotations=READ)
    def get_preset(slot: int) -> dict[str, Any]:
        """A stored preset decoded (without loading it)."""
        return _call(lambda: tools.get_preset(slot))

    @server.tool(annotations=READ)
    def list_user_irs() -> dict[str, Any]:
        """Names of the user cabinet IR slots (CAB 27-36) and NR amp captures (AMP 56-65)."""
        return _call(tools.list_user_irs)

    @server.tool(annotations=READ)
    def get_settings() -> dict[str, Any]:
        """System settings (input/OTG level, screen, CAB SIM THRU) and the rhythm box."""
        return _call(tools.get_settings)

    @server.tool(annotations=LIVE)
    def set_module(module: str, on: bool | None = None, model: str = "",
                   params: list[ParamValue] | None = None) -> dict[str, Any]:
        """Change one module live: switch it on/off, pick a model and set parameters.
        Not saved; undo reverts it."""
        values = {p.name: p.value for p in params or []}
        return _call(lambda: tools.set_module(module, on, model, values))

    @server.tool(annotations=LIVE)
    def apply_patch(modules: list[ModuleSetting], name: str = "") -> dict[str, Any]:
        """Set several modules at once (a whole sound). Modules not listed are unchanged.
        Not saved; undo reverts it."""
        data = [m.model_dump() for m in modules]
        return _call(lambda: tools.apply_patch(data, name))

    @server.tool(annotations=LIVE)
    def undo() -> dict[str, Any]:
        """Go back to the sound before the last set_module/apply_patch of this session."""
        return _call(tools.undo)

    @server.tool(annotations=LIVE)
    def select_preset(slot: int, discard_changes: bool = False) -> dict[str, Any]:
        """Load a stored preset. If the current one has unsaved changes, ask the user first
        and pass discard_changes=true only if they agree."""
        return _call(lambda: tools.select_preset(slot, discard_changes))

    return server


def _open_editor(args: argparse.Namespace) -> Any:
    from ge150.protocol.session import DeviceSession
    from ge150.services.editor import Editor

    if args.sim:
        from ge150.sim.sim_transport import SimTransport

        transport: Any = SimTransport()
    else:
        from ge150.usb import open_transport

        transport = open_transport(args.backend, args.device)
    session = DeviceSession(transport).start()
    editor = Editor(session)
    editor.sync()
    return session, editor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ge150-mcp", description=__doc__.splitlines()[0])
    parser.add_argument("--sim", action="store_true", help="use the built-in simulator")
    parser.add_argument("--backend", choices=("auto", "hidraw", "usb"), default="auto")
    parser.add_argument("--device", help="hidraw node, e.g. /dev/hidraw4")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    # stdout carries the MCP protocol: every log goes to stderr.
    logging.basicConfig(stream=sys.stderr,
                        level=logging.DEBUG if args.verbose else logging.WARNING)
    try:
        session, editor = _open_editor(args)
    except Exception as exc:
        print(f"ge150-mcp: cannot open the pedal: {exc}", file=sys.stderr)
        return 1
    try:
        build_server(PedalTools(editor)).run("stdio")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
