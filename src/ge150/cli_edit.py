"""Editing commands of ``ge150ctl`` (live edits, saving, IR slots).

Live edits only change the pedal's edit buffer. Commands that store data on the
pedal ask for confirmation unless ``--yes`` is given (plan.md §0, rule 4).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from ge150.formats import amp_nr, mbf, mo_json, wav_ir
from ge150.model.catalog import load_catalog
from ge150.model.preset import MODULES
from ge150.protocol import messages as msg
from ge150.protocol.opcodes import Op
from ge150.protocol.session import DeviceSession
from ge150.services import backup as backup_service
from ge150.services import reader
from ge150.services.editor import Editor, EditorError

Handler = Callable[[argparse.Namespace], int]
ArgSetup = Callable[[argparse.ArgumentParser], object]


def _confirm(args: argparse.Namespace, what: str) -> bool:
    if getattr(args, "yes", False):
        return True
    if not sys.stdin.isatty():
        print(f"refusing to {what} without --yes", file=sys.stderr)
        return False
    return input(f"{what}? [y/N] ").strip().lower() in ("y", "yes", "s", "si", "sí")


def _editor(args: argparse.Namespace, presets: bool = False) -> tuple[DeviceSession, Editor]:
    session: DeviceSession = args.make_session()
    session.start()
    editor = Editor(session)
    if presets:
        reader.read_all_presets(session)
    reader.read_current(session)
    return session, editor


def _safe(name: str) -> str:
    """File-name friendly version of a preset or IR name."""
    clean = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()
    return clean or "unnamed"


def _value(text: str) -> float | str:
    try:
        return float(text)
    except ValueError:
        return text


def _show_module(editor: Editor, index: int) -> None:
    block = editor.module(index)
    model = editor.catalog[index].model_for_type(block.type)
    params = ", ".join(f"{p.name}={p.format(block.words[p.word])}"
                       for p in (model.params if model else ()))
    label = model.label if model else f"?{block.type}"
    print(f"{MODULES[index].name}: {'ON' if block.switch else 'off'} {label}  {params}")


# --- offline -----------------------------------------------------------------


def cmd_models(args: argparse.Namespace) -> int:
    index = Editor.module_index(args.module)
    info = load_catalog()[index]
    for i, model in enumerate(info.models):
        params = ", ".join(p.name for p in model.params)
        flags = " (user slot)" if model.user_slot else ""
        print(f"{i:3d}  {model.label:22}{flags}  {params}")
    return 0


# --- live edits --------------------------------------------------------------


def cmd_set(args: argparse.Namespace) -> int:
    session, editor = _editor(args)
    with session:
        index = Editor.module_index(args.module)
        raw = editor.set_param(index, args.param, _value(args.value))
        session.flush()
        print(f"raw={raw}")
        _show_module(editor, index)
    return 0


def cmd_switch(args: argparse.Namespace) -> int:
    session, editor = _editor(args)
    with session:
        index = Editor.module_index(args.module)
        editor.set_switch(index, args.command == "on")
        session.flush()
        _show_module(editor, index)
    return 0


def cmd_type(args: argparse.Namespace) -> int:
    session, editor = _editor(args)
    with session:
        index = Editor.module_index(args.module)
        models = editor.catalog[index].models
        if args.model.isdigit():
            type_index = int(args.model) - 1  # pedal numbering (01:...)
        else:
            names = [m.name.lower() for m in models]
            if args.model.lower() not in names:
                raise EditorError(f"unknown model {args.model!r}; see: ge150ctl models")
            type_index = names.index(args.model.lower())
        editor.set_type(index, type_index)
        session.flush()
        _show_module(editor, index)
    return 0


def cmd_exp(args: argparse.Namespace) -> int:
    session, editor = _editor(args)
    with session:
        editor.set_exp(args.key.upper(), args.value)
        session.flush()
        print(editor.state.edit.exp if editor.state.edit else "?")
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    session, editor = _editor(args, presets=True)
    with session:
        if editor.state.dirty and not _confirm(args, "discard unsaved changes of the pedal"):
            return 1
        editor.select(args.slot)
        print(f"selected {args.slot}: {editor.state.presets[args.slot].name}")
    return 0


# --- persistent ----------------------------------------------------------------


def cmd_save(args: argparse.Namespace) -> int:
    session, editor = _editor(args, presets=True)
    with session:
        slot = args.slot or editor.state.current_slot
        old = editor.state.presets.get(slot or 0)
        what = f"overwrite preset {slot} ({old.name if old else '?'})"
        if not _confirm(args, what):
            return 1
        preset = editor.save(slot, args.name)
        print(f"saved {preset.slot}: {preset.name}")
    return 0


def cmd_rename(args: argparse.Namespace) -> int:
    session, editor = _editor(args, presets=True)
    with session:
        old = editor.state.presets[args.slot].name
        if not _confirm(args, f"rename preset {args.slot} {old!r} -> {args.name!r}"):
            return 1
        editor.rename(args.slot, args.name)
        print(f"renamed {args.slot}: {args.name}")
    return 0


def cmd_copy(args: argparse.Namespace) -> int:
    session, editor = _editor(args, presets=True)
    with session:
        src, dst = editor.state.presets[args.source], editor.state.presets[args.target]
        if not _confirm(args, f"overwrite preset {dst.slot} ({dst.name}) with {src.name}"):
            return 1
        editor.copy_preset(args.source, args.target)
        print(f"copied {args.source} -> {args.target}")
    return 0


# --- .mo preset files -----------------------------------------------------------


def cmd_export(args: argparse.Namespace) -> int:
    """Read-only: save stored presets as vendor-compatible .mo files."""
    session, editor = _editor(args, presets=True)
    with session:
        presets = editor.state.presets
    slots = range(1, 201) if args.slot == "all" else [int(args.slot)]
    out = Path(args.path)
    if args.slot == "all" or out.is_dir():
        out.mkdir(parents=True, exist_ok=True)
    for slot in slots:
        preset = presets[slot]
        target = out / f"{slot:03d} {_safe(preset.name)}.mo" if out.is_dir() else out
        mo_json.save(target, preset)
        print(f"{slot:3d} -> {target}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    session, editor = _editor(args, presets=True)
    with session:
        base = editor.state.presets[args.slot]
        preset = mo_json.load(args.file, base)
        if not _confirm(args, f"overwrite preset {args.slot} ({base.name}) with {preset.name!r}"):
            return 1
        editor.copy_preset_data(preset)
        print(f"imported {args.file} -> {args.slot}: {preset.name}")
    return 0


# --- full backup ---------------------------------------------------------------


def _progress(label: str, step: int, total: int) -> None:
    print(f"\r[{step:3d}/{total}] {label:<16}", end="", flush=True, file=sys.stderr)


def cmd_backup(args: argparse.Namespace) -> int:
    """Read-only: save presets, system, rhythm and user IRs as a vendor .mbf file."""
    session, editor = _editor(args)
    with session:
        backup = backup_service.create_backup(editor, _progress)
    print(file=sys.stderr)
    mbf.save(args.file, backup)
    print(f"saved {args.file}: {len(backup.presets)} presets, {len(backup.irs)} IRs")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    backup = mbf.load(args.file)
    if not _confirm(args, f"OVERWRITE ALL 200 presets (and {len(backup.irs)} IRs) from "
                          f"{args.file}"):
        return 1
    session, editor = _editor(args, presets=True)
    with session:
        backup_service.restore_backup(editor, backup, _progress, include_irs=not args.no_ir)
    print(file=sys.stderr)
    print(f"restored {args.file}")
    return 0


# --- IR slots ------------------------------------------------------------------


def cmd_ir_export(args: argparse.Namespace) -> int:
    """Read-only: save every user IR of the pedal as a 44.1 kHz 24-bit WAV."""
    out = Path(args.directory)
    out.mkdir(parents=True, exist_ok=True)
    session, editor = _editor(args)
    with session:
        chunks = editor.read_ir_backup()
    for chunk in chunks:
        path = out / f"IR{(chunk.slot or 0) + 1:02d} {_safe(chunk.name)}.wav"
        path.write_bytes(wav_ir.ir_to_wav(wav_ir.unpack_planar(chunk.data)))
        print(f"slot {chunk.slot}: {path}")
    if not chunks:
        print("no user IRs on the pedal")
    return 0


def cmd_ir_upload(args: argparse.Namespace) -> int:
    payload = wav_ir.load_ir_file(args.file)
    name = (args.name or Path(args.file).stem)[: msg.USER_NAME_LEN]
    session, editor = _editor(args)
    with session:
        names = reader.read_user_names(session)
        old = names.ir[args.slot - 1]
        if not _confirm(args, f"replace IR slot {args.slot} ({old}) with {name!r}"):
            return 1
        editor.upload_user_slot(Op.USER_IR, args.slot - 1, name, payload)
        print(f"IR slot {args.slot}: {editor.state.user_names.ir[args.slot - 1]}"
              if editor.state.user_names else "uploaded")
    return 0


def cmd_ir_delete(args: argparse.Namespace) -> int:
    session, editor = _editor(args)
    with session:
        old = reader.read_user_names(session).ir[args.slot - 1]
        if not _confirm(args, f"delete IR slot {args.slot} ({old})"):
            return 1
        editor.delete_user_slot(Op.USER_IR, args.slot - 1)
        print(f"IR slot {args.slot} deleted")
    return 0


def cmd_nr_upload(args: argparse.Namespace) -> int:
    payload = amp_nr.load_nr_file(args.file)
    name = (args.name or Path(args.file).stem)[: msg.USER_NAME_LEN]
    session, editor = _editor(args)
    with session:
        old = reader.read_user_names(session).nr[args.slot - 1]
        if not _confirm(args, f"replace NR slot {args.slot} ({old}) with {name!r}"):
            return 1
        editor.upload_user_slot(Op.USER_NR, args.slot - 1, name, payload)
        names = editor.state.user_names
        print(f"NR slot {args.slot}: {names.nr[args.slot - 1] if names else '?'}")
    return 0


def cmd_nr_delete(args: argparse.Namespace) -> int:
    session, editor = _editor(args)
    with session:
        old = reader.read_user_names(session).nr[args.slot - 1]
        if not _confirm(args, f"delete NR slot {args.slot} ({old})"):
            return 1
        editor.delete_user_slot(Op.USER_NR, args.slot - 1)
        print(f"NR slot {args.slot} deleted")
    return 0


# --- registry ------------------------------------------------------------------


def _module_param(p: argparse.ArgumentParser) -> None:
    p.add_argument("module", help="fx, ds, amp, cab, ns, eq, mod, delay, reverb")


def _yes(p: argparse.ArgumentParser) -> None:
    p.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")


def _setup_set(p: argparse.ArgumentParser) -> None:
    _module_param(p)
    p.add_argument("param")
    p.add_argument("value", help="display value (e.g. 50, -3.5, 6L6)")


def _setup_type(p: argparse.ArgumentParser) -> None:
    _module_param(p)
    p.add_argument("model", help="number as on the pedal (1..) or model name")


def _setup_exp(p: argparse.ArgumentParser) -> None:
    p.add_argument("key", choices=[k.lower() for k in ("MODULE_CTRL", "PARA_CTRL", "FUN_SWITCH",
                                                       "VOL_SWITCH", "VOL_MIN", "VOL_MAX")])
    p.add_argument("value", type=int)


def _setup_slot(p: argparse.ArgumentParser) -> None:
    p.add_argument("slot", type=int, help="1..200")
    _yes(p)


def _setup_save(p: argparse.ArgumentParser) -> None:
    p.add_argument("--slot", type=int, help="target slot (default: current)")
    p.add_argument("--name", help="new name (default: keep)")
    _yes(p)


def _setup_rename(p: argparse.ArgumentParser) -> None:
    p.add_argument("slot", type=int)
    p.add_argument("name")
    _yes(p)


def _setup_copy(p: argparse.ArgumentParser) -> None:
    p.add_argument("source", type=int)
    p.add_argument("target", type=int)
    _yes(p)


def _setup_export(p: argparse.ArgumentParser) -> None:
    p.add_argument("slot", help="1..200 or 'all'")
    p.add_argument("path", help="output .mo file or directory")


def _setup_import(p: argparse.ArgumentParser) -> None:
    p.add_argument("file", help=".mo preset file")
    p.add_argument("slot", type=int, help="target slot 1..200")
    _yes(p)


def _setup_restore(p: argparse.ArgumentParser) -> None:
    p.add_argument("file", help=".mbf backup")
    p.add_argument("--no-ir", action="store_true", help="do not restore the user IRs")
    _yes(p)


def _setup_ir_upload(p: argparse.ArgumentParser) -> None:
    p.add_argument("slot", type=int, choices=range(1, 11), metavar="SLOT", help="1..10")
    p.add_argument("file", help="WAV impulse response")
    p.add_argument("--name", help="name shown on the pedal (default: file name)")
    _yes(p)


def _setup_nr_upload(p: argparse.ArgumentParser) -> None:
    p.add_argument("slot", type=int, choices=range(1, 11), metavar="SLOT", help="1..10")
    p.add_argument("file", help=".amp NR capture")
    p.add_argument("--name", help="name shown on the pedal (default: file name)")
    _yes(p)


def _setup_ir_delete(p: argparse.ArgumentParser) -> None:
    p.add_argument("slot", type=int, choices=range(1, 11), metavar="SLOT", help="1..10")
    _yes(p)


EDIT_COMMANDS: dict[str, tuple[Handler, str, ArgSetup]] = {
    "models": (cmd_models, "list the models of a module (offline)", _module_param),
    "set": (cmd_set, "live: set a parameter of the current preset", _setup_set),
    "on": (cmd_switch, "live: switch a module on", _module_param),
    "off": (cmd_switch, "live: switch a module off", _module_param),
    "type": (cmd_type, "live: change the model of a module", _setup_type),
    "exp": (cmd_exp, "live: set an expression-pedal field", _setup_exp),
    "select": (cmd_select, "select a preset on the pedal", _setup_slot),
    "save": (cmd_save, "STORE the edit buffer into a preset slot", _setup_save),
    "rename": (cmd_rename, "STORE a new preset name", _setup_rename),
    "copy": (cmd_copy, "STORE a copy of a preset into another slot", _setup_copy),
    "export": (cmd_export, "save stored presets as .mo files", _setup_export),
    "import": (cmd_import, "STORE a .mo preset file into a slot", _setup_import),
    "backup": (cmd_backup, "save a full .mbf backup (read-only)",
               lambda p: p.add_argument("file")),
    "restore": (cmd_restore, "OVERWRITE the whole pedal from a .mbf backup", _setup_restore),
    "ir-export": (cmd_ir_export, "save the pedal's user IRs as WAV files",
                  lambda p: p.add_argument("directory")),
    "ir-upload": (cmd_ir_upload, "STORE a WAV into a user IR slot", _setup_ir_upload),
    "ir-delete": (cmd_ir_delete, "DELETE a user IR slot", _setup_ir_delete),
    "nr-upload": (cmd_nr_upload, "STORE an .amp capture into a user NR slot", _setup_nr_upload),
    "nr-delete": (cmd_nr_delete, "DELETE a user NR slot", _setup_ir_delete),
}
