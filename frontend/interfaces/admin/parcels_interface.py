# Admin: all parcels, details with the event log, edit, courier change, cancel, delete
from PySide6.QtCore import QDate
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CheckBox, ComboBox, LineEdit, PrimaryPushButton, PushButton, SubtitleLabel, setFont

from api_client import (
    SIZES,
    STATUS_LABELS,
    TIME_SLOTS,
    ApiError,
    api,
    format_date,
    format_datetime,
    format_window,
    run_in_background,
)
from .admin_helpers import (
    FORM_MAX_WIDTH,
    MUTED_STYLE,
    AdminPage,
    Pager,
    button_row,
    confirm,
    create_table,
    fill_table,
    full_name,
    select_by_id,
    selected_row,
    set_message,
    text_or_none,
)

CLOSED_STATUSES = {"delivered", "cancelled"}
# Statuses in which the server accepts a courier change
PICKUP_COURIER_STATUSES = {"booked", "pickup_assigned", "picked_up"}
DELIVERY_COURIER_STATUSES = {"in_warehouse", "delivery_assigned", "out_for_delivery", "failed"}
CONTACT_FIELDS = {
    "last_name": "Vezetéknév",
    "first_name": "Keresztnév",
    "email": "Email cím",
    "phone": "Telefonszám",
    "postal_code": "Irányítószám",
    "city": "Település",
    "street": "Utca",
    "house_number": "Házszám",
}
SIDES = {"sender": "Feladó", "recipient": "Címzett"}


def _load(params: dict) -> dict:
    # Active couriers for the filter and the courier lists, then one page of parcels
    return {"couriers": api.get("/warehouse/couriers"), "page": api.get("/parcels", params)}


def _slot(start: str | None, end: str | None) -> str | None:
    # "08:00:00", "10:00:00" -> "08:00-10:00", the form of the request
    return f"{start[:5]}-{end[:5]}" if start and end else None


def _when(day: str | None, start: str | None, end: str | None) -> str:
    return f"{format_date(day)} ({format_window(start, end)})" if day else "nincs megadva"


def _contact_line(contact: dict) -> str:
    phone = f", {contact['phone']}" if contact["phone"] else ""
    return (
        f"{full_name(contact)} ({contact['email']}{phone}), "
        f"{contact['postal_code']} {contact['city']}, {contact['street']} {contact['house_number']}"
    )


