from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QWidget
from qfluentwidgets import FluentIcon, ToolTipFilter, ToolTipPosition, TransparentToolButton

COPY_TIP = "Csomagszám másolása"
COPIED_TIP = "Vágólapra másolva"


class CopyButton(TransparentToolButton):

    def __init__(self, value: str = "", parent=None):
        super().__init__(parent)
        self.setIcon(FluentIcon.COPY)
        self.value = value
        self.setFixedSize(26, 26)
        self.setIconSize(QSize(14, 14))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(COPY_TIP)
        self.installEventFilter(ToolTipFilter(self, 300, ToolTipPosition.TOP))
        self._resetTimer = QTimer(self)
        self._resetTimer.setSingleShot(True)
        self._resetTimer.setInterval(1500)
        self._resetTimer.timeout.connect(self._reset)
        self.clicked.connect(self.copy)

    def copy(self) -> None:
        if not self.value:
            return
        QApplication.clipboard().setText(self.value)
        self.setIcon(FluentIcon.ACCEPT)
        self.setToolTip(COPIED_TIP)
        self._resetTimer.start()

    def _reset(self) -> None:
        self.setIcon(FluentIcon.COPY)
        self.setToolTip(COPY_TIP)


class CopyableText(QWidget):

    def __init__(self, value: str, font: QFont | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("copyableText")
        # The app style sheet gives every widget a white background, it would hide the row selection
        self.setStyleSheet("#copyableText, #copyableText QLabel { background: transparent; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        self.label = QLabel(value, self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if font is not None:
            explicit = QFont(font)
            explicit.setFamily(font.family())
            if font.pixelSize() > 0:
                explicit.setPixelSize(font.pixelSize())
            else:
                explicit.setPointSizeF(font.pointSizeF())
            self.label.setFont(explicit)
        self.button = CopyButton(value, self)
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        layout.addStretch(1)


def add_copy_buttons(table: QTableWidget, column: int) -> None:
    for row in range(table.rowCount()):
        item = table.item(row, column)
        if item is None or not item.text():
            if item is None or item.data(Qt.ItemDataRole.UserRole) is None:
                table.removeCellWidget(row, column)
            continue
        value = item.text()
        item.setData(Qt.ItemDataRole.UserRole, value)
        item.setText("")
        table.setCellWidget(row, column, CopyableText(value, table.font()))
    if table.horizontalHeader().sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive:
        table.resizeColumnToContents(column)
