#!/usr/bin/env python3
"""Decode a Linux usbmon capture (pcap or pcapng) into GE150 frames.

Typical use (plan.md, phase 2): run the vendor editor in a VM with the pedal passed
through, capture on the host with ``sudo modprobe usbmon`` + Wireshark/dumpcap on
``usbmonN`` (N = bus of the pedal), then::

    python3 -I tools/decode_usbmon.py capture.pcapng [--device ADDR]

Prints one line per GE150 frame: time, direction, opcode name, payload hex.
Only interrupt transfers on endpoints 0x02 (OUT) and 0x81 (IN) are considered.
"""

from __future__ import annotations

import argparse
import struct
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ge150.protocol.framing import FrameDecoder, report_data
from ge150.protocol.opcodes import op_name

LINKTYPE_USB_LINUX = 189  # 48-byte usbmon header
LINKTYPE_USB_LINUX_MMAPPED = 220  # 64-byte usbmon header
EP_OUT, EP_IN = 0x02, 0x81


@dataclass(frozen=True)
class Urb:
    time: float
    event: str  # "S" submit, "C" complete
    transfer: int  # 1 = interrupt
    endpoint: int  # with direction bit
    device: int
    data: bytes


def _packets_pcap(data: bytes) -> Iterator[tuple[int, float, bytes]]:
    magic = data[:4]
    endian = "<" if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
    nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
    linktype = struct.unpack_from(endian + "I", data, 20)[0]
    pos = 24
    while pos + 16 <= len(data):
        sec, frac, incl, _ = struct.unpack_from(endian + "IIII", data, pos)
        yield linktype, sec + frac / (1e9 if nano else 1e6), data[pos + 16 : pos + 16 + incl]
        pos += 16 + incl


def _packets_pcapng(data: bytes) -> Iterator[tuple[int, float, bytes]]:
    pos, endian, linktypes = 0, "<", []
    while pos + 12 <= len(data):
        if data[pos : pos + 4] == b"\x0a\x0d\x0d\x0a":
            endian = "<" if data[pos + 8 : pos + 12] == b"\x4d\x3c\x2b\x1a" else ">"
            linktypes = []
        btype, blen = struct.unpack_from(endian + "II", data, pos)
        if blen < 12:
            break
        body = data[pos + 8 : pos + blen - 4]
        if btype == 1:  # interface description
            linktypes.append(struct.unpack_from(endian + "H", body, 0)[0])
        elif btype == 6:  # enhanced packet
            iface, ts_hi, ts_lo, cap = struct.unpack_from(endian + "IIII", body, 0)
            ts = ((ts_hi << 32) | ts_lo) / 1e6
            yield linktypes[iface] if iface < len(linktypes) else -1, ts, body[20 : 20 + cap]
        pos += blen


def read_urbs(path: Path) -> Iterator[Urb]:
    data = path.read_bytes()
    packets = _packets_pcapng(data) if data[:4] == b"\x0a\x0d\x0d\x0a" else _packets_pcap(data)
    for linktype, ts, pkt in packets:
        if linktype not in (LINKTYPE_USB_LINUX, LINKTYPE_USB_LINUX_MMAPPED) or len(pkt) < 48:
            continue
        header = 64 if linktype == LINKTYPE_USB_LINUX_MMAPPED else 48
        event, transfer, endpoint, device = chr(pkt[8]), pkt[9], pkt[10], pkt[11]
        yield Urb(ts, event, transfer, endpoint, device, bytes(pkt[header:]))


def decode(path: Path, device: int | None = None) -> Iterator[tuple[float, str, int, bytes]]:
    """Yield (time, "->"/"<-", opcode, data) for every GE150 frame in the capture."""
    decoders = {EP_OUT: FrameDecoder(), EP_IN: FrameDecoder()}
    for urb in read_urbs(path):
        if urb.transfer != 1 or urb.endpoint not in decoders or not urb.data:
            continue
        if device is not None and urb.device != device:
            continue
        # OUT data travels with the submission, IN data with the completion.
        if (urb.endpoint == EP_OUT) != (urb.event == "S"):
            continue
        for frame in decoders[urb.endpoint].feed(report_data(urb.data)):
            yield urb.time, "->" if urb.endpoint == EP_OUT else "<-", frame.opcode, frame.data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("capture", type=Path)
    parser.add_argument("--device", type=int, help="USB device address to keep")
    args = parser.parse_args()
    start = None
    for ts, direction, opcode, data in decode(args.capture, args.device):
        start = ts if start is None else start
        print(f"{ts - start:9.3f} {direction} {op_name(opcode):24} {data.hex(' ')}")


if __name__ == "__main__":
    main()
