import random

import pytest

from ge150.protocol.crc import crc16_gsm
from ge150.protocol.framing import (
    Frame,
    FrameDecoder,
    FrameError,
    encode_frame,
    report_data,
    split_reports,
)

# Identification frame hard-coded in the vendor launcher (GE150.exe FUN_00408a30).
IDENTIFY_FRAME = bytes.fromhex("aa55020000001297")


def test_crc_matches_vendor_identify_frame() -> None:
    assert crc16_gsm(bytes.fromhex("02000000")) == 0x1297


def test_crc_check_value() -> None:
    # Standard CRC-16/GSM check value for "123456789".
    assert crc16_gsm(b"123456789") == 0xCE3C


def test_encode_identify() -> None:
    assert encode_frame(0x00, b"\x00") == IDENTIFY_FRAME


def test_encode_read_all_presets() -> None:
    assert encode_frame(0xA0, b"\x01") == bytes.fromhex("aa550200a0011fc8")


def test_encode_rejects_bad_opcode() -> None:
    with pytest.raises(FrameError):
        encode_frame(0x100)


def test_split_reports_short_frame() -> None:
    reports = split_reports(IDENTIFY_FRAME)
    assert len(reports) == 1
    assert reports[0][0] == len(IDENTIFY_FRAME)
    assert reports[0][1:9] == IDENTIFY_FRAME
    assert len(reports[0]) == 64 and reports[0][9:] == bytes(55)


def test_split_reports_long_frame() -> None:
    frame = encode_frame(0xC3, bytes(range(160)) * 1)
    reports = split_reports(frame)
    assert [r[0] for r in reports] == [63, 63, len(frame) - 126]
    assert b"".join(report_data(r) for r in reports) == frame


def test_report_data_fallback_for_implausible_length() -> None:
    report = bytes([0]) + bytes(range(1, 64))
    assert report_data(report) == report[1:]


def test_decoder_roundtrip_with_garbage_and_split_feeds() -> None:
    frames = [Frame(0x20, bytes([i]) + bytes(160)) for i in range(1, 6)]
    stream = b"\x00\x13\xaa" + b"".join(f.encode() for f in frames) + b"\xaa"
    decoder = FrameDecoder()
    got = []
    rng = random.Random(1)
    pos = 0
    while pos < len(stream):
        step = rng.randint(1, 40)
        got.extend(decoder.feed(stream[pos : pos + step]))
        pos += step
    assert got == frames
    assert decoder.stats.frames == 5


def test_decoder_skips_bad_crc_and_resyncs() -> None:
    good = Frame(0x16, b"\x07")
    bad = bytearray(Frame(0x16, b"\x05").encode())
    bad[-1] ^= 0xFF
    decoder = FrameDecoder()
    assert decoder.feed(bytes(bad) + good.encode()) == [good]
    assert decoder.stats.crc_errors == 1


def test_decoder_handles_header_split_between_feeds() -> None:
    frame = Frame(0x34, b"\x02")
    raw = frame.encode()
    decoder = FrameDecoder()
    assert decoder.feed(raw[:1]) == []
    assert decoder.feed(raw[1:]) == [frame]


def test_decoder_feed_reports() -> None:
    frame = Frame(0x30, bytes(150))
    decoder = FrameDecoder()
    assert decoder.feed_reports(split_reports(frame.encode())) == [frame]
