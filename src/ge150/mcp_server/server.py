"""``ge150-mcp``: MCP server (stdio) that lets Claude Code, Codex or any MCP client drive
the pedal through :class:`~ge150.mcp_server.tools.PedalTools`.

    ge150-mcp            # the GE150 editor if it is open, else the pedal on USB
    ge150-mcp --sim      # the built-in simulator when the editor is not open

Only one program may own the pedal. When the GE150 editor is open this server forwards every
call to it (``bridge.py``): the GUI shows the AI's changes at once and asks the user before
anything is stored. Otherwise it opens the pedal itself and storing is refused.
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
STORE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)
WEB = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)
WEB_STORE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=True)


class ParamValue(BaseModel):
    name: str = Field(description="parameter name from get_catalog, e.g. GAIN")
    value: str = Field(description="display value, e.g. 65, -3.5, 380 or an enum option")


class ModuleSetting(BaseModel):
    module: str = Field(description="FX, DS, AMP, CAB, NS, EQ, MOD, DELAY or REVERB")
    on: bool
    model: str = Field("", description="model name from get_catalog; empty keeps the current")
    params: list[ParamValue] = Field(default_factory=list)


class PresetModuleEdit(BaseModel):
    module: str = Field(description="FX, DS, AMP, CAB, NS, EQ, MOD, DELAY or REVERB")
    on: bool | None = Field(None, description="omit to keep the preset's on/off")
    model: str = Field("", description="model name from get_catalog; empty keeps the current")
    params: list[ParamValue] = Field(default_factory=list)


class PresetEditSpec(BaseModel):
    slot: int = Field(description="stored preset number 1..200")
    modules: list[PresetModuleEdit]


def _call(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except ToolError as exc:
        raise MCPToolError(str(exc)) from exc


def build_server(tools: PedalTools | Any) -> MCPServer:
    """``tools``: a :class:`PedalTools` or a proxy with the same methods (``bridge.py``)."""
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
    def get_guitar() -> dict[str, Any]:
        """The guitar the user is playing (brand, model, year, woods, pickups, electronics,
        strings, tuning), as registered in the GE150 editor. Its pickups and woods shape how
        much gain, EQ and brightness a patch needs."""
        return _call(tools.get_guitar)

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

    @server.tool(annotations=READ)
    def get_presets(query: str) -> dict[str, Any]:
        """Every stored preset whose name contains query (e.g. "av83"), decoded, in one
        call."""
        return _call(lambda: tools.get_presets(query))

    @server.tool(annotations=LIVE)
    def propose_preset_edits(edits: list[PresetEditSpec], summary: str = "") -> dict[str, Any]:
        """Propose changes to several STORED presets at once (values per preset, so
        relative changes like "-10 %" are computed by you from get_presets). Nothing is
        written: the GE150 editor shows a review table and the user applies or discards.
        summary: one line for the user."""
        data = [e.model_dump() for e in edits]
        return _call(lambda: tools.propose_preset_edits(data, summary))

    @server.tool(annotations=STORE)
    def save_preset(slot: int = 0, name: str = "") -> dict[str, Any]:
        """Store the current sound in preset ``slot`` (0 = the current one), optionally
        renamed (up to 14 chars). The GE150 editor asks the user to confirm; only when
        the user asked to save."""
        return _call(lambda: tools.save_preset(slot, name))

    @server.tool(annotations=WEB)
    def tone3000_search(query: str) -> dict[str, Any]:
        """Search cabinet IRs on TONE3000 (e.g. "Marshall 1960 V30"). Rate-limited: few,
        precise searches."""
        return _call(lambda: tools.tone3000_search(query))

    @server.tool(annotations=WEB)
    def tone3000_get(tone_id: int) -> dict[str, Any]:
        """A TONE3000 tone: title, author, licence and its IR files."""
        return _call(lambda: tools.tone3000_get(tone_id))

    @server.tool(annotations=WEB_STORE)
    def load_tone3000_ir(slot: int = 0, tone_id: int = 0, model_id: int = 0,
                         name: str = "", use: bool = True) -> dict[str, Any]:
        """Download a TONE3000 IR, store it in a user IR slot (CAB 27..36) and select it
        in the CAB module (live; use=false only stores it). slot 0 = automatic: the slot
        already holding this IR, else a free one, else the editor asks the user which one
        to overwrite. tone_id 0 opens the TONE3000 catalogue so the user picks one. The
        GE150 editor asks the user to confirm."""
        return _call(lambda: tools.load_tone3000_ir(slot, tone_id, model_id, name, use))

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
    parser.add_argument("--standalone", action="store_true",
                        help="open the pedal even if the GE150 editor is running")
    parser.add_argument("--editor-only", action="store_true",
                        help="only forward to the GE150 editor; never open the pedal (used by "
                             "the editor's own AI panel)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    # stdout carries the MCP protocol: every log goes to stderr.
    logging.basicConfig(stream=sys.stderr,
                        level=logging.DEBUG if args.verbose else logging.WARNING)
    from ge150.mcp_server.bridge import find_editor

    remote = None if args.standalone else find_editor()
    if remote is not None:
        logging.info("forwarding to the GE150 editor at %s", remote.url)
        build_server(remote).run("stdio")
        return 0
    if args.editor_only:
        print("ge150-mcp: the GE150 editor is not answering (--editor-only)", file=sys.stderr)
        return 1
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
