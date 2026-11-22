from collections.abc import Iterator

import pytest

from ge150.protocol.session import DeviceSession
from ge150.services import tone_ai
from ge150.services.editor import Editor
from ge150.sim.sim_transport import SimTransport


class FakeBackend(tone_ai.Backend):
    name = "Fake"

    def __init__(self, answer: dict[str, object]) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def run(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        return self.answer


ANSWER = {
    "name": "SLASH LEAD",
    "explanation": "Marshall-style lead with a Les Paul.",
    "modules": [
        {"module": "FX", "on": False, "model": "", "params": []},
        {"module": "DS", "on": True, "model": "808",
         "params": [{"name": "GAIN", "value": "30"}, {"name": "VOLUME", "value": "150"}]},
        {"module": "AMP", "on": True, "model": "PLX100",
         "params": [{"name": "GAIN", "value": "70"}, {"name": "BOGUS", "value": "1"}]},
        {"module": "CAB", "on": True, "model": "1960 412",
         "params": [{"name": "MIC", "value": "SM57"}, {"name": "CENTER", "value": "25"}]},
        {"module": "DELAY", "on": True, "model": "no such delay", "params": []},
    ],
}


@pytest.fixture
def editor() -> Iterator[Editor]:
    session = DeviceSession(SimTransport(), frame_delay=0, multipart_delay=0)
    with session:
        ed = Editor(session)
        ed.sync()
        yield ed


def test_prompt_has_catalogue_gear_and_current_patch(editor: Editor) -> None:
    prompt = tone_ai.Conversation().prompt(editor, "Slash")
    assert "808 (based on Ibanez TS808 Tube Screamer)" in prompt
    assert "PLX100 (based on Marshall Plexi Super Lead 100)" in prompt
    assert "# Current patch" in prompt and prompt.rstrip().endswith("Slash")


def test_proposal_is_validated_and_applied_live(editor: Editor) -> None:
    backend = FakeBackend(ANSWER)
    assistant = tone_ai.ToneAssistant(editor, backend)
    proposal = assistant.ask("Slash, Sweet Child")
    assert proposal.name == "SLASH LEAD"
    ds = editor.module(1)
    assert ds.switch and editor.catalog[1].model_for_type(ds.type).name == "808"
    gain = next(p for p in editor.catalog[1].models[1].params if p.name == "GAIN")
    volume = next(p for p in editor.catalog[1].models[1].params if p.name == "VOLUME")
    assert ds.words[gain.word] == gain.to_raw(30)
    assert ds.words[volume.word] == volume.to_raw(volume.max)  # clamped
    assert not editor.module(0).switch
    cab = editor.catalog[3].model_for_type(editor.module(3).type)
    assert cab.name == "1960 412"
    assert any("BOGUS" in w for w in proposal.warnings)
    assert any("no such delay" in w for w in proposal.warnings)
    assert editor.state.dirty  # live only: nothing stored


def test_follow_up_carries_the_conversation(editor: Editor) -> None:
    backend = FakeBackend(ANSWER)
    assistant = tone_ai.ToneAssistant(editor, backend)
    assistant.ask("Slash")
    assistant.ask("more gain", apply=False)
    assert "User: Slash" in backend.prompts[1] and "more gain" in backend.prompts[1]


def test_schema_is_strict_for_both_clis() -> None:
    def check(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(tone_ai.SCHEMA)


def test_no_module_is_an_error(editor: Editor) -> None:
    with pytest.raises(tone_ai.ToneAIError):
        tone_ai.parse_proposal({"name": "", "explanation": "", "modules": []}, editor)


def test_undo_restores_previous_sound(editor: Editor) -> None:
    before = list(editor.state.edit.words)  # type: ignore[union-attr]
    assistant = tone_ai.ToneAssistant(editor, FakeBackend(ANSWER))
    assistant.ask("Slash")
    assert editor.state.edit.words != before  # type: ignore[union-attr]
    assert assistant.undo()
    assert editor.state.edit.words == before  # type: ignore[union-attr]
    assert not assistant.undo()
