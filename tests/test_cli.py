from pathlib import Path

import pytest

from ge150.cli import main
from ge150.formats import wav_ir


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = main(["--sim", *argv])
    return code, capsys.readouterr().out


def test_read_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "probe")[1].startswith("device:   MOOER_GE150")
    code, out = run(capsys, "presets")
    assert code == 0 and len(out.splitlines()) == 200
    assert "IR (CAB 27-36)" in run(capsys, "user-names")[1]


def test_models_is_offline(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "models", "delay")
    assert code == 0 and "09:DUAL DELAY" in out


def test_live_edits(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "set", "reverb", "level", "77")
    assert code == 0 and "LEVEL=77" in out
    assert "05:US BLUES CL" in run(capsys, "type", "amp", "5")[1]
    assert run(capsys, "type", "delay", "dual delay")[1].startswith("DELAY:")
    assert run(capsys, "off", "eq")[1].startswith("EQ: off")


def test_out_of_range_value_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--sim", "set", "mod", "rate", "101"]) == 2
    assert "outside" in capsys.readouterr().err


def test_persistent_commands_need_confirmation(capsys: pytest.CaptureFixture[str],
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["--sim", "save", "--name", "X"]) == 1
    assert "without --yes" in capsys.readouterr().err
    assert run(capsys, "save", "--name", "X", "-y") == (0, "saved 1: X\n")
    assert run(capsys, "rename", "3", "NEW", "-y")[0] == 0
    assert run(capsys, "copy", "3", "4", "-y")[0] == 0


def test_ir_upload_and_export(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    wav = tmp_path / "cab.wav"
    wav.write_bytes(wav_ir.ir_to_wav([1000 - i for i in range(512)]))
    code, out = run(capsys, "ir-upload", "2", str(wav), "-y")
    assert code == 0 and "IR slot 2: cab" in out
    # Each CLI call uses a fresh simulator, so the export of a new one is empty.
    assert "no user IRs" in run(capsys, "ir-export", str(tmp_path / "out"))[1]


def test_mo_export_and_import(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    target = tmp_path / "p.mo"
    assert run(capsys, "export", "7", str(target))[0] == 0
    assert '"schema": "GE150 Preset"' in target.read_text()
    code, out = run(capsys, "import", str(target), "9", "-y")
    assert code == 0 and "-> 9: PRESET 007" in out
    assert run(capsys, "export", "all", str(tmp_path / "all"))[0] == 0
    assert len(list((tmp_path / "all").glob("*.mo"))) == 200


def test_backup_and_restore_commands(capsys: pytest.CaptureFixture[str], tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "GE150.mbf"
    code, out = run(capsys, "backup", str(path))
    assert code == 0 and "200 presets" in out and path.stat().st_size > 0x400
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["--sim", "restore", str(path)]) == 1  # needs --yes
    capsys.readouterr()
    assert run(capsys, "restore", str(path), "-y")[0] == 0


def test_nr_upload(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    from ge150.formats import amp_nr

    amp = tmp_path / "Plexi.amp"
    amp.write_bytes(amp_nr.build_amp(list(range(512))))
    code, out = run(capsys, "nr-upload", "1", str(amp), "-y")
    assert code == 0 and "NR slot 1: Plexi" in out
    assert run(capsys, "nr-delete", "1", "-y")[0] == 0
