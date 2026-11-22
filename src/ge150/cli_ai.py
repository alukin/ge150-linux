"""``ge150ctl ai``: describe a sound and get it on the pedal (AI tone assistant)."""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Callable

from ge150.services import reader, tone_ai
from ge150.services.editor import Editor

Handler = Callable[[argparse.Namespace], int]
ArgSetup = Callable[[argparse.ArgumentParser], object]


def cmd_ai(args: argparse.Namespace) -> int:
    backend = tone_ai.make_backend(args.provider or "", args.model or "")
    session = args.make_session()
    with session:
        editor = Editor(session)
        reader.read_user_names(session)
        reader.read_current(session)
        print(f"asking {backend.name}…")
        assistant = tone_ai.ToneAssistant(editor, backend)
        proposal = assistant.ask(" ".join(args.request), apply=not args.dry_run)
        session.flush()
    if proposal.name:
        print(f"\n{proposal.name}")
    print(proposal.explanation, "\n")
    for row in proposal.describe(editor.catalog):
        print("  " + row)
    for warning in proposal.warnings:
        print(f"  ! {warning}")
    print("\n(dry run: nothing sent)" if args.dry_run else
          "\napplied live: use `ge150ctl save` to store it")
    return 0


def cmd_mcp_install(args: argparse.Namespace) -> int:
    from ge150.mcp_server import install

    clients = [args.client] if args.client else [c for c in ("claude", "codex")
                                                  if shutil.which(c)]
    if not clients:
        print("install Claude Code (claude) or Codex (codex) first")
        return 1
    for client in clients:
        print(f"{client}: {install.install(client, args.sim)}")
    print("\nnow ask, e.g.: claude \"ponme el tono de Gilmour en Comfortably Numb\"\n"
          "(close the GE150 editor first: only one program can use the pedal)")
    return 0


def _setup_mcp_install(p: argparse.ArgumentParser) -> None:
    p.add_argument("--client", choices=("claude", "codex"), help="default: every one installed")
    p.add_argument("--sim", action="store_true", help="register the simulator instead")


def _setup_ai(p: argparse.ArgumentParser) -> None:
    p.add_argument("request", nargs="+", help='e.g. "Slash, Sweet Child O\' Mine"')
    p.add_argument("--provider", choices=sorted(tone_ai.BACKENDS),
                   help="default: the first one installed")
    p.add_argument("--model", help="model name passed to the CLI")
    p.add_argument("--dry-run", action="store_true", help="show the proposal, send nothing")


AI_COMMANDS: dict[str, tuple[Handler, str, ArgSetup]] = {
    "ai": (cmd_ai, "live: describe a sound and let Claude/Codex set the patch", _setup_ai),
    "mcp-install": (cmd_mcp_install, "register the GE150 MCP server in Claude Code / Codex",
                    _setup_mcp_install),
}
