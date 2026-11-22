"""«Mis guitarras»: register the guitars the user plays, so the AI knows what goes into the
pedal. "Identificar con IA" fills the empty fields from brand + model + serial number (the
user reviews them before saving)."""

from __future__ import annotations

import html
import re
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QPixmap, QResizeEvent, QShowEvent, QTransform
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ge150.services import guitars
from ge150.services.guitars import Guitar, GuitarStore

#: Short values: one line. The rest wraps and grows with its text.
SHORT = ("brand", "year", "serial", "scale", "tuning")


class _Field(QPlainTextEdit):
    """A text box as tall as its wrapped text (2-6 lines), Enter does not add lines."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("guitarField")
        self.setTabChangesFocus(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Fires after every relayout (new text or new width), unlike contentsChanged.
        self.document().documentLayout().documentSizeChanged.connect(lambda _: self._fit())
        self._fit()

    def text(self) -> str:
        return " ".join(self.toPlainText().split())

    def setText(self, text: str) -> None:
        self.setPlainText(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.focusNextChild()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """A new width rewraps the text: measure again once the relayout is done."""
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            QTimer.singleShot(0, self._fit)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._fit)

    def _fit(self) -> None:
        """Exactly the height of the wrapped text (1-6 lines). A plain-text document measures
        its height in lines, not pixels."""
        doc = self.document()
        lines = min(max(round(doc.documentLayout().documentSize().height()), 1), 6)
        margins = self.contentsMargins()
        self.setFixedHeight(int(lines * self.fontMetrics().lineSpacing()
                                + 2 * doc.documentMargin() + margins.top()
                                + margins.bottom()) + 2)


class _Identified(QObject):
    done = Signal(object, str)  # (guitar, confidence, why) or None, error


class GuitarDialog(QDialog):
    def __init__(self, store: GuitarStore, provider: str = "", model: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store, self.provider, self.model = store, provider, model
        self.setWindowTitle("Mis guitarras")
        self.resize(1180, 680)
        self.image = ""
        self.editing: Guitar | None = None
        self.evidence: dict[str, str] = {}
        self.report = ""
        self._loading = False
        self._identified = _Identified(self)
        self._identified.done.connect(self._identify_done)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setWordWrap(True)  # long names on two lines, no sideways scrolling
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(lambda _: self._show_selected())
        left_layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        add = QPushButton("Nueva")
        add.clicked.connect(self._new)
        self.delete = QPushButton("Borrar")
        self.delete.clicked.connect(self._delete)
        row.addWidget(add)
        row.addWidget(self.delete)
        left_layout.addLayout(row)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("Escribe marca, modelo y número de serie, y aprieta <b>Identificar con "
                      "IA</b>: completa lo que falte buscando la ficha de fábrica. Revisa los "
                      "datos antes de guardar.")
        hint.setObjectName("note")
        hint.setWordWrap(True)
        right_layout.addWidget(hint)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self.inputs: dict[str, QLineEdit | _Field] = {}
        self.tags: dict[str, QLabel] = {}
        for name, label in guitars.FIELDS:
            edit: QLineEdit | _Field = QLineEdit() if name in SHORT else _Field()
            self.inputs[name] = edit
            tag = QLabel()
            tag.setObjectName("evidenceTag")
            tag.setFixedWidth(84)
            tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tags[name] = tag
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(edit, 1)
            row.addWidget(tag, 0, Qt.AlignmentFlag.AlignTop)
            form.addRow(label, row)
            changed = edit.textEdited if isinstance(edit, QLineEdit) else edit.textChanged
            changed.connect(lambda *_, n=name: self._typed(n))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        right_layout.addWidget(scroll, 1)
        self.status = QLabel()
        self.status.setObjectName("note")
        self.status.setWordWrap(True)
        right_layout.addWidget(self.status)
        self.report_view = QTextBrowser()  # how the guitar was identified, with its sources
        self.report_view.setObjectName("guitarReport")
        self.report_view.setOpenExternalLinks(True)
        self.report_view.setMaximumHeight(130)
        right_layout.addWidget(self.report_view)
        buttons = QHBoxLayout()
        self.identify_button = QPushButton("Identificar con IA")
        self.identify_button.clicked.connect(self._identify)
        self.use_button = QPushButton("Usar esta guitarra")
        self.use_button.clicked.connect(self._use)
        save = QPushButton("Guardar")
        save.setObjectName("saveButton")
        save.clicked.connect(self._save)
        buttons.addWidget(self.identify_button)
        buttons.addStretch(1)
        buttons.addWidget(self.use_button)
        buttons.addWidget(save)
        right_layout.addLayout(buttons)

        photo = QWidget()
        photo_layout = QVBoxLayout(photo)
        photo_layout.setContentsMargins(0, 0, 0, 0)
        self.picture = QLabel()
        self.picture.setObjectName("guitarPicture")
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setMinimumSize(220, 300)
        photo_layout.addWidget(self.picture, 1)
        photo_buttons = QHBoxLayout()
        change = QPushButton("Cambiar foto…")
        change.clicked.connect(self._choose_picture)
        self.remove_picture = QPushButton("Quitar")
        self.remove_picture.clicked.connect(lambda: self._set_picture(""))
        photo_buttons.addWidget(change, 1)
        photo_buttons.addWidget(self.remove_picture)
        photo_layout.addLayout(photo_buttons)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.addWidget(photo)
        splitter.setSizes([240, 620, 300])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
        self._reload(store.active)
        if not store.guitars:
            self._new()

    # --- list -----------------------------------------------------------------------

    def _reload(self, select: str = "") -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for guitar in self.store.guitars:
            active = guitar.id == self.store.active
            item = QListWidgetItem(("✓ " if active else "") + guitar.title)
            item.setToolTip(guitar.title + ("\nEn uso: va con cada pedido a la IA" if active
                                            else ""))
            item.setData(Qt.ItemDataRole.UserRole, guitar.id)
            self.list.addItem(item)
            if guitar.id == select:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self._show_selected()

    def _show_selected(self) -> None:
        item = self.list.currentItem()
        guitar = self.store.get(str(item.data(Qt.ItemDataRole.UserRole))) if item else None
        if guitar is not None:
            self._fill(guitar)
        self.delete.setEnabled(guitar is not None)

    def _fill(self, guitar: Guitar) -> None:
        self.editing = guitar
        self.evidence, self.report = dict(guitar.evidence), guitar.report
        self._set_picture(guitar.image)
        self._loading = True
        for name, edit in self.inputs.items():
            edit.setText(getattr(guitar, name))
            if isinstance(edit, QLineEdit):
                edit.setCursorPosition(0)  # show the start of a long value
        self._loading = False
        self._show_tags()
        self.status.setText("")
        self._show_report(guitar.report)

    # --- picture -----------------------------------------------------------------------

    def _set_picture(self, path: str) -> None:
        self.image = path
        pixmap = QPixmap(path) if path else QPixmap()
        self.remove_picture.setEnabled(not pixmap.isNull())
        if pixmap.isNull():
            self.picture.setPixmap(QPixmap())
            self.picture.setText("Sin foto.\nAl identificar con IA se busca la foto oficial; "
                                 "también puedes poner una tuya.")
            self.picture.setWordWrap(True)
            return
        if pixmap.width() > pixmap.height() * 1.3:  # lying photo: stand it up, neck at the top
            pixmap = pixmap.transformed(QTransform().rotate(-90),
                                        Qt.TransformationMode.SmoothTransformation)
        self._pixmap = pixmap
        self._fit_picture()

    def _fit_picture(self) -> None:
        pixmap = getattr(self, "_pixmap", None)
        if self.image and pixmap is not None:
            self.picture.setPixmap(pixmap.scaled(
                self.picture.size() - QSize(16, 16), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_picture()

    def _choose_picture(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Foto de la guitarra", "",
                                              "Imágenes (*.jpg *.jpeg *.png *.webp)")
        if not path:
            return
        guitar = self._form()
        try:
            guitars.set_own_image(guitar, Path(path))
        except OSError as exc:
            QMessageBox.warning(self, "Foto", str(exc))
            return
        self._set_picture(guitar.image)
        self.status.setText("Foto cambiada: aprieta <b>Guardar</b>.")

    def _show_report(self, report: str) -> None:
        self.report_view.setVisible(bool(report))
        text = html.escape(report)
        text = re.sub(r"(https?://[^\s<]+)", r"<a style='color:#ff8a1f' href='\1'>\1</a>", text)
        self.report_view.setHtml(text.replace("\n", "<br>"))

    def _show_tags(self) -> None:
        for name, tag in self.tags.items():
            level = self.evidence.get(name, "")
            tag.setText(level)
            tag.setToolTip(guitars.EVIDENCE.get(level, ""))
            tag.setProperty("level", level)
            tag.style().unpolish(tag)
            tag.style().polish(tag)

    def _typed(self, name: str) -> None:
        """The user's own data needs no evidence label."""
        if not self._loading and self.evidence.pop(name, None) is not None:
            self._show_tags()

    def _form(self) -> Guitar:
        guitar = Guitar(id=self.editing.id if self.editing else Guitar().id)
        for name, edit in self.inputs.items():
            setattr(guitar, name, edit.text().strip())
        guitar.evidence = {k: v for k, v in self.evidence.items() if getattr(guitar, k)}
        guitar.report = self.report
        guitar.image = self.image
        return guitar

    def _new(self) -> None:
        self.list.clearSelection()
        self._fill(Guitar())
        self.inputs["brand"].setFocus()

    def _save(self) -> Guitar | None:
        guitar = self._form()
        if not (guitar.brand or guitar.model):
            QMessageBox.warning(self, "Mis guitarras", "Escribe al menos la marca o el modelo.")
            return None
        self.store.put(guitar)
        if not self.store.active:
            self.store.use(guitar.id)
        self._reload(guitar.id)
        self.status.setText("Guardada.")
        return guitar

    def _use(self) -> None:
        guitar = self._save()
        if guitar is not None:
            self.store.use(guitar.id)
            self._reload(guitar.id)
            self.status.setText(f"Usando {html.escape(guitar.title)} como contexto de la IA.")

    def _delete(self) -> None:
        if self.editing is None or not self.store.get(self.editing.id):
            return
        answer = QMessageBox.question(self, "Borrar", f"¿Borrar {self.editing.title}?")
        if answer == QMessageBox.StandardButton.Yes:
            self.store.remove(self.editing.id)
            self._reload(self.store.active)
            if not self.store.guitars:
                self._new()

    # --- identify ---------------------------------------------------------------------

    def _identify(self) -> None:
        guitar = self._form()
        if not (guitar.brand and (guitar.model or guitar.serial)):
            QMessageBox.information(self, "Identificar", "Escribe la marca y el modelo o el "
                                    "número de serie.")
            return
        self.identify_button.setEnabled(False)
        self.status.setText("Buscando la ficha de esta guitarra… (puede tardar un minuto)")
        provider, model = self.provider, self.model

        def work() -> None:
            try:
                result: object = guitars.identify(guitar, provider, model)
                error = ""
            except Exception as exc:  # shown in the dialog
                result, error = None, str(exc)
            self._identified.done.emit(result, error)

        threading.Thread(target=work, name="ge150-guitar", daemon=True).start()

    def _identify_done(self, result: object, error: str) -> None:
        self.identify_button.setEnabled(True)
        if not isinstance(result, tuple):
            self.status.setText(f"No se pudo identificar: {html.escape(error)}")
            return
        guitar, confidence, why = result
        self._loading = True
        for name, edit in self.inputs.items():
            value = getattr(guitar, name)
            if value and not edit.text().strip():
                edit.setText(value)
                if isinstance(edit, QLineEdit):
                    edit.setCursorPosition(0)
                if name in guitar.evidence:
                    self.evidence[name] = guitar.evidence[name]
        self._loading = False
        self.report = why
        if guitar.image and not self.image:
            self._set_picture(guitar.image)
        self._show_tags()
        self._show_report(why)
        self.status.setText(f"<b>Confianza {html.escape(confidence)}.</b> "
                            "Revisa los datos y aprieta <b>Guardar</b>.")
