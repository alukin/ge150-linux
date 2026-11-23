from collections.abc import Iterator

import pytest

from ge150.protocol.session import DeviceSession
from ge150.services.editor import Editor
from ge150.services.hw_check import HardwareCheck, save_report
from ge150.sim.sim_transport import SimTransport


@pytest.fixture
def editor() -> Iterator[Editor]:
    session = DeviceSession(SimTransport(), frame_delay=0, multipart_delay=0)
    with session:
        yield Editor(session)


def test_the_whole_check_passes_and_leaves_the_pedal_as_it_was(editor: Editor,
                                                               tmp_path) -> None:  # type: ignore[no-untyped-def]
    lines: list[str] = []
    report = HardwareCheck(editor, (198, 199, 200), log=lines.append).run()
    assert report.passed, report.markdown()
    steps = {c.step for c in report.checks}
    assert {"1", "2", "3", "4", "10"} <= steps
    assert report.backup is not None and report.backup.exists()
    assert report.checks[-1].name == "Todo como estaba" and report.checks[-1].ok
    path = save_report(report, tmp_path)
    assert "TODO OK" in path.read_text() and "MOOER_GE150" in path.read_text()


def test_tap_without_any_tap_is_reported_and_restored(editor: Editor) -> None:
    report = HardwareCheck(editor, (198, 199, 200), log=lambda _: None, tap_seconds=0.3,
                           only_tap=True).run()
    tap = next(c for c in report.checks if c.step == "9")
    assert tap.ok is False and "no llegó" in tap.detail
    assert report.checks[-1].ok  # the delay switched on for the test is undone


def test_refuses_a_loaded_preset_with_unsaved_changes(editor: Editor) -> None:
    from ge150.services.editor import EditorError

    editor.sync()
    block = editor.module(1)
    block.switch = not block.switch
    editor.write_module(block)
    with pytest.raises(EditorError, match="unsaved changes"):
        HardwareCheck(editor, (198, 199, 200), log=lambda _: None).run()


def test_needs_three_different_presets(editor: Editor) -> None:
    with pytest.raises(ValueError):
        HardwareCheck(editor, (1, 1, 2))
