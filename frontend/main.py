import sys
from qfluentwidgets import NavigationItemPosition, FluentWindow, SubtitleLabel, setFont
from qfluentwidgets import FluentIcon as FIF
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout
from PySide6.QtGui import QIcon
import lucide
from interfaces.login import LoginInterface

class Widget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = QHBoxLayout(self)

        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)

        # Must set a globally unique object name for the sub-interface
        self.setObjectName(text.replace(' ', '-'))


class Window(FluentWindow):
    """ Main Interface """

    def __init__(self):
        super().__init__()

        # Create sub-interfaces, when actually using, replace Widget with your own sub-interface
        self.homeInterface = Widget('Főoldal', self)
        self.trackInterface = Widget('Nyomkövetés', self)
        self.packageInterface = Widget('Csomagfeladás', self)
        self.settingInterface = Widget('Beállítások', self)
        self.loginInterface = LoginInterface()
        self.testInterface1 = Widget('Teszt 1', self)

        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, 'Főoldal')
        self.addSubInterface(self.trackInterface, FIF.SEARCH, 'Nyomkövetés')
        self.addSubInterface(self.packageInterface, FIF.APPLICATION, 'Csomagfeladás')

        self.navigationInterface.addSeparator()

        self.addSubInterface(self.loginInterface, FIF.ROBOT, 'Bejelentkezés', NavigationItemPosition.SCROLL)
        self.addSubInterface(self.testInterface1, FIF.ALBUM, 'Test 1', parent=self.loginInterface)

        self.addSubInterface(self.settingInterface, FIF.SETTING, 'Settings', NavigationItemPosition.BOTTOM)

    def initWindow(self):
        self.resize(900, 700)
        self.setWindowIcon(QIcon('C:/Users/User/Projekt-labor-2026-27-1/frontend/resources/truck-icon.png'))
        self.setWindowTitle('Csomagkezelő')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Window()
  
    w.show()
    app.exec()
