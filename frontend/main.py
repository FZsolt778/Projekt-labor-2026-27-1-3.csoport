import sys

if __name__ == "__main__":
    sys.modules["main"] = sys.modules[__name__]

from PySide6.QtWidgets import QApplication
from interfaces.main_window import Window
from theme import setup_theme, setup_fluent_theme
import resources_rc
from api_client import api


w: Window | None = None

if __name__ == '__main__':
    app = QApplication(sys.argv)

    setup_fluent_theme()
    setup_theme(app)

    w = Window()
  
    w.showFullScreen()
    app.exec()
