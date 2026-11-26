from math import ceil

from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QValueAxis
from PySide6.QtCore import QDate, QDateTime, QMargins, QPointF, QRectF, Qt, QTime
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import QDateEdit, QGridLayout, QHBoxLayout, QLabel, QTabWidget, QToolTip, QWidget
from qfluentwidgets import PushButton, SubtitleLabel, setFont

from api_client import ApiError, api, format_date, run_in_background
from theme import ACCENT, ACCENT_LIGHT, BORDER, TEXT_SECONDARY
from .admin_helpers import MUTED_STYLE, AdminPage, create_table, fill_table, full_name

WARNING_COLOR = "#FAB219"
CRITICAL_COLOR = "#D13438"
WARNING_PERCENT = 75
CRITICAL_PERCENT = 90
DEFAULT_DAYS = 30


def _load_stats(from_date: str, to_date: str) -> dict:
    period = {"from_date": from_date, "to_date": to_date}
    return {
        "now": api.get("/stats/warehouse"),
        "history": api.get("/stats/warehouse/history", period),
        "couriers": api.get("/stats/couriers", period),
    }


def _number(value: float | None, digits: int = 1) -> str:
    # Hungarian decimal comma
    return "–" if value is None else f"{value:.{digits}f}".replace(".", ",")


class UtilizationMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.percent = 0.0
        self.setFixedHeight(12)

    def set_percent(self, percent: float) -> None:
        self.percent = max(0.0, min(percent, 100.0))
        self.update()

    def color(self) -> str:
        if self.percent >= CRITICAL_PERCENT:
            return CRITICAL_COLOR
        if self.percent >= WARNING_PERCENT:
            return WARNING_COLOR
        return ACCENT

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = self.height() / 2
        painter.setBrush(QColor(ACCENT_LIGHT))
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        if self.percent > 0:
            width = max(self.width() * self.percent / 100, self.height())
            painter.setBrush(QColor(self.color()))
            painter.drawRoundedRect(QRectF(0, 0, width, self.height()), radius, radius)
        painter.end()


