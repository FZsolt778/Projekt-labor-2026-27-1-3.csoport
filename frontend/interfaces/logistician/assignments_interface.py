# Logistician (and admin): parcels around the warehouse, check-in and courier assignment for one or more parcels
from datetime import date

from PySide6.QtCore import QDate, QItemSelectionModel
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QAbstractItemView, QDateEdit, QFrame, QHBoxLayout, QLabel, QListWidget, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    setFont,
)

from api_client import (
    STATUS_LABELS,
    TIME_SLOTS,
    ApiError,
    api,
    format_date,
    format_datetime,
    format_window,
    run_in_background,
)
from components.copy_button import CopyButton, add_copy_buttons
from ..admin.admin_helpers import (
    ERROR_STYLE,
    MUTED_STYLE,
    AdminPage,
    DateFilter,
    Pager,
    create_table,
    fill_table,
    full_name,
    set_message,
    text_or_none,
)

# Physically in the warehouse, the server counts the same against the capacity
IN_WAREHOUSE_STATUSES = ("in_warehouse", "delivery_assigned")
# What the server accepts for each operation (warehouse services)
ACTIONS = {
    "check_in": ("Beérkeztetés", {"picked_up", "failed"},
                 ""),
    "pickup": ("Felvétel kiosztása", {"booked", "pickup_assigned"},
               ""),
    "delivery": ("Kiszállítás kiosztása", {"in_warehouse", "delivery_assigned"},
                 ""),
}
DONE_MESSAGES = {
    "check_in": "{} csomag beérkeztetve.",
    "pickup": "{} csomag felvétele kiosztva.",
    "delivery": "{} csomag kiszállítása kiosztva.",
}
ENDPOINTS = {"check_in": "/warehouse/check-in", "pickup": "/warehouse/assign-pickup",
             "delivery": "/warehouse/assign-delivery"}


def _load(params: dict) -> dict:
    in_house = sum(api.get("/parcels", {"status": status, "limit": 1})["total"] for status in IN_WAREHOUSE_STATUSES)
    return {
        "page": api.get("/parcels", params),
        "couriers": api.get("/warehouse/couriers"),
        "warehouse": api.get("/warehouse"),
        "in_warehouse": in_house,
    }


def _post(path: str, body: dict, action: str, count: int) -> tuple[str, int]:
    api.post(path, body)
    return action, count


def _when(day: str | None, start: str | None, end: str | None) -> str:
    return f"{format_date(day)} {format_window(start, end)}" if day else "–"


def _slot(start: str | None, end: str | None) -> str | None:
    # "08:00:00", "10:00:00" -> "08:00-10:00", the form of the request
    return f"{start[:5]}-{end[:5]}" if start and end else None


def _address(contact: dict) -> str:
    return f"{contact['postal_code']} {contact['city']}, {contact['street']} {contact['house_number']}"


class AssignDialog(MessageBoxBase):

    def __init__(self, parent, couriers: list[dict], count: int, delivery: dict | None = None):
        super().__init__(parent)
        title = "Kiszállítás kiosztása" if delivery is not None else "Felvétel kiosztása"
        self.titleLabel = SubtitleLabel(title, self.widget)
        self.infoLabel = BodyLabel(f"{count} csomag", self.widget)
        self.infoLabel.setStyleSheet(MUTED_STYLE)
        self.courierBox = ComboBox(self.widget)
        self.courierBox.setPlaceholderText("Válassz futárt...")
        for courier in couriers:
            self.courierBox.addItem(full_name(courier), userData=courier["id"])
        self.courierBox.setCurrentIndex(-1)
        self.courierBox.currentIndexChanged.connect(lambda index: self.yesButton.setEnabled(index >= 0))
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.courierBox)
        if not couriers:
            empty = QLabel("Nincs aktív futár, akihez a csomag kiosztható.", self.widget)
            empty.setStyleSheet(ERROR_STYLE)
            self.viewLayout.addWidget(empty)

        self.deliveryDate: QDateEdit | None = None
        self.deliverySlot: ComboBox | None = None
        if delivery is not None:
            # Not in the past and not before the latest pickup of the chosen parcels (server rule)
            self.deliveryDate = QDateEdit(self.widget)
            self.deliveryDate.setCalendarPopup(True)
            self.deliveryDate.setDisplayFormat("yyyy-MM-dd")
            self.deliveryDate.setMinimumDate(delivery["min_date"])
            self.deliveryDate.setDate(delivery["date"])
            self.deliverySlot = ComboBox(self.widget)
            self.deliverySlot.addItems(TIME_SLOTS)
            if delivery["slot"] in TIME_SLOTS:
                self.deliverySlot.setCurrentText(delivery["slot"])
            self.viewLayout.addWidget(QLabel("Kiszállítás napja", self.widget))
            self.viewLayout.addWidget(self.deliveryDate)
            self.viewLayout.addWidget(QLabel("Kiszállítási idősáv", self.widget))
            self.viewLayout.addWidget(self.deliverySlot)

        self.yesButton.setText("Kiosztás")
        self.yesButton.setEnabled(False)
        self.cancelButton.setText("Mégse")
        self.widget.setMinimumWidth(380)

    def values(self) -> dict:
        body = {"courier_id": self.courierBox.currentData()}
        if self.deliveryDate is not None:
            body["delivery_date"] = self.deliveryDate.date().toString("yyyy-MM-dd")
            body["delivery_slot"] = self.deliverySlot.currentText()
        return body


