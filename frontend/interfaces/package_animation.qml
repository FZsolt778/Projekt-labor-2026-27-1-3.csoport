
import QtQuick 2.15
import QtLottie 1.0

Rectangle {
    width: 180
    height: 180
    color: "transparent"

    LottieAnimation {
        anchors.fill: parent
        source: Qt.resolvedUrl("track.json")
        autoPlay: true
        loops: -1

        onStatusChanged: {
            console.log("Lottie status:", status)
        }
    }
}