class StatisticsInterface(AdminPage):
    def __init__(self, text: str = "Admin Statistics", parent=None):
        super().__init__(
            text.replace(" ", "-"),
            "Statisztikák",
            ""
            "",
            parent,
        )
        self.history_points: list[dict] = []

        period = QHBoxLayout()
        self.fromDate = self._date_edit(QDate.currentDate().addDays(-(DEFAULT_DAYS - 1)))
        self.toDate = self._date_edit(QDate.currentDate())
        self.applyButton = PushButton("Lekérdezés", self.content)
        self.applyButton.clicked.connect(self.refresh)
        period.addWidget(QLabel("Időszak:", self.content))
        period.addWidget(self.fromDate)
        period.addWidget(QLabel("–", self.content))
        period.addWidget(self.toDate)
        period.addWidget(self.applyButton)
        period.addStretch(1)
        self.contentLayout.insertLayout(2, period)

        # Warehouse now
        self._add_section_title("A raktár most")
        self.nowLabel = QLabel(self.content)
        setFont(self.nowLabel, 16, QFont.Weight.DemiBold)
        self.contentLayout.addWidget(self.nowLabel)
        self.meter = UtilizationMeter(self.content)
        self.contentLayout.addWidget(self.meter)
        self.sizeLabel = QLabel(self.content)
        self.sizeLabel.setStyleSheet(MUTED_STYLE)
        self.contentLayout.addWidget(self.sizeLabel)

        # Warehouse per day
        self._add_section_title("A raktár napi kihasználtsága")
        self.historyTiles = self._tile_row(["Átlagos kihasználtság", "Legtöbb csomag egy napon"])
        self.historyTabs = QTabWidget(self.content)
        self.chartView = self._build_chart()
        self.historyTable = create_table(["Nap", "Csomagok a nap végén", "Kihasználtság"])
        self.historyTabs.addTab(self.chartView, "Grafikon")
        self.historyTabs.addTab(self.historyTable, "Táblázat")
        self.contentLayout.addWidget(self.historyTabs)

        # Couriers
        self._add_section_title("Futárok az időszakban")
        self.courierTiles = self._tile_row([
            "Felvételek", "Kézbesítések", "Sikertelen kísérletek",
            "Átlagos kiszállítási idő", "Átlagos átfutási idő",
        ])
        self.courierTable = create_table([
            "Futár", "Felvétel", "Kézbesítés", "Sikertelen", "Aktív nap",
            "Kézbesítés / nap", "Átl. kiszállítási idő (perc)", "Átl. átfutás (óra)",
        ], stretch=0)
        self.contentLayout.addWidget(self.courierTable)
        hint = QLabel(
            "Kiszállítási idő: az indulástól a kézbesítésig. Átfutás: a felvételtől a kézbesítésig.",
            self.content,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(MUTED_STYLE)
        self.contentLayout.addWidget(hint)
        self.contentLayout.addStretch(1)

    # --- Layout ---

    def _date_edit(self, value: QDate) -> QDateEdit:
        edit = QDateEdit(value, self.content)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setMaximumDate(QDate.currentDate())
        edit.setMinimumHeight(42)
        return edit

    def _add_section_title(self, text: str) -> None:
        title = SubtitleLabel(text, self.content)
        setFont(title, 20, QFont.Weight.DemiBold)
        self.contentLayout.addWidget(title)

    def _tile_row(self, labels: list[str]) -> list[QLabel]:
        # Stat tiles: muted label above a semibold value
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        values = []
        for column, text in enumerate(labels):
            label = QLabel(text, self.content)
            label.setStyleSheet(MUTED_STYLE)
            value = QLabel("–", self.content)
            setFont(value, 22, QFont.Weight.DemiBold)
            grid.addWidget(label, 0, column)
            grid.addWidget(value, 1, column)
            values.append(value)
        grid.setColumnStretch(len(labels), 1)
        self.contentLayout.addLayout(grid)
        return values

    def _build_chart(self) -> QChartView:
        self.series = QLineSeries()
        pen = QPen(QColor(ACCENT))
        pen.setWidth(2)
        self.series.setPen(pen)
        self.series.setMarkerSize(8)
        self.series.hovered.connect(self._on_point_hovered)

        chart = QChart()
        chart.addSeries(self.series)
        chart.legend().hide()
        chart.setMargins(QMargins(0, 8, 8, 0))
        chart.setBackgroundRoundness(0)

        self.xAxis = QDateTimeAxis()
        self.xAxis.setFormat("MM. dd.")
        self.yAxis = QValueAxis()
        self.yAxis.setLabelFormat("%d")
        self.yAxis.setTitleText("Kihasználtság (%)")
        for axis in (self.xAxis, self.yAxis):
            axis.setLabelsColor(QColor(TEXT_SECONDARY))
            axis.setGridLineColor(QColor(BORDER))
            axis.setLinePenColor(QColor(BORDER))
            axis.setTitleBrush(QColor(TEXT_SECONDARY))
        self.xAxis.setGridLineVisible(False)
        chart.addAxis(self.xAxis, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(self.yAxis, Qt.AlignmentFlag.AlignLeft)
        self.series.attachAxis(self.xAxis)
        self.series.attachAxis(self.yAxis)

        view = QChartView(chart, self.content)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(280)
        return view

    # --- Data ---

    def refresh(self) -> None:
        if not self.can_load():
            return
        from_date, to_date = self.fromDate.date(), self.toDate.date()
        if from_date > to_date:
            self.show_message("A kezdő dátum nem lehet későbbi a záró dátumnál.", error=True)
            return
        self.refreshButton.setEnabled(False)
        self.applyButton.setEnabled(False)
        self.show_message("Statisztikák betöltése...")
        run_in_background(
            _load_stats, from_date.toString("yyyy-MM-dd"), to_date.toString("yyyy-MM-dd"),
            on_success=self._on_loaded, on_error=self._on_load_error,
        )

    def _on_load_error(self, error: ApiError) -> None:
        self.refreshButton.setEnabled(True)
        self.applyButton.setEnabled(True)
        self.show_message(error.message, error=True)

    def _on_loaded(self, stats: dict) -> None:
        self.refreshButton.setEnabled(True)
        self.applyButton.setEnabled(True)
        self._show_now(stats["now"])
        self._show_history(stats["history"])
        self._show_couriers(stats["couriers"])
        history = stats["history"]
        self.show_message(f"Időszak: {format_date(history['from_date'])} – {format_date(history['to_date'])}")

    def _show_now(self, now: dict) -> None:
        percent = now["utilization_percent"]
        self.meter.set_percent(percent)
        text = f"{now['parcel_count']} / {now['capacity']} csomag ({_number(percent)} %)"
        if percent >= CRITICAL_PERCENT:
            text += " · Majdnem tele"
        elif percent >= WARNING_PERCENT:
            text += " · Magas kihasználtság"
        self.nowLabel.setText(text)
        sizes = now["by_size"]
        self.sizeLabel.setText(
            f"{now['name']} · méret szerint: " + " · ".join(f"{size}: {sizes[size]}" for size in ("S", "M", "L", "XL"))
        )

    def _show_history(self, history: dict) -> None:
        points = history["points"]
        self.history_points = points
        self.historyTiles[0].setText(f"{_number(history['avg_utilization_percent'])} %")
        self.historyTiles[1].setText(f"{history['peak_parcel_count']} csomag")
        fill_table(self.historyTable, [
            [format_date(p["day"]), str(p["parcel_count"]), f"{_number(p['utilization_percent'])} %"]
            for p in points
        ])

        self.series.clear()
        for point in points:
            self.series.append(QPointF(self._msecs(point["day"]), point["utilization_percent"]))
        # Markers only while they do not crowd the line
        self.series.setPointsVisible(len(points) <= 14)
        if points:
            first, last = self._msecs(points[0]["day"]), self._msecs(points[-1]["day"])
            self.xAxis.setRange(QDateTime.fromMSecsSinceEpoch(first), QDateTime.fromMSecsSinceEpoch(max(last, first + 1)))
            self.xAxis.setTickCount(min(max(len(points), 2), 8))
        peak = max((p["utilization_percent"] for p in points), default=0)
        self.yAxis.setRange(0, max(100, ceil(peak / 10) * 10))
        self.yAxis.setTickCount(6)

    def _show_couriers(self, report: dict) -> None:
        totals = report["daily_totals"]
        tiles = self.courierTiles
        tiles[0].setText(str(sum(day["pickups"] for day in totals)))
        tiles[1].setText(str(sum(day["deliveries"] for day in totals)))
        tiles[2].setText(str(sum(day["failed"] for day in totals)))
        minutes = report["avg_delivery_minutes"]
        hours = report["avg_lead_time_hours"]
        tiles[3].setText("–" if minutes is None else f"{_number(minutes, 0)} perc")
        tiles[4].setText("–" if hours is None else f"{_number(hours)} óra")
        fill_table(self.courierTable, [
            [
                full_name(item["courier"]),
                str(item["pickups_count"]),
                str(item["deliveries_count"]),
                str(item["failed_count"]),
                str(item["active_days"]),
                _number(item["avg_deliveries_per_day"]),
                _number(item["avg_delivery_minutes"], 0),
                _number(item["avg_lead_time_hours"]),
            ]
            for item in report["couriers"]
        ])

    @staticmethod
    def _msecs(day: str) -> int:
        return QDateTime(QDate.fromString(day, "yyyy-MM-dd"), QTime(0, 0)).toMSecsSinceEpoch()

    def _on_point_hovered(self, point: QPointF, state: bool) -> None:
        if not state or not self.history_points:
            QToolTip.hideText()
            return
        nearest = min(self.history_points, key=lambda p: abs(self._msecs(p["day"]) - point.x()))
        QToolTip.showText(
            QCursor.pos(),
            f"{format_date(nearest['day'])}: {nearest['parcel_count']} csomag "
            f"({_number(nearest['utilization_percent'])} %)",
        )
