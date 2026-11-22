"""Chat with Claude Code or Codex acting on the pedal through ``ge150-mcp`` (phase 11.3).

Unlike :mod:`ge150.services.tone_ai` (one JSON proposal, no tools), the agent reads and
changes the sound itself with the MCP tools; with the GE150 editor open ``ge150-mcp``
forwards to it, so every change shows at once and storing asks the user. Each backend keeps
its session id so follow-ups ("a bit less gain") continue the same conversation. Only the
``ge150`` tools are enabled: no shell, no file access.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from ge150.mcp_server.install import server_command
from ge150.services.tone_ai import ToneAIError

TIMEOUT_S = 900  # the user may take a while to confirm a save or to pick an IR

GUIDE = """You are the tone assistant of the GE150 editor, a Linux editor for the MOOER GE150
guitar multi-effects pedal. Use the ge150 tools to read the current sound and the catalogue
and to change the sound live. Prefer one apply_patch with every module you change. Only call
save_preset when the user asks to save. Answer in the
user's language, briefly: what you changed and why, as a short list. You cannot use any
other tool, file or command."""

#: Added when the user turns on "Cabs de TONE3000" in the panel.
CABS_GUIDE = """When the user asks for a new sound (not a small tweak), also look for a real
cabinet IR on TONE3000 that suits it: one or two precise tone3000_search queries (the cabinet
and speakers, e.g. "Marshall 1960A V30"), tone3000_get to pick one IR file (mic and position),
then load_tone3000_ir with slot 0: it reuses the slot that already holds that IR, else a free
one, else the editor lets the user choose which to overwrite, and it selects the IR in the CAB
module. Tell the user its author and licence. If TONE3000 is not signed in, nothing suits, or
the user declines, keep a factory CAB."""


@dataclass
class ModelChoice:
    """A model the user can pick; empty ``id`` = the CLI's own default."""

    id: str
    label: str
    efforts: tuple[str, ...] = ()


@dataclass
class Reply:
    text: str
    session: str = ""


def _workdir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    path = Path(base) / "ge150" / "agent"
    path.mkdir(parents=True, exist_ok=True)
    return path


_RUNNING: set[subprocess.Popen[str]] = set()
_LOCK = threading.Lock()


def _run(args: list[str], stdin: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, cwd=cwd)
    except FileNotFoundError as exc:
        raise ToneAIError(f"{args[0]} is not installed") from exc
    with _LOCK:
        _RUNNING.add(process)
    try:
        stdout, stderr = process.communicate(stdin, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise ToneAIError(f"{args[0]} did not finish within {TIMEOUT_S} s") from exc
    finally:
        with _LOCK:
            _RUNNING.discard(process)
    if process.returncode < 0:
        raise ToneAIError("stopped")
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def stop_all() -> int:
    """Stop every running request (Stop button, or the editor closing)."""
    with _LOCK:
        running = list(_RUNNING)
    for process in running:
        process.terminate()
    return len(running)


#: Current Claude models (full ids, so the version is the one shown). Claude Code has no
#: command that lists them; update this list when a new family ships.
CLAUDE_MODELS = (("claude-fable-5-2", "Fable 5.2"), ("claude-opus-5-5", "Opus 5.5"),
                 ("claude-sonnet-5-5", "Sonnet 5.5"), ("claude-haiku-5-5", "Haiku 5.5"))


class Agent:
    name = ""
    command = ""

    def __init__(self, model: str = "", server: list[str] | None = None,
                 effort: str = "") -> None:
        self.model = model
        self.effort = effort
        # The panel's agents act on the open editor only: never a second owner of the USB.
        self.server = server or [*server_command(), "--editor-only"]
        self.session = ""
        self.search_cabs = False

    @property
    def guide(self) -> str:
        if self.search_cabs:
            return f"{GUIDE}\n\n{CABS_GUIDE}"
        return f"{GUIDE}\nOnly call load_tone3000_ir when the user asks for an IR."

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.command) is not None

    @classmethod
    def models(cls) -> list[ModelChoice]:
        """Models to offer (may run the CLI: call it off the GUI thread)."""
        return [ModelChoice("", "Predeterminado")]

    def ask(self, request: str) -> str:
        reply = self.run(request, self.session)
        self.session = reply.session or self.session
        return reply.text

    def reset(self) -> None:
        self.session = ""

    def run(self, request: str, session: str) -> Reply:
        raise NotImplementedError


