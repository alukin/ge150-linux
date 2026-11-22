"""Secondary dialogs: user IR slots and expression-pedal settings."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ge150.formats import wav_ir
from ge150.model.preset import EXP_KEYS
from ge150.protocol import messages as msg
from ge150.protocol.opcodes import Op
from ge150.services.editor import Editor
from ge150.services.tone3000 import Download, IrSources, Tone3000Client
from ge150.ui.worker import TaskRunner


class _Fetched(QObject):
    done = Signal(object, str)  # Download or None, error


class IrDialog(QDialog):
    """List the 10 user IR slots; upload a WAV, delete a slot or export all to WAV."""

    def __init__(self, editor: Editor, runner: TaskRunner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor, self.runner = editor, runner
        self.setWindowTitle("IR de usuario (CAB 27-36)")
        self.resize(560, 380)
        self.sources = IrSources()
        self._fetched = _Fetched(self)
        self._fetched.done.connect(self._tone3000_ready)
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        self.upload = QPushButton("Cargar WAV…")
        self.tone3000 = QPushButton("TONE3000…")
        self.tone3000.setToolTip("Elegir una IR en el catálogo de TONE3000 y cargarla en la ranura")
        self.delete = QPushButton("Borrar")
        self.export = QPushButton("Exportar todos…")
        for b in (self.upload, self.tone3000, self.delete, self.export):
            buttons.addWidget(b)
        layout.addLayout(buttons)
        self.status = QLabel()
        layout.addWidget(self.status)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.upload.clicked.connect(self._upload)
        self.tone3000.clicked.connect(self._from_tone3000)
        self.delete.clicked.connect(self._delete)
        self.export.clicked.connect(self._export)
        runner.busy_changed.connect(self._busy)
        self.refresh()

    def refresh(self) -> None:
        names = self.editor.state.user_names
        sources = self.sources.load()
        self.list.clear()
        for i in range(msg.USER_SLOTS):
            name = names.ir[i] if names else "?"
            text = f"IR {i + 1:2d}  (CAB {27 + i})   {name}"
            source = sources.get(str(i + 1))
            if source and source.get("title", "")[: msg.USER_NAME_LEN] == name:
                text += f"   · TONE3000: {source['author']} ({source['license']})"
            self.list.addItem(text)
            if source:
                self.list.item(i).setToolTip(f"{source['title']} / {source['model']}\n"
                                             f"{source['author']} · {source['license']}\n"
                                             f"{source['url']}")
        if self.list.count():
            self.list.setCurrentRow(0)

    def _busy(self, busy: bool) -> None:
        for b in (self.upload, self.tone3000, self.delete, self.export):
            b.setEnabled(not busy)
        self.status.setText("Trabajando…" if busy else "")

    def _slot(self) -> int:
        return max(0, self.list.currentRow())

    def _failed(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _upload(self) -> None:
        slot = self._slot()
        path, _ = QFileDialog.getOpenFileName(self, "Elegir IR", "", "WAV (*.wav)")
        if not path:
            return
        try:
            payload = wav_ir.load_ir_file(path)
        except (OSError, wav_ir.WavError) as exc:
            self._failed(str(exc))
            return
        name = Path(path).stem[: msg.USER_NAME_LEN]
        answer = QMessageBox.question(self, "Confirmar",
                                      f"¿Reemplazar la ranura IR {slot + 1} por «{name}»?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.runner.run(lambda: self.editor.upload_user_slot(Op.USER_IR, slot, name, payload),
                        lambda _: self.refresh(), self._failed)

    def _delete(self) -> None:
        slot = self._slot()
        answer = QMessageBox.question(self, "Confirmar", f"¿Borrar la ranura IR {slot + 1}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        def deleted(_: object) -> None:
            self.sources.forget(slot + 1)
            self.refresh()

        self.runner.run(lambda: self.editor.delete_user_slot(Op.USER_IR, slot), deleted,
                        self._failed)

    def _from_tone3000(self) -> None:
        """Pick in the TONE3000 catalogue (browser), download, confirm, store."""
        client = Tone3000Client()
        if not client.creds.client_id:
            key, ok = QInputDialog.getText(
                self, "TONE3000", "Clave publicable (Publishable Key, t3k_pub_…) de los "
                "ajustes de API de tu cuenta de TONE3000:")
            if not ok or not key.strip():
                return
            client.set_client_id(key)
        self.tone3000.setEnabled(False)
        self.status.setText("Elige una IR en TONE3000 (se abrió el navegador)…")

        def work() -> None:  # not on the pedal's runner: the user may take minutes
            try:
                download: object = client.download(client.select_tone())
                error = ""
            except Exception as exc:  # shown in a dialog
                download, error = None, str(exc)
            self._fetched.done.emit(download, error)

        threading.Thread(target=work, name="ge150-tone3000", daemon=True).start()

    def _tone3000_ready(self, download: object, error: str) -> None:
        self.tone3000.setEnabled(True)
        self.status.setText("")
        if not isinstance(download, Download):
            self._failed(f"TONE3000: {error}")
            return
        try:
            payload = wav_ir.load_ir_file(download.path)
        except (OSError, wav_ir.WavError) as exc:
            self._failed(str(exc))
            return
        slot, tone = self._slot(), download.tone
        name = tone.title[: msg.USER_NAME_LEN]
        answer = QMessageBox.question(
            self, "Confirmar", f"¿Cargar «{tone.title} / {download.model.name}» en la ranura IR "
            f"{slot + 1}?\n\nAutor: {tone.author}\nLicencia: {tone.license}\n{tone.page_url}")
        if answer != QMessageBox.StandardButton.Yes:
            return

        def stored(_: object) -> None:
            self.sources.record(slot + 1, download)
            self.refresh()

        self.runner.run(lambda: self.editor.upload_user_slot(Op.USER_IR, slot, name, payload),
                        stored, self._failed)

    def _export(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if not directory:
            return

        def done(chunks: list[msg.BackupChunk]) -> None:
            for chunk in chunks:
                clean = "".join(c if c.isalnum() or c in " -_" else "_" for c in chunk.name)
                path = Path(directory) / f"IR{(chunk.slot or 0) + 1:02d} {clean.strip()}.wav"
                path.write_bytes(wav_ir.ir_to_wav(wav_ir.unpack_planar(chunk.data)))
            self.status.setText(f"{len(chunks)} IR exportados a {directory}")

        self.runner.run(self.editor.read_ir_backup, done, self._failed)


class ExpDialog(QDialog):
    """Raw expression-pedal words of the current preset (meaning partly unknown)."""

    def __init__(self, editor: Editor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Pedal de expresión (preset actual)")
        layout = QFormLayout(self)
        self.spins: dict[str, QSpinBox] = {}
        exp = editor.state.edit.exp if editor.state.edit else {}
        for key in EXP_KEYS:
            spin = QSpinBox()
            spin.setRange(0, 0xFFFF)
            spin.setValue(exp.get(key, 0))
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda v, k=key: self.editor.set_exp(k, v))
            self.spins[key] = spin
            layout.addRow(key, spin)
        info = QLabel("Valores crudos. Se envían en vivo; guarda el preset para conservarlos.")
        info.setWordWrap(True)
        layout.addRow(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
