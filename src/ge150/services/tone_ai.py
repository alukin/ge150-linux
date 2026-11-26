"""AI tone assistant: describe a sound, get a GE150 preset applied live.

The request goes to a coding-assistant CLI the user already has (Claude Code ``claude``
or OpenAI ``codex``), so it runs on the user's subscription without API keys. Both CLIs
return JSON constrained by :data:`SCHEMA`. The prompt carries the exact GE150 catalogue
(modules, models with the gear they are based on, parameters and ranges) and the current
edit buffer; the proposal is validated against the catalogue and written to the edit
buffer only (nothing is stored until the user saves).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ge150.model.catalog import Model, ModuleInfo, Param
from ge150.model.gear import MODULE_TAGS, gear_for
from ge150.model.preset import EXP_B, MODULES, Preset
from ge150.services.editor import Editor

TIMEOUT_S = 240

SYSTEM_PROMPT = """You are an expert guitar tone designer configuring a MOOER GE150 \
multi-effects pedal. The user describes a sound (an artist, a song, a genre or \
characteristics) or asks to adjust the current one. Answer with a complete patch using ONLY \
the modules, model names, parameter names, ranges and options listed in the catalogue. \
Signal chain order is fixed: FX/COMP -> DS/OD -> AMP -> CAB -> NS -> EQ -> MOD -> DELAY -> \
REVERB. Use the "based on" gear to recreate real rigs. Give a value for every parameter of \
each model you switch on, inside its range. Switch off modules the sound does not need. \
User IR/NR slots are only worth choosing when their names fit the request. Keep the \
explanation short (3-6 sentences, in the language of the user's request): the reference \
rig and the key choices."""

#: Structured output accepted by both ``claude --json-schema`` and ``codex --output-schema``
#: (strict: every property required, no free-form objects).
SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "explanation", "modules"],
    "properties": {
        "name": {"type": "string", "description": "short preset name, max 14 characters"},
        "explanation": {"type": "string"},
        "modules": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["module", "on", "model", "params"],
                "properties": {
                    "module": {"type": "string", "enum": list(MODULE_TAGS)},
                    "on": {"type": "boolean"},
                    "model": {"type": "string", "description": "model name, '' to keep"},
                    "params": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["name", "value"],
                            "properties": {"name": {"type": "string"},
                                           "value": {"type": "string"}},
                        },
                    },
                },
            },
        },
    },
}


class ToneAIError(Exception):
    pass


# --- prompt --------------------------------------------------------------------------


def _param_text(param: Param) -> str:
    if param.kind == "enum":
        return f"{param.name} [{' | '.join(param.options)}]"
    if param.kind == "number":
        unit = f" {param.unit}" if param.unit else ""
        return f"{param.name} {param.min:g}..{param.max:g}{unit}"
    return param.name


def catalog_text(catalog: Sequence[ModuleInfo], user_names: dict[str, list[str]] | None = None
                 ) -> str:
    """The catalogue, one model per line: ``number NAME (based on X): params``."""
    lines = []
    for index, info in enumerate(catalog):
        lines.append(f"## {MODULE_TAGS[index]} ({info.name})")
        for model in info.models:
            if model.hidden:
                continue
            name = model.name
            if model.user_slot and user_names:
                bank = user_names.get(MODULE_TAGS[index], [])
                slot = model.number - (27 if MODULE_TAGS[index] == "CAB" else 56)
                if 0 <= slot < len(bank):
                    name = f"{model.name} (user slot: {bank[slot]})"
            gear = gear_for(index, model.number)
            origin = "" if gear.generic or not gear.name else f" (based on {gear.name})"
            params = ", ".join(_param_text(p) for p in model.params)
            lines.append(f"- {name}{origin}: {params}")
    return "\n".join(lines)


def current_text(editor: Editor) -> str:
    """The edit buffer in the same vocabulary as the answer."""
    if editor.state.edit is None:
        return "(unknown)"
    rows = []
    for index in range(len(MODULES)):
        block = editor.module(index)
        model = editor.catalog[index].model_for_type(block.type)
        if model is None:
            continue
        params = ", ".join(f"{p.name}={p.format(block.words[p.word])}" for p in model.params)
        state = "ON" if block.switch else "off"
        name = editor.model_display(index, block.type)
        rows.append(f"{MODULE_TAGS[index]}: {state} {name} ({params})")
    return "\n".join(rows)