class LogisticianInterface(AdminPage):

    def __init__(self, text: str = "Logistician Interface", parent=None):
        super().__init__(
            text.replace(" ", "-"),
            "Logisztika",
            ""
            ""
            "",
            parent,
        )
        self.parcels: list[dict] = []
        self.couriers: list[dict] = []
        self.detail_id: int | None = None
        self._keep_ids: set[int] = set()
        self._busy = False

        # The warehouse and its load (F-20)
        self.warehouseLabel = QLabel(self.content)
        setFont(self.warehouseLabel, 15, QFont.Weight.DemiBold)
        self.contentLayout.insertWidget(2, self.warehouseLabel)

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
        self.contentLayout.insertLayout(3, filters)
        self.pickupDayFilter = DateFilter("Felvétel napja", self.content)
        self.deliveryDayFilter = DateFilter("Kiszállítás napja", self.content)
        dayFilters = QHBoxLayout()
        dayFilters.addWidget(self.pickupDayFilter)
        dayFilters.addSpacing(24)
        dayFilters.addWidget(self.deliveryDayFilter)
        dayFilters.addStretch(1)
        self.contentLayout.insertLayout(4, dayFilters)

        self.actionButtons = {}
        actions = QHBoxLayout()
        for action, (label, _statuses, _rule) in ACTIONS.items():
            button = PrimaryPushButton(label, self.content)
            button.clicked.connect(lambda _checked=False, a=action: self._run(a))
            button.setEnabled(False)
            actions.addWidget(button)
            self.actionButtons[action] = button
        self.selectionLabel = QLabel(self.content)
        self.selectionLabel.setStyleSheet(MUTED_STYLE)
        actions.addSpacing(12)
        actions.addWidget(self.selectionLabel)
        actions.addStretch(1)
        self.contentLayout.addLayout(actions)
        self.ruleLabel = QLabel(self.content)
        self.ruleLabel.setWordWrap(True)
        self.ruleLabel.setStyleSheet(MUTED_STYLE)
        self.ruleLabel.hide()
        self.contentLayout.addWidget(self.ruleLabel)

        self.table = create_table(
            ["Csomagszám", "Állapot", "Méret", "Feladó", "Címzett", "Felvétel", "Kiszállítás",
             "Felvevő futár", "Kiszállító futár"],
            self.content,
            stretch=4,
        )
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.contentLayout.addWidget(self.table)
        self.pager = Pager(self.content)
        self.pager.pageChanged.connect(self.refresh)
        self.contentLayout.addWidget(self.pager)

        # Details of a single selected parcel, with the event log (F-15)
        self.detailFrame = QFrame(self.content)
        detailLayout = QVBoxLayout(self.detailFrame)
        detailLayout.setContentsMargins(0, 8, 0, 0)
        detailLayout.setSpacing(10)
        self.detailTitle = SubtitleLabel(self.detailFrame)
        setFont(self.detailTitle, 22, QFont.Weight.DemiBold)
        self.detailCopyButton = CopyButton(parent=self.detailFrame)
        titleRow = QHBoxLayout()
        titleRow.addWidget(self.detailTitle)
        titleRow.addWidget(self.detailCopyButton)
        titleRow.addStretch(1)
        detailLayout.addLayout(titleRow)
        self.detailLabel = QLabel(self.detailFrame)
        self.detailLabel.setWordWrap(True)
        detailLayout.addWidget(self.detailLabel)
        eventsTitle = SubtitleLabel("Eseménynapló", self.detailFrame)
        setFont(eventsTitle, 16, QFont.Weight.DemiBold)
        detailLayout.addWidget(eventsTitle)
        self.eventsList = QListWidget(self.detailFrame)
        self.eventsList.setMinimumHeight(200)
        detailLayout.addWidget(self.eventsList)
        self.detailFrame.hide()
        self.contentLayout.addWidget(self.detailFrame)
        self.contentLayout.addStretch(1)

    def showEvent(self, event) -> None:
        QFrame.showEvent(self, event)
        self.refresh()

    def can_load(self) -> bool:
        if api.is_logged_in and api.role in ("logistician", "admin"):
            return True
        self.show_message("Ez a felület raktárosok és adminisztrátorok számára érhető el.")
        return False

    # --- loading ---------------------------------------------------------

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
            "pickup_date": self.pickupDayFilter.value(),
            "delivery_date": self.deliveryDayFilter.value(),
        }
        self.refreshButton.setEnabled(False)
        self.show_message("Csomagok betöltése...")
        run_in_background(_load, params, on_success=self._on_loaded, on_error=self._on_load_error)

    def _on_loaded(self, result: dict) -> None:
        self.refreshButton.setEnabled(True)
        keep, self._keep_ids = self._keep_ids or self._selected_ids(), set()
        self.detail_id = None
        self.couriers = result["couriers"]
        chosen = self.courierFilter.currentData()
        self.courierFilter.clear()
        self.courierFilter.addItem("Minden futár", userData=None)
        for courier in self.couriers:
            self.courierFilter.addItem(full_name(courier), userData=courier["id"])
        self.courierFilter.setCurrentIndex(max(self.courierFilter.findData(chosen), 0))

        warehouse, inside = result["warehouse"], result["in_warehouse"]
        percent = inside / warehouse["capacity"] * 100
        self.warehouseLabel.setText(
            f"{warehouse['name']}: {inside} / {warehouse['capacity']} csomag a raktárban "
            f"({percent:.1f} %), szabad hely: {max(warehouse['capacity'] - inside, 0)}"
        )
        self.warehouseLabel.setStyleSheet(ERROR_STYLE if percent >= 90 else "")

        page = result["page"]
        self.parcels = page["items"]
        self.pager.set_page(page)
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
        add_copy_buttons(self.table, 0)
        self.show_message(f"{page['total']} csomag felel meg a szűrésnek.")
        # Keep the selection over a reload (e.g. after an operation)
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for row, parcel in enumerate(self.parcels):
            if parcel["id"] in keep:
                self.table.selectionModel().select(self.table.model().index(row, 0), flags)
        self._on_selection_changed()

    def _on_load_error(self, error: ApiError) -> None:
        self.refreshButton.setEnabled(True)
        self.show_message(error.message, error=True)

    # --- selection and details -------------------------------------------

    def _selected(self) -> list[dict]:
        rows = sorted(index.row() for index in self.table.selectionModel().selectedRows())
        return [self.parcels[row] for row in rows if row < len(self.parcels)]

    def _selected_ids(self) -> set[int]:
        return {parcel["id"] for parcel in self._selected()}

    def _on_selection_changed(self) -> None:
        selected = self._selected()
        statuses = {parcel["status"] for parcel in selected}
        rules = []
        for action, (_label, allowed, rule) in ACTIONS.items():
            enabled = bool(selected) and statuses <= allowed and not self._busy
            self.actionButtons[action].setEnabled(enabled)
            if selected and not statuses <= allowed:
                rules.append(rule)
        self.selectionLabel.setText(f"{len(selected)} csomag kijelölve" if selected else "Jelölj ki csomagot a művelethez.")
        self.ruleLabel.setText("\n".join(rules))
        self.ruleLabel.setVisible(bool(rules))

        if len(selected) != 1:
            self.detail_id = None
            self.detailFrame.hide()
            return
        parcel = selected[0]
        if parcel["id"] == self.detail_id and self.detailFrame.isVisible():
            return
        self.detail_id = parcel["id"]
        self.detailTitle.setText(parcel["tracking_number"])
        self.detailCopyButton.value = parcel["tracking_number"]
        self.detailLabel.setText("Részletek betöltése...")
        self.eventsList.clear()
        self.detailFrame.show()
        run_in_background(api.get, f"/parcels/{parcel['id']}", on_success=self._on_detail_loaded,
                          on_error=self._on_detail_error)

    def _on_detail_loaded(self, parcel: dict) -> None:
        if parcel["id"] != self.detail_id:
            return
        sender, recipient = parcel["sender"], parcel["recipient"]
        lines = [
            f"{STATUS_LABELS.get(parcel['status'], parcel['status'])} · Méret: {parcel['size']}",
            f"Feladó: {full_name(sender)}, {_address(sender)}, {sender.get('phone') or 'nincs telefonszám'}",
            f"Címzett: {full_name(recipient)}, {_address(recipient)}, {recipient.get('phone') or 'nincs telefonszám'}",
            f"Felvétel: {_when(parcel['pickup_date'], parcel['pickup_window_start'], parcel['pickup_window_end'])}"
            f" · futár: {full_name(parcel['pickup_courier'])}",
            f"Kiszállítás: {_when(parcel['delivery_date'], parcel['delivery_window_start'], parcel['delivery_window_end'])}"
            f" · futár: {full_name(parcel['delivery_courier'])}",
        ]
        milestones = [("Felvéve", parcel["picked_up_at"]), ("Raktárba érkezett", parcel["warehouse_arrived_at"]),
                      ("Kiszállításra indult", parcel["out_for_delivery_at"]), ("Kézbesítve", parcel["delivered_at"])]
        done = [f"{label}: {format_datetime(value)}" for label, value in milestones if value]
        if done:
            lines.append(" · ".join(done))
        # Also resets the error colour of an earlier failed load
        set_message(self.detailLabel, "\n".join(lines))
        self.eventsList.clear()
        for event in parcel["events"]:
            line = f"{format_datetime(event['occurred_at'])} — {STATUS_LABELS.get(event['status'], event['status'])}"
            if event["courier"]:
                line += f" · Futár: {full_name(event['courier'])}"
            line += f" · Rögzítette: {full_name(event['actor']) if event['actor'] else 'vendég'}"
            if event["note"]:
                line += f"\n{event['note']}"
            self.eventsList.addItem(line)

    def _on_detail_error(self, error: ApiError) -> None:
        set_message(self.detailLabel, error.message, error=True)

    # --- operations ----------------------------------------------------------

    def _run(self, action: str) -> None:
        selected = self._selected()
        if not selected or self._busy:
            return
        body = {"tracking_numbers": [parcel["tracking_number"] for parcel in selected]}
        if action != "check_in":
            delivery = self._delivery_defaults(selected) if action == "delivery" else None
            dialog = AssignDialog(self.window(), self.couriers, len(selected), delivery)
            try:
                if not dialog.exec():
                    return
                body.update(dialog.values())
            finally:
                dialog.deleteLater()
        self._busy = True
        self._keep_ids = {parcel["id"] for parcel in selected}
        self._on_selection_changed()
        run_in_background(_post, ENDPOINTS[action], body, action, len(selected),
                          on_success=self._on_action_done, on_error=self._on_action_error)

    @staticmethod
    def _delivery_defaults(selected: list[dict]) -> dict:
        latest_pickup = max(date.fromisoformat(parcel["pickup_date"]) for parcel in selected)
        min_date = QDate(max(date.today(), latest_pickup))
        default, slot = min_date, None
        # A single, already scheduled parcel keeps its time as the starting point
        if len(selected) == 1 and selected[0]["delivery_date"]:
            current = QDate.fromString(selected[0]["delivery_date"], "yyyy-MM-dd")
            default = current if current >= min_date else min_date
            slot = _slot(selected[0]["delivery_window_start"], selected[0]["delivery_window_end"])
        return {"min_date": min_date, "date": default, "slot": slot}

    def _on_action_done(self, result: tuple[str, int]) -> None:
        action, count = result
        self._busy = False
        self._notify(InfoBar.success, "Sikeres művelet", DONE_MESSAGES[action].format(count))
        self.refresh()

    def _on_action_error(self, error: ApiError) -> None:
        self._busy = False
        # The server names every parcel that blocked the operation
        self._notify(InfoBar.error, "Sikertelen művelet", error.message)
        self.refresh()

    def _notify(self, show, title: str, content: str) -> None:
        show(title=title, content=content, isClosable=True, position=InfoBarPosition.TOP_RIGHT,
             duration=6000, parent=self)
