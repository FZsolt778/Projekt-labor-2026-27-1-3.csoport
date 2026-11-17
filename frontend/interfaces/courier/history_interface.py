from qfluentwidgets import BodyLabel, ComboBox, PrimaryPushButton, SubtitleLabel, setFont
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from api_client import (
    ApiError,
    STATUS_LABELS,
    TASK_LABELS,
    api,
    format_date,
    format_datetime,
    run_in_background,
)


class DeliveryHistoryInterface(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(" ", "-"))

        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(24, 16, 24, 16)
        self.mainLayout.setSpacing(12)

        header = QHBoxLayout()
        self.title = SubtitleLabel("Szállítási előzmények", self)
        setFont(self.title, 32, QFont.Weight.Bold)
        header.addWidget(self.title)
        header.addStretch(1)
        self.refreshButton = PrimaryPushButton("Frissítés", self)
        self.refreshButton.clicked.connect(self.refresh)
        header.addWidget(self.refreshButton)
        self.mainLayout.addLayout(header)

        self.description = BodyLabel(
            "Tekintsd meg a saját felvételi és kézbesítési eseményeidet napi, heti vagy havi bontásban.",
            self,
        )
        self.description.setWordWrap(True)
        self.description.setStyleSheet("color: #6B6B6B;")
        self.mainLayout.addWidget(self.description)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Időszak:", self))
        self.periodCombo = ComboBox(self)
        self.periodCombo.addItem("Napi", userData="day")
        self.periodCombo.addItem("Heti", userData="week")
        self.periodCombo.addItem("Havi", userData="month")
        filters.addWidget(self.periodCombo)

        filters.addWidget(QLabel("Dátum:", self))
        self.dayEdit = QDateEdit(self)
        self.dayEdit.setCalendarPopup(True)
        self.dayEdit.setDisplayFormat("yyyy. MM. dd.")
        self.dayEdit.setDate(QDate.currentDate())
        filters.addWidget(self.dayEdit)
        filters.addStretch(1)
        self.mainLayout.addLayout(filters)

        self.messageLabel = QLabel("Válassz időszakot, majd frissítsd az előzményeket.", self)
        self.messageLabel.setWordWrap(True)
        self.mainLayout.addWidget(self.messageLabel)

        summary = QHBoxLayout()
        self.periodLabel = BodyLabel("", self)
        self.pickupsLabel = BodyLabel("Felvételek: 0", self)
        self.deliveriesLabel = BodyLabel("Kézbesítések: 0", self)
        self.failedLabel = BodyLabel("Sikertelen: 0", self)
        for label in (
            self.periodLabel,
            self.pickupsLabel,
            self.deliveriesLabel,
            self.failedLabel,
        ):
            summary.addWidget(label)
        summary.addStretch(1)
        self.mainLayout.addLayout(summary)

        self.historyTable = QTableWidget(0, 7, self)
        self.historyTable.setHorizontalHeaderLabels(
            [
                "Időpont",
                "Feladat",
                "Csomagazonosító",
                "Eredmény",
                "Méret",
                "Kapcsolattartó",
                "Megjegyzés",
            ]
        )
        self.historyTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.historyTable.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.historyTable.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.historyTable.verticalHeader().hide()
        self.historyTable.horizontalHeader().setStretchLastSection(True)
        self.historyTable.setMinimumHeight(240)
        self.mainLayout.addWidget(self.historyTable, 1)

    def refresh(self) -> None:
        if not api.is_logged_in:
            self.messageLabel.setText("Az előzmények megtekintéséhez jelentkezz be.")
            return
        if api.role != "courier":
            self.messageLabel.setText("Ez a felület futárok számára érhető el.")
            return

        self.refreshButton.setEnabled(False)
        self.periodCombo.setEnabled(False)
        self.dayEdit.setEnabled(False)
        self.historyTable.setRowCount(0)
        self.periodLabel.setText("")
        self.pickupsLabel.setText("Felvételek: 0")
        self.deliveriesLabel.setText("Kézbesítések: 0")
        self.failedLabel.setText("Sikertelen: 0")
        self.messageLabel.setText("Szállítási előzmények betöltése...")
        run_in_background(
            api.get,
            "/courier/history",
            params={
                "period": self.periodCombo.currentData(),
                "day": self.dayEdit.date().toString(Qt.DateFormat.ISODate),
            },
            on_success=self._on_history_loaded,
            on_error=self._on_load_error,
        )

    def _set_loading_finished(self) -> None:
        self.refreshButton.setEnabled(True)
        self.periodCombo.setEnabled(True)
        self.dayEdit.setEnabled(True)

    def _on_history_loaded(self, history: dict) -> None:
        self._set_loading_finished()
        items = history["items"]
        self.historyTable.setRowCount(len(items))

        for row, item in enumerate(items):
            contact = item.get("contact") or {}
            contact_name = " ".join(
                part
                for part in (
                    contact.get("last_name", ""),
                    contact.get("first_name", ""),
                )
                if part
            )
            values = (
                format_datetime(item["occurred_at"]),
                TASK_LABELS.get(item["task"], item["task"]),
                item["tracking_number"],
                STATUS_LABELS.get(item["status"], item["status"]),
                item["size"],
                contact_name or "–",
                item.get("note") or "–",
            )
            for column, value in enumerate(values):
                self.historyTable.setItem(row, column, QTableWidgetItem(str(value)))

        self.periodLabel.setText(
            f"Időszak: {format_date(history['from_date'])} – "
            f"{format_date(history['to_date'])}"
        )
        self.pickupsLabel.setText(f"Felvételek: {history['pickups_count']}")
        self.deliveriesLabel.setText(f"Kézbesítések: {history['deliveries_count']}")
        self.failedLabel.setText(f"Sikertelen: {history['failed_count']}")
        self.messageLabel.setText(
            f"{len(items)} saját szállítási esemény az adott időszakban."
            if items
            else "Ebben az időszakban nincs rögzített szállítási esemény."
        )

    def _on_load_error(self, error: ApiError) -> None:
        self._set_loading_finished()
        self.messageLabel.setText(error.message)
