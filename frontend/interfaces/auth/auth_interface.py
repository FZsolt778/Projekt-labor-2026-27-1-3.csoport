from qfluentwidgets import Pivot
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QWidget,
    QStackedWidget
)
from .login_interface import LoginInterface
from .registration_interface import RegistrationInterface

class AuthInterface(QWidget):

    def __init__(self, window):
        super().__init__()
        self.setObjectName("AuthInterface")
        self.pivot = Pivot(self)
        self.stackedWidget = QStackedWidget(self)
        self.vBoxLayout = QVBoxLayout(self)

        self.loginInterface = LoginInterface("Login Interface", window, self)
        self.registrationInterface = RegistrationInterface("Registration Interface", window, self)

        # Add tabs
        self.addSubInterface(self.loginInterface, 'loginInterface', 'Bejelentkezés')
        self.addSubInterface(self.registrationInterface, 'registrationInterface', 'Regisztráció')

        # Connect signal and initialize the current tab
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.loginInterface)
        self.pivot.setCurrentItem(self.loginInterface.objectName())

        self.vBoxLayout.setContentsMargins(30, 0, 30, 30)
        self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignHCenter)
        self.vBoxLayout.addWidget(self.stackedWidget)
        self.resize(400, 400)

    def addSubInterface(self, widget: QWidget, objectName: str, text: str):
        widget.setObjectName(objectName)
        #widget.setAlignment(Qt.AlignCenter)
        self.stackedWidget.addWidget(widget)

        # Use the globally unique objectName as the route key
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

'''
Szerepkör	Email	Jelszó
Ügyfél	teszt.ugyfel@example.com	Teszt1234
Futár	teszt.futar@example.com	Teszt1234
Logisztikus	teszt.logisztikus@example.com	Teszt1234
Admin	teszt.admin@example.com	Teszt1234
'''
