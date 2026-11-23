"""«Acerca de»: what the app is, who made it, where its data lives, what is installed and the
credits. «Copiar información» puts the system details on the clipboard for bug reports."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QSize, Qt, QUrl, qVersion
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ge150 import __version__
from ge150.model.device_state import DeviceState

REPO = "https://github.com/wh01s17/ge150-linux"
AUTHOR = "wh01s17"
AUTHOR_URL = "https://github.com/wh01s17"
LINKS = (("Repositorio", REPO, "El código, la documentación y las versiones"),
         ("Novedades", f"{REPO}/blob/main/CHANGELOG.md", "Qué cambió en cada versión"),
         ("Reportar un problema", f"{REPO}/issues/new",
          "Abre un issue en GitHub (pega ahí la información de «Tu sistema»)"))
LOGO = Path(__file__).resolve().parent.parent / "data" / "ge150.svg"


def _xdg(variable: str, default: str) -> Path:
    return Path(os.environ.get(variable) or str(Path.home() / default)) / "ge150"


def folders() -> list[tuple[str, Path, str]]:
    """(name, path, what is there) of the places the editor keeps things."""
    data = _xdg("XDG_DATA_HOME", ".local/share")
    return [("Configuración", _xdg("XDG_CONFIG_HOME", ".config"),
             "Guitarras, sesión de TONE3000 y ajustes"),
            ("Backups automáticos", data / "backups",
             "Copia completa de la pedalera antes de cada edición masiva (los últimos 20)"),
            ("Conversaciones con la IA", data / "chats", "El historial de ambos chats"),
            ("Datos del editor", data,
             "Fotos de guitarras, origen de las IR, informes de hw-check"),
            ("Caché", _xdg("XDG_CACHE_HOME", ".cache"),
             "IR descargadas de TONE3000 e imágenes; se puede borrar")]


def _link(text: str, url: str) -> str:
    return f"<a href='{url}' style='color:#ff8a1f; text-decoration:none'>{text}</a>"


def _label(html: str, note: bool = False) -> QLabel:
    label = QLabel(html)
    label.setWordWrap(True)
    label.setOpenExternalLinks(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    if note:
        label.setObjectName("note")
    return label


class AboutDialog(QDialog):
    def __init__(self, state: DeviceState, connection: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Acerca de GE150 Editor")
        self.setObjectName("aboutDialog")
        self.resize(660, 560)
        self.state, self.connection = state, connection
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 14)
        layout.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(QIcon(str(LOGO)).pixmap(QSize(72, 72)))
        head.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        title = QLabel("GE150 Editor")
        title.setObjectName("aboutTitle")
        version = QLabel(f"versión {__version__}")
        version.setObjectName("countBadge")
        version.setProperty("on", True)
        row = QHBoxLayout()
        row.addWidget(title)
        row.addWidget(version, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)
        texts.addLayout(row)
        texts.addWidget(_label("Editor libre para la pedalera <b>MOOER GE150</b> en Linux: "
                               "presets, efectos, IR de cabinas, TONE3000 y un asistente de "
                               "tono con IA."))
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        for text, url, tip in LINKS:
            button = QPushButton(text)
            button.setToolTip(tip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            buttons.addWidget(button)
        buttons.addStretch(1)
        texts.addLayout(buttons)
        head.addLayout(texts, 1)
        layout.addLayout(head)

        tabs = QTabWidget()
        tabs.setObjectName("aboutTabs")
        tabs.addTab(self._project(), "Proyecto")
        tabs.addTab(self._system(), "Tu sistema")
        tabs.addTab(self._data(), "Tus datos")
        tabs.addTab(self._credits(), "Créditos")
        layout.addWidget(tabs, 1)
        close = QDialogButtonBox()
        close.addButton("Cerrar", QDialogButtonBox.ButtonRole.RejectRole)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    # --- tabs -----------------------------------------------------------------------------

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        return page, layout

    def _project(self) -> QWidget:
        page, layout = self._page()
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.addRow("Creado por", _label(_link(AUTHOR, AUTHOR_URL)))
        form.addRow("Licencia", _label(f"{_link('MIT', f'{REPO}/blob/main/LICENSE')}: libre "
                                       "para usar, copiar y modificar"))
        form.addRow("Código", _label(_link(REPO.removeprefix("https://"), REPO)))
        form.addRow("Probado con", _label("MOOER GE150, firmware V1.3.8"))
        layout.addLayout(form)
        layout.addWidget(_label(
            "<b>Tus datos.</b> El editor no envía nada a ningún lado por su cuenta. Solo sale "
            "información de tu equipo cuando usas la IA (va a Claude o a ChatGPT con tu cuenta) "
            "o TONE3000 (con tu cuenta de TONE3000).", note=True))
        layout.addWidget(_label(
            "<b>Cuida tu pedalera.</b> Antes de cambios grandes conviene un backup completo "
            "(<i>Archivo → Backup completo</i>). La edición masiva hace uno automático.",
            note=True))
        layout.addWidget(_label(
            "Proyecto independiente: no está afiliado ni respaldado por MOOER. MOOER y GE150 son "
            "marcas de sus dueños. El protocolo USB se obtuvo por ingeniería inversa del editor "
            "oficial, que no se incluye ni se distribuye.", note=True))
        layout.addStretch(1)
        return page

    def system_info(self) -> list[tuple[str, str]]:
        info = self.state.info
        pedal = f"{info.name} {info.firmware}" if info else "sin conectar"
        agents = ", ".join(n for n in ("claude", "codex") if shutil.which(n)) or "ninguno"
        try:
            from ge150.services.tone3000 import TokenStore

            t3k = "conectada" if TokenStore().load().signed_in else "sin conectar"
        except Exception:  # never break the dialog
            t3k = "?"
        return [("Editor", __version__), ("Pedalera", pedal),
                ("Conexión", self.connection or "—"),
                ("Asistente IA", f"{agents} (en el PATH)"), ("Cuenta TONE3000", t3k),
                ("Python", platform.python_version()),
                ("Qt / PySide6", f"{qVersion()} / {pyside_version}"),
                ("Sistema", f"{platform.system()} {platform.release()} ({platform.machine()})"),
                ("Escritorio", os.environ.get("XDG_CURRENT_DESKTOP", "—")
                 + f" · {QGuiApplication.platformName()}")]

    def _system(self) -> QWidget:
        page, layout = self._page()
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(6)
        for name, value in self.system_info():
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(name, value_label)
        layout.addLayout(form)
        layout.addStretch(1)
        copy = QPushButton("Copiar información")
        copy.setObjectName("aiButton")
        copy.setToolTip("Para pegarla al reportar un problema")
        copy.clicked.connect(lambda: self._copy(copy))
        layout.addWidget(copy, 0, Qt.AlignmentFlag.AlignLeft)
        return page

    def report_text(self) -> str:
        lines = [f"- {name}: {value}" for name, value in self.system_info()]
        return "GE150 Editor\n" + "\n".join(lines) + f"\n- Python: {sys.executable}"

    def _copy(self, button: QPushButton) -> None:
        QGuiApplication.clipboard().setText(self.report_text())
        button.setText("Copiada ✓")

    def _data(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(_label("Dónde guarda el editor lo tuyo. Nada de esto se sube a ningún "
                                "lado.", note=True))
        for name, path, what in folders():
            row = QHBoxLayout()
            text = _label(f"<b>{name}</b><br><span style='color:#8b95a3'>{what}</span><br>"
                          f"<code>{path}</code>")
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(text, 1)
            button = QPushButton("Abrir")
            button.setEnabled(path.exists())
            button.setToolTip(str(path) if path.exists() else "Todavía no existe")
            button.clicked.connect(
                lambda _=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))))
            row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _credits(self) -> QWidget:
        page, layout = self._page()
        items = (
            ("Fotos de los equipos", "Wikimedia Commons y páginas de los fabricantes, de sus "
             "autores y con su licencia: "
             + _link("ver créditos", f"{REPO}/blob/main/src/ge150/data/photos/CREDITS.md")),
            ("IR de TONE3000", "De sus autores, con la licencia de cada una (se muestra al "
             "cargarlas). " + _link("tone3000.com", "https://www.tone3000.com")),
            ("Íconos", _link("Lucide", "https://lucide.dev") + " (licencia ISC)"),
            ("Asistente de tono", _link("Claude Code", "https://claude.com/claude-code") + " y "
             + _link("Codex", "https://github.com/openai/codex") + ", con tu suscripción"),
            ("Hecho con", "Python, " + _link("Qt / PySide6", "https://doc.qt.io/qtforpython-6/")
             + " y el SDK de " + _link("MCP", "https://modelcontextprotocol.io")),
        )
        for title, text in items:
            layout.addWidget(_label(f"<b>{title}</b><br>{text}"))
        layout.addStretch(1)
        return page
