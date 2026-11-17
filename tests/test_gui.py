from PySide6.QtWidgets import QLineEdit


def test_main_window_builds(qapp):
    import main as frontend_main
    window = frontend_main.Window()
    assert window.windowTitle() == "Csomagkezelő"
    # Not logged in: tracking, booking and the login screen
    names = [interface.objectName() for interface in window.subInterfaces]
    assert names == ["Tracking-Interface", "Booking-Interface", "AuthInterface"]


def test_login_page_fields(qapp):
    from interfaces.auth.login_interface import LoginInterface
    page = LoginInterface("Login Interface", None)
    assert page.objectName() == "Login-Interface"
    assert page.passwordEdit.echoMode() == QLineEdit.Password
    assert page.loginButton.text() == "Bejelentkezés"