class ParcelsInterface(AdminPage):
    def __init__(self, text: str = "Admin Parcels", parent=None):
        super().__init__(
            text.replace(" ", "-"),
            "Csomagok",
            ""
            "",
            parent,
        )
        self.parcels: list[dict] = []
        self.couriers: list[dict] = []
        self.selected_id: int | None = None
        self.current: dict | None = None
        self._notice: str | None = None

        filters = QHBoxLayout()
        self.searchEdit = LineEdit(self.content)
        self.searchEdit.setPlaceholderText("Csomagszám, feladó vagy címzett neve")
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.returnPressed.connect(self._apply_filters)
        self.statusFilter = ComboBox(self.content)
        self.statusFilter.addItem("Minden állapot", userData=None)
        for status, label in STATUS_LABELS.items():
            self.statusFilter.addItem(label, userData=status)
        self.courierFilter = ComboBox(self.content)
        self.courierFilter.addItem("Minden futár", userData=None)
        self.filterButton = PushButton("Szűrés", self.content)
        self.filterButton.clicked.connect(self._apply_filters)
        filters.addWidget(self.searchEdit, 2)
        filters.addWidget(self.statusFilter, 1)
        filters.addWidget(self.courierFilter, 1)
        filters.addWidget(self.filterButton)
        self.contentLayout.insertLayout(2, filters)

        self.table = create_table(
            ["Csomagszám", "Állapot", "Méret", "Feladó", "Címzett", "Felvétel", "Kiszállítás",
             "Felvevő futár", "Kiszállító futár"],
            self.content,
            stretch=4,
        )
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.contentLayout.addWidget(self.table)
        self.pager = Pager(self.content)
        self.pager.pageChanged.connect(self.refresh)
        self.contentLayout.addWidget(self.pager)

        self.detailFrame = QFrame(self.content)
        self.detailLayout = QVBoxLayout(self.detailFrame)
        self.detailLayout.setContentsMargins(0, 8, 0, 0)
        self.detailLayout.setSpacing(10)
        self.detailTitle = SubtitleLabel(self.detailFrame)
        setFont(self.detailTitle, 22, QFont.Weight.DemiBold)
        self.detailLayout.addWidget(self.detailTitle)
        self.detailMessage = QLabel(self.detailFrame)
        self.detailMessage.setWordWrap(True)
        self.detailLayout.addWidget(self.detailMessage)
        self.detailsLabel = QLabel(self.detailFrame)
        self.detailsLabel.setWordWrap(True)
        self.detailLayout.addWidget(self.detailsLabel)

        self._build_data_section()
        self._build_courier_section()
        self._build_action_section()

        self._add_section_title("Események")
        self.eventsList = QListWidget(self.detailFrame)
        self.eventsList.setMinimumHeight(240)
        self.detailLayout.addWidget(self.eventsList)

        self.detailFrame.hide()
        self.contentLayout.addWidget(self.detailFrame)
        self.contentLayout.addStretch(1)

    # --- Layout ---

    def _add_section_title(self, text: str) -> None:
        title = SubtitleLabel(text, self.detailFrame)
        setFont(title, 18, QFont.Weight.DemiBold)
        self.detailLayout.addWidget(title)

    @staticmethod
    def _date_edit(parent: QWidget) -> QDateEdit:
        edit = QDateEdit(parent)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setMinimumHeight(42)
        return edit

    def _build_data_section(self) -> None:
        self._add_section_title("Adatok")
        self.dataTabs = QTabWidget(self.detailFrame)

        parcelTab = QWidget()
        form = QFormLayout(parcelTab)
        self.sizeCombo = ComboBox(parcelTab)
        self.sizeCombo.addItems(SIZES)
        self.pickupDate = self._date_edit(parcelTab)
        self.pickupSlot = ComboBox(parcelTab)
        self.pickupSlot.addItems(TIME_SLOTS)
        self.deliveryCheck = CheckBox("Van kiszállítási időpont", parcelTab)
        self.deliveryDate = self._date_edit(parcelTab)
        self.deliverySlot = ComboBox(parcelTab)
        self.deliverySlot.addItems(TIME_SLOTS)
        self.deliveryCheck.toggled.connect(self.deliveryDate.setEnabled)
        self.deliveryCheck.toggled.connect(self.deliverySlot.setEnabled)
        form.addRow("Méret", self.sizeCombo)
        form.addRow("Felvétel napja", self.pickupDate)
        form.addRow("Felvételi idősáv", self.pickupSlot)
        form.addRow("", self.deliveryCheck)
        form.addRow("Kiszállítás napja", self.deliveryDate)
        form.addRow("Kiszállítási idősáv", self.deliverySlot)
        self.dataTabs.addTab(parcelTab, "Csomag")

        self.contactFields: dict[str, dict[str, LineEdit]] = {}
        for side, label in SIDES.items():
            tab = QWidget()
            sideForm = QFormLayout(tab)
            self.contactFields[side] = {}
            for field, field_label in CONTACT_FIELDS.items():
                edit = LineEdit(tab)
                edit.setMinimumHeight(42)
                sideForm.addRow(field_label, edit)
                self.contactFields[side][field] = edit
            self.dataTabs.addTab(tab, label)
        self.dataTabs.setMaximumWidth(FORM_MAX_WIDTH)
        self.detailLayout.addWidget(self.dataTabs)

        self.saveDataButton = PrimaryPushButton("Adatok mentése", self.detailFrame)
        self.saveDataButton.clicked.connect(self.save_data)
        self.detailLayout.addLayout(button_row(self.saveDataButton))

    def _build_courier_section(self) -> None:
        self._add_section_title("Futárok")
        self.courierFrame = QFrame(self.detailFrame)
        self.courierFrame.setMaximumWidth(FORM_MAX_WIDTH)
        form = QFormLayout(self.courierFrame)
        form.setContentsMargins(0, 0, 0, 0)
        self.pickupCourierCombo = ComboBox(self.courierFrame)
        self.deliveryCourierCombo = ComboBox(self.courierFrame)
        form.addRow("Felvevő futár", self.pickupCourierCombo)
        form.addRow("Kiszállító futár", self.deliveryCourierCombo)
        self.detailLayout.addWidget(self.courierFrame)
        self.courierHint = QLabel(self.detailFrame)
        self.courierHint.setWordWrap(True)
        self.courierHint.setStyleSheet(MUTED_STYLE)
        self.detailLayout.addWidget(self.courierHint)
        self.saveCouriersButton = PrimaryPushButton("Futárok mentése", self.detailFrame)
        self.saveCouriersButton.clicked.connect(self.save_couriers)
        self.detailLayout.addLayout(button_row(self.saveCouriersButton))

    def _build_action_section(self) -> None:
        self._add_section_title("Műveletek")
        self.cancelParcelButton = PushButton("Lemondás", self.detailFrame)
        self.cancelParcelButton.clicked.connect(self.cancel_parcel)
        self.deleteButton = PushButton("Végleges törlés", self.detailFrame)
        self.deleteButton.clicked.connect(self.delete_parcel)
        self.detailLayout.addLayout(button_row(self.cancelParcelButton, self.deleteButton))

    # --- List ---

    def _apply_filters(self) -> None:
        self.pager.reset()
        self.refresh()

    def refresh(self) -> None:
        if not self.can_load():
            return
        params = {
            **self.pager.params(),
            "search": text_or_none(self.searchEdit),
            "status": self.statusFilter.currentData(),
            "courier_id": self.courierFilter.currentData(),
        }
        self.refreshButton.setEnabled(False)
        self.show_message("Csomagok betöltése...")
        run_in_background(_load, params, on_success=self._on_loaded, on_error=self._on_load_error)

    def _on_loaded(self, result: dict) -> None:
        self.refreshButton.setEnabled(True)
        self.couriers = result["couriers"]
        chosen = self.courierFilter.currentData()
        self.courierFilter.clear()
        self.courierFilter.addItem("Minden futár", userData=None)
        for courier in self.couriers:
            self.courierFilter.addItem(full_name(courier), userData=courier["id"])
        self.courierFilter.setCurrentIndex(max(self.courierFilter.findData(chosen), 0))

        page = result["page"]
        self.parcels = page["items"]
        self.pager.set_page(page)
        self.detailFrame.hide()
        selected_id, self.selected_id, self.current = self.selected_id, None, None
        fill_table(self.table, [
            [
                parcel["tracking_number"],
                STATUS_LABELS.get(parcel["status"], parcel["status"]),
                parcel["size"],
                full_name(parcel["sender"]),
                full_name(parcel["recipient"]),
                _when(parcel["pickup_date"], parcel["pickup_window_start"], parcel["pickup_window_end"]),
                _when(parcel["delivery_date"], parcel["delivery_window_start"], parcel["delivery_window_end"]),
                full_name(parcel["pickup_courier"]),
                full_name(parcel["delivery_courier"]),
            ]
            for parcel in self.parcels
        ])
        self.show_message(self._notice or f"{page['total']} csomag felel meg a szűrésnek.")
        self._notice = None
        select_by_id(self.table, self.parcels, selected_id)

    def _on_load_error(self, error: ApiError) -> None:
        self.refreshButton.setEnabled(True)
        self.show_message(error.message, error=True)

    def _on_selection_changed(self) -> None:
        row = selected_row(self.table)
        if not 0 <= row < len(self.parcels):
            return
        parcel_id = self.parcels[row]["id"]
        self.selected_id, self.current = parcel_id, None
        self.detailTitle.setText(self.parcels[row]["tracking_number"])
        set_message(self.detailMessage, "Részletek betöltése...")
        self.detailFrame.setEnabled(False)
        self.detailFrame.show()
        run_in_background(
            api.get, f"/parcels/{parcel_id}",
            on_success=lambda detail: self._on_detail_loaded(parcel_id, detail),
            on_error=lambda error: self._on_detail_error(parcel_id, error),
        )

    # --- Details ---

    def _on_detail_loaded(self, parcel_id: int, parcel: dict) -> None:
        if parcel_id != self.selected_id:
            return
        self.current = parcel
        status = parcel["status"]
        closed = status in CLOSED_STATUSES
        milestones = [
            ("Felvéve", parcel["picked_up_at"]),
            ("Raktárba érkezett", parcel["warehouse_arrived_at"]),
            ("Kiszállításra indult", parcel["out_for_delivery_at"]),
            ("Kézbesítve", parcel["delivered_at"]),
        ]

        self._fill_data_form(parcel)
        self._fill_courier_form(parcel)
        self.cancelParcelButton.setEnabled(not closed)
        self.eventsList.clear()
        for event in parcel["events"]:
            line = f"{format_datetime(event['occurred_at'])} — {STATUS_LABELS.get(event['status'], event['status'])}"
            if event["courier"]:
                line += f" · Futár: {full_name(event['courier'])}"
            line += f" · Rögzítette: {full_name(event['actor']) if event['actor'] else 'vendég'}"
            if event["note"]:
                line += f"\n{event['note']}"
            self.eventsList.addItem(line)
        set_message(self.detailMessage, "")
        self.detailFrame.setEnabled(True)

    def _on_detail_error(self, parcel_id: int, error: ApiError) -> None:
        if parcel_id != self.selected_id:
            return
        self.detailFrame.setEnabled(True)
        set_message(self.detailMessage, error.message, error=True)

    def _fill_data_form(self, parcel: dict) -> None:
        self.sizeCombo.setCurrentText(parcel["size"])
        self.pickupDate.setDate(QDate.fromString(parcel["pickup_date"], "yyyy-MM-dd"))
        self.pickupSlot.setCurrentText(_slot(parcel["pickup_window_start"], parcel["pickup_window_end"]))
        has_delivery = parcel["delivery_date"] is not None
        self.deliveryCheck.setChecked(has_delivery)
        self.deliveryDate.setEnabled(has_delivery)
        self.deliverySlot.setEnabled(has_delivery)
        if has_delivery:
            self.deliveryDate.setDate(QDate.fromString(parcel["delivery_date"], "yyyy-MM-dd"))
            self.deliverySlot.setCurrentText(_slot(parcel["delivery_window_start"], parcel["delivery_window_end"]))
        else:
            self.deliveryDate.setDate(QDate.fromString(parcel["pickup_date"], "yyyy-MM-dd"))
            self.deliverySlot.setCurrentIndex(0)
        for side in SIDES:
            for field, edit in self.contactFields[side].items():
                edit.setText(parcel[side][field] or "")

    def _fill_courier_form(self, parcel: dict) -> None:
        status = parcel["status"]
        for combo, key, allowed in (
            (self.pickupCourierCombo, "pickup_courier", PICKUP_COURIER_STATUSES),
            (self.deliveryCourierCombo, "delivery_courier", DELIVERY_COURIER_STATUSES),
        ):
            assigned = parcel[key]
            combo.clear()
            combo.addItem("– nincs –", userData=None)
            for courier in self.couriers:
                combo.addItem(full_name(courier), userData=courier["id"])
            if assigned is not None and combo.findData(assigned["id"]) < 0:
                # Assigned, but no longer an active courier
                combo.addItem(f"{full_name(assigned)} (inaktív)", userData=assigned["id"])
            combo.setCurrentIndex(max(combo.findData(assigned["id"] if assigned else None), 0))
            combo.setEnabled(status in allowed)
        if status in CLOSED_STATUSES:
            hint = "Lezárt csomag: a futárok már nem módosíthatók, és a csomag nem mondható le."
        else:
            hint = (
                ""
                ""
            )
        self.courierHint.setText(hint)
        self.saveCouriersButton.setEnabled(status not in CLOSED_STATUSES)

    # --- Actions ---

    def save_data(self) -> None:
        parcel = self.current
        if parcel is None:
            return
        body: dict = {}
        if self.sizeCombo.currentText() != parcel["size"]:
            body["size"] = self.sizeCombo.currentText()
        pickup_date = self.pickupDate.date().toString("yyyy-MM-dd")
        if pickup_date != parcel["pickup_date"]:
            body["pickup_date"] = pickup_date
        if self.pickupSlot.currentText() != _slot(parcel["pickup_window_start"], parcel["pickup_window_end"]):
            body["pickup_slot"] = self.pickupSlot.currentText()
        if self.deliveryCheck.isChecked():
            delivery = (self.deliveryDate.date().toString("yyyy-MM-dd"), self.deliverySlot.currentText())
        else:
            delivery = (None, None)
        if delivery != (parcel["delivery_date"], _slot(parcel["delivery_window_start"], parcel["delivery_window_end"])):
            # The server expects the day and the slot together
            body["delivery_date"], body["delivery_slot"] = delivery

        for side, side_label in SIDES.items():
            values = {field: text_or_none(edit) for field, edit in self.contactFields[side].items()}
            missing = [label for field, label in CONTACT_FIELDS.items() if field != "phone" and not values[field]]
            if missing:
                set_message(self.detailMessage, f"{side_label}: kötelező mező: " + ", ".join(missing), error=True)
                return
            changes = {field: value for field, value in values.items() if value != parcel[side][field]}
            if changes:
                body[side] = changes

        if not body:
            set_message(self.detailMessage, "Nincs módosítás.")
            return
        self._run((api.patch, f"/parcels/{parcel['id']}", body), "adatai elmentve")

    def save_couriers(self) -> None:
        parcel = self.current
        if parcel is None:
            return
        body = {}
        for combo, key in ((self.pickupCourierCombo, "pickup_courier"), (self.deliveryCourierCombo, "delivery_courier")):
            assigned = parcel[key]["id"] if parcel[key] else None
            if combo.isEnabled() and combo.currentData() != assigned:
                body[f"{key}_id"] = combo.currentData()
        if not body:
            set_message(self.detailMessage, "Nincs módosítás.")
            return
        self._run((api.patch, f"/parcels/{parcel['id']}/couriers", body), "futárai elmentve")

    def cancel_parcel(self) -> None:
        parcel = self.current
        if parcel is None or not confirm(
            self, "Csomag lemondása",
            f"A(z) {parcel['tracking_number']} csomag lemondott állapotba kerül, és már nem lehet folytatni "
            "a szállítását. Az adatai és az eseménynaplója megmaradnak.",
            "Lemondás",
        ):
            return
        self._run((api.post, f"/parcels/{parcel['id']}/cancel"), "lemondva")

    def delete_parcel(self) -> None:
        parcel = self.current
        if parcel is None or not confirm(
            self, "Csomag végleges törlése",
            f"A(z) {parcel['tracking_number']} csomag az eseménynaplójával együtt véglegesen törlődik. "
            "Ez nem vonható vissza. Ha csak a szállítást kell leállítani, használd a lemondást.",
            "Végleges törlés",
        ):
            return
        self._run((api.delete, f"/parcels/{parcel['id']}"), "törölve")
        # Nothing to reselect after the reload
        self.selected_id = None

    def _run(self, call: tuple, done: str) -> None:
        # call: (api method, path[, body])
        tracking = self.current["tracking_number"]
        self.detailFrame.setEnabled(False)
        set_message(self.detailMessage, "Mentés...")
        run_in_background(
            *call,
            on_success=lambda _: self._after_action(f"A(z) {tracking} csomag {done}."),
            on_error=self._on_action_error,
        )

    def _after_action(self, notice: str) -> None:
        self._notice = notice
        self.refresh()

    def _on_action_error(self, error: ApiError) -> None:
        if self.current is not None:
            self.selected_id = self.current["id"]
        self.detailFrame.setEnabled(True)
        set_message(self.detailMessage, error.message, error=True)
