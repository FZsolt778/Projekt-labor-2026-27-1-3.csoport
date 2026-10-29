
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
            border-radius: 6px;
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
            border-radius: 6px;
            padding: 8px 14px;
        }}

        QPushButton:hover {{
            background-color: {ACCENT_LIGHT};
        }}

        QPushButton:disabled {{
            color: {TEXT_SECONDARY};
        }}
    """)



def setup_fluent_theme():
    # Világos téma
    setTheme(Theme.LIGHT)

    # Egyetlen hangsúlyszín
    setThemeColor(QColor(35, 131, 226))
