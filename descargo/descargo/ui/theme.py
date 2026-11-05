"""Identidad visual de DescarGO."""

from ..utils import ASSETS_DIR

CHECK_ICON = (ASSETS_DIR / "check.svg").as_posix()

PALETTES = {
    "light": {
        "ACCENT": "#3D6BFF", "ACCENT_2": "#6E4CF5", "BG": "#F3F5FA", "SURFACE": "#FFFFFF",
        "SURFACE_2": "#F0F2F8", "BORDER": "#DCE1EC", "TEXT": "#1A1F36", "MUTED": "#69718F",
        "SUCCESS": "#16A34A", "WARNING": "#E08E0B", "DANGER": "#E5394B", "YAPE": "#742284",
    },
    "dark": {
        "ACCENT": "#4F7CFF", "ACCENT_2": "#7C5CFF", "BG": "#0E111C", "SURFACE": "#161A2B",
        "SURFACE_2": "#1E2338", "BORDER": "#2A3150", "TEXT": "#E8EBF7", "MUTED": "#8E96BA",
        "SUCCESS": "#22C55E", "WARNING": "#F5A524", "DANGER": "#F04F5F", "YAPE": "#742284",
    },
}
THEMES = {"light": "Claro", "dark": "Oscuro"}
_current = "light"


def accent() -> str:
    return PALETTES[_current]["ACCENT"]


