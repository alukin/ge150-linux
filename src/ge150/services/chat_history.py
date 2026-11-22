"""Saved AI conversations, to reopen one as it was (like the AgentHub plugin for Obsidian).

``$XDG_DATA_HOME/ge150/chats/index.json`` lists them (newest first) and ``<id>.json`` keeps
what the chat showed plus each CLI's session id, so reopening continues the same
conversation (``claude --resume``, ``codex exec resume``). Each chat (side panel, «Asistente»
tab) has its own ``scope``. Files are only readable by the user.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")  # ids become file names


@dataclass
class ChatEntry:
    id: str
    scope: str
    title: str
    provider: str  # the agent used last ("claude", "codex")
    created: float
    updated: float
    slot: int = 0  # the preset selected on the pedal during the conversation (0 = unknown)
    preset: str = ""  # its name then


@dataclass
class Chat:
    entry: ChatEntry
    blocks: list[str] = field(default_factory=list)  # the chat's HTML, block by block
    sessions: dict[str, str] = field(default_factory=dict)  # provider -> CLI session id


def new_id() -> str:
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def title_for(request: str) -> str:
    """The first request, on one line, as the conversation's title."""
    text = " ".join(request.split())
    return text if len(text) <= 70 else text[:69].rstrip() + "…"


class ChatStore:
    def __init__(self, directory: Path | None = None) -> None:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        self.directory = directory or Path(base) / "ge150" / "chats"

    # --- reading ----------------------------------------------------------------------

    def entries(self, scope: str = "") -> list[ChatEntry]:
        entries = [e for e in self._index() if not scope or e.scope == scope]
        return sorted(entries, key=lambda e: e.updated, reverse=True)

    def load(self, chat_id: str) -> Chat | None:
        entry = next((e for e in self._index() if e.id == chat_id), None)
        if entry is None or not _ID.match(chat_id):
            return None
        try:
            data = json.loads(self._path(chat_id).read_text())
        except (OSError, ValueError):
            return Chat(entry)
        blocks = [str(b) for b in data.get("blocks") or []]
        sessions = {str(k): str(v) for k, v in (data.get("sessions") or {}).items() if v}
        return Chat(entry, blocks, sessions)

    # --- writing ----------------------------------------------------------------------

    def save(self, chat: Chat) -> None:
        if not _ID.match(chat.entry.id):
            raise ValueError(f"invalid chat id {chat.entry.id!r}")
        chat.entry.updated = time.time()
        self._write(self._path(chat.entry.id),
                    {"blocks": chat.blocks, "sessions": chat.sessions})
        entries = [e for e in self._index() if e.id != chat.entry.id]
        self._write_index([chat.entry, *entries])

    def rename(self, chat_id: str, title: str) -> None:
        entries = self._index()
        for entry in entries:
            if entry.id == chat_id:
                entry.title = title.strip() or entry.title
        self._write_index(entries)

    def delete(self, chat_id: str) -> None:
        self._write_index([e for e in self._index() if e.id != chat_id])
        if _ID.match(chat_id):
            self._path(chat_id).unlink(missing_ok=True)

    # --- files ------------------------------------------------------------------------

    def _path(self, chat_id: str) -> Path:
        return self.directory / f"{chat_id}.json"

    def _index(self) -> list[ChatEntry]:
        try:
            data = json.loads((self.directory / "index.json").read_text())
        except (OSError, ValueError):
            return []
        entries = []
        for item in data if isinstance(data, list) else []:
            try:
                entry = ChatEntry(**{k: item[k] for k in ChatEntry.__dataclass_fields__
                                     if k in item})
            except (KeyError, TypeError):
                continue
            if _ID.match(entry.id):
                entries.append(entry)
        return entries

    def _write_index(self, entries: list[ChatEntry]) -> None:
        self._write(self.directory / "index.json", [asdict(e) for e in entries])

    def _write(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle)
        tmp.replace(path)
