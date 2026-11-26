# Parcel details shared by the screens: status, a step bar with the milestones and four cards
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, SimpleCardWidget, StrongBodyLabel

from api_client import STATUS_LABELS, format_date, format_window, to_local

ACCENT = "#2383E2"
INACTIVE = "#C8CDD2"
MUTED = "#6B6B6B"
DANGER = "#D13438"
# Pill colours (background, text) by the kind of status
PILL_COLORS = {
    "booked": ("#EEF1F4", "#3D4A55"),
    "pickup_assigned": ("#EEF1F4", "#3D4A55"),
    "picked_up": ("#E3EFFB", "#185A9D"),
    "in_warehouse": ("#E3EFFB", "#185A9D"),
    "delivery_assigned": ("#E3EFFB", "#185A9D"),
    "out_for_delivery": ("#E3EFFB", "#185A9D"),
    "delivered": ("#E2F3E5", "#1E6B2E"),
    "failed": ("#FCEBD9", "#9A4A0A"),
    "cancelled": ("#FBE3E4", "#A4262C"),
}
# Step bar: label and the milestone that marks it done
STEPS = (
    ("Előjegyezve", "created_at"),
    ("Felvéve", "picked_up_at"),
    ("Raktárban", "warehouse_arrived_at"),
    ("Úton", "out_for_delivery_at"),
    ("Kézbesítve", "delivered_at"),
)
# How far the parcel got; milestones of an earlier attempt may still be set, the status decides
STATUS_STEP = {
    "booked": 0, "pickup_assigned": 0, "picked_up": 1, "in_warehouse": 2,
    "delivery_assigned": 2, "out_for_delivery": 3, "failed": 3, "delivered": 4,
}


def _name(person: dict | None) -> str:
    return f"{person['last_name']} {person['first_name']}" if person else "–"


def _courier(courier: dict | None) -> str:
    # Staff screens also get the courier's phone, the others only the name
    if not courier:
        return "még nincs kijelölve"
    phone = courier.get("phone")
    return f"{_name(courier)}, {phone}" if phone else _name(courier)


def _short_time(value: str | None) -> str:
    local = to_local(value)
    return local.strftime("%m. %d. %H:%M") if local else ""


def _long_time(value: str | None) -> str:
    local = to_local(value)
    return local.strftime("%Y. %m. %d. %H:%M") if local else "–"


