
from qfluentwidgets import (
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    ComboBox,
    PrimaryPushButton,
    setFont,
)

from PySide6.QtWidgets import (
    QFrame,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QSizePolicy,
    QScrollArea,
    QLabel,
    QDateEdit,
)

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont


class BookingInterface(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)

        self.setObjectName(text.replace(" ", "-"))

        # ==================================================
        # FŐ ELRENDEZÉS
        # ==================================================

        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(24, 16, 24, 16)
        self.mainLayout.setSpacing(0)

        # Görgethető tartalom
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.formContent = QWidget()
        self.formLayout = QVBoxLayout(self.formContent)
        self.formLayout.setContentsMargins(12, 8, 12, 24)
        self.formLayout.setSpacing(14)

        self.scrollArea.setWidget(self.formContent)
        self.mainLayout.addWidget(self.scrollArea)

        # ==================================================
        # FEJLÉC
        # ==================================================

        self.title = SubtitleLabel(
            "Csomagfeladás",
            self.formContent
        )
        setFont(self.title, 32, QFont.Weight.Bold)

        self.description = BodyLabel(
            "Add meg a csomag és a szállítás adatait.",
            self.formContent
        )
        self.description.setStyleSheet("color: #6B6B6B;")

        self.formLayout.addWidget(self.title)
        self.formLayout.addWidget(self.description)
        self.formLayout.addSpacing(8)

        # ==================================================
        # CSOMAG ADATAI
        # ==================================================

        self.add_section_title("Csomag adatai")

        self.sizeCombo = ComboBox(self.formContent)
        self.sizeCombo.addItems(["S", "M", "L"])
        self.sizeCombo.setCurrentText("S")
        self.sizeCombo.setMinimumHeight(42)
        self.sizeCombo.setMaximumWidth(260)

        self.formLayout.addWidget(QLabel("Csomag mérete"))
        self.formLayout.addWidget(self.sizeCombo)

        # ==================================================
        # FELADÓ ÉS CÍMZETT - KÉT OSZLOP
        # ==================================================

        self.peopleLayout = QGridLayout()
        self.peopleLayout.setContentsMargins(0, 0, 0, 0)
        self.peopleLayout.setHorizontalSpacing(24)
        self.peopleLayout.setVerticalSpacing(12)

        self.senderFrame, self.sender = self.create_person_section(
            "Feladó adatai"
        )

        self.recipientFrame, self.recipient = self.create_person_section(
            "Címzett adatai"
        )

        self.peopleLayout.addWidget(self.senderFrame, 0, 0)
        self.peopleLayout.addWidget(self.recipientFrame, 0, 1)

        self.peopleLayout.setColumnStretch(0, 1)
        self.peopleLayout.setColumnStretch(1, 1)

        self.formLayout.addLayout(self.peopleLayout)

        # ==================================================
        # FELVÉTEL ÉS KÉZBESÍTÉS
        # ==================================================

        self.add_section_title("Szállítás időpontjai")

        self.scheduleLayout = QGridLayout()
        self.scheduleLayout.setContentsMargins(0, 0, 0, 0)
        self.scheduleLayout.setHorizontalSpacing(24)
        self.scheduleLayout.setVerticalSpacing(10)

        self.pickupDate = self.create_date_edit()
        self.pickupSlot = self.create_slot_combo()

        self.deliveryDate = self.create_date_edit()
        self.deliverySlot = self.create_slot_combo()

        pickupTitle = SubtitleLabel(
            "Csomag felvétele",
            self.formContent
        )
        setFont(pickupTitle, 16, QFont.Weight.DemiBold)

        deliveryTitle = SubtitleLabel(
            "Kézbesítés",
            self.formContent
        )
        setFont(deliveryTitle, 16, QFont.Weight.DemiBold)

        self.scheduleLayout.addWidget(pickupTitle, 0, 0)
        self.scheduleLayout.addWidget(deliveryTitle, 0, 1)

        self.scheduleLayout.addWidget(
            QLabel("Dátum", self.formContent), 1, 0
        )
        self.scheduleLayout.addWidget(
            QLabel("Dátum", self.formContent), 1, 1
        )

        self.scheduleLayout.addWidget(self.pickupDate, 2, 0)
        self.scheduleLayout.addWidget(self.deliveryDate, 2, 1)

        self.scheduleLayout.addWidget(
            QLabel("Idősáv", self.formContent), 3, 0
        )
        self.scheduleLayout.addWidget(
            QLabel("Idősáv", self.formContent), 3, 1
        )

        self.scheduleLayout.addWidget(self.pickupSlot, 4, 0)
        self.scheduleLayout.addWidget(self.deliverySlot, 4, 1)

        self.scheduleLayout.setColumnStretch(0, 1)
        self.scheduleLayout.setColumnStretch(1, 1)

        self.formLayout.addLayout(self.scheduleLayout)

        # ==================================================
        # FELADÁS GOMB
        # ==================================================

        self.bookingButton = PrimaryPushButton(
            "Csomag feladása",
            self.formContent
        )
        self.bookingButton.setMinimumHeight(48)
        setFont(self.bookingButton, 14, QFont.Weight.DemiBold)

        self.bookingButton.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.formLayout.addSpacing(8)
        self.formLayout.addWidget(self.bookingButton)

    # ======================================================
    # SEGÉDFÜGGVÉNYEK
    # ======================================================

    def add_section_title(self, text: str):
        """Szakaszcím létrehozása."""
        label = SubtitleLabel(text, self.formContent)
        setFont(label, 20, QFont.Weight.DemiBold)

        self.formLayout.addSpacing(8)
        self.formLayout.addWidget(label)

    def create_line_edit(self, placeholder: str) -> LineEdit:
        """Egységes szöveges beviteli mező."""
        edit = LineEdit(self.formContent)
        edit.setPlaceholderText(placeholder)
        edit.setClearButtonEnabled(True)
        edit.setMinimumHeight(42)

        edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        return edit

    def create_person_section(self, title: str):
        """Feladó vagy címzett adatainak létrehozása."""

        frame = QFrame(self.formContent)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(10)

        sectionTitle = SubtitleLabel(title, frame)
        setFont(sectionTitle, 18, QFont.Weight.DemiBold)
        layout.addWidget(sectionTitle)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        fields = {
            "last_name": self.create_line_edit("Vezetéknév"),
            "first_name": self.create_line_edit("Keresztnév"),
            "email": self.create_line_edit("E-mail-cím"),
            "phone": self.create_line_edit("Telefonszám"),
            "postal_code": self.create_line_edit("Irányítószám"),
            "city": self.create_line_edit("Város"),
            "street": self.create_line_edit("Utca, közterület"),
            "house_number": self.create_line_edit("Házszám"),
        }

        grid.addWidget(fields["last_name"], 0, 0)
        grid.addWidget(fields["first_name"], 0, 1)

        grid.addWidget(fields["email"], 1, 0, 1, 2)
        grid.addWidget(fields["phone"], 2, 0, 1, 2)

        grid.addWidget(fields["postal_code"], 3, 0)
        grid.addWidget(fields["city"], 3, 1)

        grid.addWidget(fields["street"], 4, 0)
        grid.addWidget(fields["house_number"], 4, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        layout.addLayout(grid)

        return frame, fields

    def create_date_edit(self) -> QDateEdit:
        """Dátumválasztó."""

        dateEdit = QDateEdit(self.formContent)
        dateEdit.setCalendarPopup(True)
        dateEdit.setDisplayFormat("yyyy-MM-dd")
        dateEdit.setDate(QDate.currentDate())
        dateEdit.setMinimumDate(QDate.currentDate())
        dateEdit.setMinimumHeight(42)

        dateEdit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        return dateEdit

    def create_slot_combo(self) -> ComboBox:
        """Szállítási idősáv kiválasztása."""

        combo = ComboBox(self.formContent)

        combo.addItems([
            "08:00-10:00",
            "10:00-12:00",
            "12:00-14:00",
            "14:00-16:00",
            "16:00-18:00",
        ])

        combo.setMinimumHeight(42)

        combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        return combo

    # ======================================================
    # API PAYLOAD
    # ======================================================

    def get_payload(self) -> dict:
        """Az API által elvárt JSON-struktúra előállítása."""

        def get_person_data(fields: dict) -> dict:
            return {
                key: edit.text().strip()
                for key, edit in fields.items()
            }

        return {
            "size": self.sizeCombo.currentText(),

            "sender": get_person_data(self.sender),

            "recipient": get_person_data(self.recipient),

            "pickup_date": self.pickupDate.date().toString(
                "yyyy-MM-dd"
            ),

            "pickup_slot": self.pickupSlot.currentText(),

            "delivery_date": self.deliveryDate.date().toString(
                "yyyy-MM-dd"
            ),

            "delivery_slot": self.deliverySlot.currentText(),
        }
