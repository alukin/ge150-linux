import json
import subprocess
from pathlib import Path

import pytest

from ge150.services import tone_agent
from ge150.services.tone_ai import ToneAIError


def fake_run(stdout: str, code: int = 0, answer: str = ""):  # type: ignore[no-untyped-def]
    calls: list[list[str]] = []

    def run(args: list[str], stdin: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if answer and "-o" in args:
            Path(args[args.index("-o") + 1]).write_text(answer)
        return subprocess.CompletedProcess(args, code, stdout, "boom")

    return run, calls


def test_claude_agent_keeps_the_session(monkeypatch: pytest.MonkeyPatch) -> None:
    run, calls = fake_run(json.dumps({"result": "Listo: JCM800.", "session_id": "s1"}))
    monkeypatch.setattr(tone_agent, "_run", run)
    agent = tone_agent.ClaudeAgent(server=["/x/ge150-mcp"])
    assert agent.ask("Slash") == "Listo: JCM800."
    agent.ask("menos ganancia")
    first, second = calls
    config = json.loads(first[first.index("--mcp-config") + 1])
    assert config["mcpServers"]["ge150"]["command"] == "/x/ge150-mcp"
    assert first[first.index("--tools") + 1] == "" and "mcp__ge150__*" in first
    assert "--resume" not in first and second[second.index("--resume") + 1] == "s1"


def test_claude_agent_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    run, _ = fake_run(json.dumps({"is_error": True, "result": "usage limit"}))
    monkeypatch.setattr(tone_agent, "_run", run)
    with pytest.raises(ToneAIError, match="usage limit"):
        tone_agent.ClaudeAgent(server=["x"]).ask("hola")


def test_codex_agent_resumes_the_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    events = "\n".join([json.dumps({"type": "thread.started", "thread_id": "t9"}), "noise"])
    run, calls = fake_run(events, answer="Apliqué un clean.")
    monkeypatch.setattr(tone_agent, "_run", run)
    agent = tone_agent.CodexAgent(server=["/x/ge150-mcp", "--sim"])
    assert agent.ask("clean") == "Apliqué un clean." and agent.session == "t9"
    agent.ask("más brillo")
    assert calls[0][:3] == ["codex", "exec", "--skip-git-repo-check"]
    assert calls[1][:4] == ["codex", "exec", "resume", "t9"]
    assert 'mcp_servers.ge150.args=["--sim"]' in calls[0]
    assert 'sandbox_mode="read-only"' in calls[0] and calls[0][-1] == "-"
    agent.reset()
    assert agent.session == ""


def test_stop_all_ends_a_running_request(tmp_path: Path) -> None:
    import threading
    import time

    errors: list[str] = []

    def run() -> None:
        try:
            tone_agent._run(["sleep", "30"], "", tmp_path)
        except ToneAIError as exc:
            errors.append(str(exc))

    thread = threading.Thread(target=run)
    thread.start()
    for _ in range(100):
        if tone_agent._RUNNING:
            break
        time.sleep(0.01)
    assert tone_agent.stop_all() == 1
    thread.join(5)
    assert errors == ["stopped"] and not tone_agent._RUNNING


def test_model_and_effort_reach_both_clis(tmp_path: Path) -> None:
    claude = tone_agent.ClaudeAgent(server=["x"], model="opus", effort="high").args("")
    assert claude[claude.index("--model") + 1] == "opus"
    assert claude[claude.index("--effort") + 1] == "high"
    codex = tone_agent.CodexAgent(server=["x"], model="gpt-6-sol", effort="max")
    args = codex.args("", tmp_path / "o.txt")
    assert args[args.index("-m") + 1] == "gpt-6-sol"
    assert 'model_reasoning_effort="max"' in args
    assert "--effort" not in tone_agent.ClaudeAgent(server=["x"]).args("")


def test_codex_models_come_from_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    listed = {"models": [
        {"slug": "gpt-a", "display_name": "GPT A", "visibility": "list",
         "supported_reasoning_levels": [{"effort": "low"}, {"effort": "ultra"}]},
        {"slug": "hidden", "display_name": "H", "visibility": "hide"}]}

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, json.dumps(listed), "")

    monkeypatch.setattr(tone_agent.subprocess, "run", run)
    choices = tone_agent.CodexAgent.models()
    assert [c.id for c in choices] == ["", "gpt-a"]
    assert choices[1].efforts == ("low", "ultra")
    claude = tone_agent.ClaudeAgent.models()
    assert [c.label for c in claude][:3] == ["Predeterminado", "Fable 5.2", "Opus 5.5"]
    assert claude[2].id == "claude-opus-5-5"