def build_stylesheet(theme: str = "light") -> str:
    global _current
    _current = theme if theme in PALETTES else "light"
    p = PALETTES[_current]
    ACCENT, ACCENT_2, BG, SURFACE = p["ACCENT"], p["ACCENT_2"], p["BG"], p["SURFACE"]
    SURFACE_2, BORDER, TEXT, MUTED = p["SURFACE_2"], p["BORDER"], p["TEXT"], p["MUTED"]
    SUCCESS, WARNING, DANGER, YAPE = p["SUCCESS"], p["WARNING"], p["DANGER"], p["YAPE"]
    return f"""
* {{
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#Central {{ background: {BG}; }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}

QFrame#Sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QPushButton#NavButton {{
    text-align: left; background: transparent; border: none; border-radius: 10px;
    padding: 11px 14px; font-weight: 600; font-size: 10.5pt; color: {MUTED};
}}
QPushButton#NavButton:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton#NavButton:checked {{ background: rgba(61,107,255,0.12); color: {ACCENT}; }}
QLabel#SidebarNote {{ color: {MUTED}; font-size: 8.5pt; }}
QPushButton#AuthorLink {{
    background: transparent; border: 1px solid {BORDER}; border-radius: 10px; padding: 7px 12px;
    color: {TEXT}; font-weight: 600;
}}
QPushButton#AuthorLink:hover {{ border-color: #D62976; color: #D62976; }}
QLabel#PageTitle {{ font-size: 18pt; font-weight: 700; }}
QLabel#ItemThumb {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; font-size: 22pt;
}}
QLabel#BrandTitle {{ font-size: 20pt; font-weight: 700; }}
QLabel#BrandTagline {{ color: {MUTED}; font-size: 9pt; }}
QLabel#Muted, QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel#SectionTitle {{ font-size: 11pt; font-weight: 600; }}
QLabel#DialogTitle {{ font-size: 13pt; font-weight: 700; }}
QLabel#Badge {{
    background: {SURFACE_2}; color: {MUTED}; border: 1px solid {BORDER};
    border-radius: 9px; padding: 2px 10px; font-size: 8.5pt;
}}
QLabel#EmptyState {{ color: {MUTED}; font-size: 11pt; }}
QLabel#Thumb {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; font-size: 24pt; }}

QFrame#Card {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px;
}}
QFrame#ItemCard {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
}}
QFrame#NoticeCard {{
    background: rgba(79,124,255,0.10); border: 1px solid rgba(79,124,255,0.35); border-radius: 10px;
}}
QFrame#YapeCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {YAPE}, stop:1 #9B3DB8);
    border-radius: 16px;
}}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 9px 12px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit#UrlInput {{ font-size: 11pt; padding: 12px 14px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT};
    outline: none; padding: 4px;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; border: none; }}

QPushButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 9px 16px; font-weight: 600;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {SURFACE_2}; }}
QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_2});
    border: none; color: white; padding: 11px 22px;
}}
QPushButton#Primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_2}, stop:1 {ACCENT});
}}
QPushButton#Primary:disabled {{ background: {BORDER}; color: {MUTED}; }}
QPushButton#Primary, QPushButton#Coffee {{ color: #FFFFFF; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid transparent; padding: 7px 10px; }}
QPushButton#Ghost:hover {{ background: {SURFACE_2}; border-color: {BORDER}; }}
QPushButton#Coffee {{
    background: {YAPE}; border: none; color: white; padding: 9px 16px;
}}
QPushButton#Coffee:hover {{ background: #8A2C9E; }}
QPushButton#Danger, QPushButton[class="danger"] {{ color: {DANGER}; }}
QPushButton#Danger:hover, QPushButton[class="danger"]:hover {{ border-color: {DANGER}; }}
QPushButton#Small {{ padding: 5px 10px; font-size: 9pt; border-radius: 8px; }}

QRadioButton#Choice, QRadioButton#QualityOption {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px; padding: 10px 12px;
}}
QRadioButton#Choice {{ font-size: 11pt; font-weight: 600; padding: 12px 16px; }}
QRadioButton#Choice:checked, QRadioButton#QualityOption:checked {{
    border: 1px solid {ACCENT}; background: rgba(79,124,255,0.14);
}}
QRadioButton#Choice:hover, QRadioButton#QualityOption:hover {{ border-color: {ACCENT}; }}
QRadioButton::indicator {{
    width: 14px; height: 14px; border-radius: 9px; border: 2px solid {MUTED}; background: transparent;
}}
QRadioButton::indicator:hover {{ border-color: {ACCENT}; }}
QRadioButton::indicator:checked {{ border: 5px solid {ACCENT}; background: #FFFFFF; width: 8px; height: 8px; }}
QCheckBox::indicator, QListView::indicator {{
    width: 16px; height: 16px; border-radius: 5px; border: 2px solid {MUTED}; background: {SURFACE_2};
}}
QCheckBox::indicator:hover, QListView::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked, QListView::indicator:checked {{
    background: {ACCENT}; border-color: {ACCENT}; image: url("{CHECK_ICON}");
}}
QCheckBox::indicator:disabled {{ border-color: {BORDER}; }}
QCheckBox {{ spacing: 8px; }}

QProgressBar {{
    background: {SURFACE_2}; border: none; border-radius: 4px; height: 8px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_2});
}}
QProgressBar[state="ok"]::chunk {{ background: {SUCCESS}; }}
QProgressBar[state="warn"]::chunk {{ background: {WARNING}; }}
QProgressBar[state="fail"]::chunk {{ background: {DANGER}; }}
QProgressBar[state="scan"]::chunk {{ background: #2BB3C0; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 10px 18px; margin-right: 4px;
    border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; min-width: 30px; }}

QTableWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
    gridline-color: transparent; alternate-background-color: {SURFACE_2};
    selection-background-color: rgba(79,124,255,0.30); selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {SURFACE}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 8px; font-weight: 600;
}}
QListWidget {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px; padding: 4px;
}}
QListWidget::item {{ padding: 6px; border-radius: 6px; }}
QListWidget::item:selected {{ background: rgba(79,124,255,0.25); }}

QStatusBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; color: {MUTED}; }}
QStatusBar QLabel {{ color: {MUTED}; padding: 0 8px; }}
QGroupBox {{
    border: 1px solid {BORDER}; border-radius: 12px; margin-top: 14px; padding: 14px 12px 10px 12px;
    font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {MUTED}; }}
QMessageBox {{ background: {BG}; }}
"""
