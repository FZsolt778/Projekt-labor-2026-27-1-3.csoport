from qfluentwidgets import (
    NavigationItemPosition,
    FluentWindow,
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    CheckBox,
    setFont,
    FluentIcon as FIF
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit
)

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
