import logging
from pathlib import Path
from qfluentwidgets import (
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    PrimaryPushButton,
    setFont,
    CardWidget,
    ComboBox
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from enum import Enum

from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QFont, QIcon
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QStackedLayout
from api_client import STATUS_LABELS, api, run_in_background
from qtlottie import init_qml

logger = logging.getLogger(__name__)

class ManagerEndPoints(str, Enum):
    PICKUP = "pickup"
    START = "start"
    DELIVER = "deliver"
    FAIL = "fail"


class ManagementInterface(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(' ', '-'))
        
    
        self.mainLayout = QStackedLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setStackingMode(
            QStackedLayout.StackingMode.StackAll
        )

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

         #-------Form Title-------
        self.title = SubtitleLabel("Csomagkezelés", self.contentWidget)
        setFont(self.title, 60, QFont.Bold)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("background: transparent;")

        #-------Body Label-------
        self.description = BodyLabel(
                    "Csomag állatot jelölés",
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
        self.managementContainer = QWidget(self.contentWidget)
        self.managementContainer.setStyleSheet("background: transparent;")
        self.managementContainer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            vertical_policy,
        )
        self.managementLayout = QHBoxLayout(self.managementContainer)
        self.managementLayout.setContentsMargins(0, 0, 0, 0)
        
        #--------Combo Box-----------
        
        self.statusBox = ComboBox(self.managementContainer)

        # Add options
        self.statusBox.addItem('Felvett', userData=ManagerEndPoints.PICKUP.value);
        self.statusBox.addItem('Kiszálított', userData=ManagerEndPoints.DELIVER.value);
        self.statusBox.addItem('Kezdés', userData=ManagerEndPoints.START.value);
        self.statusBox.addItem('Töröl', userData=ManagerEndPoints.FAIL.value);
        
        setFont(self.statusBox, 24, QFont.Bold)
        self.statusBox.setFixedHeight(100)
        self.statusBox.setStyleSheet("border-radius: 25px")
        self.statusBox.setPlaceholderText("Válassz...")
        self.statusBox.setCurrentIndex(-1);

        # Signal of current option index change
        self.statusBox.currentIndexChanged.connect(self._on_track_box_changed)

        
        
        #--------Search Input----------
        self.parcelEdit = LineEdit(self.managementContainer)
        self.parcelEdit.setPlaceholderText("Csomag azonosító")
        self.parcelEdit.setClearButtonEnabled(True)
        self.parcelEdit.setTextMargins(44, 0, 8, 0)
        setFont(self.parcelEdit, 24, QFont.Bold)
        self.parcelEdit.setFixedHeight(100)
        self.parcelEdit.setStyleSheet("border-radius: 25px")
        self.searchIcon = QSvgWidget(
            ":/icons/barcode.svg",
             self.parcelEdit
        )
        self.searchIcon.setFixedSize(28, 28)
        self.searchIcon.move(10, (self.parcelEdit.height() - self.searchIcon.height()) // 2)
        #--------Status  Button---------
        self.searchButton = PrimaryPushButton("", self.managementContainer)
        self.searchButton.setIcon(QIcon(":/icons/package-start.svg"))
        self.searchButton.setIconSize(QSize(36, 36))
        self.searchButton.clicked.connect(self.onClickStatus)
        self.searchButton.setFixedHeight(100)
        self.searchButton.setFixedWidth(100)
        self.searchButton.setStyleSheet("border-radius: 25px; background-color: #2383E2;")



        #------Add Widget to Horizontal Search Layout
        self.managementLayout.addStretch(1)
        self.managementLayout.addWidget(self.statusBox, 1, Qt.AlignVCenter)
        self.managementLayout.addSpacing(15)
        self.managementLayout.addWidget(self.parcelEdit, 2, Qt.AlignVCenter)
        self.managementLayout.addSpacing(15)
        self.managementLayout.addWidget(self.searchButton, 1, Qt.AlignVCenter)
        self.managementLayout.addStretch(1)



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
        self.trackingCardContent.setSpacing(0)

        self.trackingInfo = QWidget(self.trackingCard)
        self.trackingInfo.setStyleSheet("background: transparent;")
        self.trackingInfoLayout = QVBoxLayout(self.trackingInfo)
        self.trackingInfoLayout.setContentsMargins(0, 0, 0, 0)
        self.trackingInfoLayout.setSpacing(8)
        self.currentStatusLabel = QLabel("")
        self.currentStatusLabel.setStyleSheet(
            "color: #2383E2; font-size: 20px; font-weight: 700;"
            "background: transparent;"
        )
        self.trackingInfoLayout.addWidget(self.currentStatusLabel)

        self.trackingNumberLabel = QLabel("")
        self.trackingNumberLabel.setStyleSheet(
            "font-size: 15px; font-weight: 600; background: transparent;"
        )
        self.trackingInfoLayout.addWidget(self.trackingNumberLabel)

        self.packageSizeLabel = QLabel("")
        self.packageSizeLabel.setStyleSheet(
            "color: #6B6B6B; background: transparent;"
        )
        self.trackingInfoLayout.addWidget(self.packageSizeLabel)
        self.trackingCardContent.addWidget(self.trackingInfo, 3)

        self.lottieAnimationContainer = QWidget(self.trackingCard)
        self.lottieAnimationContainer.setObjectName("lottieAnimationContainer")
        self.lottieAnimationContainer.setStyleSheet("background: transparent;")
        self.trackingCardContent.addWidget(self.lottieAnimationContainer, 7)
        self.lottieAnimationPath = (
            Path(__file__).resolve().parents[2]
            / "resources"
            / "animations"
            / "delivery.json"
        )
        self.lottieAnimationLayout = QVBoxLayout(self.lottieAnimationContainer)
        self.lottieAnimationLayout.setContentsMargins(0, 0, 0, 0)
        self.lottieAnimationWidget: QQuickWidget | None = None
        self._load_lottie_animation()



       

        #--------Add Widgets to Vertical Layout---------
        self.hVoxLayout.addSpacing(15)
        self.hVoxLayout.addWidget(self.title,1)
        self.hVoxLayout.addWidget(self.description,1)
        self.hVoxLayout.addWidget(self.managementContainer,3)
        self.hVoxLayout.addLayout(self.trackingCardLayout,5)
        self.hVoxLayout.addSpacing(15)
        
        #hide tracking card
        self.hide_widget(self.trackingCard)
        
        
        
    def set_tracking_card(self, parcelTracking) -> None:
        self.trackingNumberLabel.setText(f"Csomagszám: {parcelTracking['tracking_number']}");
        self.packageSizeLabel.setText(f"{parcelTracking['size']} Méret");
        status = parcelTracking["status"]
        self.currentStatusLabel.setText(STATUS_LABELS.get(status, status))
        
        if not self.trackingCard.isVisible():
            self.trackingCard.show();

    def _load_lottie_animation(self) -> None:
        if not self.lottieAnimationPath.is_file():
            logger.warning(
                "Lottie animation file not found: %s",
                self.lottieAnimationPath,
            )
            return

        if not init_qml():
            raise RuntimeError("Could not register the Qt Lottie QML component.")

        qml_path = (
            Path(__file__).resolve().parents[2]
            / "resources"
            / "animations"
            / "lottie_player.qml"
        )
        self.lottieAnimationWidget = QQuickWidget(self.lottieAnimationContainer)
        self.lottieAnimationWidget.setResizeMode(
            QQuickWidget.ResizeMode.SizeRootObjectToView
        )
        self.lottieAnimationWidget.setClearColor(Qt.GlobalColor.transparent)
        self.lottieAnimationWidget.rootContext().setContextProperty(
            "animationSource",
            QUrl.fromLocalFile(str(self.lottieAnimationPath)),
        )
        self.lottieAnimationWidget.statusChanged.connect(
            self._on_lottie_status_changed
        )
        self.lottieAnimationLayout.addWidget(self.lottieAnimationWidget)
        self.lottieAnimationWidget.setSource(QUrl.fromLocalFile(str(qml_path)))

        animation = self.lottieAnimationWidget.rootObject()
        if animation is not None:
            animation.error.connect(self._on_lottie_error)

        if self.lottieAnimationWidget.status() == QQuickWidget.Status.Error:
            self._on_lottie_status_changed(QQuickWidget.Status.Error)

    def _on_lottie_status_changed(self, status) -> None:
        widget = self.lottieAnimationWidget
        if status != QQuickWidget.Status.Error or widget is None:
            return
        errors = "; ".join(error.toString() for error in widget.errors())
        logger.error("Could not load Lottie player: %s", errors)

    @staticmethod
    def _on_lottie_error(message: str) -> None:
        logger.error("Lottie animation failed: %s", message)
            
    
    def hide_widget(self, widget : QWidget) -> None:
        sp_retain = widget.sizePolicy()
        sp_retain.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(sp_retain)
        widget.hide()
        
    def onClickStatus(self) -> None:
        self.searchButton.setEnabled(False)
        parcel_id : str = self.parcelEdit.text().strip()
        end_point : str = self.statusBox.currentData();
        run_in_background(
            api.post,
            f"/courier/parcels/{parcel_id}/{end_point}",
            on_success=self._on_tracking_success,
            on_error=self._on_tracking_error,
        )
    def _on_tracking_success(self, result: object) -> None:
        #self.set_tracking_card(result)
        print(result);
        self.searchButton.setEnabled(True)
        
    def _on_tracking_error(self) -> None:
        self.searchButton.setEnabled(True)
    
    def _on_track_box_changed(self) -> None:
        if self.statusBox.currentIndex() == 0: #Felvett
            self.searchButton.setIcon(QIcon(":/icons/package-plus.svg"))
        elif self.statusBox.currentIndex() == 1: #Kiszálított
            self.searchButton.setIcon(QIcon(":/icons/package-check.svg"))
        elif self.statusBox.currentIndex() == 2: #Kezdés
            self.searchButton.setIcon(QIcon(":/icons/package-start.svg"))
        elif self.statusBox.currentIndex() == 3: #Törlés
            self.searchButton.setIcon(QIcon(":/icons/package-x.svg"))
