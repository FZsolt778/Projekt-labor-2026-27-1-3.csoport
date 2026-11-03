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

    def __init__(self):
        super().__init__()
        self.setObjectName("AuthInterface")
        self.pivot = Pivot(self)
        self.stackedWidget = QStackedWidget(self)
        self.vBoxLayout = QVBoxLayout(self)

        self.loginInterface = LoginInterface("Login Interface",self)
        self.registrationInterface = RegistrationInterface("Registration Interface", self)

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
class LoginInterface(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setObjectName("LoginInterface")

        # Fő layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(80, 60, 80, 60)
        self.layout.setSpacing(15)

        # Cím
        self.title = SubtitleLabel("Bejelentkezés", self)
        setFont(self.title, 28)

        self.usernameEdit = LineEdit(self)

        # Set placeholder text
        self.usernameEdit.setPlaceholderText("example@example.com")
        # Enable clear button
        self.usernameEdit.setClearButtonEnabled(True)

        

        # Jelszó
        self.passwordEdit = PasswordLineEdit(self)
        self.passwordEdit.setPlaceholderText("Jelszó")

        # Bejelentkezés
        self.loginButton = PrimaryPushButton(
            FIF.PEOPLE,
            "Bejelentkezés",
            self
        )

        # Elrendezés
        self.layout.addWidget(
            self.title,
            alignment=Qt.AlignHCenter
        )

        self.layout.addSpacing(30)

        self.layout.addWidget(self.usernameEdit)
        self.layout.addWidget(self.passwordEdit)

        self.layout.addSpacing(10)

        self.layout.addWidget(self.loginButton)

        self.layout.addStretch(1)
'''