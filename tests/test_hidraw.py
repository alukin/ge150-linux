from pathlib import Path

from ge150.usb.hidraw_transport import find_hidraw_devices


def _node(root: Path, name: str, hid_id: str) -> None:
    dev = root / name / "device"
    dev.mkdir(parents=True)
    (dev / "uevent").write_text(
        f"DRIVER=hid-generic\nHID_ID={hid_id}\nHID_NAME=STMicroelectronics GE150\n"
        "HID_UNIQ=00000000001A\n"
    )


def test_find_hidraw_devices_filters_by_id(tmp_path: Path) -> None:
    _node(tmp_path, "hidraw3", "0003:0000046D:0000C52B")
    _node(tmp_path, "hidraw7", "0003:00000483:00005703")
    found = find_hidraw_devices(sysfs=tmp_path)
    assert [d.path for d in found] == ["/dev/hidraw7"]
    assert found[0].serial == "00000000001A"


def test_find_hidraw_devices_empty(tmp_path: Path) -> None:
    assert find_hidraw_devices(sysfs=tmp_path) == []
