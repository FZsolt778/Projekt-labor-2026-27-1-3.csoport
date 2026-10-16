from qfluentwidgets import (
    NavigationItemPosition,
    FluentWindow,
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    CheckBox,
    setFont,
    FluentIcon as FIF,
    SearchLineEdit,
    PushButton
)

from pathlib import Path

from PySide6.QtCore import (Qt,QUrl)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QGraphicsDropShadowEffect
)

import qtlottie
qtlottie.init_qml()

from PySide6.QtQuickWidgets import QQuickWidget


from PySide6.QtGui import QColor

class TrackInterface(QFrame):
    def __init__(self, parent = None):
        super().__init__(parent = parent)
        #Object name
        self.setObjectName("TrackInterface")
        
        # Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(80, 60, 80, 60)
        self.layout.setSpacing(15)
        
        # Tittle
        self.title = SubtitleLabel("Csomagkövetés", self)
        setFont(self.title, 28)

        self.track_line = SearchLineEdit(self)
        self.track_line.setPlaceholderText("Csomag Azonosító")
        self.track_line.setClearButtonEnabled(True)
        self.track_line.setFixedSize(400,60)
        self.track_line.setStyleSheet("""
        SearchLineEdit {
        border-radius: 25%;
        font-size: 20px;
        padding: 8px 12px;
        }
        """)

        #shadow
        shadow = QGraphicsDropShadowEffect(self.track_line)
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))

        self.track_line.setGraphicsEffect(shadow)

        #lottie




# A TrackInterface.__init__ metódusában:

        base_dir = Path(__file__).resolve().parent
        qml_path = "package_animation.qml"

        self.animation = QQuickWidget(self)
        self.animation.setResizeMode(
            QQuickWidget.ResizeMode.SizeRootObjectToView
        )
        self.animation.statusChanged.connect(
            lambda status: print(
                "Lottie QML hibák:",
                [e.toString() for e in self.animation.errors()]
            ) if status == QQuickWidget.Status.Error else None
        )
        self.animation.setSource(QUrl.fromLocalFile(str(qml_path)))
        self.animation.setFixedSize(180, 180)

        self.animation.setClearColor(Qt.transparent)

        self.layout.addWidget(
            self.title,
            alignment=Qt.AlignHCenter
        )
        self.layout.addWidget(
            self.animation,
            alignment=Qt.AlignHCenter
        )


      



        self.layout.addWidget(
            self.track_line,
            alignment=Qt.AlignHCenter
        )

   


