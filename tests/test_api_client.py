import time
from datetime import datetime, timezone
import httpx
import pytest
from PySide6.QtCore import QThread

from frontend.api_client import ApiClient, ApiError, format_date, format_datetime, format_window, run_in_background


def fake_api(status_code: int = 200, body=None, *, seen: list | None = None, error: Exception | None = None):
    # seen collects the sent requests
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if error is not None:
            raise error
        if body is None:
            return httpx.Response(status_code)
        if isinstance(body, str):
            return httpx.Response(status_code, text=body)
        return httpx.Response(status_code, json=body)
    return ApiClient(http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test"))


def raises(api: ApiClient, method: str = "get", path: str = "/x", **kwargs) -> ApiError:
    with pytest.raises(ApiError) as error:
        getattr(api, method)(path, **kwargs)
    return error.value


# --- Error messages ----------------------------------------------

def test_field_error_is_hungarian():
    api = fake_api(422, {"detail": [{"type": "string_too_short", "loc": ["body", "new_password"], "msg": "..."}]})
    error = raises(api, "post")
    assert (error.status_code, error.message) == (422, "Új jelszó: Túl rövid")
    assert error.field_errors == {"new_password": "Túl rövid"}


def test_nested_field_error():
    api = fake_api(422, {"detail": [
        {"type": "string_pattern_mismatch", "loc": ["body", "sender", "postal_code"], "msg": "..."},
        {"type": "missing", "loc": ["body", "size"], "msg": "Field required"},
    ]})
    error = raises(api, "post")
    assert error.message == "Feladó – Irányítószám: Hibás formátum\nMéret: Kötelező mező"
    assert error.field_errors == {"sender.postal_code": "Hibás formátum", "size": "Kötelező mező"}


def test_server_rule_message_without_prefix():
    api = fake_api(422, {"detail": [{"type": "value_error", "loc": ["body"],
                                     "msg": "Value error, Az új jelszó nem egyezhet meg a régivel"}]})
    error = raises(api, "post")
    assert error.message == "Az új jelszó nem egyezhet meg a régivel"
    assert error.field_errors == {}


def test_server_text_detail_is_passed_on():
    error = raises(fake_api(409, {"detail": "Az email cím már foglalt"}), "post")
    assert (error.status_code, error.message) == (409, "Az email cím már foglalt")


@pytest.mark.parametrize("status, message", [
    (403, "Nincs jogosultságod ehhez a művelethez"),
    (500, "Szerverhiba (500)"),
])
def test_fallback_message_without_detail(status, message):
    assert raises(fake_api(status, "Internal Server Error")).message == message


@pytest.mark.parametrize("error, message", [
    (httpx.ConnectError("down"), "A szerver nem érhető el"),
    (httpx.ConnectTimeout("slow"), "A szerver nem érhető el"),
    (httpx.ReadTimeout("slow"), "A szerver nem válaszolt időben"),
])
def test_network_errors(error, message):
    result = raises(fake_api(error=error))
    assert (result.status_code, result.message) == (None, message)


# --- Session -----------------------------------------------------

def test_login_stores_token_and_sends_it(qapp):
    seen = []
    api = fake_api(200, {"access_token": "abc", "token_type": "bearer", "expires_in": 1800,
                         "role": "courier", "user_id": 7}, seen=seen)
    api.login("futar@teszt.hu", "jelszo123")
    assert (api.is_logged_in, api.role, api.user_id) == (True, "courier", 7)
    # Login is form data, not JSON
    assert seen[0].headers["content-type"] == "application/x-www-form-urlencoded"
    assert "Authorization" not in seen[0].headers

    api.get("/courier/tasks")
    assert seen[1].headers["Authorization"] == "Bearer abc"


def test_failed_login_keeps_server_message(qapp):
    api = fake_api(401, {"detail": "Hibás email vagy jelszó"})
    expired = []
    api.events.session_expired.connect(lambda: expired.append(True))
    with pytest.raises(ApiError) as error:
        api.login("a@teszt.hu", "rossz")
    assert error.value.message == "Hibás email vagy jelszó"
    assert not api.is_logged_in and expired == []


def test_expired_token_logs_out(qapp):
    api = fake_api(401, {"detail": "Érvénytelen vagy lejárt token"})
    api.token, api.role = "lejart", "customer"
    expired = []
    api.events.session_expired.connect(lambda: expired.append(True))
    error = raises(api)
    assert error.message == "Lejárt a munkamenet, jelentkezz be újra"
    assert (api.is_logged_in, api.role, expired) == (False, None, [True])


def test_no_token_needs_login(qapp):
    api = fake_api(401, {"detail": "Not authenticated"})
    expired = []
    api.events.session_expired.connect(lambda: expired.append(True))
    assert raises(api).message == "Bejelentkezés szükséges"
    assert expired == []


def test_logout_clears_the_session():
    api = fake_api()
    api.token, api.role, api.user_id = "abc", "admin", 1
    api.logout()
    assert (api.token, api.role, api.user_id, api.is_logged_in) == (None, None, None, False)


# --- Requests ----------------------------------------------------

def test_empty_response_is_none():
    assert fake_api(204).post("/auth/change-password", json={}) is None


def test_unset_filters_are_left_out():
    seen = []
    fake_api(200, {"items": []}, seen=seen).get("/parcels", params={"status": "booked", "search": None})
    assert str(seen[0].url) == "http://test/parcels?status=booked"


# --- Background calls --------------------------------------------

def wait_for(qapp, condition, timeout: float = 5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_background_success_runs_on_gui_thread(qapp):
    results = []
    run_in_background(fake_api(200, {"ok": True}).get, "/x",
                      on_success=lambda r: results.append((r, QThread.currentThread() == qapp.thread())))
    assert wait_for(qapp, lambda: results)
    assert results == [({"ok": True}, True)]


def test_background_error(qapp):
    errors = []
    run_in_background(fake_api(404, {"detail": "A csomag nem található"}).get, "/x", on_error=errors.append)
    assert wait_for(qapp, lambda: errors)
    assert (errors[0].status_code, errors[0].message) == (404, "A csomag nem található")


def test_background_unexpected_exception(qapp):
    def broken():
        raise ValueError("hiba")
    errors = []
    run_in_background(broken, on_error=errors.append)
    assert wait_for(qapp, lambda: errors)
    assert (errors[0].status_code, errors[0].message) == (None, "Váratlan hiba: hiba")


# --- Formatting --------------------------------------------------

def test_format_helpers():
    assert format_window("08:00:00", "10:00:00") == "08:00–10:00"
    assert format_window(None, "10:00:00") == "–"
    assert format_date("2026-10-21") == "2026. 10. 21."
    assert format_date(None) == "–"
    assert format_datetime(None) == "–"


def test_format_datetime_converts_utc_to_local():
    expected = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc).astimezone().strftime("%Y. %m. %d. %H:%M")
    assert format_datetime("2026-10-21T10:00:00") == expected