@dataclass
class Turn:
    request: str
    answer: str


@dataclass
class Conversation:
    """Earlier turns are replayed as context: each CLI call is stateless."""

    turns: list[Turn] = field(default_factory=list)

    def prompt(self, editor: Editor, request: str) -> str:
        names = editor.state.user_names
        user = {"CAB": list(names.ir), "AMP": list(names.nr)} if names else None
        parts = [SYSTEM_PROMPT, "# Catalogue\n" + catalog_text(editor.catalog, user),
                 "# Current patch\n" + current_text(editor)]
        if self.turns:
            history = "\n\n".join(f"User: {t.request}\nYou: {t.answer}" for t in self.turns)
            parts.append("# Conversation so far\n" + history)
        parts.append("# Request\n" + request)
        return "\n\n".join(parts)


# --- backends ------------------------------------------------------------------------


class Backend:
    name = ""
    command = ""

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.command) is not None

    def run(self, prompt: str, schema: dict[str, object] | None = None,
            system: str = "", web: bool = False) -> dict[str, object]:
        """One answer as JSON matching ``schema`` (default: a patch proposal); ``web`` lets
        it search and read web pages (and nothing else)."""
        raise NotImplementedError


def _run(args: list[str], stdin: str, cwd: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, input=stdin, capture_output=True, text=True, cwd=cwd,
                              timeout=TIMEOUT_S, check=False)
    except FileNotFoundError as exc:
        raise ToneAIError(f"{args[0]} is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToneAIError(f"{args[0]} did not answer within {TIMEOUT_S} s") from exc


class ClaudeBackend(Backend):
    """Claude Code in print mode: no tools, no MCP servers, no user settings, so the
    request carries only our prompt (about 1 K tokens of overhead)."""

    name, command = "Claude", "claude"

    def __init__(self, model: str = "") -> None:
        self.model = model

    def run(self, prompt: str, schema: dict[str, object] | None = None,
            system: str = "", web: bool = False) -> dict[str, object]:
        tools = "WebSearch,WebFetch" if web else ""
        args = [self.command, "-p", "--output-format", "json", "--no-session-persistence",
                "--tools", tools, "--strict-mcp-config", "--setting-sources", "",
                "--json-schema", json.dumps(schema or SCHEMA), "--system-prompt",
                system or "You design guitar patches and answer only with the schema."]
        if self.model:
            args += ["--model", self.model]
        if web:  # variadic: the prompt goes on stdin
            args += ["--allowedTools", "WebSearch", "WebFetch"]
        with tempfile.TemporaryDirectory() as cwd:
            result = _run(args, prompt, cwd)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ToneAIError(f"claude: {(result.stderr or result.stdout).strip()[:300]}") from exc
        if data.get("is_error"):
            raise ToneAIError(f"claude: {data.get('result') or data.get('subtype')}")
        structured = data.get("structured_output")
        if isinstance(structured, dict):
            return structured
        return _parse_json(str(data.get("result", "")), "claude")


class CodexBackend(Backend):
    """OpenAI Codex CLI: read-only sandbox, ephemeral session, JSON schema output."""

    name, command = "Codex", "codex"

    def __init__(self, model: str = "") -> None:
        self.model = model

    def run(self, prompt: str, schema: dict[str, object] | None = None,
            system: str = "", web: bool = False) -> dict[str, object]:
        if system:
            prompt = f"{system}\n\n{prompt}"
        with tempfile.TemporaryDirectory() as cwd:
            schema_file = Path(cwd) / "schema.json"
            schema_file.write_text(json.dumps(schema or SCHEMA))
            out = Path(cwd) / "answer.json"
            args = [self.command, "exec", "--skip-git-repo-check", "--ephemeral",
                    "--sandbox", "read-only", "--output-schema", str(schema_file), "-o", str(out)]
            if web:
                args += ["-c", 'web_search="live"']
            if self.model:
                args += ["-m", self.model]
            result = _run([*args, "-"], prompt, cwd)
            if result.returncode != 0 or not out.exists():
                raise ToneAIError(f"codex: {(result.stderr or result.stdout).strip()[-300:]}")
            return _parse_json(out.read_text(), "codex")


BACKENDS: dict[str, type[Backend]] = {"claude": ClaudeBackend, "codex": CodexBackend}


def available_backends() -> list[str]:
    return [key for key, cls in BACKENDS.items() if cls.available()]


def make_backend(key: str = "", model: str = "") -> Backend:
    """``key`` = "claude" / "codex"; empty picks the first one installed."""
    keys = [key] if key else available_backends()
    if not keys or keys[0] not in BACKENDS:
        raise ToneAIError("install Claude Code (claude) or Codex (codex) and sign in")
    cls = BACKENDS[keys[0]]
    return cls(model)  # type: ignore[call-arg]


def _parse_json(text: str, who: str) -> dict[str, object]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToneAIError(f"{who} did not answer with JSON: {text[:200]}") from exc
    if not isinstance(data, dict):
        raise ToneAIError(f"{who} answered {type(data).__name__}, expected an object")
    return data


# --- proposal -> edit buffer ------------------------------------------------------------


@dataclass
class ModuleChange:
    index: int
    on: bool
    model: Model | None
    raw: dict[int, int]  # word -> raw value


@dataclass
class Proposal:
    name: str
    explanation: str
    changes: list[ModuleChange]
    warnings: list[str]

    def describe(self, catalog: Sequence[ModuleInfo]) -> list[str]:
        rows = []
        for change in self.changes:
            tag = MODULE_TAGS[change.index]
            if not change.on:
                rows.append(f"{tag}: off")
                continue
            model = change.model
            params = ", ".join(f"{p.name}={p.format(change.raw[p.word])}"
                               for p in (model.params if model else ()) if p.word in change.raw)
            rows.append(f"{tag}: ON {model.label if model else ''}  {params}".rstrip())
        return rows


def _find_model(info: ModuleInfo, text: str) -> Model | None:
    wanted = text.strip().lower()
    if not wanted:
        return None
    head = wanted.split(":", 1)
    for model in info.models:
        if model.hidden:
            continue
        if wanted in (model.name.lower(), model.label.lower()):
            return model
        if head[0].isdigit() and int(head[0]) == model.number:
            return model
    for model in info.models:  # "BLACK RAT" vs "black rat distortion"
        if not model.hidden and model.name.lower() in wanted:
            return model
    return None


def _find_user_slot(editor: Editor, index: int, text: str) -> Model | None:
    """A user IR/NR slot named the way the AI saw it: "VOX AC30 BLUE 2",
    "32:VOX AC30 BLUE 2", "CAB 32" or "CAB 32 (user IR: VOX AC30 BLUE 2)"."""
    wanted = " ".join(text.strip().lower().split())
    for type_index, model in enumerate(editor.catalog[index].models):
        if not model.user_slot:
            continue
        label = editor.model_label(index, type_index).lower()
        name = label.split(":", 1)[-1].strip()
        tag = f"{MODULE_TAGS[index].lower()} {model.number}"
        display = editor.model_display(index, type_index).lower()
        loaded = name != model.name.lower()
        if wanted in (label, display, tag) or (loaded and wanted == name):
            return model
    return None


def _value_to_raw(param: Param, value: str) -> int | None:
    text = value.strip()
    if param.kind == "enum":
        options = [o.lower() for o in param.options]
        if text.lower() in options:
            return options.index(text.lower())
        if text.isdigit() and int(text) < len(options):
            return int(text)
        return None
    try:
        number = float(text.split()[0].replace(",", "."))
    except (ValueError, IndexError):
        return None
    if param.kind == "number":
        number = max(param.min, min(param.max, number))
        return param.to_raw(number)
    return int(number)


def parse_proposal(data: dict[str, object], editor: Editor,
                   base: Preset | None = None) -> Proposal:
    """Validate the CLI answer against the catalogue (unknown names become warnings).

    ``base``: the stored preset being changed (default: the edit buffer); a module without
    "on" keeps its state there."""
    warnings: list[str] = []
    changes: list[ModuleChange] = []
    modules = data.get("modules")
    for item in modules if isinstance(modules, list) else []:
        if not isinstance(item, dict) or item.get("module") not in MODULE_TAGS:
            warnings.append(f"unknown module entry: {item!r}"[:120])
            continue
        index = MODULE_TAGS.index(str(item["module"]))
        info = editor.catalog[index]
        block = base.module(index) if base is not None else editor.module(index)
        current = info.model_for_type(block.type)
        model = (_find_user_slot(editor, index, str(item.get("model", "")))
                 or _find_model(info, str(item.get("model", ""))) or current)
        if item.get("model") and model is current and current is not None and \
                _find_user_slot(editor, index, str(item["model"])) is not current and \
                str(item["model"]).lower() not in current.name.lower():
            warnings.append(f"{MODULE_TAGS[index]}: unknown model {item['model']!r}")
        raw: dict[int, int] = {}
        params = item.get("params")
        for entry in params if isinstance(params, list) else []:
            if not isinstance(entry, dict):
                continue
            pname = str(entry.get("name", "")).strip().lower()
            param = next((p for p in (model.params if model else ()) if p.name.lower() == pname),
                         None)
            value = _value_to_raw(param, str(entry.get("value", ""))) if param else None
            if param is None or value is None:
                warnings.append(f"{MODULE_TAGS[index]}: ignored {entry.get('name')}="
                                f"{entry.get('value')}")
                continue
            raw[param.word] = value
        on = bool(item["on"]) if item.get("on") is not None else block.switch
        changes.append(ModuleChange(index, on, model, raw))
    if not changes:
        raise ToneAIError("the answer has no modules")
    return Proposal(str(data.get("name", ""))[:14], str(data.get("explanation", "")),
                    changes, warnings)


def apply_proposal(editor: Editor, proposal: Proposal) -> None:
    """Write every proposed module to the edit buffer (live, nothing stored)."""
    for change in proposal.changes:
        block = editor.module(change.index)
        if change.model is not None:
            info = editor.catalog[change.index]
            block.type = info.models.index(change.model)
        block.switch = change.on
        for word, raw in change.raw.items():
            block.words[word] = raw & 0xFFFF
        editor.write_module(block)


def apply_to_words(words: Sequence[int], proposal: Proposal,
                   catalog: Sequence[ModuleInfo]) -> list[int]:
    """The preset words with the proposal applied (pure: writes nothing to the pedal)."""
    preset = Preset(1, "", list(words))
    for change in proposal.changes:
        block = preset.module(change.index)
        if change.model is not None:
            block.type = catalog[change.index].models.index(change.model)
        block.switch = change.on
        for word, raw in change.raw.items():
            block.words[word] = raw & 0xFFFF
        preset.set_module(block)
    return preset.words


def restore_words(editor: Editor, words: Sequence[int]) -> None:
    """Put back a previous edit buffer, module by module, and its EXP settings (undo of a
    proposal, or hearing a planned preset: the buffer must end up equal to ``words``, or it
    looks like unsaved changes of the user's)."""
    for index in range(len(MODULES)):
        block = editor.module(index)
        old = list(words[block.layout.slice])
        if old != block.words:
            block.words[:] = old
            editor.write_module(block)
    if len(words) >= EXP_B.stop:
        editor.write_exp_words(words)


class ToneAssistant:
    """Ask -> validate -> apply, keeping the conversation for follow-up requests and the
    edit buffer before each applied proposal (for :meth:`undo`)."""

    def __init__(self, editor: Editor, backend: Backend) -> None:
        self.editor, self.backend = editor, backend
        self.conversation = Conversation()
        self.history: list[list[int]] = []

    def ask(self, request: str, apply: bool = True) -> Proposal:
        data = self.backend.run(self.conversation.prompt(self.editor, request))
        proposal = parse_proposal(data, self.editor)
        summary = proposal.explanation + "\n" + "\n".join(proposal.describe(self.editor.catalog))
        self.conversation.turns.append(Turn(request, summary))
        if apply:
            if self.editor.state.edit is not None:
                self.history.append(list(self.editor.state.edit.words))
            apply_proposal(self.editor, proposal)
        return proposal

    def undo(self) -> bool:
        """Back to the sound before the last applied proposal."""
        if not self.history:
            return False
        restore_words(self.editor, self.history.pop())
        return True
