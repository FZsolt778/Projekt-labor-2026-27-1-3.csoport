from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import BodyLabel, LineEdit, MessageBoxBase, SubtitleLabel

PICKUP, START, DELIVER, FAIL = "pickup", "start", "deliver", "fail"

ACTION_LABELS = {
    PICKUP: "Felvétel",
    START: "Indulás",
    DELIVER: "Kézbesítés",
    FAIL: "Sikertelen kísérlet",
}

SUCCESS_MESSAGES = {
    PICKUP: "Felvetted a(z) {} csomagot.",
    START: "Elindultál a(z) {} csomaggal.",
    DELIVER: "Kézbesítetted a(z) {} csomagot.",
    FAIL: "Rögzítetted a sikertelen kísérletet: {}.",
}

NOTE_MAX_LENGTH = 255


def available_actions(task: str, status: str) -> list[str]:
    if task == "pickup" and status == "pickup_assigned":
        return [PICKUP, FAIL]
    if task == "delivery" and status == "delivery_assigned":
        return [START]
    if task == "delivery" and status == "out_for_delivery":
        return [DELIVER, FAIL]
    return []


def waiting_hint(task: str, status: str) -> str:
    if task == "pickup" and status == "picked_up":
        return "A csomag nálad van: vidd be a raktárba, ott a raktáros beérkezteti."
    if task == "delivery" and status == "failed":
        return "A kézbesítés nem sikerült: vidd vissza a csomagot a raktárba."
    return ""


class FailNoteDialog(MessageBoxBase):

    def __init__(self, tracking_number: str, task: str | None, parent: QWidget):
        super().__init__(parent)
        if task == "pickup":
            effect = "A sikertelen felvétel lemondja a csomagot, a feladó újra előjegyezheti."
        elif task == "delivery":
            effect = ("A csomagot vissza kell vinni a raktárba. Több sikertelen kézbesítés után "
                      "a rendszer lemondja a csomagot.")
        else:
            effect = ("Felvételnél a csomag lemondásra kerül, kiszállításnál vissza kell vinni "
                      "a raktárba.")
        self.titleLabel = SubtitleLabel("Sikertelen kísérlet", self.widget)
        self.infoLabel = BodyLabel(f"{tracking_number}: írd le röviden, mi történt.\n{effect}", self.widget)
        self.infoLabel.setWordWrap(True)
        self.noteEdit = LineEdit(self.widget)
        self.noteEdit.setPlaceholderText("Pl. nem volt otthon a címzett")
        self.noteEdit.setMaxLength(NOTE_MAX_LENGTH)
        self.noteEdit.setClearButtonEnabled(True)
        self.errorLabel = QLabel(self.widget)
        self.errorLabel.setStyleSheet("color: #D13438; background: transparent;")
        self.errorLabel.hide()
        self.noteEdit.textChanged.connect(self.errorLabel.hide)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.noteEdit)
        self.viewLayout.addWidget(self.errorLabel)
        self.yesButton.setText("Rögzítés")
        self.cancelButton.setText("Mégse")
        self.widget.setMinimumWidth(480)
        self.noteEdit.setFocus()

    @property
    def note(self) -> str:
        return self.noteEdit.text().strip()

    def validate(self) -> bool:
        if self.note:
            return True
        self.errorLabel.setText("Az indoklás megadása kötelező.")
        self.errorLabel.show()
        return False


def ask_fail_note(source: QWidget, tracking_number: str, task: str | None = None) -> str | None:
    # None when the courier cancels
    dialog = FailNoteDialog(tracking_number, task, source.window())
    try:
        return dialog.note if dialog.exec() else None
    finally:
        dialog.deleteLater()
