"""The editor hosts the MCP tools for ``ge150-mcp`` (Claude Code, Codex...).

Tool calls arrive on HTTP threads (``mcp_server/bridge.py``) and share the pedal lock with
the GUI's :class:`~ge150.ui.worker.TaskRunner`, so they never overlap. Writing the pedal's
memory asks the user in a dialog on the GUI thread; the calling thread waits for the answer.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from ge150.mcp_server.bridge import LocalServer
from ge150.mcp_server.tools import PedalTools
from ge150.services.editor import Editor
from ge150.ui.worker import TaskRunner

log = logging.getLogger(__name__)
ANSWER_TIMEOUT_S = 300
LABELS = {"get_catalog": "revisa el catálogo", "get_current_patch": "lee el sonido actual",
          "list_presets": "lee la lista de presets", "get_preset": "lee un preset",
          "list_user_irs": "lee las IR de usuario", "get_settings": "lee los ajustes",
          "set_module": "cambia un módulo", "apply_patch": "aplica un sonido",
          "undo": "deshace", "select_preset": "cambia de preset", "save_preset": "guarda",
          "tone3000_search": "busca en TONE3000", "tone3000_get": "lee TONE3000",
          "load_tone3000_ir": "descarga una IR"}


class AiHost(QObject):
    #: tool name, emitted for every call (on the GUI thread).
    called = Signal(str)
    _ask = Signal(str, object)
    _call = Signal(str)

    def __init__(self, editor: Editor, runner: TaskRunner, parent: QWidget) -> None:
        super().__init__(parent)
        self.window = parent
        self.tools = PedalTools(editor, runner.lock, confirm=self.confirm)
        self.server: LocalServer | None = None
        self._ask.connect(self._on_ask)
        self._call.connect(self.called)

    def start(self) -> None:
        if self.server is not None:
            return
        try:
            self.server = LocalServer(self.tools, self._call.emit).start()
        except OSError as exc:  # the editor still works without it
            log.warning("cannot share the pedal with AI clients: %s", exc)

    def stop(self) -> None:
        if self.server is not None:
            self.server.stop()
            self.server = None

    def confirm(self, question: str) -> bool:
        if QThread.currentThread() is self.thread():
            return self._question(question)
        box: dict[str, Any] = {"event": threading.Event(), "answer": False}
        self._ask.emit(question, box)
        box["event"].wait(ANSWER_TIMEOUT_S)
        return bool(box["answer"])

    def _on_ask(self, question: str, box: dict[str, Any]) -> None:
        try:
            box["answer"] = self._question(question)
        finally:
            box["event"].set()

    def _question(self, question: str) -> bool:
        self.window.raise_()
        self.window.activateWindow()
        answer = QMessageBox.question(self.window, "Asistente IA", question,
                                      QMessageBox.StandardButton.Yes
                                      | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes
