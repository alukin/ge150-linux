from collections.abc import Iterator

import pytest

from ge150.mcp_server.tools import PedalTools, ToolError
from ge150.protocol.session import DeviceSession
from ge150.services.editor import Editor
from ge150.sim.sim_transport import SimTransport


@pytest.fixture
def tools() -> Iterator[PedalTools]:
    session = DeviceSession(SimTransport(), frame_delay=0, multipart_delay=0)
    with session:
        editor = Editor(session)
        editor.sync()
        yield PedalTools(editor)


def test_catalog_index_and_module(tools: PedalTools) -> None:
    index = tools.get_catalog()
    assert [m["module"] for m in index["modules"]][:3] == ["FX", "DS", "AMP"]
    ds = tools.get_catalog("ds")
    ts = next(m for m in ds["models"] if m["model"] == "808")
    assert ts["based_on"] == "Ibanez TS808 Tube Screamer"
    assert {"name": "GAIN", "min": 0, "max": 100} in ts["params"]
    with pytest.raises(ToolError):
        tools.get_catalog("phaser")


def test_patch_presets_and_user_slots(tools: PedalTools) -> None:
    patch = tools.get_current_patch()
    assert patch["slot"] == 1 and len(patch["modules"]) == 9
    assert patch["unsaved_changes"] is False
    assert len(tools.list_presets()["presets"]) == 200
    assert tools.list_presets("042")["presets"] == [{"slot": 42, "name": "PRESET 042"}]
    assert tools.get_preset(5)["name"] == "PRESET 005"
    assert len(tools.list_user_irs()["ir"]) == 10
    assert set(tools.get_settings()) == {"system", "rhythm"}


def test_live_changes_and_undo(tools: PedalTools) -> None:
    before = tools.get_current_patch()
    result = tools.set_module("amp", True, "J800", {"GAIN": 80, "NOPE": 1})
    assert any("J800" in row for row in result["applied"])
    assert any("NOPE" in w for w in result["warnings"])
    amp = tools.get_current_patch()["modules"][2]
    assert amp["model"] == "J800" and amp["params"]["GAIN"] == "80"
    tools.apply_patch([{"module": "MOD", "on": False, "model": "", "params": []}])
    assert tools.undo()["undone"] and tools.undo()["undone"]
    assert tools.get_current_patch()["modules"] == before["modules"]
    assert tools.undo() == {"undone": False, "reason": "nothing to undo"}


def test_select_preset_protects_unsaved_changes(tools: PedalTools) -> None:
    tools.set_module("DS", False)
    with pytest.raises(ToolError, match="unsaved"):
        tools.select_preset(7)
    assert tools.select_preset(7, discard_changes=True)["slot"] == 7
    with pytest.raises(ToolError):
        tools.select_preset(500)


def test_nothing_resets_or_restores() -> None:
    names = {n for n in dir(PedalTools) if not n.startswith("_")}
    assert not names & {"rename", "factory_reset", "restore", "restore_backup", "firmware"}


def test_saving_needs_the_user(tools: PedalTools) -> None:
    tools.set_module("DS", False)
    with pytest.raises(ToolError, match="editor open"):
        tools.save_preset()
    asked: list[str] = []
    tools.confirm = lambda q: asked.append(q) is not None  # declines
    with pytest.raises(ToolError, match="declined"):
        tools.save_preset(30, "AI TONE")
    tools.confirm = lambda q: True
    assert tools.save_preset(30, "AI TONE") == {"saved": True, "slot": 30, "name": "AI TONE"}
    assert tools.editor.state.presets[30].name == "AI TONE" and "30" in asked[0]


class FakeT3k:
    class creds:
        signed_in = True

    def __init__(self, wav: bytes, tmp) -> None:  # type: ignore[no-untyped-def]
        from ge150.services.tone3000 import Download, Tone, ToneModel

        path = tmp / "ir.wav"
        path.write_bytes(wav)
        tone = Tone(42, "Mesa 4x12 V30", "irmaker", "", "", "cc-by", "ir", "cab")
        self.download_result = Download(tone, ToneModel(7, "SM57", "u"), path)
        self.picked = False

    def select_tone(self) -> int:
        self.picked = True
        return 42

    def download(self, tone_id: int, model_id: int | None) -> object:
        return self.download_result


def test_load_tone3000_ir_with_confirmation(tools: PedalTools, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from ge150.formats import wav_ir

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    fake = FakeT3k(wav_ir.ir_to_wav([4_000_000] + [0] * 511), tmp_path)
    tools._tone3000 = fake
    with pytest.raises(ToolError, match="editor open"):
        tools.load_tone3000_ir(4, 42)
    tools.confirm = lambda q: "irmaker" in q and "cc-by" in q
    result = tools.load_tone3000_ir(4)
    assert fake.picked and result["author"] == "irmaker" and result["model"] == "CAB 30"
    entry = tools.list_user_irs()["ir"][3]
    assert entry["name"] == "Mesa 4x12 V30" and entry["tone3000"]["author"] == "irmaker"
    assert "tone3000" not in tools.list_user_irs()["ir"][0]


def test_ai_sees_and_picks_user_irs_by_their_name(tools: PedalTools) -> None:
    from ge150.formats import wav_ir
    from ge150.protocol.opcodes import Op
    from ge150.services import tone_ai

    editor = tools.editor
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ir.wav"
        path.write_bytes(wav_ir.ir_to_wav([4_000_000] + [0] * 511))
        payload = wav_ir.load_ir_file(path)
    editor.upload_user_slot(Op.USER_IR, 5, "VOX AC30 BLUE 2", payload)  # CAB 32
    tools.apply_patch([{"module": "CAB", "on": True, "model": "VOX AC30 BLUE 2"}])
    cab = tools.get_current_patch()["modules"][3]
    assert cab["model"] == "CAB 32 (user IR: VOX AC30 BLUE 2)"
    assert "CAB 32 (user IR: VOX AC30 BLUE 2)" in tone_ai.current_text(editor)
    catalog = {m["number"]: m["model"] for m in tools.get_catalog("CAB")["models"]}
    assert catalog[32] == "CAB 32 (user IR: VOX AC30 BLUE 2)"
    assert catalog[33] == "CAB 33 (empty user IR slot)"
    tools.apply_patch([{"module": "CAB", "on": True, "model": "01:US DLX 112"}])
    result = tools.apply_patch([{"module": "CAB", "on": True, "model": catalog[32]}])
    assert not result["warnings"] and editor.module(3).type == 31
    tools.apply_patch([{"module": "CAB", "on": True, "model": "CAB 32"}])
    assert editor.module(3).type == 31
