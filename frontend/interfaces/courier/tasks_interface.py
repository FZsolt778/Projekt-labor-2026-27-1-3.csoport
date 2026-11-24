from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    setFont,
)

from api_client import STATUS_LABELS, TASK_LABELS, ApiError, api, format_date, format_window, run_in_background
from components.copy_button import CopyButton, add_copy_buttons
from ..admin.admin_helpers import create_table, selected_row
from .courier_actions import (
    ACTION_LABELS,
    DELIVER,
    FAIL,
    PICKUP,
    START,
    SUCCESS_MESSAGES,
    ask_fail_note,
    available_actions,
    waiting_hint,
)

MUTED_STYLE = "color: #6B6B6B;"


def _contact(task: dict) -> dict:
    parcel = task["parcel"]
    return parcel["sender"] if task["task"] == "pickup" else parcel["recipient"]


def _name(contact: dict) -> str:
    return f'{contact["last_name"]} {contact["first_name"]}'


def _address(contact: dict) -> str:
    return f'{contact["postal_code"]} {contact["city"]}, {contact["street"]} {contact["house_number"]}'


def _when(task: dict) -> str:
    parcel = task["parcel"]
    if task["task"] == "pickup":
        day, start, end = parcel["pickup_date"], parcel["pickup_window_start"], parcel["pickup_window_end"]
    else:
        day, start, end = parcel["delivery_date"], parcel["delivery_window_start"], parcel["delivery_window_end"]
    return f"{format_date(day)} {format_window(start, end)}" if day else "–"


def _load_tasks(request: int, params: dict) -> tuple[int, list[dict]]:
    return request, api.get("/courier/tasks", params)


def _post_action(number: str, action: str, body: dict | None) -> tuple[str, str]:
    api.post(f"/courier/parcels/{number}/{action}", body)
    return action, number


def _matches(task: dict, query: str) -> bool:
    parcel = task["parcel"]
    parts = [parcel["tracking_number"]]
    for contact in (parcel["sender"], parcel["recipient"]):
        parts += [_name(contact), f'{contact["first_name"]} {contact["last_name"]}', _address(contact),
                  contact.get("phone") or "", contact["email"]]
    return query in " ".join(parts).casefold()


