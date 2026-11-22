"""Side panel: chat with Claude Code or Codex, which change the sound with the MCP tools.

The agent runs ``ge150-mcp``, which forwards to this editor (``ai_host.py``): each tool
call appears in the chat as it happens, the GUI updates at once, and storing asks the user.
"""

from __future__ import annotations

import html
import importlib.util
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ge150.services import tone_agent
from ge150.ui.ai_host import LABELS, AiHost

EXAMPLES = ("Tono de Slash en el solo de Sweet Child O' Mine",
            "Clean brillante con chorus estilo The Police",
            "Más ganancia y menos graves",
            "Busca en TONE3000 una IR de Mesa 4x12 y cárgala en la ranura 10")
USER, AI, MUTED, ERROR = "#ff8a1f", "#7fd3ff", "#8b95a3", "#ff8a80"


class _Prompt(QPlainTextEdit):
    """Enter sends, Shift+Enter makes a new line."""

    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if enter and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class _Done(QObject):
    finished = Signal(object, str)  # reply text (or None), error
    noted = Signal(str)


class AIPanel(QDockWidget):
    def __init__(self, host: AiHost, parent: QWidget | None = None) -> None:
        super().__init__("Asistente IA", parent)
        self.setObjectName("aiPanel")
        self.host = host
        self.agents: dict[str, tone_agent.Agent] = {}
        self.blocks: list[str] = []
        self.busy = False
        self._done = _Done(self)
        self._done.finished.connect(self._finished)
        self._done.noted.connect(self._note)
        host.called.connect(self._tool_called)

        body = QWidget()
        layout = QVBoxLayout(body)
        top = QHBoxLayout()
        self.provider = QComboBox()
        for key in tone_agent.available_agents():
            self.provider.addItem(tone_agent.AGENTS[key].name, key)
        self.new_button = QPushButton("Nueva")
        self.new_button.setToolTip("Empezar una conversación nueva")
        self.new_button.clicked.connect(self.new_conversation)
        top.addWidget(self.provider, 1)
        top.addWidget(self.new_button)
        layout.addLayout(top)

        self.chat = QTextBrowser()
        self.chat.setObjectName("aiChat")
        self.chat.setOpenExternalLinks(True)
        layout.addWidget(self.chat, 1)
        self.status = QLabel()
        self.status.setObjectName("note")
        layout.addWidget(self.status)
        self.prompt = _Prompt()
        self.prompt.setObjectName("aiPrompt")
        self.prompt.setPlaceholderText("Describe el sonido (Enter para enviar)")
        self.prompt.setFixedHeight(76)
        self.prompt.submitted.connect(self.ask)
        layout.addWidget(self.prompt)
        buttons = QHBoxLayout()
        self.undo_button = QPushButton("Deshacer")
        self.undo_button.setToolTip("Volver al sonido anterior al último cambio de la IA")
        self.undo_button.clicked.connect(self.undo)
        self.ask_button = QPushButton("Enviar")
        self.ask_button.setObjectName("saveButton")
        self.ask_button.clicked.connect(self._send_or_stop)
        buttons.addWidget(self.undo_button)
        buttons.addStretch(1)
        buttons.addWidget(self.ask_button)
        layout.addLayout(buttons)
        self.setWidget(body)
        self.setMinimumWidth(340)
        self._welcome()

    def _welcome(self) -> None:
        if importlib.util.find_spec("mcp") is None:
            self._ready(False)
            self._note("Falta el SDK de MCP: <code>pip install 'ge150-linux[ai]'</code>.")
        elif self.provider.count() == 0:
            self._ready(False)
            self._note("No encontré <b>claude</b> ni <b>codex</b>. Instala Claude Code o Codex e "
                       "inicia sesión con tu cuenta.")
        else:
            examples = "".join(f"<li>{html.escape(e)}</li>" for e in EXAMPLES)
            self._note("Pide un sonido y lo ajusto <b>en vivo</b>. No se guarda hasta que aprietes "
                       "<b>Guardar</b> o me lo pidas (te pregunto antes). Ejemplos:<ul>"
                       f"{examples}</ul>")

    # --- actions ----------------------------------------------------------------------

    def _agent(self) -> tone_agent.Agent:
        key = str(self.provider.currentData())
        if key not in self.agents:
            self.agents[key] = tone_agent.AGENTS[key]()
        return self.agents[key]

    def ask(self, text: str = "") -> None:
        request = (text or self.prompt.toPlainText()).strip()
        if not request or self.busy or not self.prompt.isEnabled():
            return
        agent = self._agent()
        self.prompt.clear()
        self._bubble("Tú", html.escape(request).replace("\n", "<br>"), USER)
        self._set_busy(True, f"{agent.name} está trabajando…")

        def work() -> None:
            try:
                reply: object = agent.ask(request)
                error = ""
            except Exception as exc:  # shown in the chat
                reply, error = None, str(exc)
            self._done.finished.emit(reply, error)

        threading.Thread(target=work, name="ge150-agent", daemon=True).start()

    def _send_or_stop(self) -> None:
        if self.busy:
            tone_agent.stop_all()
            self.status.setText("Deteniendo…")
        else:
            self.ask()

    def undo(self) -> None:
        def work() -> None:
            try:
                undone = self.host.tools.undo().get("undone")
            except Exception as exc:  # shown in the chat
                self._done.noted.emit(f"<span style='color:{ERROR}'>{html.escape(str(exc))}</span>")
                return
            self._done.noted.emit("Volví al sonido anterior." if undone else
                                  "No hay cambios de la IA para deshacer.")

        threading.Thread(target=work, daemon=True).start()

    def new_conversation(self) -> None:
        for agent in self.agents.values():
            agent.reset()
        self.blocks.clear()
        self._welcome()

    # --- results ----------------------------------------------------------------------

    def _finished(self, reply: object, error: str) -> None:
        self._set_busy(False)
        if error == "stopped":
            self._note("Detenido. Lo que alcanzó a cambiar sigue aplicado (Deshacer lo revierte).")
        elif error:
            self._note(f"<span style='color:{ERROR}'>Error: {html.escape(error)}</span>")
        elif isinstance(reply, str):
            self._bubble(self.provider.currentText(), _markdown(reply), AI)

    def _tool_called(self, tool: str) -> None:
        if self.busy:
            self._add(f"<div style='color:{MUTED}'>· {LABELS.get(tool, tool)}</div>")

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.busy = busy
        self.ask_button.setText("Detener" if busy else "Enviar")
        self.undo_button.setEnabled(not busy)
        self.provider.setEnabled(not busy)
        self.prompt.setReadOnly(busy)
        self.status.setText(text)

    def _ready(self, ok: bool) -> None:
        for widget in (self.ask_button, self.undo_button, self.prompt, self.provider):
            widget.setEnabled(ok)

    def _add(self, block: str) -> None:
        """Whole-document render: ``append`` would continue an open list."""
        self.blocks.append(block)
        self.chat.setHtml("".join(self.blocks))
        bar = self.chat.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _note(self, text: str) -> None:
        self._add(f"<p style='color:{MUTED}'>{text}</p>")

    def _bubble(self, who: str, body: str, colour: str) -> None:
        self._add(f"<p style='margin-top:12px'><b style='color:{colour}'>{html.escape(who)}</b>"
                  f"</p><div>{body}</div>")


def _markdown(text: str) -> str:
    """The little Markdown agents use (lists, **bold**) as HTML."""
    import re

    out: list[str] = []
    in_list = False
    for line in text.splitlines():
        item = re.match(r"\s*[-*•]\s+(.*)", line)
        if item and not in_list:
            out.append("<ul>")
            in_list = True
        elif not item and in_list:
            out.append("</ul>")
            in_list = False
        content = html.escape(item.group(1) if item else line)
        content = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", content)
        content = re.sub(r"`(.+?)`", r"<code>\1</code>", content)
        out.append(f"<li>{content}</li>" if item else (f"{content}<br>" if content else ""))
    if in_list:
        out.append("</ul>")
    return "".join(out)
