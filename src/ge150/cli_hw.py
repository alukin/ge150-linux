"""``ge150ctl hw-check``: verify the editor's writes on the real pedal (``services/hw_check``)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from ge150.services.editor import Editor
from ge150.services.hw_check import HardwareCheck, save_report


def cmd_hw_check(args: argparse.Namespace) -> int:
    from ge150.mcp_server.bridge import find_editor

    if not args.sim and find_editor() is not None:
        print("error: el editor GE150 está abierto; ciérralo (la pedalera admite un solo "
              "programa a la vez)", file=sys.stderr)
        return 2
    slots = tuple(int(s) for s in args.slots.split(","))
    if len(slots) != 3:
        print("error: --slots necesita tres presets, p. ej. 198,199,200", file=sys.stderr)
        return 2
    with args.make_session() as session:
        editor = Editor(session)
        check = HardwareCheck(editor, (slots[0], slots[1], slots[2]),
                              tap_seconds=args.tap, backups=not args.no_backup,
                              only_tap=args.only_tap)
        if not args.yes and not _confirm(editor, slots):
            print("cancelado")
            return 1
        report = check.run()
    path = save_report(report)
    print()
    print(report.markdown())
    print(f"Informe guardado en {path}")
    return 0 if report.passed else 1


def _confirm(editor: Editor, slots: tuple[int, ...]) -> bool:
    from ge150.services import reader

    reader.read_all_presets(editor.session)
    names = ", ".join(f"{s:03d} «{editor.state.presets[s].name}»" for s in slots
                      if s in editor.state.presets)
    print(f"Se escribirán temporalmente los presets {names} y se dejarán como estaban.")
    print("Antes se hace un backup completo. ¿Continuar? [s/N] ", end="", flush=True)
    return sys.stdin.readline().strip().lower() in ("s", "si", "sí", "y", "yes")


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--slots", required=True,
                   help="tres presets de prueba que se pueden escribir, p. ej. 198,199,200")
    p.add_argument("--tap", type=float, default=0.0, metavar="SEGUNDOS",
                   help="también probar el TAP: te pide pisarlo durante estos segundos")
    p.add_argument("--no-backup", action="store_true", help="no hacer el backup previo")
    p.add_argument("--only-tap", action="store_true",
                   help="solo la prueba del TAP (no escribe presets; usar con --tap)")
    p.add_argument("-y", "--yes", action="store_true", help="no pedir confirmación")


Handler = Callable[[argparse.Namespace], int]
HW_COMMANDS: dict[str, tuple[Handler, str, Callable[[argparse.ArgumentParser], None]]] = {
    "hw-check": (cmd_hw_check, "verify bulk edit, preview and backup on the real pedal",
                 _setup),
}
