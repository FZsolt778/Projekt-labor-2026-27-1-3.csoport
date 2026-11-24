import QtQuick 2.15
import QtLottie 1.0

LottieAnimation {
    id: lottieAnimation
    anchors.fill: parent
    source: animationSource
    autoPlay: false
    loops: -1
    maxRenderSize: 256
    transform: Translate {
        y: -lottieAnimation.height * 0.12
    }

    onError: console.error("Lottie animation failed: " + message)
}
