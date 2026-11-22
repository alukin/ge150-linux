"""Dark theme: Fusion style, palette and stylesheet."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#ff8a1f"
BG = "#15181d"
PANEL = "#1d2127"
RAISED = "#262b33"
BORDER = "#323843"
TEXT = "#e9edf2"
MUTED = "#8b95a3"

STYLE = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-size: 13px; }}
QMenuBar {{ background: {BG}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {RAISED}; }}
QMenu {{ background: {PANEL}; border: 1px solid {BORDER}; }}
QStatusBar {{ background: {BG}; color: {MUTED}; }}
QSplitter::handle {{ background: {BG}; }}

QFrame#headerBar {{ background: {PANEL}; border-bottom: 1px solid {BORDER}; }}
QLabel#presetNumber {{
    font-size: 28px; font-weight: 800; color: {ACCENT}; min-width: 64px;
}}
QLabel#presetName {{ font-size: 24px; font-weight: 700; }}
QLabel#dirtyBadge {{
    background: #5a3a12; color: #ffcf99; border-radius: 9px; padding: 2px 10px;
    font-size: 11px; font-weight: 700;
}}
QPushButton#saveButton {{
    background: {ACCENT}; color: #1a1208; font-weight: 800; border: none;
    border-radius: 8px; padding: 8px 18px;
}}
QPushButton#saveButton:disabled {{ background: {RAISED}; color: {MUTED}; }}

QPushButton#aiButton {{
    background: {RAISED}; color: {TEXT}; font-weight: 700; border: 1px solid {ACCENT};
    border-radius: 8px; padding: 8px 14px;
}}
QPushButton#aiButton:hover {{ background: #2d2620; }}
QPushButton#aiButton:checked {{ background: #3a2a1a; }}
QDockWidget#aiPanel {{ color: {MUTED}; font-weight: 700; }}
QDockWidget#aiPanel::title {{ background: {BG}; padding: 8px 10px; }}
QTextBrowser#aiChat {{ background: {PANEL}; border: none; border-radius: 10px; padding: 8px; }}
QPlainTextEdit#aiPrompt {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px;
}}
QFrame#modulePage {{ background: {PANEL}; border-radius: 14px; }}
QLabel#moduleTitle {{ font-size: 22px; font-weight: 800; letter-spacing: 1px; }}
QLabel#basedOn {{ color: {MUTED}; font-size: 12px; }}
QLabel#note, QLabel#paramName {{ color: {MUTED}; font-size: 11px; }}
QPushButton#bigPower {{
    border-radius: 15px; padding: 6px; font-weight: 800; border: 2px solid {BORDER};
    background: {RAISED}; color: {MUTED};
}}
QPushButton#bigPower:checked {{ background: #1f7a3a; border-color: #2fb35a; color: white; }}
QComboBox {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px;
}}
QListWidget#modelGallery {{ background: {BG}; border-radius: 12px; padding: 6px; }}
QListWidget#modelGallery::item {{
    color: {MUTED}; font-size: 11px; font-weight: 700; border-radius: 10px; padding: 4px;
    border: 2px solid transparent;
}}
QListWidget#modelGallery::item:hover {{ background: {RAISED}; color: {TEXT}; }}
QListWidget#modelGallery::item:selected {{
    background: #2d2620; border-color: {ACCENT}; color: {TEXT};
}}
QComboBox QAbstractItemView {{
    background: {PANEL}; border: 1px solid {BORDER}; selection-background-color: {ACCENT};
    selection-color: #1a1208;
}}

QFrame#chainBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; }}
QFrame#moduleTile {{
    background: {RAISED}; border: 2px solid transparent; border-radius: 12px;
}}
QFrame#moduleTile:hover {{ border-color: {BORDER}; }}
QFrame#moduleTile[selected="true"] {{ border-color: {ACCENT}; background: #2d2620; }}
QLabel#tileName {{ font-weight: 800; color: {MUTED}; font-size: 11px; letter-spacing: 1px; }}
QFrame#moduleTile[on="true"] QLabel#tileName {{ color: {TEXT}; }}
QLabel#modelLabel {{ font-size: 11px; }}
QLabel#modelLabel:disabled {{ color: {MUTED}; }}
QPushButton#power {{
    border-radius: 12px; border: 1px solid {BORDER}; background: {PANEL}; color: {MUTED};
    font-weight: 800;
}}
QPushButton#power:checked {{ background: #1f7a3a; border-color: #2fb35a; color: white; }}

QLineEdit {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px;
}}
QListWidget {{
    background: {PANEL}; border: none; border-radius: 10px; padding: 4px; outline: none;
}}
QListWidget::item {{ padding: 5px 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {ACCENT}; color: #1a1208; }}
QListWidget::item:hover:!selected {{ background: {RAISED}; }}
QGroupBox {{
    border: 1px solid {BORDER}; border-radius: 10px; margin-top: 14px; padding-top: 8px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: {MUTED}; }}
QPushButton {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 12px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QSpinBox, QDoubleSpinBox {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px;
}}
QProgressBar {{ background: {RAISED}; border: none; border-radius: 4px; height: 8px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG, QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: PANEL, QPalette.ColorRole.AlternateBase: RAISED,
        QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.Button: RAISED,
        QPalette.ColorRole.ButtonText: TEXT, QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#1a1208", QPalette.ColorRole.ToolTipBase: PANEL,
        QPalette.ColorRole.ToolTipText: TEXT, QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Mid: BORDER,
    }
    for role, colour in roles.items():
        palette.setColor(role, QColor(colour))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(MUTED))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(MUTED))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
