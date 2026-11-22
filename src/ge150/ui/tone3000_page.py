"""TONE3000 tab: the TONE3000 catalogue inside the app, and "add to the pedal".

The catalogue is TONE3000's own Select flow (``prompt=select_tone``, cabinet IRs only) in an
embedded browser. When the user picks a tone, TONE3000 redirects to our callback URL; the
page intercepts that navigation instead of loading it, exchanges the code for tokens and
shows the tone on the right (image, author, licence, files) with a slot chooser. The
catalogue then starts again so the user can keep browsing. Without Qt WebEngine the same
flow runs in the system browser.
"""

from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ge150.protocol import messages as msg
from ge150.services.editor import Editor
from ge150.services.tone3000 import Pending, Tone, ToneModel, parse_callback
from ge150.ui.tone3000_loader import Tone3000Loader
from ge150.ui.tone_detail import ToneDetail
from ge150.ui.worker import TaskRunner

HINT = ("Busca una cabina en el catálogo y aprieta «Select» en la IR que quieras: aparece a la "
        "derecha para agregarla a la pedalera.")


class _Callbacks(QObject):
    url = Signal(str)


def _web_view(callbacks: _Callbacks, is_callback: Any) -> QWidget | None:
    """An embedded browser that hands TONE3000's redirect to us, or None without WebEngine."""
    try:
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        return None

    class Page(QWebEnginePage):
        def acceptNavigationRequest(self, url: QUrl, kind: Any, main_frame: bool) -> bool:
            if is_callback(url.toString()):
                callbacks.url.emit(url.toString())
                return False
            return bool(super().acceptNavigationRequest(url, kind, main_frame))

    view = QWebEngineView()
    # A named profile lives on disk; forcing persistence also keeps session cookies, so the
    # TONE3000 sign-in (an emailed code) survives restarts of the editor.
    profile = QWebEngineProfile("ge150-tone3000", view)
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
    view.setPage(Page(profile, view))
    return view


