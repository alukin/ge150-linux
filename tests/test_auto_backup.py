import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from ge150.formats import mbf
from ge150.model.gear import MODULE_TAGS
from ge150.protocol.session import DeviceSession
from ge150.services import auto_backup, bulk_edit
from ge150.services.editor import Editor
from ge150.sim.sim_transport import SimTransport

REVERB = MODULE_TAGS.index("REVERB")


@pytest.fixture
def editor() -> Iterator[Editor]:
    session = DeviceSession(SimTransport(), frame_delay=0, multipart_delay=0)
    with session:
        editor = Editor(session)
        editor.sync()
        yield editor


def _toggle_reverb(editor: Editor, slot: int) -> list[bulk_edit.PresetEdit]:
    on = editor.state.presets[slot].module(REVERB).switch
    return bulk_edit.plan_edits(editor, [{"slot": slot, "modules": [{"module": "REVERB",
                                                                      "on": not on}]}])


def test_the_backup_is_a_full_mbf_of_the_pedal(editor: Editor) -> None:
    path = auto_backup.save_before(editor, "aplicar")
    assert path.parent == auto_backup.backup_dir() and path.name.startswith("auto-")
    assert os.stat(path).st_mode & 0o777 == 0o600
    data = mbf.load(path)
    assert len(data.presets) == 200
    assert data.presets[27].words == editor.state.presets[28].words


def test_only_old_automatic_backups_are_deleted(tmp_path: Path) -> None:
    mine = tmp_path / "mi-backup.mbf"
    mine.write_bytes(b"x")
    for i in range(25):
        path = tmp_path / f"auto-2026{i:04d}.mbf"
        path.write_bytes(b"x")
        os.utime(path, (1000 + i, 1000 + i))
    deleted = auto_backup.prune(tmp_path, keep=20)
    assert len(deleted) == 5 and all(p.name < "auto-20260005" for p in deleted)
    assert mine.exists() and len(list(tmp_path.glob("auto-*.mbf"))) == 20


def test_apply_backs_up_first_and_writes_nothing_if_it_fails(editor: Editor) -> None:
    before = list(editor.state.presets[22].words)
    order: list[str] = []

    def failing() -> Path:
        order.append("backup")
        raise OSError("disco lleno")

    with pytest.raises(bulk_edit.BackupError, match="no se escribió nada"):
        bulk_edit.apply(editor, _toggle_reverb(editor, 22), failing)
    assert editor.state.presets[22].words == before and order == ["backup"]

    applied = bulk_edit.apply(editor, _toggle_reverb(editor, 22),
                              lambda: auto_backup.save_before(editor, "aplicar"))
    assert applied.backup is not None and applied.backup.exists()
    assert mbf.load(applied.backup).presets[21].words == before  # the version before writing
    assert editor.state.presets[22].words != before


def test_no_backup_when_nothing_would_be_written(editor: Editor) -> None:
    calls: list[int] = []
    edits = bulk_edit.plan_edits(editor, [{"slot": 22, "modules": [{"module": "REVERB"}]}])
    assert not edits[0].changed
    bulk_edit.apply(editor, edits, lambda: calls.append(1) or Path("x"))  # type: ignore[func-returns-value]
    assert calls == []
