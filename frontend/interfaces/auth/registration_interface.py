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
    QVBoxLayout,
    QSizePolicy
)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt

from PySide6.QtGui import QFont


class RegistrationInterface(QFrame):

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

        
        
        
        #-------First Name-------
        self.firstNameEdit  = LineEdit(self.formFrame)
        self.firstNameEdit.setPlaceholderText("Keresztnév")
        self.firstNameEdit.setClearButtonEnabled(True)
        self.firstNameEdit.setMinimumHeight(50)
        self.firstNameEdit.setSizePolicy(
                            QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed
                        )

       
                
                
        #------Add to layout------
        self.nameForm.addWidget(self.lastNameEdit, 1)
        self.nameForm.addWidget(self.firstNameEdit, 1)


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

        self.cityEdit = LineEdit(self.formFrame)
        self.cityEdit.setPlaceholderText("Város")
        self.cityEdit.setMinimumHeight(50)

        self.addressCityForm.addWidget(self.postalCodeEdit, 1)
        self.addressCityForm.addWidget(self.cityEdit, 2)

        # Utca és házszám
        self.streetForm = QHBoxLayout()
        self.streetForm.setSpacing(10)

        self.streetEdit = LineEdit(self.formFrame)
        self.streetEdit.setPlaceholderText("Utca, közterület neve")
        self.streetEdit.setMinimumHeight(50)

        self.houseNumberEdit = LineEdit(self.formFrame)
        self.houseNumberEdit.setPlaceholderText("Házszám")
        self.houseNumberEdit.setMinimumHeight(50)

        self.streetForm.addWidget(self.streetEdit, 3)
        self.streetForm.addWidget(self.houseNumberEdit, 1)


        #------Login------
        self.loginButton = PrimaryPushButton(
            "Regisztráció",
            self.formFrame
        )
        self.loginButton.setMinimumHeight(50)
        setFont(self.loginButton, 16, QFont.DemiBold)
                        
        self.loginButton.setSizePolicy(
                            QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed
                )
        

        self.formLayout.addStretch(1)
        self.formLayout.addWidget(self.title)
        self.formLayout.addSpacing(5)
        self.formLayout.addWidget(self.description)
        self.formLayout.addSpacing(15)
        self.formLayout.addLayout(self.nameForm)
        self.formLayout.addWidget(self.emailEdit)
        self.formLayout.addWidget(self.passwordEdit)
        self.formLayout.addWidget(self.phoneEdit)
        self.formLayout.addLayout(self.addressCityForm)
        self.formLayout.addLayout(self.streetForm)
        self.formLayout.addSpacing(5)
        self.formLayout.addWidget(self.loginButton)
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