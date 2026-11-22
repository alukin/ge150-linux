"""Side panel: chat with Claude Code or Codex, which change the sound with the MCP tools.

The agent runs ``ge150-mcp``, which forwards to this editor (``ai_host.py``): each tool
call appears in the chat as it happens, the GUI updates at once, and storing asks the user.
"""

from __future__ import annotations

import html
import importlib.util
import threading

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ge150.services import tone_agent, tone_ai
from ge150.ui.ab_compare import SoundCompare
from ge150.ui.ai_host import LABELS, AiHost
from ge150.ui.ai_options import AgentOptions
from ge150.ui.icons import icon
from ge150.ui.theme import ACCENT
from ge150.ui.theme import MUTED as MUTED_ICON

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
        self._before: list[int] | None = None
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
        # The composer (like the AgentHub plugin for Obsidian): context chips, the message and a
        # toolbar with option pills and a round send/stop button, all inside one rounded box.
        self.composer = QFrame()
        self.composer.setObjectName("composer")
        box = QVBoxLayout(self.composer)
        box.setContentsMargins(10, 8, 8, 8)
        box.setSpacing(4)
        self.context = QPushButton()
        self.context.setObjectName("contextChip")
        self.context.setCheckable(True)
        self.context.setChecked(True)
        self.context.setCursor(Qt.CursorShape.PointingHandCursor)
        self.context.toggled.connect(lambda _: self.refresh_context())
        box.addWidget(self.context, 0, Qt.AlignmentFlag.AlignLeft)
        self.prompt = _Prompt()
        self.prompt.setObjectName("aiPrompt")
        self.prompt.setPlaceholderText("Describe el sonido…  (Enter envía, Shift+Enter salto)")
        self.prompt.setFixedHeight(64)
        self.prompt.submitted.connect(self.ask)
        self.prompt.installEventFilter(self)
        box.addWidget(self.prompt)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        self.undo_button = QToolButton()
        self.undo_button.setObjectName("pill")
        self.undo_button.setIcon(icon("undo", MUTED_ICON, 13))
        self.undo_button.setToolTip("Deshacer: volver al sonido anterior al último cambio de la IA")
        self.undo_button.clicked.connect(self.undo)
        self.options = AgentOptions()
        self.provider.currentIndexChanged.connect(
            lambda _: self.options.set_provider(str(self.provider.currentData() or "")))
        self.options.set_provider(str(self.provider.currentData() or ""))
        self.ask_button = QToolButton()
        self.ask_button.setObjectName("sendButton")
        self.ask_button.setIcon(icon("arrow-up", "#1b1205", 16))
        self.ask_button.setToolTip("Enviar (Enter)")
        self.ask_button.clicked.connect(self._send_or_stop)
        toolbar.addWidget(self.undo_button)
        toolbar.addWidget(self.options)
        toolbar.addStretch(1)
        toolbar.addWidget(self.ask_button)
        box.addLayout(toolbar)
        self.compare = SoundCompare(host)
        layout.addWidget(self.compare)
        layout.addWidget(self.composer)
        self.setWidget(body)
        self.setMinimumWidth(340)
        self.refresh_context()
        self._welcome()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """The whole box shows the focus of the message (like :focus-within)."""
        if watched is self.prompt and event.type() in (QEvent.Type.FocusIn,
                                                       QEvent.Type.FocusOut):
            self.composer.setProperty("focused", event.type() == QEvent.Type.FocusIn)
            self.composer.style().unpolish(self.composer)
            self.composer.style().polish(self.composer)
        return super().eventFilter(watched, event)

    def refresh_context(self) -> None:
        """The chip: the selected preset goes with each message unless the user unticks it."""
        state = self.host.tools.editor.state
        slot = state.current_slot
        stored = state.presets.get(slot or 0)
        self.compare.preset_changed(slot, list(stored.words) if stored else None)
        preset = state.presets.get(slot or 0)
        label = f"{slot:03d} {preset.name if preset else ''}".strip() if slot else "—"
        font = self.context.font()
        font.setStrikeOut(not self.context.isChecked())  # QSS text-decoration ignores :checked
        self.context.setFont(font)
        on = self.context.isChecked()
        self.context.setIcon(icon("sliders" if on else "slash", ACCENT if on else MUTED_ICON, 13))
        if on:
            self.context.setText(f"Preset actual: {label}")
            self.context.setToolTip("Se envía con tu mensaje. Clic para no incluirlo.")
        else:
            self.context.setText(f"Preset actual no incluido: {label}")
            self.context.setToolTip("Clic para incluir el preset actual en tu mensaje.")

    def _with_context(self, request: str) -> str:
        if not self.context.isChecked():
            return request
        editor = self.host.tools.editor
        state = editor.state
        if state.edit is None:
            return request
        preset = state.presets.get(state.current_slot or 0)
        name = preset.name if preset else ""
        changed = " (con cambios sin guardar)" if state.dirty else ""
        return (f"[Contexto: preset seleccionado {state.current_slot} «{name}»{changed}. "
                f"Sonido actual:\n{tone_ai.current_text(editor)}]\n\n{request}")

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
        """The provider's agent (one per provider keeps its conversation), with the model
        and effort picked now: changing them goes on with the same conversation."""
        key = str(self.provider.currentData())
        if key not in self.agents:
            self.agents[key] = tone_agent.AGENTS[key]()
        agent = self.agents[key]
        agent.model, agent.effort = self.options.selection()
        return agent

    def ask(self, text: str = "") -> None:
        request = (text or self.prompt.toPlainText()).strip()
        if not request or self.busy or not self.prompt.isEnabled():
            return
        agent = self._agent()
        message = self._with_context(request)
        # "Original" = the preset as stored on the pedal, not the AI's previous suggestion.
        state = self.host.tools.editor.state
        stored = state.presets.get(state.current_slot or 0)
        edit = state.edit
        self._before = list(stored.words) if stored is not None else (
            list(edit.words) if edit is not None else None)
        self.compare.clear()
        self.prompt.clear()
        self._bubble("Tú", html.escape(request).replace("\n", "<br>"), USER)
        self._set_busy(True, f"{agent.name} está trabajando…")

        def work() -> None:
            try:
                reply: object = agent.ask(message)
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
        self.compare.clear()
        self.blocks.clear()
        self._welcome()

    # --- results ----------------------------------------------------------------------

    def _finished(self, reply: object, error: str) -> None:
        self._set_busy(False)
        state = self.host.tools.editor.state
        if self._before is not None and state.edit is not None:
            self.compare.offer(self._before, list(state.edit.words), state.current_slot)
        self._before = None
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
        self.ask_button.setIcon(icon("square", ACCENT, 12) if busy else
                                icon("arrow-up", "#1b1205", 16))
        self.ask_button.setToolTip("Detener" if busy else "Enviar (Enter)")
        self.ask_button.setProperty("busy", busy)
        self.ask_button.style().unpolish(self.ask_button)
        self.ask_button.style().polish(self.ask_button)
        self.undo_button.setEnabled(not busy)
        self.provider.setEnabled(not busy)
        self.options.setEnabled(not busy)
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
