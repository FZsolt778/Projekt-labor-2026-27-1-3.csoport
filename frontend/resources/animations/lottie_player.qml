import QtQuick 2.15
import QtLottie 1.0

LottieAnimation {
    anchors.fill: parent
    source: animationSource
    autoPlay: true
    loops: -1

    onError: console.error("Lottie animation failed: " + message)
}
