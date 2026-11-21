import importlib.util
import struct
import sys
from pathlib import Path

from ge150.protocol.framing import Frame, split_reports

spec = importlib.util.spec_from_file_location(
    "decode_usbmon", Path(__file__).resolve().parents[1] / "tools" / "decode_usbmon.py")
assert spec and spec.loader
decode_usbmon = importlib.util.module_from_spec(spec)
sys.modules["decode_usbmon"] = decode_usbmon
spec.loader.exec_module(decode_usbmon)


def usbmon_packet(event: str, endpoint: int, data: bytes, device: int = 14) -> bytes:
    header = bytearray(64)
    struct.pack_into("<Q", header, 0, 1)
    header[8], header[9], header[10], header[11] = ord(event), 1, endpoint, device
    return bytes(header) + data


def make_pcap(packets: list[bytes]) -> bytes:
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 220)
    for i, pkt in enumerate(packets):
        out += struct.pack("<IIII", 100, i * 1000, len(pkt), len(pkt)) + pkt
    return out


def make_pcapng(packets: list[bytes]) -> bytes:
    def block(btype: int, body: bytes) -> bytes:
        body += bytes(-len(body) % 4)
        size = len(body) + 12
        return struct.pack("<II", btype, size) + body + struct.pack("<I", size)

    out = block(0x0A0D0D0A, struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1))
    out += block(1, struct.pack("<HHI", 220, 0, 65535))
    for i, pkt in enumerate(packets):
        out += block(6, struct.pack("<IIIII", 0, 0, i, len(pkt), len(pkt)) + pkt)
    return out


def scenario() -> list[bytes]:
    request = Frame(0xA0, b"\x01").encode()
    answer = Frame(0x20, bytes([1]) + bytes(158)).encode()
    packets = [usbmon_packet("S", 0x02, r) for r in split_reports(request)]
    packets += [usbmon_packet("C", 0x02, b"")]  # completion of the OUT transfer: no data
    packets += [usbmon_packet("C", 0x81, r) for r in split_reports(answer)]
    packets += [usbmon_packet("C", 0x81, split_reports(answer)[0], device=3)]  # other device
    return packets


def test_pcap_and_pcapng(tmp_path: Path) -> None:
    for name, maker in (("c.pcap", make_pcap), ("c.pcapng", make_pcapng)):
        path = tmp_path / name
        path.write_bytes(maker(scenario()))
        frames = [(d, op) for _, d, op, _ in decode_usbmon.decode(path, device=14)]
        assert frames == [("->", 0xA0), ("<-", 0x20)], name
