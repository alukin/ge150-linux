"""System and rhythm-box commands of ``ge150ctl`` (plan.md §2.11).

These are global settings, not presets: the pedal keeps them, and the previous value can
be set back at any time, so they do not ask for confirmation.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import replace

from ge150.model import settings
from ge150.model.settings import RhythmValues, SystemValues
from ge150.protocol.session import DeviceSession
from ge150.services import reader
from ge150.services.editor import Editor, EditorError

Handler = Callable[[argparse.Namespace], int]
ArgSetup = Callable[[argparse.ArgumentParser], object]

SYSTEM_FIELDS = ("input", "screen", "cab-left", "cab-right", "otg")
RHYTHM_FIELDS = ("state", "mode", "style", "bpm", "vol")


def _choice(value: str, options: tuple[str, ...], what: str) -> int:
    names = [o.lower() for o in options]
    if value.lower() not in names:
        raise EditorError(f"{what} must be one of: {', '.join(options)}")
    return names.index(value.lower())


def _int(value: str, what: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise EditorError(f"{what} must be a number, got {value!r}") from None


def _print(rows: list[tuple[str, str]]) -> None:
    for name, value in rows:
        print(f"{name:12} {value}")


def apply_system_field(values: SystemValues, field: str, value: str) -> SystemValues:
    try:
        if field == "input":
            return replace(values, input_level=settings.level_index(value))
        if field == "otg":
            return replace(values, otg_level=settings.level_index(value))
    except ValueError as exc:
        raise EditorError(str(exc)) from None
    if field == "screen":
        return replace(values, screen=_int(value, "screen"))
    on = bool(_choice(value, settings.CAB_THRU, "CAB SIM THRU"))
    return replace(values, **{"cab_left_on" if field == "cab-left" else "cab_right_on": on})


def apply_rhythm_field(values: RhythmValues, field: str, value: str) -> RhythmValues:
    if field == "state":
        return replace(values, on=bool(_choice(value, ("off", "on"), "state")))
    if field == "mode":
        return replace(values, mode=_choice(value, settings.RHYTHM_MODES, "mode"), style=0)
    if field == "style":
        return replace(values, style=_int(value, "style") - 1)  # pedal numbering
    if field == "bpm":
        return replace(values, bpm=_int(value, "bpm"))
    return replace(values, volume=_int(value, "vol"))


def cmd_system_set(args: argparse.Namespace) -> int:
    session: DeviceSession = args.make_session()
    with session:
        editor = Editor(session)
        reader.read_all_presets(session)  # the system block arrives after the dump
        current = editor.system_values()
        if current is None:
            raise EditorError("the pedal did not send its system settings")
        new = apply_system_field(current, args.field, args.value)
        try:
            editor.set_system_values(new)
        except ValueError as exc:
            raise EditorError(str(exc)) from None
        session.flush()
    _print(new.describe())
    return 0


def cmd_rhythm_set(args: argparse.Namespace) -> int:
    session: DeviceSession = args.make_session()
    with session:
        editor = Editor(session)
        reader.read_rhythm(session)
        current = editor.rhythm_values() or RhythmValues()
        new = apply_rhythm_field(current, args.field, args.value)
        try:
            editor.set_rhythm_values(new)
        except ValueError as exc:
            raise EditorError(str(exc)) from None
        session.flush()
    _print(new.describe())
    return 0


def _setup_system(p: argparse.ArgumentParser) -> None:
    p.add_argument("field", choices=SYSTEM_FIELDS)
    p.add_argument("value", help="input/otg: 0, 0.5, -5, - (mute); screen: 0-20; cab: on/thru")


def _setup_rhythm(p: argparse.ArgumentParser) -> None:
    p.add_argument("field", choices=RHYTHM_FIELDS)
    p.add_argument("value", help="state: on/off; mode: rhythm/metronome; style: 1..; bpm; vol")


SETTINGS_COMMANDS: dict[str, tuple[Handler, str, ArgSetup]] = {
    "system-set": (cmd_system_set, "change a system setting (input, screen, cab, otg)",
                   _setup_system),
    "rhythm-set": (cmd_rhythm_set, "change the rhythm box (state, mode, style, bpm, vol)",
                   _setup_rhythm),
}
