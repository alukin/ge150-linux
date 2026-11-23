"""Main window: preset list, signal chain, module editor, menus and status bar."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ge150.formats import mbf, mo_json
from ge150.model import device_state as ds
from ge150.model.preset import NAME_LEN, is_valid_name
from ge150.protocol.session import DeviceSession
from ge150.services import backup as backup_service
from ge150.services import reader
from ge150.services.editor import Editor
from ge150.ui.ai_host import LABELS, AiHost
from ge150.ui.ai_panel import AIPanel
from ge150.ui.assistant_page import AssistantPage
from ge150.ui.bridge import StateBridge
from ge150.ui.chain_view import ChainView
from ge150.ui.dialogs import ExpDialog, IrDialog
from ge150.ui.module_editor import ModuleEditor
from ge150.ui.preset_list import PresetList
from ge150.ui.settings_dialog import SettingsDialog
from ge150.ui.tone3000_page import Tone3000Page
from ge150.ui.worker import TaskRunner


class MainWindow(QMainWindow):
    def __init__(self, editor: Editor, session: DeviceSession) -> None:
        super().__init__()
        self.editor, self.session = editor, session
        self.state = editor.state
        self.runner = TaskRunner(self)
        self.bridge = StateBridge(self.state, session, self)
        self.ai_host = AiHost(editor, self.runner, self)
        self.ai_host.called.connect(
            lambda tool: self.statusBar().showMessage(f"IA: {LABELS.get(tool, tool)}", 4000))
        self.setWindowTitle("GE150 Editor")
        self.resize(1280, 820)

        self.presets = PresetList(self.state)
        self.presets.setMinimumWidth(230)
        self.header = QLabel("Conectando…")  # full text, kept for status and tests
        self.header.hide()
        self.number = QLabel("-")
        self.number.setObjectName("presetNumber")
        self.name = QLabel("Conectando…")
        self.name.setObjectName("presetName")
        self.dirty_badge = QLabel("MODIFICADO")
        self.dirty_badge.setObjectName("dirtyBadge")
        self.dirty_badge.hide()
        self.save_button = QPushButton("Guardar")
        self.save_button.setObjectName("saveButton")
        self.save_button.setToolTip("Guardar el preset en su ranura (Ctrl+S)")
        self.save_button.clicked.connect(self.save_current)
        header_bar = QFrame()
        header_bar.setObjectName("headerBar")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(18, 10, 18, 10)
        self.logo = QLabel()
        self.logo.setObjectName("appLogo")
        logo_file = resources.files("ge150.data").joinpath("ge150.svg")
        self.logo.setPixmap(QIcon(str(logo_file)).pixmap(QSize(40, 40), self.devicePixelRatioF()))
        self.logo.setToolTip("GE150 Editor")
        header_layout.addWidget(self.logo)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.number)
        header_layout.addWidget(self.name)
        header_layout.addSpacing(14)
        header_layout.addWidget(self.dirty_badge)
        header_layout.addStretch(1)
        header_layout.addWidget(self.header)
        self.ai_button = QPushButton("✦ IA")
        self.ai_button.setObjectName("aiButton")
        self.ai_button.setCheckable(True)
        self.ai_button.setToolTip("Asistente de tono con IA (Ctrl+K)")
        header_layout.addWidget(self.ai_button)
        header_layout.addWidget(self.save_button)

        self.chain = ChainView(editor)
        self.module_editor = ModuleEditor(editor)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.presets)
        splitter.addWidget(self.module_editor)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1020])
        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(12, 12, 12, 12)
        middle_layout.addWidget(splitter)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(header_bar)
        effects = QWidget()
        effects_layout = QVBoxLayout(effects)
        effects_layout.setContentsMargins(0, 0, 0, 0)
        effects_layout.setSpacing(0)
        effects_layout.addWidget(middle, 1)
        effects_layout.addWidget(self.chain)
        self.tone3000 = Tone3000Page(editor, self.runner)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(effects, "Efectos")
        self.tabs.addTab(self.tone3000, "TONE3000")
        self.assistant = AssistantPage(editor, self.runner, self.ai_host)
        self.tabs.addTab(self.assistant, "Asistente")
        self.ai_host.proposed.connect(self._proposed)
        central_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self.central = central

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.hide()
        self.status_label = QLabel()
        self.statusBar().addPermanentWidget(self.status_label)
        self.statusBar().addPermanentWidget(self.progress)

        self.ai_panel = AIPanel(self.ai_host, self)
        self.ai_panel.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea
                                      | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ai_panel)
        self.ai_panel.hide()
        self.ai_button.toggled.connect(self.ai_panel.setVisible)
        self.ai_panel.visibilityChanged.connect(self.ai_button.setChecked)
        toggle = QAction(self)
        toggle.setShortcut(QKeySequence("Ctrl+K"))
        toggle.triggered.connect(self.ai_button.toggle)
        self.addAction(toggle)

        self._build_menus()
        self.presets.activated.connect(self.load_preset)
        self.presets.action_requested.connect(self._preset_action)
        self.chain.module_selected.connect(self.module_editor.show_module)
        self.chain.error.connect(self._error)
        self.module_editor.error.connect(self._error)
        self.bridge.changed.connect(self._on_change)
        self.bridge.disconnected.connect(self._on_disconnect)
        self.bridge.progress.connect(self._on_progress)
        self.runner.busy_changed.connect(lambda busy: self.progress.setVisible(busy))
        self.central.setEnabled(False)

    # --- menus ---------------------------------------------------------------

    def _action(self, menu_name: str, text: str, slot, shortcut: str | None = None) -> QAction:  # type: ignore[no-untyped-def]
        menu = self._menus.get(menu_name) or self.menuBar().addMenu(menu_name)
        self._menus[menu_name] = menu
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_menus(self) -> None:
        self._menus: dict[str, Any] = {}
        self._action("&Archivo", "Importar .mo al preset seleccionado…", self.import_mo, "Ctrl+I")
        self._action("&Archivo", "Exportar preset seleccionado…", self.export_mo, "Ctrl+E")
        self._action("&Archivo", "Exportar los 200 presets…", self.export_all)
        self._action("&Archivo", "Guardar snapshot JSON…", self.save_snapshot)
        self._action("&Archivo", "Backup completo (.mbf)…", self.backup)
        self._action("&Archivo", "Restaurar backup (.mbf)…", self.restore)
        self._action("&Archivo", "Abrir carpeta de backups automáticos",
                     self.open_auto_backups)
        self._action("&Archivo", "Salir", self.close, "Ctrl+Q")
        self._action("&Preset", "Guardar", self.save_current, "Ctrl+S")
        self._action("&Preset", "Guardar en otra ranura…", self.save_as, "Ctrl+Shift+S")
        self._action("&Preset", "Renombrar…", lambda: self.rename(self.state.current_slot), "F2")
        self._action("&Preset", "Descartar cambios", self.discard)
        self._action("&Herramientas", "IR de usuario…", self.open_ir)
        self._action("&Herramientas", "Pedal de expresión…", self.open_exp)
        self._action("&Herramientas", "Sistema y caja de ritmos…", self.open_settings)
        self._action("&Herramientas", "Mis guitarras…", lambda: self.ai_panel.manage_guitars())
        self._action("&Herramientas", "Restaurar valores de fábrica…", self.factory_reset)
        self._action("&Herramientas", "Volver a leer la pedalera", self.start_sync, "F5")
        self._action("Ay&uda", "Acerca de", self.about)

    def _proposed(self, edits: object, summary: str) -> None:
        """The AI proposes changes to stored presets: review them in «Asistente»."""
        self.assistant.show_proposal(list(edits), summary)  # type: ignore[call-overload]
        self.tabs.setCurrentWidget(self.assistant)

    # --- sync ------------------------------------------------------------------

    def start_sync(self) -> None:
        self.statusBar().showMessage("Leyendo la pedalera…")
        self.central.setEnabled(False)
        self.runner.run(self.editor.sync, self._synced, self._error)

    def _synced(self, _: object) -> None:
        info = self.state.info
        version = f"{info.name} {info.firmware}" if info else "?"
        self.status_label.setText(f"{version}  ·  {self.session.transport.description}")
        self.statusBar().showMessage("Listo", 3000)
        self.central.setEnabled(True)
        self.presets.reload()
        self.assistant.reload_presets()
        self._refresh_current()
        self.module_editor.show_module(self.chain.selected)
        self.ai_host.start()
        self.ai_panel.refresh_context()
        self.assistant.chat.refresh_context()

    # --- state changes (GUI thread) ------------------------------------------

    def _on_change(self, kind: str, slot: int, module: int) -> None:
        if kind == ds.KIND_PRESETS:
            self.presets.reload()
            self.assistant.reload_presets()
        elif kind == ds.KIND_PRESET:
            self.presets.update_slot(slot)
            self.assistant.update_slot(slot)
            self.ai_panel.refresh_context()
            self.assistant.chat.refresh_context()
        elif kind in (ds.KIND_CURRENT, ds.KIND_SELECTED):
            self._refresh_current()
            self.ai_panel.refresh_context()
            self.assistant.chat.refresh_context()
            self.assistant.current_changed()
        elif kind == ds.KIND_USER_NAMES:
            self.chain.refresh()
            self.module_editor.show_module(self.module_editor.index)
        elif kind in (ds.KIND_MODULE, ds.KIND_EXP):
            self.chain.refresh()
            if module in (-1, self.module_editor.index):
                self.module_editor.refresh()
            self._refresh_header()
            if self.state.current_slot:
                self.presets.update_slot(self.state.current_slot)

    def _refresh_current(self) -> None:
        self.chain.refresh()
        self.module_editor.refresh()
        self.presets.mark_current()
        self._refresh_header()

    def _refresh_header(self) -> None:
        slot = self.state.current_slot
        stored = self.state.presets.get(slot or 0)
        name = stored.name if stored else ""
        mark = "   (modificado)" if self.state.dirty else ""
        self.header.setText(f"{slot or '-':>3}  {name}{mark}")
        self.number.setText(f"{slot:03d}" if slot else "-")
        self.name.setText(name.strip() or "-")
        self.dirty_badge.setVisible(self.state.dirty)

    def _on_disconnect(self, reason: str) -> None:
        self.central.setEnabled(False)
        self.status_label.setText("Desconectada")
        QMessageBox.warning(self, "Pedalera desconectada",
                            f"Se perdió la conexión con la GE150:\n{reason}\n\n"
                            "Vuelve a conectarla y reinicia el editor.")

    def _error(self, message: str) -> None:
        self.statusBar().showMessage(f"Error: {message}", 8000)
        QMessageBox.warning(self, "Error", message)

    # --- preset actions ------------------------------------------------------

    def _confirm(self, text: str) -> bool:
        answer = QMessageBox.question(self, "Confirmar", text)
        return answer == QMessageBox.StandardButton.Yes

    def _resolve_dirty(self) -> bool:
        """Ask what to do with unsaved edits. False = cancel the operation."""
        if not self.state.dirty:
            return True
        answer = QMessageBox.question(
            self, "Cambios sin guardar",
            "El preset actual tiene cambios sin guardar. ¿Guardarlos antes de continuar?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            self.editor.save()
        return True

    def load_preset(self, slot: int) -> None:
        if slot == self.state.current_slot:
            return
        if not self._resolve_dirty():
            self.presets.select_slot(self.state.current_slot)  # cancelled: stay on it
            return
        self.runner.run(lambda: self.editor.select(slot), None, self._error)

    def save_current(self) -> None:
        slot = self.state.current_slot
        stored = self.state.presets.get(slot or 0)
        if slot and self._confirm(f"¿Guardar los cambios en el preset {slot} "
                                  f"({stored.name if stored else ''})?"):
            self.runner.run(self.editor.save, lambda _: self._refresh_header(), self._error)

    def save_as(self) -> None:
        slot, ok = QInputDialog.getInt(self, "Guardar en", "Ranura de destino (1-200):",
                                       self.presets.selected_slot() or 1, 1, 200)
        if not ok:
            return
        current = self.state.presets.get(self.state.current_slot or 0)
        name, ok = QInputDialog.getText(self, "Nombre", "Nombre del preset:",
                                        text=current.name if current else "")
        if not ok or not self._valid_name(name):
            return
        target = self.state.presets.get(slot)
        if self._confirm(f"¿Sobrescribir el preset {slot} ({target.name if target else ''})?"):
            self.runner.run(lambda: self.editor.save(slot, name), None, self._error)

    def _valid_name(self, name: str) -> bool:
        if is_valid_name(name):
            return True
        QMessageBox.warning(self, "Nombre no válido",
                            f"Hasta {NAME_LEN} caracteres: letras, números, '-' y espacio.")
        return False

    def rename(self, slot: int | None) -> None:
        stored = self.state.presets.get(slot or 0)
        if stored is None:
            return
        name, ok = QInputDialog.getText(self, "Renombrar", f"Nuevo nombre del preset {slot}:",
                                        text=stored.name)
        if ok and name != stored.name and self._valid_name(name):
            self.runner.run(lambda: self.editor.rename(stored.slot, name), None, self._error)

    def discard(self) -> None:
        slot = self.state.current_slot
        if slot and self.state.dirty and self._confirm("¿Descartar los cambios sin guardar?"):
            self.runner.run(lambda: self.editor.select(slot), None, self._error)

    def _preset_action(self, action: str, slot: int) -> None:
        if action == "rename":
            self.rename(slot)
        elif action == "copy":
            self.presets.clipboard = slot
            self.statusBar().showMessage(f"Preset {slot} copiado", 3000)
        elif action == "paste" and self.presets.clipboard is not None:
            source = self.presets.clipboard
            target = self.state.presets.get(slot)
            if self._confirm(f"¿Sobrescribir el preset {slot} ({target.name if target else ''}) "
                             f"con el {source}?"):
                self.runner.run(lambda: self.editor.copy_preset(source, slot), None, self._error)
        elif action == "export":
            self.export_mo(slot)
        elif action == "import":
            self.import_mo(slot)

    # --- files ---------------------------------------------------------------

    def export_mo(self, slot: int | None = None) -> None:
        slot = slot or self.presets.selected_slot() or self.state.current_slot
        preset = self.state.presets.get(slot or 0)
        if preset is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar preset", f"{preset.name}.mo",
                                              "Preset GE150 (*.mo)")
        if path:
            mo_json.save(path, preset)
            self.statusBar().showMessage(f"Exportado {path}", 4000)

    def export_all(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if not directory:
            return
        for slot, preset in sorted(self.state.presets.items()):
            clean = "".join(c if c.isalnum() or c in " -_" else "_" for c in preset.name).strip()
            mo_json.save(Path(directory) / f"{slot:03d} {clean or 'unnamed'}.mo", preset)
        self.statusBar().showMessage(f"{len(self.state.presets)} presets exportados", 4000)

    def import_mo(self, slot: int | None = None) -> None:
        slot = slot or self.presets.selected_slot()
        base = self.state.presets.get(slot or 0)
        if base is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Importar preset", "", "Preset GE150 (*.mo)")
        if not path:
            return
        try:
            preset = mo_json.load(path, base)
        except (OSError, mo_json.MoError) as exc:
            self._error(str(exc))
            return
        if self._confirm(f"¿Sobrescribir el preset {base.slot} ({base.name}) con «{preset.name}»?"):
            self.runner.run(lambda: self.editor.copy_preset_data(preset), None, self._error)

    def save_snapshot(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Guardar snapshot", "ge150_snapshot.json",
                                              "JSON (*.json)")
        if not path:
            return

        def done(data: object) -> None:
            Path(path).write_text(json.dumps(data, indent=1) + "\n")
            self.statusBar().showMessage(f"Snapshot guardado en {path}", 4000)

        self.runner.run(lambda: reader.snapshot(self.session), done, self._error)

    def _progress(self, label: str, step: int, total: int) -> None:
        # Called from the worker thread: only touch Qt through queued signals.
        self.bridge.progress.emit(label, step, total)

    def backup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Backup completo", "GE150.mbf",
                                              "Backup GE150 (*.mbf)")
        if not path:
            return

        def done(result: object) -> None:
            assert isinstance(result, mbf.Backup)
            mbf.save(path, result)
            self.statusBar().showMessage(
                f"Backup guardado: {len(result.presets)} presets, {len(result.irs)} IR", 6000)

        self.runner.run(lambda: backup_service.create_backup(self.editor, self._progress),
                        done, self._error)

    def open_auto_backups(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from ge150.services.auto_backup import backup_dir

        directory = backup_dir()
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def restore(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Restaurar backup", "", "Backup GE150 (*.mbf)")
        if not path:
            return
        try:
            data = mbf.load(path)
        except (OSError, mbf.MbfError) as exc:
            self._error(str(exc))
            return
        if not self._confirm(f"Se SOBRESCRIBIRÁN los 200 presets y {len(data.irs)} IR de la "
                             "pedalera con el backup. ¿Continuar?"):
            return
        self.runner.run(lambda: backup_service.restore_backup(self.editor, data, self._progress),
                        lambda _: self.start_sync(), self._error)

    def factory_reset(self) -> None:
        """DESTRUCTIVE, with two confirmations and an optional backup first."""
        box = QMessageBox(QMessageBox.Icon.Warning, "Restaurar valores de fábrica",
                          "Se BORRARÁN los 200 presets, las IR y capturas NR de usuario y los "
                          "ajustes de sistema: la pedalera vuelve a como salió de fábrica.\n\n"
                          "Se recomienda hacer antes un backup completo.", parent=self)
        with_backup = box.addButton("Hacer backup y continuar…",
                                    QMessageBox.ButtonRole.AcceptRole)
        without = box.addButton("Continuar sin backup", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() not in (with_backup, without):
            return
        path = ""
        if box.clickedButton() is with_backup:
            path, _ = QFileDialog.getSaveFileName(self, "Backup antes del reset", "GE150.mbf",
                                                  "Backup GE150 (*.mbf)")
            if not path:
                return
        phrase = "BORRAR TODO"
        text, ok = QInputDialog.getText(self, "Confirmar reset de fábrica",
                                        f"Escribe «{phrase}» para restaurar la pedalera:")
        if not ok or text.strip() != phrase:
            return

        def task() -> None:
            if path:
                mbf.save(path, backup_service.create_backup(self.editor, self._progress))
            backup_service.factory_reset(self.editor)

        self.central.setEnabled(False)
        self.statusBar().showMessage("Restaurando valores de fábrica…")
        self.runner.run(task, self._synced, self._error)

    def _on_progress(self, label: str, step: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(step)
        self.statusBar().showMessage(label)

    # --- tools -----------------------------------------------------------------

    def open_ir(self) -> None:
        IrDialog(self.editor, self.runner, self).exec()

    def open_exp(self) -> None:
        if self.state.edit is not None:
            ExpDialog(self.editor, self).exec()

    def open_settings(self) -> None:
        SettingsDialog(self.editor, self).exec()

    def about(self) -> None:
        from ge150.ui.about_dialog import AboutDialog

        connection = self.session.transport.description if self.state.info else ""
        AboutDialog(self.state, connection, self).exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        from ge150.services import tone_agent

        tone_agent.stop_all()
        self.ai_host.stop()
        self.runner.wait(5000)
        self.bridge.detach()
        super().closeEvent(event)
