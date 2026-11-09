from qfluentwidgets import (
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    setFont,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from api_client import ApiError, api, run_in_background


class LoginInterface(QFrame):
    def onClickLogin(self) -> None:
        self._clear_field_error(self.emailEdit, self.emailErrorLabel)
        self._clear_field_error(self.passwordEdit, self.passwordErrorLabel)
        self.loginErrorLabel.clear()
        self.loginErrorLabel.hide()

        email = self.emailEdit.text().strip()
        password = self.passwordEdit.text()
        is_valid = True

        if not email:
            self._show_field_error(
                self.emailEdit,
                self.emailErrorLabel,
                "Az email cím megadása kötelező.",
            )
            is_valid = False

        if not password:
            self._show_field_error(
                self.passwordEdit,
                self.passwordErrorLabel,
                "A jelszó megadása kötelező.",
            )
            is_valid = False

        if not is_valid:
            return

        self.formFrame.setEnabled(False)
        self.loginButton.setText("Bejelentkezés folyamatban...")
        run_in_background(
            api.login,
            email,
            password,
            on_success=self._on_login_success,
            on_error=self._on_login_error,
        )

    @staticmethod
    def _show_field_error(field: QWidget, label: QLabel, message: str) -> None:
        field.setStyleSheet("border: 1px solid #D13438;")
        label.setText(message)
        label.show()

    @staticmethod
    def _clear_field_error(field: QWidget, label: QLabel) -> None:
        field.setStyleSheet("")
        label.clear()
        label.hide()

    def _on_login_input_changed(self, field: QWidget, label: QLabel) -> None:
        self._clear_field_error(field, label)
        self.loginErrorLabel.clear()
        self.loginErrorLabel.hide()

    def _on_login_success(self) -> None:
        self._finish_login_request()
        

    def _on_login_error(self, error: ApiError) -> None:
        self._finish_login_request()
        self.loginErrorLabel.setText(error.message)
        self.loginErrorLabel.show()

    def _finish_login_request(self) -> None:
        self.formFrame.setEnabled(True)
        self.loginButton.setText("Bejelentkezés")

        
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)

        self.setObjectName(text.replace(" ", "-"))

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setSpacing(0)

        #left form
        self.formFrame = QFrame(self)
        self.formLayout = QVBoxLayout(self.formFrame)
        self.formLayout.setContentsMargins(100, 40, 100, 40)
        self.formLayout.setSpacing(10)
       
       
        #-------Form Title-------
        self.title = SubtitleLabel("Bejelentkezés", self.formFrame)
        setFont(self.title, 45, QFont.Bold)
        self.title.setAlignment(Qt.AlignCenter)
      
      
        #-------Body Label-------
        self.description = BodyLabel(
            "Jelentkezz be a fiókodba",
            self.formFrame
        )

        self.description.setAlignment(Qt.AlignCenter)
        setFont(self.description,25)
        self.description.setStyleSheet("color: gray;")
        
        #-------email-------
        self.emailEdit = LineEdit(self.formFrame)
        self.emailEdit.setPlaceholderText("Mail")
        self.emailEdit.setClearButtonEnabled(True)
        self.emailEdit.setTextMargins(32, 0, 8, 0)
        self.emailEdit.setMinimumHeight(50)
        
        self.emailEdit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.emailErrorLabel = QLabel(self.formFrame)
        self.emailErrorLabel.setStyleSheet("color: #D13438;")
        self.emailErrorLabel.setFont(QFont(self.font().family(), 9))
        self.emailErrorLabel.setWordWrap(True)
        self.emailErrorLabel.hide()

        self.emailFieldLayout = QVBoxLayout()
        self.emailFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.emailFieldLayout.setSpacing(8)
        self.emailFieldLayout.addWidget(self.emailEdit)
        self.emailFieldLayout.addWidget(self.emailErrorLabel)

        self.emailIcon = QSvgWidget(
            ":/icons/mail.svg",
             self.emailEdit
        )
        self.emailIcon.setFixedSize(18, 18)
        self.emailIcon.move(10, (self.emailEdit.height() - self.emailIcon.height()) // 2)



        #-------password-------
        self.passwordEdit = PasswordLineEdit(self.formFrame)
        self.passwordEdit.setPlaceholderText("Jelszó")
        self.passwordEdit.setTextMargins(32, 0, 8, 0)
        self.passwordEdit.setMinimumHeight(50)
                
        self.passwordEdit.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed
        )

        self.passwordErrorLabel = QLabel(self.formFrame)
        self.passwordErrorLabel.setStyleSheet("color: #D13438;")
        self.passwordErrorLabel.setFont(QFont(self.font().family(), 9))
        self.passwordErrorLabel.setWordWrap(True)
        self.passwordErrorLabel.hide()

        self.passwordFieldLayout = QVBoxLayout()
        self.passwordFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.passwordFieldLayout.setSpacing(8)
        self.passwordFieldLayout.addWidget(self.passwordEdit)
        self.passwordFieldLayout.addWidget(self.passwordErrorLabel)

        self.passwordIcon = QSvgWidget(
                    ":/icons/lock-keyhole.svg",
                     self.passwordEdit
                )
        self.passwordIcon.setFixedSize(18, 18)
        self.passwordIcon.move(10, (self.passwordEdit.height() - self.passwordIcon.height()) // 2)

        self.loginErrorLabel = QLabel(self.formFrame)
        self.loginErrorLabel.setStyleSheet("color: #D13438;")
        self.loginErrorLabel.setFont(QFont(self.font().family(), 9))
        self.loginErrorLabel.setWordWrap(True)
        self.loginErrorLabel.hide()


        #------Login------
        self.loginButton = PrimaryPushButton(
            "Bejelentkezés",
            self.formFrame
        )
        self.loginButton.setMinimumHeight(50)
        setFont(self.loginButton, 16, QFont.DemiBold)
                        
        self.loginButton.setSizePolicy(
                            QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed
                )
        self.loginButton.clicked.connect(self.onClickLogin)
        self.emailEdit.textChanged.connect(
            lambda: self._on_login_input_changed(self.emailEdit, self.emailErrorLabel)
        )
        self.passwordEdit.textChanged.connect(
            lambda: self._on_login_input_changed(
                self.passwordEdit,
                self.passwordErrorLabel,
            )
        )

        self.formLayout.addStretch(1)
        self.formLayout.addWidget(self.title)
        self.formLayout.addSpacing(5)
        self.formLayout.addWidget(self.description)
        self.formLayout.addSpacing(15)
        self.formLayout.addLayout(self.emailFieldLayout)
        self.formLayout.addSpacing(10)
        self.formLayout.addLayout(self.passwordFieldLayout)
        self.formLayout.addSpacing(10)
        self.formLayout.addWidget(self.loginButton)
        self.formLayout.addWidget(self.loginErrorLabel)
        self.formLayout.addStretch(1)

        #right illustration
        self.illustrationFrame = QFrame(self)
        self.illustrationLayout = QVBoxLayout(
            self.illustrationFrame
        )
        self.illustrationLayout.setContentsMargins(30, 30, 30, 30)

        self.illustration = QSvgWidget(
            ":/illustrations/auth.svg",
             self.illustrationFrame
        )

        self.illustration.setMinimumSize(250, 250)

        self.illustration.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.illustrationLayout.addWidget(self.illustration, Qt.AlignCenter)

        self.hBoxLayout.addWidget(self.formFrame, 1)
        self.hBoxLayout.addWidget(self.illustrationFrame, 1)

def test():
    print("OK")