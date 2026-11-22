"""``ge150ctl ai``: describe a sound and get it on the pedal (AI tone assistant)."""

from __future__ import annotations

import argparse
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


def _setup_ai(p: argparse.ArgumentParser) -> None:
    p.add_argument("request", nargs="+", help='e.g. "Slash, Sweet Child O\' Mine"')
    p.add_argument("--provider", choices=sorted(tone_ai.BACKENDS),
                   help="default: the first one installed")
    p.add_argument("--model", help="model name passed to the CLI")
    p.add_argument("--dry-run", action="store_true", help="show the proposal, send nothing")


AI_COMMANDS: dict[str, tuple[Handler, str, ArgSetup]] = {
    "ai": (cmd_ai, "live: describe a sound and let Claude/Codex set the patch", _setup_ai),
}