class Tone3000Page(QWidget):
    def __init__(self, editor: Editor, runner: TaskRunner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.loader = Tone3000Loader(editor, runner, self)
        self.client = self.loader.client
        self.pending: Pending | None = None
        self.tone: Tone | None = None
        self.models: list[ToneModel] = []
        self.user_name = ""
        self.view: QWidget | None = None
        self._callbacks = _Callbacks(self)
        # Queued: handle it after the browser has finished refusing that navigation; loading
        # a page from inside acceptNavigationRequest aborts Qt WebEngine.
        self._callbacks.url.connect(self._callback, Qt.ConnectionType.QueuedConnection)
        self.loader._done.connect(self._background_done)
        self.loader.stored.connect(self._stored)
        self.loader.failed.connect(self._failed)
        self.loader.status.connect(self._status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        bar = QFrame()
        bar.setObjectName("modulePage")
        top = QHBoxLayout(bar)
        top.setContentsMargins(16, 10, 16, 10)
        brand = QLabel("TONE3000")
        brand.setObjectName("moduleTitle")
        self.account = QLabel()
        self.account.setObjectName("basedOn")
        self.home_button = QPushButton("Catálogo")
        self.home_button.setToolTip("Volver al inicio del catálogo")
        self.home_button.clicked.connect(self.start_catalogue)
        self.key_button = QPushButton("Clave…")
        self.key_button.clicked.connect(self._change_key)
        self.logout_button = QPushButton("Cerrar sesión")
        self.logout_button.clicked.connect(self._logout)
        top.addWidget(brand)
        top.addSpacing(10)
        top.addWidget(self.account)
        top.addStretch(1)
        for button in (self.home_button, self.key_button, self.logout_button):
            top.addWidget(button)
        layout.addWidget(bar)

        self.stack = QStackedWidget()
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setObjectName("note")
        self.stack.addWidget(self.message)

        side = QFrame()
        side.setObjectName("modulePage")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(16, 14, 16, 14)
        self.detail = ToneDetail()
        side_layout.addWidget(self.detail, 1)
        form = QFormLayout()
        self.file_combo = QComboBox()
        self.slot_combo = QComboBox()
        form.addRow("Archivo", self.file_combo)
        form.addRow("Ranura", self.slot_combo)
        side_layout.addLayout(form)
        self.add_button = QPushButton("Agregar a la pedalera")
        self.add_button.setObjectName("saveButton")
        self.add_button.clicked.connect(self._add)
        side_layout.addWidget(self.add_button)
        self.side = side
        self.side.hide()

        splitter = QSplitter()
        splitter.addWidget(self.stack)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 420])
        layout.addWidget(splitter, 1)
        self.note = QLabel(HINT)
        self.note.setObjectName("note")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self._refresh_account()

    def _status(self, text: str) -> None:
        self.note.setText(text or HINT)

    def _failed(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    # --- catalogue ------------------------------------------------------------------

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self._refresh_slots()
        if self.pending is None:
            self.start_catalogue()

    def start_catalogue(self) -> None:
        if not self.client.creds.client_id:
            self._show_message("Para ver el catálogo falta la clave publicable de tu cuenta "
                               "de TONE3000 (botón <b>Clave…</b>).")
            return
        self.pending = self.client.begin("select_tone")
        if self.view is None:
            self.view = _web_view(self._callbacks, self.client.is_callback)
            if self.view is not None:
                self.stack.addWidget(self.view)
        if self.view is None:  # no Qt WebEngine: the system browser and the loopback server
            self._show_message("Este sistema no tiene navegador integrado (Qt WebEngine): "
                               "el catálogo se abrió en tu navegador.")
            self.loader.background(self._select_outside, slot=-4)
            return
        self.stack.setCurrentWidget(self.view)
        self.view.load(QUrl(self.pending.url))

    def _select_outside(self) -> object:
        tone_id = self.client.select_tone()
        return self.client.tone(tone_id), self.client.models(tone_id)

    def _show_message(self, text: str) -> None:
        self.message.setText(text)
        self.stack.setCurrentWidget(self.message)

    def _callback(self, url: str) -> None:
        pending = self.pending
        if pending is None:
            return
        callback = parse_callback(url)
        if callback.error == "access_denied":  # the user closed or cancelled the flow
            self.start_catalogue()
            return

        def work() -> object:
            self.client.finish(pending, callback)
            if not callback.tone_id:  # plain sign-in, no tone chosen
                return None
            tone_id = int(callback.tone_id)
            return self.client.tone(tone_id), self.client.models(tone_id)

        self.note.setText("Leyendo la IR elegida…")
        self.loader.background(work, slot=-4)
        self.start_catalogue()  # keep browsing; TONE3000 remembers the sign-in

    def _background_done(self, result: object, error: str, slot: int) -> None:
        if slot == -5 and isinstance(result, dict):  # silent: only the account label
            self.user_name = str(result.get("display_name") or result.get("username") or "")
            self._refresh_account()
        if slot != -4:
            return
        self.note.setText(HINT)
        self._refresh_account()
        if error:
            QMessageBox.warning(self, "TONE3000", error)
        elif isinstance(result, tuple):
            self._show_tone(*result)

    # --- the chosen tone ------------------------------------------------------------

    def _show_tone(self, tone: Tone, models: list[ToneModel]) -> None:
        self.tone, self.models = tone, models
        self.detail.show_slot({"title": tone.title, "author": tone.author,
                               "author_url": tone.author_url, "avatar_url": tone.avatar_url,
                               "license": tone.license, "description": tone.description,
                               "image_url": tone.image_url, "url": tone.page_url},
                              tone.title)
        self.file_combo.clear()
        for model in models:
            self.file_combo.addItem(model.name, model.id)
        self.add_button.setEnabled(bool(models) and tone.format in ("", "ir"))
        self.side.show()
        if not self.user_name:
            self.loader.background(self.client.user, slot=-5)

    def _refresh_slots(self) -> None:
        names = self.editor.state.user_names
        current = max(0, self.slot_combo.currentIndex())
        self.slot_combo.clear()
        for i in range(msg.USER_SLOTS):
            name = names.ir[i] if names else "?"
            self.slot_combo.addItem(f"IR {i + 1}  (CAB {27 + i})  ·  {name}", i)
        self.slot_combo.setCurrentIndex(current)

    def _add(self) -> None:
        if self.tone is None:
            return
        model = self.file_combo.currentData()
        self.loader.add(self.tone.id, int(model) if model is not None else None,
                        int(self.slot_combo.currentData()))

    def _stored(self, slot: int) -> None:
        self._refresh_slots()
        self.note.setText(f"Lista en la ranura IR {slot + 1}: elige CAB {27 + slot} en la "
                          "pestaña Efectos para escucharla.")

    # --- account --------------------------------------------------------------------

    def _refresh_account(self) -> None:
        creds = self.client.creds
        if not creds.client_id:
            text = "Falta la clave publicable."
        elif creds.signed_in:
            who = f" como <b>{html.escape(self.user_name)}</b>" if self.user_name else ""
            text = f"Sesión iniciada{who}."
        else:
            text = "Elige una IR en el catálogo (botón «Select») para conectar tu cuenta."
        self.account.setText(text)
        self.logout_button.setVisible(creds.signed_in)

    def _logout(self) -> None:
        self.client.logout()
        self.user_name = ""
        if self.view is not None:  # also forget the TONE3000 web session
            self.view.page().profile().cookieStore().deleteAllCookies()
        self._refresh_account()
        self.start_catalogue()

    def _change_key(self) -> None:
        old = self.client.creds.client_id
        self.client.creds.client_id = ""
        if not self.loader.ensure_key():
            self.client.creds.client_id = old
        self._refresh_account()
        self.start_catalogue()
