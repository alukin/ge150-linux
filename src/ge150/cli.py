"""``ge150ctl``: command line access to the Mooer GE150."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path

from ge150.cli_ai import AI_COMMANDS
from ge150.cli_edit import EDIT_COMMANDS
from ge150.cli_settings import SETTINGS_COMMANDS
from ge150.cli_t3k import T3K_COMMANDS
from ge150.model.settings import RhythmValues, SystemValues
from ge150.protocol.framing import FrameDecoder, report_data, split_reports
from ge150.protocol.opcodes import op_name
from ge150.protocol.session import DeviceSession, SessionError
from ge150.services import reader
from ge150.services.editor import EditorError
from ge150.services.tone3000 import Tone3000Error
from ge150.services.tone_ai import ToneAIError
from ge150.usb import open_transport
from ge150.usb.transport import Transport, TransportError


def _transport(args: argparse.Namespace) -> Transport:
    if args.sim:
        from ge150.sim.sim_transport import SimTransport

        return SimTransport()
    return open_transport(args.backend, args.device)


def _session(args: argparse.Namespace) -> DeviceSession:
    session = DeviceSession(_transport(args))
    if args.raw:
        session.add_raw_listener(lambda d, r: print(f"{'>>' if d == 'out' else '<<'} {r.hex(' ')}",
                                                    file=sys.stderr))
    return session


# --- commands ----------------------------------------------------------------


def cmd_devices(args: argparse.Namespace) -> int:
    from ge150.usb.hidraw_transport import find_hidraw_devices

    devices = find_hidraw_devices()
    for d in devices:
        print(f"{d.path}  {d.name}  serial={d.serial}")
    if not devices:
        print("no GE150 hidraw node found (is the pedal connected?)")
    return 0 if devices else 1


def cmd_probe(args: argparse.Namespace) -> int:
    with _session(args) as session:
        if not args.no_flush:
            # The vendor launcher sends 8 zero bytes before identifying (FUN_00408a30).
            report = bytes([len(reader.FLUSH_REPORT_DATA)]) + reader.FLUSH_REPORT_DATA
            session.transport.write_report(report.ljust(64, b"\x00"))
            time.sleep(0.05)
        info = reader.identify(session)
    print(f"device:   {info.name}")
    print(f"firmware: {info.firmware}")
    print(f"other:    {info.field_a!r} {info.field_c!r} {info.field_d!r}  rev {info.revision!r}")
    print(f"raw:      {info.raw.hex(' ')}")
    return 0


def cmd_sniff(args: argparse.Namespace) -> int:
    """Print every input report and decoded frame for N seconds (no requests sent)."""
    transport = _transport(args)
    transport.open()
    decoder = FrameDecoder()
    end = time.monotonic() + args.seconds
    try:
        while time.monotonic() < end:
            report = transport.read_report(0.2)
            if report is None:
                continue
            print(f"<< {report.hex(' ')}")
            for frame in decoder.feed(report_data(report)):
                print(f"   {op_name(frame.opcode)}  {frame.data.hex(' ')}")
    finally:
        transport.close()
    print(f"frames={decoder.stats.frames} crc_errors={decoder.stats.crc_errors}", file=sys.stderr)
    return 0


def cmd_presets(args: argparse.Namespace) -> int:
    with _session(args) as session:
        presets, _ = reader.read_all_presets(session)
    for slot in sorted(presets):
        print(f"{slot:3d}  {presets[slot].name}")
    return 0


def cmd_current(args: argparse.Namespace) -> int:
    with _session(args) as session:
        current = reader.read_current(session)
    print(f"slot {current.slot}  page {current.page}")
    for m in reader.describe_words(current.words):
        params = ", ".join(f"{p['name']}={p['value']}" for p in m["params"])
        extra = f"  (other words {m['unused_words']})" if args.all_words else ""
        print(f"  {m['module']:8} {'ON ' if m['on'] else 'off'} {m['model']:18} {params}{extra}")
    print(f"  EXP words: {current.words[66:72]}")
    return 0


def cmd_system(args: argparse.Namespace) -> int:
    with _session(args) as session:
        _, system = reader.read_all_presets(session)
    if system is None:
        print("no system block received")
        return 1
    for name, value in SystemValues.from_blocks(system.blocks).describe():
        print(f"{name:12} {value}")
    print("raw          " + " | ".join(d.hex(" ") for d in system.blocks.values()))
    return 0


def cmd_rhythm(args: argparse.Namespace) -> int:
    with _session(args) as session:
        data = reader.read_rhythm(session)
    for name, value in RhythmValues.from_bytes(data).describe():
        print(f"{name:12} {value}")
    print(f"raw          {data.hex(' ')}")
    return 0


def cmd_user_names(args: argparse.Namespace) -> int:
    with _session(args) as session:
        names = reader.read_user_names(session)
    print("slot  IR (CAB 27-36)      NR (AMP 56-65)")
    for i, (ir, nr) in enumerate(zip(names.ir, names.nr, strict=True)):
        print(f"{i:4d}  {ir:18}  {nr}")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    with _session(args) as session:
        data = reader.snapshot(session)
    text = json.dumps(data, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"saved {args.out} ({len(data['presets'])} presets)")
    else:
        print(text)
    return 0


def cmd_frame(args: argparse.Namespace) -> int:
    """Encode a frame offline (no device): ge150ctl frame A0 01"""
    from ge150.protocol.framing import encode_frame

    raw = bytes.fromhex("".join(args.hex))
    frame = encode_frame(raw[0], raw[1:])
    print(frame.hex(" "))
    for report in split_reports(frame):
        print(f"  report: {report.hex(' ')}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    """Send one read-only frame and print every frame that arrives for N seconds."""
    from ge150.protocol.framing import Frame
    from ge150.protocol.opcodes import READ_ONLY

    raw = bytes.fromhex("".join(args.hex))
    frame = Frame(raw[0], raw[1:])
    if frame.opcode not in READ_ONLY:
        print(f"refusing to send {op_name(frame.opcode)}: only read-only opcodes are allowed",
              file=sys.stderr)
        return 2
    received: list[Frame] = []
    with _session(args) as session:
        session.add_listener(received.append)
        start = time.monotonic()
        session.send(frame)
        session.flush()
        time.sleep(args.listen)
    print(f"sent {op_name(frame.opcode)} {frame.data.hex(' ')}; "
          f"{len(received)} frame(s) in {time.monotonic() - start:.1f}s")
    for f in received:
        print(f"  {op_name(f.opcode)}  len={len(f.payload)}  {f.data[:48].hex(' ')}"
              f"{' ...' if len(f.data) > 48 else ''}")
    return 0


COMMANDS: dict[str, tuple[Callable[[argparse.Namespace], int], str]] = {
    "send": (cmd_send, "send one READ-ONLY frame (hex) and list the answers"),
    "devices": (cmd_devices, "list connected GE150 hidraw nodes"),
    "probe": (cmd_probe, "identify the pedal (name, firmware)"),
    "sniff": (cmd_sniff, "print incoming reports/frames without sending anything"),
    "presets": (cmd_presets, "list the 200 preset names"),
    "current": (cmd_current, "show the current edit buffer decoded"),
    "system": (cmd_system, "show the system settings"),
    "rhythm": (cmd_rhythm, "show the rhythm box settings"),
    "user-names": (cmd_user_names, "show user IR/NR slot names"),
    "snapshot": (cmd_snapshot, "dump everything readable to JSON"),
    "frame": (cmd_frame, "encode a frame offline: OPCODE [DATA] in hex"),
}


EXTRA_COMMANDS = EDIT_COMMANDS | SETTINGS_COMMANDS | AI_COMMANDS | T3K_COMMANDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ge150ctl", description=__doc__)
    parser.add_argument("--sim", action="store_true", help="use the built-in simulator")
    parser.add_argument("--backend", choices=("auto", "hidraw", "usb"), default="auto")
    parser.add_argument("--device", help="hidraw node, e.g. /dev/hidraw7")
    parser.add_argument("--raw", action="store_true", help="print every 64-byte report")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text)
        if name == "probe":
            p.add_argument("--no-flush", action="store_true", help="skip the 8 zero bytes")
        elif name == "sniff":
            p.add_argument("--seconds", type=float, default=30.0)
        elif name == "current":
            p.add_argument("--all-words", action="store_true",
                           help="also show block words not used by the model")
        elif name == "snapshot":
            p.add_argument("--out", help="output JSON file")
        elif name == "frame":
            p.add_argument("hex", nargs="+")
        elif name == "send":
            p.add_argument("hex", nargs="+", help="opcode and data, e.g. 31 01")
            p.add_argument("--listen", type=float, default=3.0, help="seconds to listen")
    for name, (_, help_text, setup) in EXTRA_COMMANDS.items():
        setup(sub.add_parser(name, help=help_text))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(asctime)s %(threadName)s %(levelname)s %(message)s")
    args.make_session = lambda: _session(args)
    handler = (COMMANDS[args.command][0] if args.command in COMMANDS
               else EXTRA_COMMANDS[args.command][0])
    try:
        return handler(args)
    except (TransportError, SessionError, EditorError, ToneAIError, Tone3000Error,
            ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
