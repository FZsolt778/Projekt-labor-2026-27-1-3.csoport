from qfluentwidgets import BodyLabel, PrimaryPushButton, SubtitleLabel, setFont
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
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
    api,
    format_date,
    format_datetime,
    format_window,
    run_in_background,
)
from .parcel_helpers import load_my_parcels


def _load_parcel_history() -> dict[str, list[dict]]:
    return {
        "sent": load_my_parcels("sent", "history"),
        "received": load_my_parcels("received", "history"),
    }


class HistoryInterface(QFrame):
    def __init__(self, text: str = "History", parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))
        self.parcels_by_direction: dict[str, list[dict]] = {
            "sent": [],
            "received": [],
        }
        self.selected_parcel_id: int | None = None

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

        self.title = SubtitleLabel("Csomagelőzmények", self.content)
        setFont(self.title, 32, QFont.Weight.Bold)
        self.description = BodyLabel(
            "A lezárt, feladott és érkező csomagjaid, valamint azok státusztörténete.",
            self.content,
        )
        self.description.setStyleSheet("color: #6B6B6B;")
        self.description.setWordWrap(True)
        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addStretch(1)
        self.refreshButton = PrimaryPushButton("Frissítés", self.content)
        self.refreshButton.clicked.connect(self.refresh)
        header.addWidget(self.refreshButton)
        self.contentLayout.addLayout(header)
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

        self.timelineTitle = SubtitleLabel("Csomag eseményei", self.content)
        setFont(self.timelineTitle, 20, QFont.Weight.DemiBold)
        self.contentLayout.addWidget(self.timelineTitle)
        self.timelineList = QListWidget(self.content)
        self.timelineList.setMinimumHeight(140)
        self.contentLayout.addWidget(self.timelineList)
        self.contentLayout.addStretch(1)

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
            self.messageLabel.setText("Az előzmények megtekintéséhez jelentkezz be.")
            return
        if api.role != "customer":
            self.messageLabel.setText("Ez a felület regisztrált ügyfelek számára érhető el.")
            return
        self.refreshButton.setEnabled(False)
        self.messageLabel.setText("Előzmények betöltése...")
        run_in_background(
            _load_parcel_history,
            on_success=self._on_history_loaded,
            on_error=self._on_load_error,
        )

    def _on_history_loaded(self, parcels: dict[str, list[dict]]) -> None:
        self.refreshButton.setEnabled(True)
        self.parcels_by_direction = parcels
        self._populate_table(self.sentTable, parcels["sent"], "sent")
        self._populate_table(self.receivedTable, parcels["received"], "received")
        total = len(parcels["sent"]) + len(parcels["received"])
        self.messageLabel.setText(f"{total} lezárt csomag található az előzményekben.")
        self.timelineList.clear()

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
        parcel_id = self.parcels_by_direction[direction][row]["id"]
        self.selected_parcel_id = parcel_id
        self.timelineList.clear()
        self.messageLabel.setText("Csomagelőzmény betöltése...")
        run_in_background(
            api.get,
            f"/parcels/my/{parcel_id}",
            on_success=lambda parcel: self._on_parcel_detail_loaded(parcel_id, parcel),
            on_error=lambda error: self._on_detail_error(parcel_id, error),
        )

    def _on_tab_changed(self, index: int) -> None:
        direction = "sent" if index == 0 else "received"
        table = self.sentTable if direction == "sent" else self.receivedTable
        if table.currentRow() >= 0:
            self._show_selected_parcel(direction)
        else:
            self.selected_parcel_id = None
            self.timelineList.clear()

    def _on_parcel_detail_loaded(self, parcel_id: int, parcel: dict) -> None:
        if parcel_id != self.selected_parcel_id:
            return
        events = parcel.get("events", [])
        if not events:
            self.timelineList.addItem("Ehhez a csomaghoz nincs rögzített esemény.")
        for event in events:
            status = STATUS_LABELS.get(event["status"], event["status"])
            line = f"{format_datetime(event['occurred_at'])} — {status}"
            if event.get("note"):
                line += f"\n{event['note']}"
            self.timelineList.addItem(line)
        self.messageLabel.setText(
            f"Előzmény: {parcel['tracking_number']} — "
            f"{STATUS_LABELS.get(parcel['status'], parcel['status'])}"
        )

    def _on_detail_error(self, parcel_id: int, error: ApiError) -> None:
        if parcel_id != self.selected_parcel_id:
            return
        self.messageLabel.setText(error.message)