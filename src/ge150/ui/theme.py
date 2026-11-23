"""Dark theme: Fusion style, palette and stylesheet."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#ff8a1f"
BG = "#15181d"
PANEL = "#1d2127"
RAISED = "#262b33"
BORDER = "#323843"
TEXT = "#e9edf2"
MUTED = "#8b95a3"
#: Down arrow of the combo boxes (QSS only takes an image file).
CHEVRON = str(Path(__file__).resolve().parent.parent / "data" / "chevron-down.svg").replace(
    "\\", "/")

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
QPushButton#aiButton:disabled {{ color: {MUTED}; border-color: #8a5a2e; }}
QFrame#composer {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px;
}}
QFrame#composer[focused="true"] {{ border-color: {ACCENT}; }}
QPlainTextEdit#aiPrompt {{ background: transparent; border: none; padding: 2px; }}
QPushButton#contextChip {{
    background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 4px 8px; font-size: 12px; text-align: left;
}}
QPushButton#contextChip:!checked {{
    background: transparent; color: {MUTED}; border-style: dashed;
}}
QPushButton#contextChip:hover {{ border-color: {ACCENT}; }}
QToolButton#guitarChip {{
    background: transparent; color: {MUTED}; border: 1px dashed {BORDER}; border-radius: 6px;
    padding: 4px 8px; font-size: 12px;
}}
QToolButton#guitarChip[on="true"] {{ background: {RAISED}; color: {TEXT}; border-style: solid; }}
QToolButton#guitarChip:hover {{ border-color: {ACCENT}; }}
QToolButton#guitarChip::menu-indicator {{ image: none; width: 0; }}
QToolButton#pill {{
    background: transparent; color: {MUTED}; border: 1px solid {BORDER}; border-radius: 11px;
    padding: 2px 9px; font-size: 12px; min-height: 18px;
}}
QToolButton#pill:hover, QToolButton#pill:open {{
    color: {TEXT}; border-color: #8a5a2e; background: #2a2119;
}}
QToolButton#pill::menu-indicator {{ image: none; width: 0; }}
QToolButton#pill:disabled {{ color: #4d5562; }}
QToolButton#pill:checked {{ color: {TEXT}; border-color: #8a5a2e; }}
QMenu#pillMenu {{ padding: 4px; border-top: 2px solid {ACCENT}; border-radius: 8px; }}
QMenu#pillMenu::item {{ padding: 5px 22px 5px 10px; border-radius: 5px; }}
QToolButton#sendButton {{
    background: {ACCENT}; color: #1b1205; border: none; border-radius: 14px;
    min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
    font-size: 15px; font-weight: 800;
}}
QToolButton#sendButton:hover {{ background: #ffa04d; }}
QToolButton#sendButton:disabled {{ background: {RAISED}; color: {MUTED}; }}
QToolButton#sendButton[busy="true"] {{
    background: #3a2a1a; color: {ACCENT}; border: 2px solid {ACCENT}; font-size: 11px;
}}
QFrame#soundCompare {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QPushButton#abButton {{
    background: transparent; color: {MUTED}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 6px 10px; font-weight: 700;
}}
QPushButton#abButton:hover {{ color: {TEXT}; border-color: #8a5a2e; }}
QPushButton#abButton:checked {{ background: {ACCENT}; color: #1b1205; border-color: {ACCENT}; }}
QDockWidget#aiPanel {{ color: {MUTED}; font-weight: 700; }}
QDockWidget#aiPanel::title {{ background: {BG}; padding: 8px 10px; }}
QTextBrowser#aiChat {{ background: {PANEL}; border: none; border-radius: 10px; padding: 8px; }}
QTabWidget#mainTabs::pane {{ border: none; }}
QTabWidget#mainTabs > QTabBar {{ background: {BG}; }}
QTabWidget#mainTabs > QTabBar::tab {{
    background: transparent; color: {MUTED}; font-weight: 700; padding: 10px 22px;
    border: none; border-bottom: 2px solid transparent;
}}
QTabWidget#mainTabs > QTabBar::tab:selected {{ color: {TEXT}; border-bottom-color: {ACCENT}; }}
QTabWidget#mainTabs > QTabBar::tab:hover {{ color: {TEXT}; }}
QLabel#toneImage {{ background: {BG}; border-radius: 10px; color: {MUTED}; }}
QLabel#licenceChip {{
    background: {RAISED}; color: {TEXT}; border-radius: 9px; padding: 2px 10px; font-weight: 700;
}}
QScrollArea#toneDescription, QScrollArea#toneDescription > QWidget > QWidget {{
    background: transparent;
}}
QLabel#sectionTitle {{ font-size: 15px; font-weight: 700; }}
QListWidget#irSlots {{ background: {BG}; border: none; border-radius: 8px; }}
QListWidget#irSlots::item {{ padding: 8px; border-bottom: 1px solid {PANEL}; }}
QListWidget#irSlots::item:selected {{ background: #3a2a1a; color: {TEXT}; }}
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
QFrame#chainBar QLabel#note {{ padding-top: 2px; }}
QFrame#moduleTile {{
    background: {RAISED}; border: 2px solid transparent; border-radius: 12px;
}}
QFrame#moduleTile[hover="true"] {{ border-color: #8a5a2e; background: #2b2722; }}
QFrame#moduleTile[selected="true"] {{ border-color: {ACCENT}; background: #2d2620; }}
QLabel#tileName {{ font-weight: 800; color: {MUTED}; font-size: 11px; letter-spacing: 1px; }}
QFrame#moduleTile[on="true"] QLabel#tileName {{ color: {TEXT}; }}
QLabel#jackLabel {{ color: {MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 1px; }}
QLabel#modelLabel {{ font-size: 11px; }}
QLabel#modelLabel:disabled {{ color: {MUTED}; }}
QPushButton#power {{
    border-radius: 12px; border: 1px solid {BORDER}; background: {PANEL}; color: {MUTED};
    font-weight: 800;
}}
QPushButton#power:checked {{ background: #1f7a3a; border-color: #2fb35a; color: white; }}

QLineEdit, QPlainTextEdit#guitarField {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px;
}}
QPlainTextEdit#guitarField {{ padding: 2px 6px; }}
QScrollArea#guitarForm, QWidget#guitarFormBody {{ background: {PANEL}; border-radius: 10px; }}
QLabel#fieldLabel {{ color: {MUTED}; padding-top: 6px; }}
QLabel#sectionTitle {{ color: {MUTED}; font-size: 11px; font-weight: 700; padding-top: 4px; }}
QFrame#sidePanel {{ background: {PANEL}; border-radius: 12px; }}
QFrame#previewBar {{
    background: #2a2119; border: 1px solid #8a5a2e; border-radius: 8px;
}}
QLabel#previewLabel {{ color: {TEXT}; font-size: 12px; }}
QToolButton#iconButton {{
    background: transparent; border: none; border-radius: 6px; padding: 5px;
}}
QToolButton#iconButton:hover, QToolButton#iconButton:checked {{ background: {RAISED}; }}
QScrollArea#historyScroll, QWidget#historyBody {{ background: transparent; }}
QFrame#historyEntry {{ border-radius: 8px; border-left: 2px solid transparent; }}
QFrame#historyEntry:hover {{ background: {RAISED}; }}
QFrame#historyEntry[current="true"] {{ border-left: 2px solid {ACCENT}; }}
QLabel#historyTitle {{ font-weight: 600; }}
QLabel#historyMeta {{ color: {MUTED}; font-size: 11px; }}
QLabel#agentBadge {{
    border-radius: 11px; font-size: 11px; font-weight: 800; color: #1a1208; background: #d97757;
}}
QLabel#agentBadge[agent="codex"] {{ background: {TEXT}; }}
QLabel#cardTitle {{ font-size: 14px; font-weight: 800; }}
QLabel#aboutTitle {{ font-size: 22px; font-weight: 800; }}
QLabel#stepTitle {{
    color: {MUTED}; font-size: 11px; font-weight: 700; padding-top: 8px; letter-spacing: 0.5px;
}}
QLabel#countBadge {{
    color: {MUTED}; background: {RAISED}; border-radius: 9px; padding: 2px 9px; font-size: 11px;
    font-weight: 700;
}}
QLabel#countBadge[on="true"] {{ color: #1a1208; background: {ACCENT}; }}
QLabel#summaryBox {{
    background: {BG}; border: 1px dashed {BORDER}; border-radius: 8px; padding: 10px 12px;
    color: {TEXT};
}}
QLabel#emptyState {{ color: {MUTED}; padding: 24px; font-size: 12px; }}
QPushButton#linkButton {{
    background: transparent; border: none; color: {ACCENT}; padding: 2px 0; font-size: 12px;
    font-weight: 600;
}}
QPushButton#linkButton:hover {{ color: #ffb066; }}
QPushButton#linkButton:disabled {{ color: {MUTED}; }}
QFrame#modeSwitch {{ background: {PANEL}; border-radius: 10px; }}
QPushButton#modeTab {{
    background: transparent; border: none; border-radius: 8px; padding: 7px 12px; color: {MUTED};
    font-weight: 700;
}}
QPushButton#modeTab:hover {{ color: {TEXT}; }}
QPushButton#modeTab:checked {{ background: {RAISED}; color: {TEXT}; }}
QPushButton#segment {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 10px;
    color: {MUTED}; font-weight: 700; font-size: 12px;
}}
QPushButton#segment:hover {{ color: {TEXT}; border-color: #8a5a2e; }}
QPushButton#segment:checked {{ background: #3a2a1a; border-color: {ACCENT}; color: {ACCENT}; }}
QWidget#assistantPage QComboBox {{ padding: 6px 28px 6px 10px; }}
QWidget#assistantPage QComboBox:hover {{ border-color: #8a5a2e; }}
QWidget#assistantPage QComboBox:disabled {{ color: {MUTED}; }}
QWidget#assistantPage QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none;
}}
QWidget#assistantPage QComboBox::down-arrow {{ image: url({CHEVRON}); width: 12px; height: 12px; }}
QWidget#assistantPage QDoubleSpinBox {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px;
}}
QWidget#assistantPage QDoubleSpinBox QLineEdit {{
    background: transparent; border: none; padding: 0;
}}
QWidget#assistantPage QDoubleSpinBox::up-button,
QWidget#assistantPage QDoubleSpinBox::down-button {{
    width: 0px; border: none; subcontrol-origin: border;  /* else the text box is 1 px wide */
}}
QWidget#assistantPage QSlider::groove:horizontal {{
    height: 4px; background: {BORDER}; border-radius: 2px;
}}
QWidget#assistantPage QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QWidget#assistantPage QSlider::handle:horizontal {{
    background: {TEXT}; border: 2px solid {ACCENT}; width: 12px; height: 12px;
    margin: -6px 0; border-radius: 8px;
}}
QListWidget#presetChecks, QTreeWidget#bulkTree {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px;
}}
QTreeWidget#bulkTree::item {{ padding: 3px 2px; }}
QTreeWidget#bulkTree QHeaderView::section {{
    background: {BG}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 4px 6px; font-size: 11px; font-weight: 700;
}}
QLabel#guitarPicture {{
    background: {PANEL}; border-radius: 12px; color: {MUTED}; padding: 8px;
}}
QLabel#evidenceTag {{ font-size: 11px; font-weight: 700; border-radius: 9px; padding: 3px 0; }}
QLabel#evidenceTag[level="oficial"] {{ background: #173d26; color: #6fdc95; }}
QLabel#evidenceTag[level="verificado"] {{ background: #16324a; color: #7fc4ff; }}
QLabel#evidenceTag[level="deducido"] {{ background: #3d3216; color: #f0c860; }}
QLabel#evidenceTag[level="probable"] {{ background: #43221a; color: #ff9b7a; }}
QLineEdit:focus, QPlainTextEdit#guitarField:focus {{ border-color: {ACCENT}; }}
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
