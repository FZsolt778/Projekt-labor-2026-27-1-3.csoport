from datetime import date

from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    SubtitleLabel,
    setFont,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from api_client import (
    ApiError,
    STATUS_LABELS,
    format_date,
    format_window,
    run_in_background,
    api,
)
from .parcel_helpers import load_my_parcels


PICKUP_SLOTS = [
    "08:00-10:00",
    "10:00-12:00",
    "12:00-14:00",
    "14:00-16:00",
    "16:00-18:00",
    "18:00-20:00",
]
EDITABLE_STATUSES = {"booked", "pickup_assigned"}


def _load_active_shipments() -> dict[str, list[dict]]:
    return {
        "sent": load_my_parcels("sent", "active"),
        "received": load_my_parcels("received", "active"),
    }


class ShipmentsInterface(QFrame):
    def __init__(self, text: str = "Shipments", parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))
        self.parcels_by_direction: dict[str, list[dict]] = {
            "sent": [],
            "received": [],
        }
        self.current_parcel: dict | None = None

        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(24, 16, 24, 16)

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.contentLayout = QVBoxLayout(self.content)
        self.contentLayout.setContentsMargins(12, 8, 12, 24)
        self.contentLayout.setSpacing(12)
        self.scrollArea.setWidget(self.content)
        self.mainLayout.addWidget(self.scrollArea)

        self.title = SubtitleLabel("Aktuális csomagjaim", self.content)
        setFont(self.title, 32, QFont.Weight.Bold)
        self.description = BodyLabel(
            "Itt követheted a feladott és érkező csomagjaidat. "
            "A még fel nem vett csomagokat a felvétel előtti napig módosíthatod.",
            self.content,
        )
        self.description.setStyleSheet("color: #6B6B6B;")
        self.description.setWordWrap(True)

        headerLayout = QHBoxLayout()
        headerLayout.addWidget(self.title)
        headerLayout.addStretch(1)
        self.refreshButton = PrimaryPushButton("Frissítés", self.content)
        self.refreshButton.clicked.connect(self.refresh)
        headerLayout.addWidget(self.refreshButton)
        self.contentLayout.addLayout(headerLayout)
        self.contentLayout.addWidget(self.description)

        self.messageLabel = QLabel(self.content)
        self.messageLabel.setWordWrap(True)
        self.contentLayout.addWidget(self.messageLabel)

        self.tabs = QTabWidget(self.content)
        self.sentTable = self._create_table()
        self.receivedTable = self._create_table()
        self.tabs.addTab(self.sentTable, "Feladott")
        self.tabs.addTab(self.receivedTable, "Érkező")
        self.contentLayout.addWidget(self.tabs)
        self.sentTable.itemSelectionChanged.connect(
            lambda: self._show_selected_parcel("sent")
        )
        self.receivedTable.itemSelectionChanged.connect(
            lambda: self._show_selected_parcel("received")
        )
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.editorFrame = QFrame(self.content)
        self.editorLayout = QVBoxLayout(self.editorFrame)
        self.editorLayout.setContentsMargins(0, 8, 0, 0)
        self.editorLayout.setSpacing(10)
        self.editorTitle = SubtitleLabel("Csomag adatai", self.editorFrame)
        setFont(self.editorTitle, 20, QFont.Weight.DemiBold)
        self.editorLayout.addWidget(self.editorTitle)
        self.detailsLabel = QLabel(self.editorFrame)
        self.detailsLabel.setWordWrap(True)
        self.editorLayout.addWidget(self.detailsLabel)
        self.editorMessage = QLabel(self.editorFrame)
        self.editorMessage.setWordWrap(True)
        self.editorLayout.addWidget(self.editorMessage)

        self.editForm = QWidget(self.editorFrame)
        self.editFormLayout = QFormLayout(self.editForm)
        self.sizeCombo = ComboBox(self.editForm)
        self.sizeCombo.addItems(["S", "M", "L", "XL"])
        self.pickupDate = QDateEdit(self.editForm)
        self.pickupDate.setCalendarPopup(True)
        self.pickupDate.setDisplayFormat("yyyy-MM-dd")
        self.pickupDate.setMinimumDate(QDate.currentDate().addDays(1))
        self.pickupDate.setMinimumHeight(42)
        self.pickupSlot = ComboBox(self.editForm)
        self.pickupSlot.addItems(PICKUP_SLOTS)
        self.postalCodeEdit = LineEdit(self.editForm)
        self.cityEdit = LineEdit(self.editForm)
        self.streetEdit = LineEdit(self.editForm)
        self.houseNumberEdit = LineEdit(self.editForm)
        for field in (
            self.postalCodeEdit,
            self.cityEdit,
            self.streetEdit,
            self.houseNumberEdit,
        ):
            field.setClearButtonEnabled(True)
            field.setMinimumHeight(42)
        self.postalCodeEdit.setPlaceholderText("Irányítószám")
        self.cityEdit.setPlaceholderText("Város")
        self.streetEdit.setPlaceholderText("Utca, közterület")
        self.houseNumberEdit.setPlaceholderText("Házszám")
        self.editFormLayout.addRow("Csomagméret", self.sizeCombo)
        self.editFormLayout.addRow("Felvétel dátuma", self.pickupDate)
        self.editFormLayout.addRow("Felvételi idősáv", self.pickupSlot)
        self.editFormLayout.addRow("Címzett irányítószáma", self.postalCodeEdit)
        self.editFormLayout.addRow("Címzett városa", self.cityEdit)
        self.editFormLayout.addRow("Címzett utcája", self.streetEdit)
        self.editFormLayout.addRow("Címzett házszáma", self.houseNumberEdit)
        self.editorLayout.addWidget(self.editForm)

        self.saveButton = PrimaryPushButton("Módosítások mentése", self.editorFrame)
        self.saveButton.clicked.connect(self.save_changes)
        self.editorLayout.addWidget(self.saveButton)
        self.editorFrame.hide()
        self.contentLayout.addWidget(self.editorFrame)
        self.contentLayout.addStretch(1)
        self._update_success_message: str | None = None

    @staticmethod
    def _create_table() -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Csomagazonosító", "Állapot", "Méret", "Felvétel", "Másik fél"]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().hide()
        table.horizontalHeader().setStretchLastSection(True)
        table.setMinimumHeight(220)
        table.setMaximumHeight(320)
        return table

    def refresh(self) -> None:
        if not api.is_logged_in:
            self.messageLabel.setText("A csomagok megtekintéséhez jelentkezz be.")
            return
        if api.role != "customer":
            self.messageLabel.setText("Ez a felület regisztrált ügyfelek számára érhető el.")
            return

        self.refreshButton.setEnabled(False)
        self.messageLabel.setText("Csomagok betöltése...")
        run_in_background(
            _load_active_shipments,
            on_success=self._on_shipments_loaded,
            on_error=self._on_load_error,
        )

    def _on_shipments_loaded(self, parcels: dict[str, list[dict]]) -> None:
        self.refreshButton.setEnabled(True)
        self.parcels_by_direction = parcels
        self._populate_table(self.sentTable, parcels["sent"], "sent")
        self._populate_table(self.receivedTable, parcels["received"], "received")
        count = len(parcels["sent"]) + len(parcels["received"])
        if self._update_success_message is not None:
            self.messageLabel.setText(self._update_success_message)
            self._update_success_message = None
        else:
            self.messageLabel.setText(f"{count} aktuális csomag található.")
        self.editorFrame.hide()

    def _on_load_error(self, error: ApiError) -> None:
        self.refreshButton.setEnabled(True)
        self.messageLabel.setText(error.message)

    def _populate_table(
        self,
        table: QTableWidget,
        parcels: list[dict],
        direction: str,
    ) -> None:
        table.setRowCount(0)
        self.parcels_by_direction[direction] = parcels
        other_side = "recipient" if direction == "sent" else "sender"
        for parcel in parcels:
            row = table.rowCount()
            table.insertRow(row)
            person = parcel[other_side]
            values = (
                parcel["tracking_number"],
                STATUS_LABELS.get(parcel["status"], parcel["status"]),
                parcel["size"],
                f'{format_date(parcel["pickup_date"])} '
                f'({format_window(parcel["pickup_window_start"], parcel["pickup_window_end"])})',
                f'{person["last_name"]} {person["first_name"]}',
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))

    def _show_selected_parcel(self, direction: str) -> None:
        table = self.sentTable if direction == "sent" else self.receivedTable
        row = table.currentRow()
        if row < 0:
            return

        parcel = self.parcels_by_direction[direction][row]
        self.current_parcel = parcel
        self.editorFrame.show()
        sender = parcel["sender"]
        recipient = parcel["recipient"]
        pickup = (
            f'{format_date(parcel["pickup_date"])} '
            f'({format_window(parcel["pickup_window_start"], parcel["pickup_window_end"])})'
        )
        delivery = (
            f'{format_date(parcel["delivery_date"])} '
            f'({format_window(parcel["delivery_window_start"], parcel["delivery_window_end"])})'
        )
        self.detailsLabel.setText(
            f"Csomagazonosító: {parcel['tracking_number']}\n"
            f"Állapot: {STATUS_LABELS.get(parcel['status'], parcel['status'])} · "
            f"Méret: {parcel['size']}\n"
            f"Feladó: {sender['last_name']} {sender['first_name']}\n"
            f"Címzett: {recipient['last_name']} {recipient['first_name']}\n"
            f"Cím: {recipient['postal_code']} {recipient['city']}, "
            f"{recipient['street']} {recipient['house_number']}\n"
            f"Felvétel: {pickup}\nKiszállítás: {delivery}"
        )
        status = parcel["status"]
        editable = (
            direction == "sent"
            and status in EDITABLE_STATUSES
            and date.fromisoformat(parcel["pickup_date"]) > date.today()
        )
        if not editable:
            self.editForm.hide()
            self.saveButton.hide()
            if direction == "received":
                self.editorMessage.setText(
                    "A beérkező csomag adatait a feladó módosíthatja."
                )
            else:
                self.editorMessage.setText(
                    "Ez a csomag már nem módosítható. A módosítás határideje "
                    "a tervezett felvétel előtti naptári nap."
                )
            return

        self.editForm.show()
        self.saveButton.show()
        self.editorMessage.setText(
            f"Az előjegyzett csomag a felvétel előtti napig módosítható. "
            f"Azonosító: {parcel['tracking_number']}"
        )
        self.sizeCombo.setCurrentText(parcel["size"])
        self.pickupDate.setDate(
            QDate.fromString(parcel["pickup_date"], "yyyy-MM-dd")
        )
        self.pickupDate.setMinimumDate(QDate.currentDate().addDays(1))
        slot = format_window(
            parcel["pickup_window_start"],
            parcel["pickup_window_end"],
        ).replace("–", "-")
        self.pickupSlot.setCurrentText(slot)
        recipient = parcel["recipient"]
        self.postalCodeEdit.setText(recipient["postal_code"])
        self.cityEdit.setText(recipient["city"])
        self.streetEdit.setText(recipient["street"])
        self.houseNumberEdit.setText(recipient["house_number"])

    def _on_tab_changed(self, index: int) -> None:
        direction = "sent" if index == 0 else "received"
        table = self.sentTable if direction == "sent" else self.receivedTable
        if table.currentRow() >= 0:
            self._show_selected_parcel(direction)
        else:
            self.current_parcel = None
            self.editorFrame.hide()

    def save_changes(self) -> None:
        parcel = self.current_parcel
        if parcel is None:
            return

        self.messageLabel.clear()
        self.editorFrame.setEnabled(False)
        payload = {
            "size": self.sizeCombo.currentText(),
            "pickup_date": self.pickupDate.date().toString("yyyy-MM-dd"),
            "pickup_slot": self.pickupSlot.currentText(),
            "recipient_address": {
                "postal_code": self.postalCodeEdit.text().strip(),
                "city": self.cityEdit.text().strip(),
                "street": self.streetEdit.text().strip(),
                "house_number": self.houseNumberEdit.text().strip(),
            },
        }
        run_in_background(
            api.patch,
            f"/parcels/my/{parcel['id']}",
            json=payload,
            on_success=self._on_update_success,
            on_error=self._on_update_error,
        )

    def _on_update_success(self, parcel: dict[str, object]) -> None:
        self.editorFrame.setEnabled(True)
        self._update_success_message = (
            f"A(z) {parcel['tracking_number']} csomag adatai sikeresen módosultak."
        )
        self.refresh()

    def _on_update_error(self, error: ApiError) -> None:
        self.editorFrame.setEnabled(True)
        self.messageLabel.setText(error.message)