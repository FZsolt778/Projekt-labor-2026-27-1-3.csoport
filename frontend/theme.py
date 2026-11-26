
# frontend/theme.py

from PySide6.QtGui import QFont,QColor
from PySide6.QtWidgets import QApplication

from qfluentwidgets import setTheme, setThemeColor, Theme

# Színek
BACKGROUND = "#FFFFFF"
SURFACE = "#FFFFFF"
TEXT = "#191919"
TEXT_SECONDARY = "#6B6B6B"
BORDER = "#E5E5E5"
ACCENT = "#2383E2"
ACCENT_HOVER = "#1B6FC2"
ACCENT_LIGHT = "#EAF3FC"
SCROLL_HANDLE = "#C4C9CE"
SCROLL_HANDLE_HOVER = "#9AA1A8"
SCROLL_HANDLE_PRESSED = "#7D858D"

# Betűtípus
FONT_FAMILY = "Inter"
FONT_FALLBACK = "Segoe UI"


def setup_theme(app: QApplication):

    font = QFont(FONT_FAMILY)
    if not font.exactMatch():
        font = QFont(FONT_FALLBACK)

    app.setFont(font)

    app.setStyleSheet(f"""
        QWidget {{
            background-color: {BACKGROUND};
            color: {TEXT};
            font-family: "{font.family()}";
        }}

        QFrame {{
            background-color: {SURFACE};
        }}

        QLineEdit {{
            background-color: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 25px;
            padding: 8px 10px;
            selection-background-color: {ACCENT};
        }}

        QLineEdit:focus {{
            border: 1px solid {ACCENT};
        }}

        QPushButton {{
            background-color: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 25px;
            padding: 8px 14px;
        }}

        QPushButton:hover {{
            background-color: {ACCENT_LIGHT};
        }}

        QPushButton:disabled {{
            color: {TEXT_SECONDARY};
        }}

        /* Thin rounded scroll bars without arrows, the track stays transparent */
        QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: 0;
        }}

        QScrollBar:horizontal {{
            background: transparent;
            height: 12px;
            margin: 0;
        }}

        QScrollBar::handle:vertical {{
            background: {SCROLL_HANDLE};
            border-radius: 3px;
            min-height: 40px;
            margin: 2px 3px;
        }}

        QScrollBar::handle:horizontal {{
            background: {SCROLL_HANDLE};
            border-radius: 3px;
            min-width: 40px;
            margin: 3px 2px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {SCROLL_HANDLE_HOVER};
            border-radius: 4px;
            margin: 2px 2px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: {SCROLL_HANDLE_HOVER};
            border-radius: 4px;
            margin: 2px 2px;
        }}

        QScrollBar::handle:pressed {{
            background: {SCROLL_HANDLE_PRESSED};
        }}

        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0;
            height: 0;
            border: none;
            background: none;
        }}

        QScrollBar::add-page, QScrollBar::sub-page {{
            background: none;
        }}

        QAbstractScrollArea::corner {{
            background: transparent;
        }}
    """)



def setup_fluent_theme():
    # Világos téma
    setTheme(Theme.LIGHT)

    # Egyetlen hangsúlyszín
    setThemeColor(QColor(35, 131, 226))
