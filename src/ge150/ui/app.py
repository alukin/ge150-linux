"""``ge150`` entry point: open the pedal (or the simulator) and show the editor."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from importlib import resources

from PySide6.QtCore import QLoggingCategory
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from ge150.protocol.session import DeviceSession
from ge150.services.editor import Editor
from ge150.ui.main_window import MainWindow
from ge150.ui.theme import apply_theme
from ge150.usb import open_transport
from ge150.usb.transport import Transport, TransportError


def _transport(args: argparse.Namespace) -> Transport:
    if args.sim:
        from ge150.sim.sim_transport import SimTransport

        return SimTransport()
    return open_transport(args.backend, args.device)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ge150", description="GE150 graphical editor")
    parser.add_argument("--sim", action="store_true", help="use the built-in simulator")
    parser.add_argument("--backend", choices=("auto", "hidraw", "usb"), default="auto")
    parser.add_argument("--device", help="hidraw node, e.g. /dev/hidraw4")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    # Before the QApplication exists: Qt registers the app ID with the desktop portal at
    # start-up, and setting it later makes a second registration that the portal rejects.
    QApplication.setApplicationName("GE150 Editor")
    QApplication.setDesktopFileName("ge150")
    if "QT_LOGGING_RULES" not in os.environ:
        # Harmless Qt Wayland bug when the focus moves between text fields.
        QLoggingCategory.setFilterRules("qt.qpa.wayland.textinput.warning=false")
    app = QApplication(sys.argv[:1])
    apply_theme(app)
    icon = resources.files("ge150.data").joinpath("ge150.svg")
    app.setWindowIcon(QIcon(str(icon)))
    try:
        session = DeviceSession(_transport(args)).start()
    except TransportError as exc:
        QMessageBox.critical(None, "GE150 no disponible",
                             f"No se pudo abrir la pedalera:\n{exc}\n\n"
                             "Prueba «ge150 --sim» para usar el simulador.")
        return 1
    window = MainWindow(Editor(session), session)
    window.show()
    window.start_sync()
    try:
        return app.exec()
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
