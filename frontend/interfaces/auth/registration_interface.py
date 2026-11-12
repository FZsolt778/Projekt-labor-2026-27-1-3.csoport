import re

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
    QLayout,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QScrollArea,
    QWidget,
)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt

from PySide6.QtGui import QFont

from api_client import ApiError, api, run_in_background
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main_window import Window


class RegistrationInterface(QFrame):

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

    def _on_registration_input_changed(
        self, field: QWidget, label: QLabel
    ) -> None:
        self._clear_field_error(field, label)

    def _validate_registration(self) -> bool:
        fields = (
            (self.lastNameEdit, self.lastNameErrorLabel),
            (self.firstNameEdit, self.firstNameErrorLabel),
            (self.emailEdit, self.emailErrorLabel),
            (self.passwordEdit, self.passwordErrorLabel),
            (self.phoneEdit, self.phoneErrorLabel),
            (self.postalCodeEdit, self.postalCodeErrorLabel),
            (self.cityEdit, self.cityErrorLabel),
            (self.streetEdit, self.streetErrorLabel),
            (self.houseNumberEdit, self.houseNumberErrorLabel),
        )
        for field, label in fields:
            self._clear_field_error(field, label)

        is_valid = True

        for field, label, name in (
            (self.lastNameEdit, self.lastNameErrorLabel, "A vezetéknév"),
            (self.firstNameEdit, self.firstNameErrorLabel, "A keresztnév"),
        ):
            value = field.text().strip()
            if not value:
                self._show_field_error(field, label, f"{name} megadása kötelező.")
                is_valid = False
            elif len(value) > 50:
                self._show_field_error(field, label, f"{name} legfeljebb 50 karakter lehet.")
                is_valid = False

        email = self.emailEdit.text().strip()
        if not email:
            self._show_field_error(
                self.emailEdit, self.emailErrorLabel, "Az email cím megadása kötelező."
            )
            is_valid = False
        elif len(email) > 100 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            self._show_field_error(
                self.emailEdit, self.emailErrorLabel, "Adj meg egy érvényes email címet."
            )
            is_valid = False

        password_length = len(self.passwordEdit.text())
        if password_length == 0:
            self._show_field_error(
                self.passwordEdit,
                self.passwordErrorLabel,
                "A jelszó megadása kötelező.",
            )
            is_valid = False
        elif password_length < 8:
            self._show_field_error(
                self.passwordEdit,
                self.passwordErrorLabel,
                "A jelszónak legalább 8 karakter hosszúnak kell lennie.",
            )
            is_valid = False
        elif password_length > 128:
            self._show_field_error(
                self.passwordEdit,
                self.passwordErrorLabel,
                "A jelszó legfeljebb 128 karakter lehet.",
            )
            is_valid = False

        phone = self.phoneEdit.text().strip()
        if phone and (
            len(phone) > 20 or not re.fullmatch(r"\+?[0-9][0-9 /-]{5,18}", phone)
        ):
            self._show_field_error(
                self.phoneEdit,
                self.phoneErrorLabel,
                "Adj meg egy érvényes telefonszámot.",
            )
            is_valid = False

        address_fields = (
            (self.postalCodeEdit, self.postalCodeErrorLabel),
            (self.cityEdit, self.cityErrorLabel),
            (self.streetEdit, self.streetErrorLabel),
            (self.houseNumberEdit, self.houseNumberErrorLabel),
        )
        address_values = [field.text().strip() for field, _ in address_fields]
        if any(address_values):
            for (field, label), value, name in zip(
                address_fields,
                address_values,
                ("Az irányítószám", "A város", "Az utca", "A házszám"),
            ):
                if not value:
                    self._show_field_error(
                        field, label, f"{name} megadása szükséges a címhez."
                    )
                    is_valid = False

            postal_code = address_values[0]
            if postal_code and not re.fullmatch(r"[1-9][0-9]{3}", postal_code):
                self._show_field_error(
                    self.postalCodeEdit,
                    self.postalCodeErrorLabel,
                    "Az irányítószám 4 számjegyből álljon, és ne kezdődjön nullával.",
                )
                is_valid = False

            for (field, label), value, name, maximum in (
                (address_fields[1], address_values[1], "A város", 50),
                (address_fields[2], address_values[2], "Az utca", 100),
                (address_fields[3], address_values[3], "A házszám", 20),
            ):
                if value and len(value) > maximum:
                    self._show_field_error(
                        field, label, f"{name} legfeljebb {maximum} karakter lehet."
                    )
                    is_valid = False

        return is_valid

    def __init__(self, text: str, w: "Window", parent=None):
        super().__init__(parent=parent)

        self.setObjectName(text.replace(" ", "-"))
        self.w = w;
        
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setFrameShape(QFrame.NoFrame)

        self.contentWidget = QWidget()
        self.hBoxLayout = QHBoxLayout(self.contentWidget)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.scrollArea.setWidget(self.contentWidget)
        self.mainLayout.addWidget(self.scrollArea)

        #left form
        self.formFrame = QFrame(self.contentWidget)
        self.formLayout = QVBoxLayout(self.formFrame)
        self.formLayout.setContentsMargins(100, 40, 100, 40)
        self.formLayout.setSpacing(15)
       
       
        #-------Form Title-------
        self.title = SubtitleLabel("Regisztráció", self.formFrame)
        setFont(self.title, 45, QFont.Bold)
        self.title.setAlignment(Qt.AlignCenter)
      
      
        #-------Body Label-------
        self.description = BodyLabel(
            "Hozz létre új fiókot",
            self.formFrame
        )

        self.description.setAlignment(Qt.AlignCenter)
        setFont(self.description,25)
        self.description.setStyleSheet("color: gray;")

        #------Name Layout------
        self.nameForm = QHBoxLayout(self.formFrame)
        #-------Last Name-------
        self.lastNameEdit = LineEdit(self.formFrame)
        self.lastNameEdit.setPlaceholderText("Vezetéknév")
        self.lastNameEdit.setClearButtonEnabled(True)
        self.lastNameEdit.setMinimumHeight(50)
        self.lastNameEdit.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed
                )

        self.lastNameErrorLabel = self._create_error_label()
        self.lastNameFieldLayout = QVBoxLayout()
        self.lastNameFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.lastNameFieldLayout.setSpacing(8)
        self.lastNameFieldLayout.addWidget(self.lastNameEdit)
        self.lastNameFieldLayout.addWidget(self.lastNameErrorLabel)

        
        #-------First Name-------
        self.firstNameEdit  = LineEdit(self.formFrame)
        self.firstNameEdit.setPlaceholderText("Keresztnév")
        self.firstNameEdit.setClearButtonEnabled(True)
        self.firstNameEdit.setMinimumHeight(50)
        self.firstNameEdit.setSizePolicy(
                            QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed
                        )

        self.firstNameErrorLabel = self._create_error_label()
        self.firstNameFieldLayout = QVBoxLayout()
        self.firstNameFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.firstNameFieldLayout.setSpacing(8)
        self.firstNameFieldLayout.addWidget(self.firstNameEdit)
        self.firstNameFieldLayout.addWidget(self.firstNameErrorLabel)

        #------Add to layout------
        self.nameForm.addLayout(self.lastNameFieldLayout, 1)
        self.nameForm.addLayout(self.firstNameFieldLayout, 1)


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

        self.emailErrorLabel = self._create_error_label()
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

        self.passwordErrorLabel = self._create_error_label()
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


        # Telefonszám
        self.phoneEdit = LineEdit(self.formFrame)
        self.phoneEdit.setPlaceholderText("Telefonszám")
        self.phoneEdit.setTextMargins(32, 0, 8, 0)
        self.phoneEdit.setMinimumHeight(50)
        self.phoneErrorLabel = self._create_error_label()
        self.phoneFieldLayout = QVBoxLayout()
        self.phoneFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.phoneFieldLayout.setSpacing(8)
        self.phoneFieldLayout.addWidget(self.phoneEdit)
        self.phoneFieldLayout.addWidget(self.phoneErrorLabel)
        self.phoneEditIcon = QSvgWidget(
                            ":/icons/phone.svg",
                             self.phoneEdit
        )
        self.phoneEditIcon.setFixedSize(18, 18)
        self.phoneEditIcon.move(10, (self.phoneEdit.height() - self.phoneEditIcon.height()) // 2)

        # Irányítószám és város
        self.addressCityForm = QHBoxLayout()
        self.addressCityForm.setSpacing(10)

        self.postalCodeEdit = LineEdit(self.formFrame)
        self.postalCodeEdit.setPlaceholderText("Irányítószám")
        self.postalCodeEdit.setMinimumHeight(50)
        self.postalCodeErrorLabel = self._create_error_label()
        self.postalCodeFieldLayout = QVBoxLayout()
        self.postalCodeFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.postalCodeFieldLayout.setSpacing(8)
        self.postalCodeFieldLayout.addWidget(self.postalCodeEdit)
        self.postalCodeFieldLayout.addWidget(self.postalCodeErrorLabel)

        self.cityEdit = LineEdit(self.formFrame)
        self.cityEdit.setPlaceholderText("Város")
        self.cityEdit.setMinimumHeight(50)
        self.cityErrorLabel = self._create_error_label()
        self.cityFieldLayout = QVBoxLayout()
        self.cityFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.cityFieldLayout.setSpacing(8)
        self.cityFieldLayout.addWidget(self.cityEdit)
        self.cityFieldLayout.addWidget(self.cityErrorLabel)

        self.addressCityForm.addLayout(self.postalCodeFieldLayout, 1)
        self.addressCityForm.addLayout(self.cityFieldLayout, 2)

        # Utca és házszám
        self.streetForm = QHBoxLayout()
        self.streetForm.setSpacing(10)

        self.streetEdit = LineEdit(self.formFrame)
        self.streetEdit.setPlaceholderText("Utca, közterület neve")
        self.streetEdit.setMinimumHeight(50)
        self.streetErrorLabel = self._create_error_label()
        self.streetFieldLayout = QVBoxLayout()
        self.streetFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.streetFieldLayout.setSpacing(8)
        self.streetFieldLayout.addWidget(self.streetEdit)
        self.streetFieldLayout.addWidget(self.streetErrorLabel)

        self.houseNumberEdit = LineEdit(self.formFrame)
        self.houseNumberEdit.setPlaceholderText("Házszám")
        self.houseNumberEdit.setMinimumHeight(50)
        self.houseNumberErrorLabel = self._create_error_label()
        self.houseNumberFieldLayout = QVBoxLayout()
        self.houseNumberFieldLayout.setContentsMargins(0, 0, 0, 0)
        self.houseNumberFieldLayout.setSpacing(8)
        self.houseNumberFieldLayout.addWidget(self.houseNumberEdit)
        self.houseNumberFieldLayout.addWidget(self.houseNumberErrorLabel)

        self.streetForm.addLayout(self.streetFieldLayout, 3)
        self.streetForm.addLayout(self.houseNumberFieldLayout, 1)


        #------Login------
        self.registrationButton = PrimaryPushButton(
            "Regisztráció",
            self.formFrame
        )
        self.registrationButton.setMinimumHeight(50)
        setFont(self.registrationButton, 16, QFont.DemiBold)
                        
        self.registrationButton.setSizePolicy(
                            QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed
                )
        
        self.registrationButton.clicked.connect(self.onClickRegistration)
        input_error_labels = (
            (self.lastNameEdit, self.lastNameErrorLabel),
            (self.firstNameEdit, self.firstNameErrorLabel),
            (self.emailEdit, self.emailErrorLabel),
            (self.passwordEdit, self.passwordErrorLabel),
            (self.phoneEdit, self.phoneErrorLabel),
            (self.postalCodeEdit, self.postalCodeErrorLabel),
            (self.cityEdit, self.cityErrorLabel),
            (self.streetEdit, self.streetErrorLabel),
            (self.houseNumberEdit, self.houseNumberErrorLabel),
        )
        for field, label in input_error_labels:
            field.textChanged.connect(
                lambda *_args, field=field, label=label:
                    self._on_registration_input_changed(field, label)
            )

        self.formLayout.addStretch(1)
        self.formLayout.addWidget(self.title)
        self.formLayout.addSpacing(5)
        self.formLayout.addWidget(self.description)
        self.formLayout.addSpacing(15)
        self.formLayout.addLayout(self.nameForm)
        self.formLayout.addLayout(self.emailFieldLayout)
        self.formLayout.addLayout(self.passwordFieldLayout)
        self.formLayout.addLayout(self.phoneFieldLayout)
        self.formLayout.addLayout(self.addressCityForm)
        self.formLayout.addLayout(self.streetForm)
        self.formLayout.addSpacing(5)
        self.formLayout.addWidget(self.registrationButton)
        self.formLayout.addStretch(1)


        #right illustration
        self.illustrationFrame = QFrame(self.contentWidget)
        self.illustrationLayout = QVBoxLayout(
            self.illustrationFrame
        )
        self.illustrationLayout.setContentsMargins(30, 30, 30, 30)

        self.illustration = QSvgWidget(
            ":/illustrations/auth.svg",
             self.illustrationFrame
        )
        self.illustration.renderer().setAspectRatioMode(
            Qt.AspectRatioMode.KeepAspectRatio
        )

        self.illustration.setMinimumSize(250, 250)

        self.illustration.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.illustrationLayout.addWidget(self.illustration, Qt.AlignCenter)

        self.hBoxLayout.addWidget(self.formFrame, 1)
        self.hBoxLayout.addWidget(self.illustrationFrame, 1)

    def onClickRegistration(self) -> None:
     if not self._validate_registration():
        return;
    
     self.formFrame.setEnabled(False)
     self.registrationButton.setText("Regisztráció folyamatban...")
     print("run in background");
     run_in_background(
        api.registration,
        self.lastNameEdit.text().strip(),
        self.firstNameEdit.text().strip(),
        self.emailEdit.text().strip(),
        self.passwordEdit.text(),
        self.phoneEdit.text().strip() or None,
        self.postalCodeEdit.text().strip() or None,
        self.cityEdit.text().strip() or None,
        self.streetEdit.text().strip() or None,
        self.houseNumberEdit.text().strip() or None,
        on_success=self._on_registration_success,
        on_error=self._on_registration_error);
            
            
    def _on_registration_success(self) -> None:
        self.formFrame.setEnabled(True)
        self.registrationButton.setText("Regisztráció")
        self.w.initNavigation();
        
    def _on_registration_error(self, error: ApiError) -> None:
        self.formFrame.setEnabled(True)
        self.registrationButton.setText("Regisztráció")

    def _create_error_label(self) -> QLabel:
        label = QLabel(self.formFrame)
        label.setStyleSheet("color: #D13438;")
        label.setFont(QFont(self.font().family(), 9))
        label.setWordWrap(True)
        label.hide()
        return label