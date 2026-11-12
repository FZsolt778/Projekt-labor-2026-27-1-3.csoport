from qfluentwidgets import (
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    setFont,
    CardWidget
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from api_client import ApiError, api, run_in_background
from PySide6.QtWidgets import QStackedLayout

from types import SimpleNamespace
import json


class ParcelTrackingTimeline(QWidget):
    STEPS = (
        ("booked", "Feladva"),
        ("picked_up", "Felvéve"),
        ("in_warehouse", "Raktárban"),
        ("out_for_delivery", "Kiszállítás"),
        ("delivered", "Kézbesítve"),
    )
    STATUS_STEP = {
        "booked": 0,
        "pickup_assigned": 0,
        "picked_up": 1,
        "warehouse_arrived": 2,
        "in_warehouse": 2,
        "delivery_assigned": 2,
        "out_for_delivery": 3,
        "delivered": 4,
        "failed": -1,
        "cancelled": -1,
    }
    STATUS_LABELS = {
        "booked": "Előjegyezve",
        "pickup_assigned": "Felvételre kiosztva",
        "picked_up": "Felvéve",
        "warehouse_arrived": "Raktárba érkezett",
        "in_warehouse": "Raktárban",
        "delivery_assigned": "Kiszállításra kiosztva",
        "out_for_delivery": "Kiszállítás alatt",
        "delivered": "Kézbesítve",
        "failed": "Sikertelen kézbesítés",
        "cancelled": "Lemondva",
    }

    def __init__(self, status: str, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(66)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        normalized_status = status.strip().lower()
        if normalized_status not in self.STATUS_STEP:
            raise ValueError(f"Ismeretlen csomagállapot: {status}")
        self.status = normalized_status
        self.active_step = self.STATUS_STEP[normalized_status]
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left = self.width() / 10
        right = self.width() - left
        center_y = 12
        step_distance = (right - left) / (len(self.STEPS) - 1)
        active_color = QColor("#2383E2")
        inactive_color = QColor("#C8CDD2")

        painter.setPen(QPen(inactive_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(left, center_y, right, center_y)
        if self.active_step > 0:
            painter.setPen(QPen(active_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(
                left,
                center_y,
                left + step_distance * self.active_step,
                center_y,
            )

        for index in range(len(self.STEPS)):
            point = left + step_distance * index
            is_active = index <= self.active_step
            painter.setPen(QPen(active_color if is_active else inactive_color, 2))
            painter.setBrush(active_color if is_active else QColor("#FFFFFF"))
            painter.drawEllipse(int(point - 6), center_y - 6, 12, 12)

            label_width = int(step_distance)
            label_x = int(point - label_width / 2)
            painter.setPen(active_color if is_active else QColor("#6B6B6B"))
            painter.setFont(QFont(self.font().family(), 9))
            painter.drawText(
                QRect(label_x, 26, label_width, 34),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self.STEPS[index][1],
            )

        painter.end()


class TrackingInterface(QFrame):
    


    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)

        self.setObjectName(text.replace(" ", "-"))

            

        self.mainLayout = QStackedLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setStackingMode(
            QStackedLayout.StackingMode.StackAll
        )

        # Háttér
        self.illustration = QSvgWidget(
            ":/illustrations/track.svg"
        )
        self.illustration.renderer().setAspectRatioMode(
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.illustration.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.illustration.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored
        )

        self.mainLayout.addWidget(self.illustration)

        # Előtér
        self.contentWidget = QWidget(self)
        self.contentWidget.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.contentWidget.setStyleSheet("background: transparent;")

        self.hVoxLayout = QVBoxLayout(self.contentWidget)
        self.hVoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hVoxLayout.setSpacing(0)

        self.mainLayout.addWidget(self.contentWidget)
        self.mainLayout.setCurrentWidget(self.contentWidget)

        self.title = SubtitleLabel("Csomagkövetés", self.contentWidget)
        setFont(self.title, 60, QFont.Bold)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("background: transparent;")

        #-------Body Label-------
        self.description = BodyLabel(
                    "Keresse meg csomagját",
                    self.contentWidget
                )
        
        self.description.setAlignment(Qt.AlignCenter)
        setFont(self.description,25)
        self.description.setStyleSheet(
            "color: gray; background: transparent;"
        )

        vertical_policy = QSizePolicy.Policy.Ignored
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, vertical_policy)
        self.description.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            vertical_policy,
        )

        #--------Search Layout---------
        self.searchContainer = QWidget(self.contentWidget)
        self.searchContainer.setStyleSheet("background: transparent;")
        self.searchContainer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            vertical_policy,
        )
        self.searchLayout = QHBoxLayout(self.searchContainer)
        self.searchLayout.setContentsMargins(0, 0, 0, 0)
        #--------Search Input----------
        self.searchEdit = LineEdit(self.searchContainer)
        self.searchEdit.setPlaceholderText("Csomag azonosító")
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.setTextMargins(44, 0, 8, 0)
        setFont(self.searchEdit, 24, QFont.Bold)
        self.searchEdit.setFixedHeight(100)
        self.searchEdit.setStyleSheet("border-radius: 25px")
        self.searchIcon = QSvgWidget(
            ":/icons/barcode.svg",
             self.searchEdit
        )
        self.searchIcon.setFixedSize(28, 28)
        self.searchIcon.move(10, (self.searchEdit.height() - self.searchIcon.height()) // 2)
        #--------Search Button---------
        self.searchButton = PrimaryPushButton("", self.searchContainer)
        self.searchButton.setIcon(QIcon(":/icons/search.svg"))
        self.searchButton.setIconSize(QSize(36, 36))
        self.searchButton.clicked.connect(self.onClickTrack)
        self.searchButton.setFixedHeight(100)
        self.searchButton.setFixedWidth(100)
        self.searchButton.setStyleSheet("border-radius: 25px; background-color: #2383E2;")



        #------Add Widget to Horizontal Search Layout
        self.searchLayout.addStretch(1)
        self.searchLayout.addWidget(self.searchEdit, 2, Qt.AlignVCenter)
        self.searchLayout.addSpacing(15)
        self.searchLayout.addWidget(self.searchButton, 1, Qt.AlignVCenter)
        self.searchLayout.addStretch(1)






        #Tracking Card
        self.trackingCard = CardWidget(self.contentWidget)
        self.trackingCard.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Ignored,
        )
        self.trackingCardLayout = QHBoxLayout()
        self.trackingCardLayout.setContentsMargins(0, 0, 0, 0)
        self.trackingCardLayout.setSpacing(0)
        self.trackingCardLayout.addStretch(1)
        self.trackingCardLayout.addWidget(self.trackingCard, 1)
        self.trackingCardLayout.addStretch(1)

        self.trackingCardContent = QVBoxLayout(self.trackingCard)
        self.trackingCardContent.setContentsMargins(24, 20, 24, 20)
        self.trackingCardContent.setSpacing(10)

        self.trackingNumberLabel = QLabel("")
        self.trackingNumberLabel.setStyleSheet(
            "font-size: 15px; font-weight: 600; background: transparent;"
        )
        self.packageSizeLabel = QLabel("")
        self.packageSizeLabel.setStyleSheet(
            "color: #6B6B6B; background: transparent;"
        )
        self.trackingHeader = QHBoxLayout()
        self.trackingHeader.addWidget(self.trackingNumberLabel)
        self.trackingHeader.addStretch(1)
        self.trackingHeader.addWidget(self.packageSizeLabel)
        self.trackingCardContent.addLayout(self.trackingHeader)

        self.currentStatusLabel = QLabel("")
        self.currentStatusLabel.setStyleSheet(
            "color: #2383E2; font-size: 20px; font-weight: 700;"
            "background: transparent;"
        )
        self.trackingCardContent.addWidget(self.currentStatusLabel)

        self.trackingTimeline = ParcelTrackingTimeline(
            "booked",
            self.trackingCard,
        )
        self.trackingCardContent.addWidget(self.trackingTimeline)

        self.routeLabel = QLabel("")
        self.routeLabel.setWordWrap(True)
        self.routeLabel.setStyleSheet(
            "font-size: 14px; font-weight: 600; background: transparent;"
        )
        self.trackingCardContent.addWidget(self.routeLabel)

        self.deliveryDateLabel = QLabel("")
        self.deliveryDateLabel.setStyleSheet(
            "color: #6B6B6B; background: transparent;"
        )
        self.trackingCardContent.addWidget(self.deliveryDateLabel)

        self.lastEventLabel = QLabel("") #Legutóbbi esemény: A csomag úton van a címzetthez.
        self.lastEventLabel.setWordWrap(True)
        self.lastEventLabel.setStyleSheet(
            "color: #6B6B6B; background: transparent;"
        )
        self.trackingCardContent.addWidget(self.lastEventLabel)
        self.trackingCardContent.addStretch(1)



       

        #--------Add Widgets to Vertical Layout---------
        self.hVoxLayout.addSpacing(15)
        self.hVoxLayout.addWidget(self.title,1)
        self.hVoxLayout.addWidget(self.description,1)
        self.hVoxLayout.addWidget(self.searchContainer,3)
        self.hVoxLayout.addLayout(self.trackingCardLayout,5)
        self.hVoxLayout.addSpacing(15)
        
        #hide tracking card
        self.hide_widget(self.trackingCard)
        
        
        
    def set_tracking_card(self, parcelTracking) -> None:
        self.trackingNumberLabel.setText(f"Csomagszám: {parcelTracking['tracking_number']}");
        self.packageSizeLabel.setText(f"{parcelTracking['size']} Méret");
        self.routeLabel.setText(f"{parcelTracking['sender']['city']}, feladó  →  {parcelTracking['recipient']['city']}, címzett")
        self.deliveryDateLabel.setText(f"Várható kézbesítés: {parcelTracking['delivery_date']}")
        
        self.set_tracking_status(parcelTracking['status'])
        
        if not self.trackingCard.isVisible():
            self.trackingCard.show();
        



    def set_tracking_status(self, status: str) -> None:
        self.trackingTimeline.set_status(status)
        self.currentStatusLabel.setText(
            ParcelTrackingTimeline.STATUS_LABELS[self.trackingTimeline.status]
        )
        
    
    def hide_widget(self, widget : QWidget) -> None:
        sp_retain = widget.sizePolicy()
        sp_retain.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(sp_retain)
        widget.hide()
        
    def onClickTrack(self) -> None:
        self.searchButton.setEnabled(False)
        trackingNumber : str = self.searchEdit.text().strip()
        run_in_background(
            api.get,
            f"/parcels/track/{trackingNumber}",
            on_success=self._on_tracking_success,
            on_error=self._on_tracking_error,
        )
    def _on_tracking_success(self, result: object) -> None:
        self.set_tracking_card(result)
        self.searchButton.setEnabled(True)
        
    def _on_tracking_error(self) -> None:
        self.searchButton.setEnabled(True)
    
    
        