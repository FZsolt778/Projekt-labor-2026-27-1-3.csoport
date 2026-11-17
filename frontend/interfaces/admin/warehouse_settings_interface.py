# Admin: warehouse name and capacity
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget
from qfluentwidgets import LineEdit, PrimaryPushButton, SpinBox

from api_client import ApiError, api, run_in_background
from .admin_helpers import FORM_MAX_WIDTH, MUTED_STYLE, AdminPage, button_row

MAX_CAPACITY = 100000


def _load_warehouse() -> dict:
    # The current parcel count is the lowest allowed capacity
    return {"warehouse": api.get("/warehouse"), "usage": api.get("/stats/warehouse")}


def _save_and_reload(body: dict) -> dict:
    api.patch("/warehouse", body)
    return _load_warehouse()


class WarehouseSettingsInterface(AdminPage):
    def __init__(self, text: str = "Admin Warehouse", parent=None):
        super().__init__(
            text.replace(" ", "-"),
            "Raktár",
            "A raktár neve és kapacitása. A kapacitás nem lehet kisebb, mint a raktárban jelenleg lévő "
            "csomagok száma, a beérkeztetés pedig ennél többet nem enged be.",
            parent,
        )
        self.warehouse: dict | None = None

        formWidget = QWidget(self.content)
        formWidget.setMaximumWidth(FORM_MAX_WIDTH)
        form = QFormLayout(formWidget)
        form.setContentsMargins(0, 0, 0, 0)
        self.nameEdit = LineEdit(formWidget)
        self.nameEdit.setMinimumHeight(42)
        self.capacitySpin = SpinBox(formWidget)
        self.capacitySpin.setRange(1, MAX_CAPACITY)
        form.addRow("Név", self.nameEdit)
        form.addRow("Kapacitás (csomag)", self.capacitySpin)
        self.contentLayout.addWidget(formWidget)
        self.usageLabel = QLabel(self.content)
        self.usageLabel.setStyleSheet(MUTED_STYLE)
        self.contentLayout.addWidget(self.usageLabel)
        self.saveButton = PrimaryPushButton("Mentés", self.content)
        self.saveButton.clicked.connect(self.save)
        self.saveButton.setEnabled(False)
        self.contentLayout.addLayout(button_row(self.saveButton))
        self.contentLayout.addStretch(1)

    def refresh(self) -> None:
        if not self.can_load():
            return
        self.refreshButton.setEnabled(False)
        self.show_message("Raktár adatainak betöltése...")
        run_in_background(_load_warehouse, on_success=self._on_loaded, on_error=self._on_error)

    def _on_loaded(self, result: dict, notice: str | None = None) -> None:
        self.refreshButton.setEnabled(True)
        self.saveButton.setEnabled(True)
        warehouse, usage = result["warehouse"], result["usage"]
        self.warehouse = warehouse
        self.nameEdit.setText(warehouse["name"])
        self.capacitySpin.setValue(warehouse["capacity"])
        self.usageLabel.setText(
            f"Jelenleg {usage['parcel_count']} csomag van a raktárban, ennél kisebb kapacitás nem adható meg."
        )
        self.show_message(notice or "")

    def _on_error(self, error: ApiError) -> None:
        self.refreshButton.setEnabled(True)
        self.saveButton.setEnabled(self.warehouse is not None)
        self.show_message(error.message, error=True)

    def save(self) -> None:
        if self.warehouse is None:
            return
        name = self.nameEdit.text().strip()
        if not name:
            self.show_message("A raktár neve nem lehet üres.", error=True)
            return
        body = {}
        if name != self.warehouse["name"]:
            body["name"] = name
        if self.capacitySpin.value() != self.warehouse["capacity"]:
            body["capacity"] = self.capacitySpin.value()
        if not body:
            self.show_message("Nincs módosítás.")
            return
        self.saveButton.setEnabled(False)
        self.show_message("Mentés...")
        run_in_background(_save_and_reload, body, on_success=self._on_saved, on_error=self._on_error)

    def _on_saved(self, result: dict) -> None:
        self._on_loaded(result, notice="A raktár adatai elmentve.")