class TasksInterface(QFrame):

    def __init__(self, text: str = "Courier Tasks", parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))
        self.tasks: list[dict] = []
        self.visible: list[dict] = []
        self.selected_id: int | None = None
        self._request = 0
        self._filling = False
        self._busy = False

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

        self.title = SubtitleLabel("Feladataim", self.content)
        setFont(self.title, 32, QFont.Weight.Bold)
        self.refreshButton = PrimaryPushButton("Frissítés", self.content)
        self.refreshButton.clicked.connect(self.refresh)
        headerLayout = QHBoxLayout()
        headerLayout.addWidget(self.title)
        headerLayout.addStretch(1)
        headerLayout.addWidget(self.refreshButton)
        self.contentLayout.addLayout(headerLayout)

        self.description = BodyLabel(
            ""
            "",
            self.content,
        )
        self.description.setStyleSheet(MUTED_STYLE)
        self.description.setWordWrap(True)
        self.contentLayout.addWidget(self.description)

        self.searchEdit = LineEdit(self.content)
        self.searchEdit.setPlaceholderText("Keresés: csomagszám, név, cím, telefonszám")
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.textChanged.connect(self._apply_search)
        self.taskFilter = ComboBox(self.content)
        for label, value in (("Minden feladat", None), ("Felvételek", "pickup"), ("Kiszállítások", "delivery")):
            self.taskFilter.addItem(label, userData=value)
        self.dayFilter = ComboBox(self.content)
        for label, offset in (("Minden nap", None), ("Ma", 0), ("Holnap", 1)):
            self.dayFilter.addItem(label, userData=offset)
        self.taskFilter.currentIndexChanged.connect(self.refresh)
        self.dayFilter.currentIndexChanged.connect(self.refresh)
        filters = QHBoxLayout()
        filters.addWidget(self.searchEdit, 3)
        filters.addWidget(self.taskFilter, 1)
        filters.addWidget(self.dayFilter, 1)
        self.contentLayout.addLayout(filters)

        self.messageLabel = QLabel(self.content)
        self.messageLabel.setWordWrap(True)
        self.contentLayout.addWidget(self.messageLabel)

        self.table = create_table(
            ["Csomagszám", "Feladat", "Állapot", "Időpont", "Név", "Cím", "Telefon", "Méret"],
            self.content,
            stretch=5,
        )
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.contentLayout.addWidget(self.table)

        self.detailFrame = QFrame(self.content)
        self.detailLayout = QVBoxLayout(self.detailFrame)
        self.detailLayout.setContentsMargins(0, 8, 0, 0)
        self.detailLayout.setSpacing(10)
        self.detailTitle = SubtitleLabel(self.detailFrame)
        setFont(self.detailTitle, 22, QFont.Weight.DemiBold)
        self.detailCopyButton = CopyButton(parent=self.detailFrame)
        titleRow = QHBoxLayout()
        titleRow.addWidget(self.detailTitle)
        titleRow.addWidget(self.detailCopyButton)
        titleRow.addStretch(1)
        self.detailLayout.addLayout(titleRow)
        self.detailLabel = QLabel(self.detailFrame)
        self.detailLabel.setWordWrap(True)
        self.detailLayout.addWidget(self.detailLabel)
        self.hintLabel = QLabel(self.detailFrame)
        self.hintLabel.setWordWrap(True)
        self.hintLabel.setStyleSheet(MUTED_STYLE)
        self.detailLayout.addWidget(self.hintLabel)

        self.actionButtons = {}
        actions = QHBoxLayout()
        for action in (PICKUP, START, DELIVER, FAIL):
            button_type = PushButton if action == FAIL else PrimaryPushButton
            button = button_type(ACTION_LABELS[action], self.detailFrame)
            button.clicked.connect(lambda _checked=False, a=action: self._run(a))
            actions.addWidget(button)
            self.actionButtons[action] = button
        actions.addStretch(1)
        self.detailLayout.addLayout(actions)
        self.detailFrame.hide()
        self.contentLayout.addWidget(self.detailFrame)
        self.contentLayout.addStretch(1)

    # Fresh list every time the page is opened
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    # --- loading ---------------------------------------------------

    def refresh(self) -> None:
        if not api.is_logged_in or api.role != "courier":
            self.messageLabel.setText("Ez a felület futárok számára érhető el.")
            return
        params = {}
        if self.taskFilter.currentData() is not None:
            params["task"] = self.taskFilter.currentData()
        offset = self.dayFilter.currentData()
        if offset is not None:
            params["day"] = (date.today() + timedelta(days=offset)).isoformat()
        self._request += 1
        request = self._request
        self.refreshButton.setEnabled(False)
        self.messageLabel.setText("Feladatok betöltése...")
        run_in_background(_load_tasks, request, params, on_success=self._on_loaded, on_error=self._on_load_error)

    def _on_loaded(self, result: tuple[int, list[dict]]) -> None:
        request, tasks = result
        if request != self._request:
            return
        self.refreshButton.setEnabled(True)
        self.tasks = tasks
        self._apply_search()

    def _on_load_error(self, error: ApiError) -> None:
        self.refreshButton.setEnabled(True)
        self.messageLabel.setText(error.message)

    def _apply_search(self) -> None:
        query = self.searchEdit.text().strip().casefold()
        self.visible = [task for task in self.tasks if not query or _matches(task, query)]
        self._filling = True
        self.table.setRowCount(0)
        for task in self.visible:
            parcel, contact = task["parcel"], _contact(task)
            values = [
                parcel["tracking_number"],
                TASK_LABELS.get(task["task"], task["task"]),
                STATUS_LABELS.get(parcel["status"], parcel["status"]),
                _when(task),
                _name(contact),
                _address(contact),
                contact.get("phone") or "–",
                parcel["size"],
            ]
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        add_copy_buttons(self.table, 0)
        self._filling = False
        self.messageLabel.setText(self._summary(query))

        ids = [task["parcel"]["id"] for task in self.visible]
        if self.selected_id in ids:
            self.table.selectRow(ids.index(self.selected_id))
            self._show_detail(self.visible[ids.index(self.selected_id)])
        else:
            self.selected_id = None
            self.detailFrame.hide()

    def _summary(self, query: str) -> str:
        if not self.tasks:
            filtered = self.taskFilter.currentData() is not None or self.dayFilter.currentData() is not None
            return "A szűrésnek megfelelő feladat nincs." if filtered else "Jelenleg nincs kiosztott feladatod."
        if not self.visible:
            return f"Nincs találat erre: „{self.searchEdit.text().strip()}”."
        pickups = sum(task["task"] == "pickup" for task in self.visible)
        text = f"{len(self.visible)} feladat: {pickups} felvétel, {len(self.visible) - pickups} kiszállítás."
        if query:
            text += f" (Összesen {len(self.tasks)}, a keresés szűkíti.)"
        return text

    # --- details and actions -------------------------------------------

    def _on_selection_changed(self) -> None:
        if self._filling:
            return
        row = selected_row(self.table)
        if not 0 <= row < len(self.visible):
            self.selected_id = None
            self.detailFrame.hide()
            return
        task = self.visible[row]
        self.selected_id = task["parcel"]["id"]
        self._show_detail(task)

    def _show_detail(self, task: dict) -> None:
        parcel, contact = task["parcel"], _contact(task)
        pickup = task["task"] == "pickup"
        other = parcel["recipient"] if pickup else parcel["sender"]
        self.detailTitle.setText(parcel["tracking_number"])
        self.detailCopyButton.value = parcel["tracking_number"]
        self.detailLabel.setText(
            f''
            f'{STATUS_LABELS.get(parcel["status"], parcel["status"])}\nMéret: {parcel["size"]}\n'
            f'{"Feladó" if pickup else "Címzett"}: {_name(contact)}, '
            f'\nTelefon: {contact.get("phone") or "–"},\nEmail: {contact["email"]}\n'
            f"Cím: {_address(contact)}\n"
            f"Időpont: {_when(task)}\n"
            f'{"Címzett" if pickup else "Feladó"}: {_name(other)}, {other["city"]}'
        )
        actions = available_actions(task["task"], parcel["status"])
        hint = waiting_hint(task["task"], parcel["status"])
        if not actions and not hint:
            hint = "Ehhez a csomaghoz most nincs teendő."
        self.hintLabel.setText(hint)
        self.hintLabel.setVisible(bool(hint))
        for action, button in self.actionButtons.items():
            button.setVisible(action in actions)
            button.setEnabled(not self._busy)
        self.detailFrame.show()

    def _current(self) -> dict | None:
        return next((task for task in self.visible if task["parcel"]["id"] == self.selected_id), None)

    def _run(self, action: str) -> None:
        task = self._current()
        if task is None or self._busy:
            return
        number = task["parcel"]["tracking_number"]
        body = None
        if action == FAIL:
            note = ask_fail_note(self, number, task["task"])
            if note is None:
                return
            body = {"note": note}
        self._set_busy(True)
        run_in_background(_post_action, number, action, body,
                          on_success=self._on_action_done, on_error=self._on_action_error)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in self.actionButtons.values():
            button.setEnabled(not busy)

    def _on_action_done(self, result: tuple[str, str]) -> None:
        action, number = result
        self._set_busy(False)
        self._notify(InfoBar.success, "Sikeres művelet", SUCCESS_MESSAGES[action].format(number))
        self.refresh()

    def _on_action_error(self, error: ApiError) -> None:
        self._set_busy(False)
        self._notify(InfoBar.error, "Sikertelen művelet", error.message)
        # The parcel may have changed meanwhile (e.g. the warehouse reassigned it)
        self.refresh()

    def _notify(self, show, title: str, content: str) -> None:
        show(title=title, content=content, isClosable=True, position=InfoBarPosition.TOP_RIGHT,
             duration=4000, parent=self)
