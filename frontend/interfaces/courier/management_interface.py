import logging
from pathlib import Path
from qfluentwidgets import (
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    PrimaryPushButton,
    setFont,
    CardWidget,
    ComboBox,
    InfoBar,
    InfoBarPosition,
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
from api_client import ApiError, STATUS_LABELS, api, run_in_background
from qtlottie import init_qml
from .courier_actions import ask_fail_note

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
                    "Csomag állapotának rögzítése",
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
        self.statusBox.addItem('Kiszállított', userData=ManagerEndPoints.DELIVER.value);
        self.statusBox.addItem('Kezdés', userData=ManagerEndPoints.START.value);
        self.statusBox.addItem('Sikertelen kísérlet', userData=ManagerEndPoints.FAIL.value);
        
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
        self.trackingCardContent.setSpacing(8)

        self.trackingInfo = QWidget(self.trackingCard)
        self.trackingInfo.setStyleSheet("background: transparent;")
        self.trackingInfo.setMaximumHeight(100)
        self.trackingInfoLayout = QVBoxLayout(self.trackingInfo)
        self.trackingInfoLayout.setContentsMargins(0, 0, 0, 0)
        self.trackingInfoLayout.setSpacing(8)
        self.currentStatusLabel = QLabel("")
        self.currentStatusLabel.setStyleSheet(
            "color: #2383E2; font-size: 22px; font-weight: 700;"
            "background: transparent;"
        )
        self.currentStatusLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.currentStatusLabel.setWordWrap(True)
        self.trackingInfoLayout.addWidget(self.currentStatusLabel)

        self.trackingNumberLabel = QLabel("")
        self.trackingNumberLabel.setStyleSheet(
            "font-size: 15px; font-weight: 600; background: transparent;"
        )
        self.trackingNumberLabel.hide()
        self.trackingInfoLayout.addWidget(self.trackingNumberLabel)

        self.packageSizeLabel = QLabel("")
        self.packageSizeLabel.setStyleSheet(
            "color: #6B6B6B; background: transparent;"
        )
        self.packageSizeLabel.hide()
        self.trackingInfoLayout.addWidget(self.packageSizeLabel)
        self.trackingCardContent.addWidget(self.trackingInfo)

        self.lottieAnimationContainer = QWidget(self.trackingCard)
        self.lottieAnimationContainer.setObjectName("lottieAnimationContainer")
        self.lottieAnimationContainer.setStyleSheet("background: transparent;")
        self.trackingCardContent.addWidget(self.lottieAnimationContainer, 1)

        self.lottieAnimationPath = (
            Path(__file__).resolve().parents[2]
            / "resources"
            / "animations"
            / "PACKAGE_DELIVERED.json"
        )
        self.lottieAnimationLayout = QVBoxLayout(self.lottieAnimationContainer)
        self.lottieAnimationLayout.setContentsMargins(0, 0, 0, 0)
        self.lottieAnimationWidget: QQuickWidget | None = None
        self._lottiePlaybackPending = False
        self._lottieErrorConnected = False
        self._activeInfoBar = None


       

        #--------Add Widgets to Vertical Layout---------
        self.hVoxLayout.addSpacing(15)
        self.hVoxLayout.addWidget(self.title,1)
        self.hVoxLayout.addWidget(self.description,1)
        self.hVoxLayout.addWidget(self.managementContainer,3)
        self.hVoxLayout.addLayout(self.trackingCardLayout,5)
        self.hVoxLayout.addSpacing(15)
        
        #hide tracking card
        self.hide_widget(self.trackingCard)
        self.lottieAnimationContainer.hide()
        # Lottie is temporarily disabled; the status message remains active.
        # self._load_lottie_animation(play=False)
        
    def set_tracking_card(self, parcelTracking) -> None:
        self.trackingNumberLabel.setText(f"Csomagszám: {parcelTracking['tracking_number']}");
        self.packageSizeLabel.setText(f"{parcelTracking['size']} Méret");
        self.trackingNumberLabel.show()
        self.packageSizeLabel.show()
        status = parcelTracking["status"]
        self.currentStatusLabel.setText(STATUS_LABELS.get(status, status))
        
        if not self.trackingCard.isVisible():
            self.trackingCard.show();

    def _load_lottie_animation(self, play: bool = True) -> None:
        if not self.lottieAnimationPath.is_file():
            logger.warning(
                "Lottie animation file not found: %s",
                self.lottieAnimationPath,
            )
            return

        if self.lottieAnimationWidget is None:
            if not init_qml():
                raise RuntimeError("Could not register the Qt Lottie QML component.")

            qml_path = (
                Path(__file__).resolve().parents[2]
                / "resources"
                / "animations"
                / "lottie_player.qml"
            )
            self.lottieAnimationWidget = QQuickWidget(
                self.lottieAnimationContainer
            )
            self.lottieAnimationWidget.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground
            )
            self.lottieAnimationWidget.setAttribute(
                Qt.WidgetAttribute.WA_AlwaysStackOnTop
            )
            self.lottieAnimationWidget.setResizeMode(
                QQuickWidget.ResizeMode.SizeRootObjectToView
            )
            self.lottieAnimationWidget.setClearColor(Qt.GlobalColor.transparent)
            self.lottieAnimationWidget.setStyleSheet("background: transparent;")
            self.lottieAnimationWidget.statusChanged.connect(
                self._on_lottie_status_changed
            )
            self.lottieAnimationWidget.rootContext().setContextProperty(
                "animationSource",
                QUrl.fromLocalFile(str(self.lottieAnimationPath)),
            )
            self.lottieAnimationLayout.addWidget(self.lottieAnimationWidget)
            self.lottieAnimationWidget.setSource(
                QUrl.fromLocalFile(str(qml_path))
            )
        else:
            self.lottieAnimationWidget.rootContext().setContextProperty(
                "animationSource",
                QUrl.fromLocalFile(str(self.lottieAnimationPath)),
            )
        animation = self.lottieAnimationWidget.rootObject()
        if animation is None:
            self._lottiePlaybackPending = play
            return

        if not self._lottieErrorConnected:
            animation.error.connect(self._on_lottie_error)
            self._lottieErrorConnected = True

        self._lottiePlaybackPending = False
        animation.stop()
        if play:
            animation.play()

    def _on_lottie_status_changed(self, status) -> None:
        widget = self.lottieAnimationWidget
        if widget is None:
            return
        if status == QQuickWidget.Status.Error:
            errors = "; ".join(error.toString() for error in widget.errors())
            logger.error("Could not load Lottie player: %s", errors)
            return

        if status == QQuickWidget.Status.Ready and self._lottiePlaybackPending:
            animation = widget.rootObject()
            if animation is not None:
                animation.error.connect(self._on_lottie_error)
                self._lottieErrorConnected = True
                self._lottiePlaybackPending = False
                animation.stop()
                animation.play()

    @staticmethod
    def _on_lottie_error(message: str) -> None:
        logger.error("Lottie animation failed: %s", message)
            
    
    def hide_widget(self, widget : QWidget) -> None:
        sp_retain = widget.sizePolicy()
        sp_retain.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(sp_retain)
        widget.hide()

    def _get_lottie_json(self, action: str) -> str | None:
        return {
            ManagerEndPoints.PICKUP.value: "PACKAGE_PICKUP.json",
            ManagerEndPoints.START.value: "PACKAGE_STARTED.json",
            ManagerEndPoints.DELIVER.value: "PACKAGE_DELIVERED.json",
            ManagerEndPoints.FAIL.value: "PACKAGE_CANCELLED.json",
        }.get(action)

    def onClickStatus(self) -> None:
        parcel_id : str = self.parcelEdit.text().strip()
        end_point : str = self.statusBox.currentData();
        if end_point is None:
            self._show_info_bar(InfoBar.warning, "Hiányzó adat", "Válaszd ki, mit szeretnél rögzíteni.")
            return
        if not parcel_id:
            self._show_info_bar(InfoBar.warning, "Hiányzó adat", "Add meg a csomagszámot.")
            return
        # The server requires a reason for a failed attempt
        body = None
        if end_point == ManagerEndPoints.FAIL.value:
            note = ask_fail_note(self, parcel_id)
            if note is None:
                return
            body = {"note": note}
        self.searchButton.setEnabled(False)
        run_in_background(
            api.post,
            f"/courier/parcels/{parcel_id}/{end_point}",
            body,
            on_success=lambda result: self._on_tracking_success(
                result,
                end_point,
                parcel_id,
            ),
            on_error=self._on_tracking_error,
        )
    def _on_tracking_success(
        self,
        result: object,
        action: str,
        requested_tracking_number: str,
    ) -> None:
        self.searchButton.setEnabled(True)
        response_tracking_number = (
            result.get("tracking_number") if isinstance(result, dict) else None
        )
        if not isinstance(response_tracking_number, str):
            response_tracking_number = requested_tracking_number

        action_messages = {
            ManagerEndPoints.PICKUP.value: "Felvette a {} csomagot.",
            ManagerEndPoints.START.value: "Elindult a {} csomaggal.",
            ManagerEndPoints.DELIVER.value: "Kézbesítette a {} csomagot.",
            ManagerEndPoints.FAIL.value: "Sikertelen kísérlet rögzítve: {}.",
        }
        message_template = action_messages.get(
            action,
            "A {} csomag állapota frissült.",
        )
        self.currentStatusLabel.setText(
            message_template.format(response_tracking_number)
        )
        self.trackingNumberLabel.clear()
        self.packageSizeLabel.clear()
        self.trackingNumberLabel.hide()
        self.packageSizeLabel.hide()
        self.trackingCard.show()
        self._show_info_bar(
            InfoBar.success,
            "Sikeres művelet",
            message_template.format(response_tracking_number),
        )

        # Lottie is temporarily disabled; the status message remains active.
        # animation_file = self._get_lottie_json(action)
        # if animation_file is not None:
        #     self.lottieAnimationPath = self.lottieAnimationPath.parent / animation_file
        #     self._load_lottie_animation(play=True)
        
    def _on_tracking_error(self, error: ApiError) -> None:
        self.searchButton.setEnabled(True)
        self._show_info_bar(
            InfoBar.error,
            "Sikertelen művelet",
            error.message,
        )

    def _show_info_bar(self, show, title: str, content: str) -> None:
        if self._activeInfoBar is not None:
            try:
                self._activeInfoBar.close()
            except RuntimeError:
                pass

        self._activeInfoBar = show(
            title=title,
            content=content,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=4000,
            parent=self,
        )
    
    def _on_track_box_changed(self) -> None:
        if self.statusBox.currentIndex() == 0: #Felvett
            self.searchButton.setIcon(QIcon(":/icons/package-plus.svg"))
        elif self.statusBox.currentIndex() == 1: #Kiszállított
            self.searchButton.setIcon(QIcon(":/icons/package-check.svg"))
        elif self.statusBox.currentIndex() == 2: #Kezdés
            self.searchButton.setIcon(QIcon(":/icons/package-start.svg"))
        elif self.statusBox.currentIndex() == 3: #Törlés
            self.searchButton.setIcon(QIcon(":/icons/package-x.svg"))
