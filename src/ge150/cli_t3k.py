"""``ge150ctl t3k-*``: TONE3000 account and cabinet IR downloads (docs/plan-ia-tone3000.md §5)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from ge150.formats import wav_ir
from ge150.protocol import messages as msg
from ge150.protocol.opcodes import Op
from ge150.services import reader
from ge150.services.editor import Editor
from ge150.services.tone3000 import IrSources, Tone3000Client

Handler = Callable[[argparse.Namespace], int]
ArgSetup = Callable[[argparse.ArgumentParser], object]


def cmd_key(args: argparse.Namespace) -> int:
    client = Tone3000Client()
    client.set_client_id(args.client_id)
    print("TONE3000 publishable key saved. Next: ge150ctl t3k-login")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    client = Tone3000Client()
    print("opening TONE3000 in the browser…")
    client.login()
    user = client.user()
    print(f"signed in as {user.get('display_name') or user.get('username')}")
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    Tone3000Client().logout()
    print("signed out of TONE3000")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    client = Tone3000Client()
    creds = client.creds
    print(f"publishable key: {'set' if creds.client_id else 'missing (ge150ctl t3k-key KEY)'}")
    print(f"session:         {'signed in' if creds.signed_in else 'signed out'}")
    print(f"redirect URI:    {client.redirect_uri}")
    sources = IrSources().load()
    for slot in sorted(sources, key=int):
        s = sources[slot]
        print(f"  IR slot {slot}: {s['title']} / {s['model']} by {s['author']} ({s['license']})")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    """Pick (or name) a TONE3000 IR, download it and STORE it in a user IR slot."""
    client = Tone3000Client()
    tone_id = args.tone
    if tone_id is None:
        print("opening the TONE3000 catalogue: pick a cabinet IR…")
        tone_id = client.select_tone()
    download = client.download(tone_id, args.model)
    tone = download.tone
    print(f"{tone.title} / {download.model.name}\n  by {tone.author} · licence {tone.license}"
          f" · {tone.page_url}")
    payload = wav_ir.load_ir_file(download.path)
    name = (args.name or tone.title)[: msg.USER_NAME_LEN]
    session = args.make_session()
    with session:
        editor = Editor(session)
        names = reader.read_user_names(session)
        old = names.ir[args.slot - 1]
        if not args.yes:
            if not sys.stdin.isatty():
                print("refusing to store without --yes", file=sys.stderr)
                return 1
            answer = input(f"replace IR slot {args.slot} ({old}) with {name!r}? [y/N] ")
            if answer.strip().lower() not in ("y", "yes", "s", "si", "sí"):
                return 1
        editor.upload_user_slot(Op.USER_IR, args.slot - 1, name, payload)
    IrSources().record(args.slot, download)
    print(f"IR slot {args.slot} (CAB {26 + args.slot}): {name}")
    return 0


def _setup_key(p: argparse.ArgumentParser) -> None:
    p.add_argument("client_id", help="publishable key from your TONE3000 API settings")


def _setup_load(p: argparse.ArgumentParser) -> None:
    p.add_argument("slot", type=int, choices=range(1, 11), metavar="SLOT", help="IR slot 1..10")
    p.add_argument("--tone", type=int, help="TONE3000 tone id (default: pick in the browser)")
    p.add_argument("--model", type=int, help="model id inside the tone (default: the first)")
    p.add_argument("--name", help="name shown on the pedal (default: the tone title)")
    p.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")


T3K_COMMANDS: dict[str, tuple[Handler, str, ArgSetup]] = {
    "t3k-key": (cmd_key, "save your TONE3000 publishable key", _setup_key),
    "t3k-login": (cmd_login, "sign in to TONE3000 in the browser", lambda p: None),
    "t3k-logout": (cmd_logout, "forget the TONE3000 session", lambda p: None),
    "t3k-status": (cmd_status, "TONE3000 session and IRs downloaded from it", lambda p: None),
    "t3k-load": (cmd_load, "STORE a TONE3000 cabinet IR into a user IR slot", _setup_load),
}
