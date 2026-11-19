# Main window session: who is logged in, logout when the token expires or the server rejects it, window icon
import time
from datetime import datetime, timedelta, timezone

import pytest

import api_client
from helpers import PASSWORD
from server.src.config import settings

GUEST_PAGES = ["Tracking-Interface", "Booking-Interface", "AuthInterface"]


def settle(qapp):
    # What the running event loop does: finish background requests, deliver their results, run pending deletes
    from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def wait_for(qapp, condition, timeout: float = 5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return False


def notices(window) -> list[str]:
    from qfluentwidgets import InfoBar
    return [bar.title for bar in window.findChildren(InfoBar) if bar.isVisible()]


def pages(window) -> list[str]:
    return [page.objectName() for page in window.subInterfaces]


def login(qapp, window, actor):
    # What the login screen does after a successful login
    api_client.api.login(actor.user.email, PASSWORD)
    window.initNavigation()
    assert wait_for(qapp, lambda: window.account is not None)


@pytest.fixture
def window(qapp, client, monkeypatch):
    # The real server code through the shared API client, one window per test
    import main  # noqa: F401  (icons)
    from qfluentwidgets.common.router import qrouter
    from interfaces.main_window import Window
    monkeypatch.setattr(api_client.api, "_http", client)
    # The router is global: forget the windows of other tests
    monkeypatch.setattr(qrouter, "stackHistories", {})
    monkeypatch.setattr(qrouter, "history", [])
    api_client.api.logout()
    w = Window()
    w.show()
    yield w
    settle(qapp)
    api_client.api.events.session_expired.disconnect(w._on_session_expired)
    api_client.api.logout()
    w.close()


def test_window_icon_is_found(window):
    assert not window.windowIcon().isNull()
    assert window.windowTitle() == "Csomagkezelő"


def test_login_shows_who_is_logged_in(qapp, window, courier):
    login(qapp, window, courier)
    name = f"Teszt {courier.user.first_name}"
    assert window._account_item().name == f"{name} (Futár)"
    assert window.windowTitle() == f"Csomagkezelő – {name} (Futár)"
    assert "Sikeres bejelentkezés" in notices(window)
    assert window.sessionTimer.isActive()
    assert settings.JWT_EXPIRE_MINUTES * 60 - 60 < api_client.api.session_seconds_left <= settings.JWT_EXPIRE_MINUTES * 60


def test_expired_token_logs_out_to_the_login_screen(qapp, window, customer):
    login(qapp, window, customer)
    api_client.api.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    window._check_session()  # what the timer does
    assert not api_client.api.is_logged_in
    assert pages(window) == GUEST_PAGES
    assert window.stackedWidget.currentWidget() is window.authInterface
    assert window.windowTitle() == "Csomagkezelő" and not window.sessionTimer.isActive()
    assert notices(window).count("Lejárt a munkamenet") == 1
    # A late 401 afterwards does nothing more
    window._on_session_expired()
    assert notices(window).count("Lejárt a munkamenet") == 1

    # Logging in again closes the notice
    settle(qapp)
    login(qapp, window, customer)
    assert wait_for(qapp, lambda: "Lejárt a munkamenet" not in notices(window))


def test_rejected_token_logs_out(qapp, window, admin):
    login(qapp, window, admin)
    api_client.api.token = "ervenytelen"
    with pytest.raises(api_client.ApiError):
        api_client.api.get("/users/me")
    assert wait_for(qapp, lambda: window.sessionRole is None)
    assert pages(window) == GUEST_PAGES
    assert window.stackedWidget.currentWidget() is window.authInterface


def test_manual_logout(qapp, window, customer):
    login(qapp, window, customer)
    window.logout()
    assert pages(window) == GUEST_PAGES
    assert "Kijelentkeztél" in notices(window) and "Lejárt a munkamenet" not in notices(window)


def test_many_login_rounds_with_navigation(qapp, window, courier, customer, admin):
    # The old pages used to stay hidden, and the router switched to one of them on the 2nd round
    for actor in (courier, customer, admin, courier):
        for page in list(window.subInterfaces):
            window.switchTo(page)
            settle(qapp)
        login(qapp, window, actor)
        for page in list(window.subInterfaces):
            window.switchTo(page)
            settle(qapp)
        window.logout()
        settle(qapp)
        assert pages(window) == GUEST_PAGES
