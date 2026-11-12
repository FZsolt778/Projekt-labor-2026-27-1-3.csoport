
import re

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
    QVBoxLayout,
    QGridLayout,
    QSizePolicy,
    QScrollArea,
    QLabel,
    QDateEdit,
)

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont

from api_client import ApiError, api, run_in_background


class BookingInterface(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)

        self.setObjectName(text.replace(" ", "-"))


        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(24, 16, 24, 16)
        self.mainLayout.setSpacing(0)

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

        self.add_section_title("Csomag adatai")

        self.sizeCombo = ComboBox(self.formContent)
        self.sizeCombo.addItems(["S", "M", "L", "XL"])
        self.sizeCombo.setCurrentText("S")
        self.sizeCombo.setMinimumHeight(42)
        self.sizeCombo.setMaximumWidth(260)

        self.formLayout.addWidget(QLabel("Csomag mérete"))
        self.formLayout.addWidget(self.sizeCombo)


        self.peopleLayout = QGridLayout()
        self.peopleLayout.setContentsMargins(0, 0, 0, 0)
        self.peopleLayout.setHorizontalSpacing(24)
        self.peopleLayout.setVerticalSpacing(12)

        self.senderFrame, self.sender, sender_errors = self.create_person_section(
            "Feladó adatai"
        )

        self.recipientFrame, self.recipient, recipient_errors = self.create_person_section(
            "Címzett adatai"
        )

        self.field_errors = {
            **{f"sender.{key}": value for key, value in sender_errors.items()},
            **{f"recipient.{key}": value for key, value in recipient_errors.items()},
        }

        self.peopleLayout.addWidget(self.senderFrame, 0, 0)
        self.peopleLayout.addWidget(self.recipientFrame, 0, 1)

        self.peopleLayout.setColumnStretch(0, 1)
        self.peopleLayout.setColumnStretch(1, 1)

        self.formLayout.addLayout(self.peopleLayout)

        self.add_section_title("Szállítás időpontjai")

        self.scheduleLayout = QGridLayout()
        self.scheduleLayout.setContentsMargins(0, 0, 0, 0)
        self.scheduleLayout.setHorizontalSpacing(24)
        self.scheduleLayout.setVerticalSpacing(10)

        self.pickupDate = self.create_date_edit()
        self.pickupSlot = self.create_slot_combo()

        self.deliveryDate = self.create_date_edit()
        self.deliverySlot = self.create_slot_combo()
        self.deliverySlot.setCurrentIndex(1)

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

        pickupDateField, self.pickupDateErrorLabel = self.create_field_container(
            self.pickupDate
        )
        deliveryDateField, self.deliveryDateErrorLabel = self.create_field_container(
            self.deliveryDate
        )
        self.field_errors["pickup_date"] = (
            self.pickupDate,
            self.pickupDateErrorLabel,
        )
        self.field_errors["delivery_date"] = (
            self.deliveryDate,
            self.deliveryDateErrorLabel,
        )

        self.scheduleLayout.addWidget(pickupDateField, 2, 0)
        self.scheduleLayout.addWidget(deliveryDateField, 2, 1)

        self.scheduleLayout.addWidget(
            QLabel("Idősáv", self.formContent), 3, 0
        )
        self.scheduleLayout.addWidget(
            QLabel("Idősáv", self.formContent), 3, 1
        )

        pickupSlotField, self.pickupSlotErrorLabel = self.create_field_container(
            self.pickupSlot
        )
        deliverySlotField, self.deliverySlotErrorLabel = self.create_field_container(
            self.deliverySlot
        )
        self.field_errors["pickup_slot"] = (
            self.pickupSlot,
            self.pickupSlotErrorLabel,
        )
        self.field_errors["delivery_slot"] = (
            self.deliverySlot,
            self.deliverySlotErrorLabel,
        )

        self.scheduleLayout.addWidget(pickupSlotField, 4, 0)
        self.scheduleLayout.addWidget(deliverySlotField, 4, 1)

        self.scheduleLayout.setColumnStretch(0, 1)
        self.scheduleLayout.setColumnStretch(1, 1)

        self.formLayout.addLayout(self.scheduleLayout)


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
        self.bookingStatusLabel = QLabel(self.formContent)
        self.bookingStatusLabel.setWordWrap(True)
        self.bookingStatusLabel.hide()
        self.formLayout.addWidget(self.bookingStatusLabel)
        self.bookingButton.clicked.connect(self.onClickBooking)

        for field, label in self.field_errors.values():
            if isinstance(field, LineEdit):
                field.textChanged.connect(
                    lambda *_args, field=field, label=label:
                        self._on_input_changed(field, label)
                )
            elif isinstance(field, QDateEdit):
                field.dateChanged.connect(
                    lambda *_args, field=field, label=label:
                        self._on_input_changed(field, label)
                )
            else:
                field.currentTextChanged.connect(
                    lambda *_args, field=field, label=label:
                        self._on_input_changed(field, label)
                )


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

        field_errors = {}
        field_containers = {}
        for key, field in fields.items():
            field_containers[key], error_label = self.create_field_container(field)
            field_errors[key] = (field, error_label)

        grid.addWidget(field_containers["last_name"], 0, 0)
        grid.addWidget(field_containers["first_name"], 0, 1)

        grid.addWidget(field_containers["email"], 1, 0, 1, 2)
        grid.addWidget(field_containers["phone"], 2, 0, 1, 2)

        grid.addWidget(field_containers["postal_code"], 3, 0)
        grid.addWidget(field_containers["city"], 3, 1)

        grid.addWidget(field_containers["street"], 4, 0)
        grid.addWidget(field_containers["house_number"], 4, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        layout.addLayout(grid)

        return frame, fields, field_errors

    def create_field_container(self, field: QWidget) -> tuple[QWidget, QLabel]:
        container = QWidget(self.formContent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        error_label = QLabel(container)
        error_label.setStyleSheet("color: #D13438;")
        error_label.setWordWrap(True)
        error_label.hide()
        layout.addWidget(field)
        layout.addWidget(error_label)
        return container, error_label

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

    def _on_input_changed(self, field: QWidget, label: QLabel) -> None:
        self._clear_field_error(field, label)
        self.bookingStatusLabel.clear()
        self.bookingStatusLabel.hide()

    def _set_status(self, message: str, *, success: bool = False) -> None:
        color = "#107C10" if success else "#D13438"
        self.bookingStatusLabel.setStyleSheet(f"color: {color};")
        self.bookingStatusLabel.setText(message)
        self.bookingStatusLabel.show()

    def _validate_booking(self) -> bool:
        for field, label in self.field_errors.values():
            self._clear_field_error(field, label)
        self.bookingStatusLabel.clear()
        self.bookingStatusLabel.hide()
        is_valid = True

        for person_name, fields in (
            ("sender", self.sender),
            ("recipient", self.recipient),
        ):
            for key, field in fields.items():
                value = field.text().strip()
                error = None
                if key == "phone":
                    if value and (
                        len(value) > 20
                        or not re.fullmatch(r"\+?[0-9][0-9 /-]{5,18}", value)
                    ):
                        error = "Adj meg egy érvényes telefonszámot."
                elif not value:
                    error = "A mező kitöltése kötelező."
                elif key in ("last_name", "first_name") and len(value) > 50:
                    error = "Legfeljebb 50 karakter lehet."
                elif key == "email" and (
                    len(value) > 100
                    or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value)
                ):
                    error = "Adj meg egy érvényes email címet."
                elif key == "postal_code" and not re.fullmatch(r"[1-9][0-9]{3}", value):
                    error = "Az irányítószám 4 számjegyű, és nem kezdődhet nullával."
                elif key == "city" and len(value) > 50:
                    error = "Legfeljebb 50 karakter lehet."
                elif key == "street" and len(value) > 100:
                    error = "Legfeljebb 100 karakter lehet."
                elif key == "house_number" and len(value) > 20:
                    error = "Legfeljebb 20 karakter lehet."

                if error:
                    field_widget, label = self.field_errors[f"{person_name}.{key}"]
                    self._show_field_error(field_widget, label, error)
                    is_valid = False

        tomorrow = QDate.currentDate().addDays(1)
        if self.pickupDate.date() < tomorrow:
            self._show_field_error(
                self.pickupDate,
                self.pickupDateErrorLabel,
                "A felvétel legkorábban holnapra foglalható.",
            )
            is_valid = False

        if self.deliveryDate.date() < self.pickupDate.date():
            self._show_field_error(
                self.deliveryDate,
                self.deliveryDateErrorLabel,
                "A kézbesítés nem lehet a felvétel előtt.",
            )
            is_valid = False
        elif (
            self.deliveryDate.date() == self.pickupDate.date()
            and self._slot_start(self.deliverySlot.currentText())
            < self._slot_end(self.pickupSlot.currentText())
        ):
            self._show_field_error(
                self.deliverySlot,
                self.deliverySlotErrorLabel,
                "Azonos napon a kézbesítési idősávnak a felvétel után kell lennie.",
            )
            is_valid = False

        return is_valid

    @staticmethod
    def _slot_start(slot: str) -> int:
        return int(slot.split("-")[0].replace(":", ""))

    @staticmethod
    def _slot_end(slot: str) -> int:
        return int(slot.split("-")[1].replace(":", ""))

    def onClickBooking(self) -> None:
        if not self._validate_booking():
            return

        self.bookingButton.setEnabled(False)
        self.bookingButton.setText("Csomag feladása folyamatban...")
        run_in_background(
            api.post,
            "/parcels",
            json=self.get_payload(),
            on_success=self._on_booking_success,
            on_error=self._on_booking_error,
        )

    def _on_booking_success(self, result: object) -> None:
        self.bookingButton.setEnabled(True)
        self.bookingButton.setText("Csomag feladása")
        tracking_number = (
            result.get("tracking_number")
            if isinstance(result, dict)
            else None
        )
        message = "Sikeres csomagfeladás."
        if tracking_number:
            message += f" Nyomkövetési szám: {tracking_number}"
        self._set_status(message, success=True)

    def _on_booking_error(self, error: ApiError) -> None:
        self.bookingButton.setEnabled(True)
        self.bookingButton.setText("Csomag feladása")
        for path, message in error.field_errors.items():
            field_and_label = self.field_errors.get(path)
            if field_and_label is not None:
                self._show_field_error(*field_and_label, message)
        self._set_status(error.message)

    def create_date_edit(self) -> QDateEdit:
        """Dátumválasztó."""

        dateEdit = QDateEdit(self.formContent)
        dateEdit.setCalendarPopup(True)
        dateEdit.setDisplayFormat("yyyy-MM-dd")
        first_available_date = QDate.currentDate().addDays(1)
        dateEdit.setDate(first_available_date)
        dateEdit.setMinimumDate(first_available_date)
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
            "18:00-20:00",
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
            data = {
                key: edit.text().strip()
                for key, edit in fields.items()
            }
            if not data["phone"]:
                data["phone"] = None
            return data

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
