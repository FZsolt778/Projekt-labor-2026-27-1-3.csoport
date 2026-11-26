# Shared building blocks of the admin screens
from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel, CheckBox, LineEdit, MessageBox, PrimaryPushButton, PushButton, SubtitleLabel, setFont,
)

from api_client import api
from theme import ACCENT_LIGHT, TEXT, TEXT_SECONDARY

PAGE_SIZE = 50
# Forms stay readable on a full-screen window
FORM_MAX_WIDTH = 760
ERROR_STYLE = "color: #D13438;"
MUTED_STYLE = f"color: {TEXT_SECONDARY};"


class AdminPage(QFrame):
    # Scrollable page with a title, refresh button, description and message line
    def __init__(self, object_name: str, title: str, description: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(object_name)

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

        self.title = SubtitleLabel(title, self.content)
        setFont(self.title, 32, QFont.Weight.Bold)
        self.headerLayout = QHBoxLayout()
        self.headerLayout.addWidget(self.title)
        self.headerLayout.addStretch(1)
        self.refreshButton = PrimaryPushButton("Frissítés", self.content)
        self.refreshButton.clicked.connect(self.refresh)
        self.headerLayout.addWidget(self.refreshButton)
        self.contentLayout.addLayout(self.headerLayout)

        self.description = BodyLabel(description, self.content)
        self.description.setStyleSheet(MUTED_STYLE)
        self.description.setWordWrap(True)
        self.contentLayout.addWidget(self.description)

        self.messageLabel = QLabel(self.content)
        self.messageLabel.setWordWrap(True)
        self.contentLayout.addWidget(self.messageLabel)
        self._loaded = False

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Loads the data when first opened (the main window builds new pages after every login)
        if not self._loaded:
            self._loaded = True
            self.refresh()

    def refresh(self) -> None:
        raise NotImplementedError

    def show_message(self, text: str, error: bool = False) -> None:
        set_message(self.messageLabel, text, error)

    def can_load(self) -> bool:
        # The server checks the role too, this only avoids a pointless request
        if not api.is_logged_in:
            self.show_message("A felület használatához jelentkezz be adminisztrátorként.")
            return False
        if api.role != "admin":
            self.show_message("Ez a felület csak adminisztrátorok számára érhető el.")
            return False
        return True


class Pager(QWidget):
    # Previous / next buttons for the paginated lists
    pageChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self)
        self.label.setStyleSheet(MUTED_STYLE)
        self.prevButton = PushButton("Előző", self)
        self.nextButton = PushButton("Következő", self)
        self.prevButton.clicked.connect(lambda: self._move(-PAGE_SIZE))
        self.nextButton.clicked.connect(lambda: self._move(PAGE_SIZE))
        layout.addWidget(self.label)
        layout.addStretch(1)
        layout.addWidget(self.prevButton)
        layout.addWidget(self.nextButton)
        self.prevButton.setEnabled(False)
        self.nextButton.setEnabled(False)

    def params(self) -> dict:
        return {"limit": PAGE_SIZE, "offset": self.offset}

    def reset(self) -> None:
        self.offset = 0

    def set_page(self, page: dict) -> None:
        self.offset = page["offset"]
        shown = len(page["items"])
        if shown:
            self.label.setText(f"{self.offset + 1}–{self.offset + shown}. / {page['total']}")
        else:
            self.label.setText("Nincs találat" if page["total"] == 0 else "Ezen az oldalon nincs több találat")
        self.prevButton.setEnabled(self.offset > 0)
        self.nextButton.setEnabled(self.offset + shown < page["total"])

    def _move(self, step: int) -> None:
        self.offset = max(0, self.offset + step)
        self.pageChanged.emit()


class DateFilter(QWidget):
    # Day filter that can be switched off (unchecked: any day)
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.check = CheckBox(label, self)
        self.edit = QDateEdit(self)
        self.edit.setCalendarPopup(True)
        self.edit.setDisplayFormat("yyyy-MM-dd")
        self.edit.setDate(QDate.currentDate())
        self.edit.setEnabled(False)
        self.check.toggled.connect(self.edit.setEnabled)
        layout.addWidget(self.check)
        layout.addWidget(self.edit)

    def value(self) -> str | None:
        return self.edit.date().toString("yyyy-MM-dd") if self.check.isChecked() else None


def set_message(label: QLabel, text: str, error: bool = False) -> None:
    label.setStyleSheet(ERROR_STYLE if error else "")
    label.setText(text)


def create_table(headers: list[str], parent=None, stretch: int | None = None) -> QTableWidget:
    # stretch: the column that takes the free space, None: all columns share it
    table = QTableWidget(0, len(headers), parent)
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().hide()
    header = table.horizontalHeader()
    if stretch is None:
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    else:
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    # The app style sheet hides the default selection colour
    table.setStyleSheet(f"QTableWidget::item:selected {{ background-color: {ACCENT_LIGHT}; color: {TEXT}; }}")
    table.setMinimumHeight(260)
    return table


def fill_table(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(0)
    for values in rows:
        row = table.rowCount()
        table.insertRow(row)
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))


def button_row(*buttons: QWidget) -> QHBoxLayout:
    # Buttons on the left, at their natural width
    layout = QHBoxLayout()
    for button in buttons:
        layout.addWidget(button)
    layout.addStretch(1)
    return layout


def selected_row(table: QTableWidget) -> int:
    # currentRow() keeps the old row after clearSelection(), this does not
    rows = table.selectionModel().selectedRows()
    return rows[0].row() if rows else -1


def select_by_id(table: QTableWidget, items: list[dict], item_id: int | None) -> None:
    # Reselects the row after a reload, if it is still on the page
    for row, item in enumerate(items):
        if item["id"] == item_id:
            table.selectRow(row)
            return


def full_name(person: dict | None) -> str:
    return f"{person['last_name']} {person['first_name']}" if person else "–"


def text_or_none(edit: LineEdit) -> str | None:
    return edit.text().strip() or None


def confirm(parent: QWidget, title: str, text: str, yes_text: str) -> bool:
    box = MessageBox(title, text, parent.window())
    box.yesButton.setText(yes_text)
    box.cancelButton.setText("Mégse")
    return bool(box.exec())