class StepBar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.done = 0
        self.problem = False
        self.times = [""] * len(STEPS)

    def set_parcel(self, parcel: dict) -> None:
        status = parcel["status"]
        if status == "cancelled":
            # A cancelled parcel stopped at its last milestone
            reached = [i for i, (_, key) in enumerate(STEPS) if i == 0 or parcel.get(key)]
            self.done = reached[-1]
        else:
            self.done = STATUS_STEP.get(status, 0)
        self.problem = status in ("failed", "cancelled")
        self.times = [_short_time(parcel.get(key)) if i <= self.done else "" for i, (_, key) in enumerate(STEPS)]
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right, y = 40, self.width() - 40, 12
        step = (right - left) / (len(STEPS) - 1)
        accent, inactive, danger = QColor(ACCENT), QColor(INACTIVE), QColor(DANGER)

        painter.setPen(QPen(inactive, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(int(left), y, int(right), y)
        if self.done:
            painter.setPen(QPen(accent, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(left), y, int(left + step * self.done), y)

        label_font = QFont(self.font().family(), 9)
        time_font = QFont(self.font().family(), 8)
        for index, (label, _) in enumerate(STEPS):
            x = left + step * index
            done = index <= self.done
            color = danger if (self.problem and index == self.done) else (accent if done else inactive)
            painter.setPen(QPen(color, 2))
            painter.setBrush(color if done else QColor("#FFFFFF"))
            painter.drawEllipse(int(x - 6), y - 6, 12, 12)
            box = QRect(int(x - step / 2), 24, int(step), 18)
            painter.setFont(label_font)
            painter.setPen(QColor("#1F1F1F") if done else QColor(MUTED))
            painter.drawText(box, Qt.AlignmentFlag.AlignHCenter, label)
            if self.times[index]:
                painter.setFont(time_font)
                painter.setPen(QColor(MUTED))
                painter.drawText(box.translated(0, 18), Qt.AlignmentFlag.AlignHCenter, self.times[index])
        painter.end()


class InfoCard(SimpleCardWidget):
    # Title and label: value rows

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(6)
        self.titleLabel = CaptionLabel(title.upper(), self)
        self.titleLabel.setStyleSheet(f"color: {MUTED}; font-weight: 600;")
        layout.addWidget(self.titleLabel)
        self.headline = StrongBodyLabel(self)
        self.headline.setWordWrap(True)
        self.headline.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.headline)
        self.rows = QGridLayout()
        self.rows.setHorizontalSpacing(12)
        self.rows.setVerticalSpacing(4)
        self.rows.setColumnStretch(1, 1)
        layout.addLayout(self.rows)
        layout.addStretch(1)
        self._title = title

    def fill(self, headline: str, rows: list[tuple[str, str]], note: str = "") -> None:
        self.titleLabel.setText((f"{self._title} · {note}" if note else self._title).upper())
        self.titleLabel.setStyleSheet(
            f"color: {ACCENT if note else MUTED}; font-weight: 600;"
        )
        self.headline.setText(headline)
        self.headline.setVisible(bool(headline))
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        for row, (key, value) in enumerate(rows):
            keyLabel = CaptionLabel(key, self)
            keyLabel.setStyleSheet(f"color: {MUTED};")
            # Same label column in every card, so the values line up
            keyLabel.setMinimumWidth(72)
            valueLabel = BodyLabel(value, self)
            valueLabel.setWordWrap(True)
            valueLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.rows.addWidget(keyLabel, row, 0, Qt.AlignmentFlag.AlignTop)
            self.rows.addWidget(valueLabel, row, 1)


class ParcelDetails(QWidget):
    # highlight: "sender" or "recipient", the party the viewer has to go to (courier)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("parcelDetails")
        # The app style sheet paints every widget white; the cards draw their own background
        self.setStyleSheet("#parcelDetails, #parcelDetails QLabel, #parcelDetails QWidget { background: transparent; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.statusPill = QLabel(self)
        self.sizeChip = QLabel(self)
        for label in (self.statusPill, self.sizeChip):
            bold = QFont(label.font())
            bold.setWeight(QFont.Weight.DemiBold)
            label.setFont(bold)
        header.addWidget(self.statusPill)
        header.addWidget(self.sizeChip)
        header.addStretch(1)
        layout.addLayout(header)

        self.stepBar = StepBar(self)
        layout.addWidget(self.stepBar)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self.senderCard = InfoCard("Feladó", self)
        self.recipientCard = InfoCard("Címzett", self)
        self.pickupCard = InfoCard("Felvétel", self)
        self.deliveryCard = InfoCard("Kiszállítás", self)
        grid.addWidget(self.senderCard, 0, 0)
        grid.addWidget(self.recipientCard, 0, 1)
        grid.addWidget(self.pickupCard, 1, 0)
        grid.addWidget(self.deliveryCard, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

    def set_parcel(self, parcel: dict, highlight: str | None = None) -> None:
        status = parcel["status"]
        background, color = PILL_COLORS.get(status, ("#EEF1F4", "#3D4A55"))
        self.statusPill.setText(STATUS_LABELS.get(status, status))
        self.statusPill.setStyleSheet(
            f"background: {background}; color: {color}; border-radius: 11px; padding: 3px 12px;"
        )
        self.sizeChip.setText(f"{parcel['size']} méret")
        self.sizeChip.setStyleSheet(
            f"background: #F3F3F3; color: {MUTED}; border-radius: 11px; padding: 3px 12px;"
        )
        self.stepBar.set_parcel(parcel)

        for card, side, note in ((self.senderCard, "sender", "felvételi cím"),
                                 (self.recipientCard, "recipient", "kiszállítási cím")):
            contact = parcel[side]
            card.fill(_name(contact), [
                ("Cím", f"{contact['postal_code']} {contact['city']}, {contact['street']} {contact['house_number']}"),
                ("Telefon", contact.get("phone") or "–"),
                ("Email", contact["email"]),
            ], note if highlight == side else "")

        self.pickupCard.fill("", [
            ("Időpont", f"{format_date(parcel['pickup_date'])} "
                        f"{format_window(parcel['pickup_window_start'], parcel['pickup_window_end'])}"),
            ("Futár", _courier(parcel.get("pickup_courier"))),
            ("Felvéve", _long_time(parcel.get("picked_up_at"))),
        ])
        if parcel.get("delivery_date"):
            when = (f"{format_date(parcel['delivery_date'])} "
                    f"{format_window(parcel['delivery_window_start'], parcel['delivery_window_end'])}")
        else:
            when = "még nincs kijelölve"
        self.deliveryCard.fill("", [
            ("Időpont", when),
            ("Futár", _courier(parcel.get("delivery_courier"))),
            ("Kézbesítve", _long_time(parcel.get("delivered_at"))),
        ])
