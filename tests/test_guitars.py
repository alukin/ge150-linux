import json
from pathlib import Path

import pytest

from ge150.services import guitars, tone_ai
from ge150.services.guitars import Guitar, GuitarStore


def test_store_keeps_guitars_and_the_one_in_use(tmp_path: Path) -> None:
    store = GuitarStore(tmp_path / "g.json")
    strat = Guitar(brand="Fender", model="Player Stratocaster", year="2019",
                   pickup_bridge="Alnico 5 single-coil", serial="MX19123456")
    store.put(strat)
    store.use(strat.id)
    again = GuitarStore(tmp_path / "g.json")
    assert again.current is not None and again.current.title == "Fender Player Stratocaster (2019)"
    text = guitars.context_text(again.current)
    assert "Alnico 5" in text and "MX19123456" not in text  # the serial stays private
    again.remove(strat.id)
    assert GuitarStore(tmp_path / "g.json").current is None


def test_identify_only_fills_empty_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class Fake(tone_ai.Backend):
        def run(self, prompt: str, schema: dict[str, object] | None = None,
                system: str = "", web: bool = False) -> dict[str, object]:
            seen.update(prompt=prompt, schema=schema, web=web)
            return {**{f: "" for f in guitars.SPEC_FIELDS}, "year": "2019",
                    "body": "Aliso", "model": "OTRO", "confidence": "media",
                    "explanation": "MX = México"}

    monkeypatch.setattr(tone_ai, "make_backend", lambda provider, model: Fake())
    guitar, confidence, why = guitars.identify(
        Guitar(brand="Fender", model="Player Stratocaster", serial="MX19123456"))
    assert guitar.year == "2019" and guitar.body == "Aliso"
    assert guitar.model == "Player Stratocaster"  # what the user typed stays
    assert (confidence, why) == ("media", "MX = México")
    assert seen["web"] is True and "MX19123456" in str(seen["prompt"])
    assert json.dumps(seen["schema"])


def test_claude_backend_web_search_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    calls: list[list[str]] = []

    def run(args: list[str], stdin: str, cwd: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps({"structured_output": {}}), "")

    monkeypatch.setattr(tone_ai, "_run", run)
    tone_ai.ClaudeBackend().run("x", {"type": "object"}, "sys", web=True)
    args = calls[0]
    assert args[args.index("--tools") + 1] == "WebSearch,WebFetch"
    assert args[-2:] == ["WebSearch", "WebFetch"] and "sys" in args