class ClaudeAgent(Agent):
    """``claude -p`` with only the ge150 MCP server and its tools; ``--resume`` continues."""

    name, command = "Claude", "claude"
    EFFORTS = ("low", "medium", "high", "xhigh", "max")

    @classmethod
    def models(cls) -> list[ModelChoice]:
        return [ModelChoice(model_id, label, cls.EFFORTS) for model_id, label in
                (("", "Predeterminado"), *CLAUDE_MODELS)]

    def args(self, session: str) -> list[str]:
        config = {"mcpServers": {"ge150": {"command": self.server[0], "args": self.server[1:]}}}
        args = [self.command, "-p", "--output-format", "json", "--tools", "",
                "--strict-mcp-config", "--setting-sources", "", "--mcp-config",
                json.dumps(config), "--append-system-prompt", self.guide,
                "--allowedTools", "mcp__ge150__*"]
        if session:
            args += ["--resume", session]
        if self.model:
            args += ["--model", self.model]
        if self.effort:
            args += ["--effort", self.effort]
        return args

    def run(self, request: str, session: str) -> Reply:
        result = _run(self.args(session), request, _workdir())  # stdin: --allowedTools is variadic
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ToneAIError(f"claude: {(result.stderr or result.stdout).strip()[:300]}") from exc
        if data.get("is_error"):
            raise ToneAIError(f"claude: {data.get('result') or data.get('subtype')}")
        return Reply(str(data.get("result", "")).strip(), str(data.get("session_id", "")))


class CodexAgent(Agent):
    """``codex exec`` (read-only sandbox) with the ge150 MCP server; ``exec resume`` continues."""

    name, command = "Codex", "codex"

    @classmethod
    def models(cls) -> list[ModelChoice]:
        """From ``codex debug models`` (the models this account can use)."""
        try:
            result = subprocess.run([cls.command, "debug", "models"], capture_output=True,
                                    text=True, timeout=20, check=False)
            listed = json.loads(result.stdout)["models"]
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
            return super().models()
        choices = [ModelChoice("", "Predeterminado", ("low", "medium", "high", "xhigh", "max"))]
        for model in listed:
            if model.get("visibility") != "list":
                continue
            efforts = tuple(str(level["effort"]) for level in
                            model.get("supported_reasoning_levels") or [])
            choices.append(ModelChoice(str(model["slug"]),
                                       str(model.get("display_name") or model["slug"]), efforts))
        return choices

    def args(self, session: str, out: Path) -> list[str]:
        config = [f"mcp_servers.ge150.command={json.dumps(self.server[0])}",
                  f"mcp_servers.ge150.args={json.dumps(self.server[1:])}",
                  'sandbox_mode="read-only"', 'approval_policy="never"',
                  f"developer_instructions={json.dumps(self.guide)}"]
        if self.effort:
            config.append(f"model_reasoning_effort={json.dumps(self.effort)}")
        args = [self.command, "exec"]
        if session:
            args += ["resume", session]
        args += ["--skip-git-repo-check", "--json", "-o", str(out)]
        for item in config:
            args += ["-c", item]
        if self.model:
            args += ["-m", self.model]
        return [*args, "-"]

    def run(self, request: str, session: str) -> Reply:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "answer.txt"
            result = _run(self.args(session, out), request, _workdir())
            text = out.read_text().strip() if out.exists() else ""
        thread = session
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started":
                thread = str(event.get("thread_id", thread))
        if result.returncode != 0 or not text:
            raise ToneAIError(f"codex: {(result.stderr or result.stdout).strip()[-300:]}")
        return Reply(text, thread)


AGENTS: dict[str, type[Agent]] = {"claude": ClaudeAgent, "codex": CodexAgent}


def available_agents() -> list[str]:
    return [key for key, cls in AGENTS.items() if cls.available()]
