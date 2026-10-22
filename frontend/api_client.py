# API client for the desktop app: HTTP calls, session, error messages, labels, time formatting.
#
# Usage:
#   from api_client import api, ApiError, run_in_background
#   api.login(email, password)                      # stores the token
#   parcels = api.get("/parcels/my", params={"scope": "active"})
#   run_in_background(api.get, "/courier/tasks", on_success=self.show_tasks, on_error=self.show_error)
#   api.events.session_expired.connect(self.show_login)
#
# Path parameters from user input must be quoted: api.get(f"/parcels/track/{quote(tn, safe='')}")
#
# Request log in the terminal: set API_DEBUG=1 (environment or .env)

import json as jsonlib
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import httpx
from dotenv import dotenv_values
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_ENV = dotenv_values(ENV_PATH)
BASE_URL = os.getenv("API_BASE_URL") or _ENV.get("API_BASE_URL") or "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 10.0
DEBUG = (os.getenv("API_DEBUG") or _ENV.get("API_DEBUG") or "").lower() in ("1", "true", "yes")


# --- Debug log ---------------------------------------------------

_SECRET_KEYS = {"password", "current_password", "new_password", "access_token"}


def _mask(value: Any) -> Any:
    # Hide passwords and tokens in the log
    if isinstance(value, dict):
        return {key: "***" if key in _SECRET_KEYS else _mask(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask(item) for item in value]
    return value


def _log(text: str) -> None:
    if DEBUG:
        print(f"[API] {text}", flush=True)


def _response_text(response: httpx.Response) -> str:
    if not response.content:
        return "(üres)"
    try:
        text = jsonlib.dumps(_mask(response.json()), ensure_ascii=False)
    except ValueError:
        text = response.text
    return text if len(text) <= 400 else text[:400] + " …"


# --- Labels ------------------------------------------------------

STATUS_LABELS = {
    "booked": "Előjegyezve",
    "pickup_assigned": "Felvételre kiosztva",
    "picked_up": "Felvéve",
    "in_warehouse": "Raktárban",
    "delivery_assigned": "Kiszállításra kiosztva",
    "out_for_delivery": "Kiszállítás alatt",
    "delivered": "Kézbesítve",
    "failed": "Sikertelen kísérlet",
    "cancelled": "Lemondva",
}

ROLE_LABELS = {
    "customer": "Ügyfél",
    "courier": "Futár",
    "logistician": "Raktáros",
    "admin": "Adminisztrátor",
}

TASK_LABELS = {"pickup": "Felvétel", "delivery": "Kiszállítás"}

SIZES = ["S", "M", "L", "XL"]

TIME_SLOTS = ["08:00-10:00", "10:00-12:00", "12:00-14:00", "14:00-16:00", "16:00-18:00", "18:00-20:00"]

FIELD_LABELS = {
    "username": "Email cím",
    "email": "Email cím",
    "password": "Jelszó",
    "current_password": "Jelenlegi jelszó",
    "new_password": "Új jelszó",
    "last_name": "Vezetéknév",
    "first_name": "Keresztnév",
    "phone": "Telefonszám",
    "postal_code": "Irányítószám",
    "city": "Település",
    "street": "Utca",
    "house_number": "Házszám",
    "role": "Szerepkör",
    "is_active": "Aktív",
    "sender": "Feladó",
    "recipient": "Címzett",
    "recipient_address": "Címzett címe",
    "size": "Méret",
    "status": "Státusz",
    "pickup_date": "Felvétel napja",
    "pickup_slot": "Felvételi idősáv",
    "delivery_date": "Kiszállítás napja",
    "delivery_slot": "Kiszállítási idősáv",
    "courier_id": "Futár",
    "pickup_courier_id": "Felvevő futár",
    "delivery_courier_id": "Kiszállító futár",
    "parcel_ids": "Csomagok",
    "note": "Megjegyzés",
    "name": "Név",
    "capacity": "Kapacitás",
    "search": "Keresés",
    "task": "Feladat",
    "day": "Nap",
    "period": "Időszak",
    "from_date": "Kezdő dátum",
    "to_date": "Záró dátum",
    "direction": "Irány",
    "scope": "Nézet",
    "limit": "Oldalméret",
    "offset": "Eltolás",
}

_ERROR_TYPE_MESSAGES = {
    "missing": "Kötelező mező",
    "string_too_short": "Túl rövid",
    "string_too_long": "Túl hosszú",
    "string_pattern_mismatch": "Hibás formátum",
    "enum": "Nem választható érték",
    "literal_error": "Nem választható érték",
    "date_parsing": "Hibás dátum",
    "date_from_datetime_parsing": "Hibás dátum",
    "int_parsing": "Számot kell megadni",
    "bool_parsing": "Igen/nem értéket kell megadni",
    "greater_than": "Túl kicsi érték",
    "greater_than_equal": "Túl kicsi érték",
    "less_than_equal": "Túl nagy érték",
    "too_short": "Legalább egy elemet ki kell választani",
    "too_long": "Túl sok elem",
    "extra_forbidden": "Nem várt mező",
}

_STATUS_MESSAGES = {
    400: "Hibás kérés",
    401: "Bejelentkezés szükséges",
    403: "Nincs jogosultságod ehhez a művelethez",
    404: "Nem található",
    409: "A művelet most nem végezhető el",
    422: "Hibás adatok",
}


# --- Errors ------------------------------------------------------

class ApiError(Exception):
    # status_code is None when the server could not be reached
    def __init__(self, status_code: int | None, message: str, field_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        # Field path (e.g. "sender.postal_code") → message, for highlighting form fields
        self.field_errors = field_errors or {}

    def __str__(self) -> str:
        return self.message


def _field_label(loc: list) -> str:
    # ["body", "sender", "postal_code"] → "Feladó – Irányítószám"; model-level errors → ""
    parts = [p for p in loc if isinstance(p, str) and p not in ("body", "query", "path")]
    return " – ".join(FIELD_LABELS.get(p, p) for p in parts)


def _validation_message(item: dict) -> str:
    msg = item.get("msg", "")
    if msg.startswith("Value error, "):
        return msg.removeprefix("Value error, ")
    if "email address" in msg:
        return "Hibás email cím"
    return _ERROR_TYPE_MESSAGES.get(item.get("type", ""), "Hibás érték")


def _error_from_response(response: httpx.Response) -> ApiError:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None

    if isinstance(detail, str):
        return ApiError(response.status_code, detail)

    if isinstance(detail, list):
        lines, fields = [], {}
        for item in detail:
            text = _validation_message(item)
            label = _field_label(item.get("loc", []))
            lines.append(f"{label}: {text}" if label else text)
            path = ".".join(p for p in item.get("loc", []) if isinstance(p, str) and p not in ("body", "query", "path"))
            if path:
                fields[path] = text
        return ApiError(response.status_code, "\n".join(lines), fields)

    fallback = _STATUS_MESSAGES.get(response.status_code, f"Szerverhiba ({response.status_code})")
    return ApiError(response.status_code, fallback)


# --- Client ------------------------------------------------------

class ApiEvents(QObject):
    # Emitted when a protected request returns 401; connect it to "show login screen"
    session_expired = Signal()


class ApiClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = TIMEOUT_SECONDS,
                 http_client: httpx.Client | None = None):
        # http_client: only for tests (e.g. FastAPI TestClient)
        self._http = http_client or httpx.Client(base_url=base_url, timeout=timeout)
        self.events = ApiEvents()
        self.token: str | None = None
        self.role: str | None = None
        self.user_id: int | None = None

    @property
    def is_logged_in(self) -> bool:
        return self.token is not None

    # --- Session ---

    def login(self, email: str, password: str) -> dict:
        # The login endpoint expects form data, not JSON
        data = self._request("POST", "/auth/login", data={"username": email, "password": password}, auth=False)
        self.token = data["access_token"]
        self.role = data["role"]
        self.user_id = data["user_id"]
        return data

    def logout(self) -> None:
        self.token = None
        self.role = None
        self.user_id = None

    # --- HTTP methods (return the parsed JSON, or None for empty responses) ---

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: Any = None) -> Any:
        return self._request("POST", path, json=json)

    def patch(self, path: str, json: Any = None) -> Any:
        return self._request("PATCH", path, json=json)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            return self._send(method, path, **kwargs)
        except ApiError as error:
            _log(f"x  ApiError({error.status_code}): {error.message}")
            raise

    def _send(self, method: str, path: str, *, params: dict | None = None, json: Any = None,
              data: dict | None = None, auth: bool = True) -> Any:
        headers = {"Authorization": f"Bearer {self.token}"} if auth and self.token else {}
        # Unset filters are left out of the query string
        params = {key: value for key, value in (params or {}).items() if value is not None}
        if DEBUG:
            body = f" json={_mask(json)}" if json is not None else (f" form={_mask(data)}" if data else "")
            query = f" query={params}" if params else ""
            _log(f"-> {method} {path}{query}{body}{' (tokennel)' if headers else ''}")
        started = perf_counter()
        try:
            response = self._http.request(method, path, params=params, json=json, data=data, headers=headers)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise ApiError(None, "A szerver nem érhető el")
        except httpx.TimeoutException:
            raise ApiError(None, "A szerver nem válaszolt időben")
        except httpx.TransportError:
            raise ApiError(None, "Hálózati hiba a szerverrel való kapcsolatban")
        _log(f"<- {response.status_code} {method} {path} ({(perf_counter() - started) * 1000:.0f} ms) {_response_text(response)}")

        if response.status_code == 401 and auth and self.token is not None:
            self.logout()
            self.events.session_expired.emit()
            raise ApiError(401, "Lejárt a munkamenet, jelentkezz be újra")
        if response.is_error:
            raise _error_from_response(response)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()


# Shared instance for the whole app
api = ApiClient()


# --- Background calls --------------------------------------------

class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()


class _Worker(QRunnable):
    def __init__(self, fn: Callable, args: tuple, kwargs: dict):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except ApiError as error:
            self.signals.failed.emit(error)
        except Exception as error:
            self.signals.failed.emit(ApiError(None, f"Váratlan hiba: {error}"))
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


# Keeps running workers alive until they finish
_running: set[_Worker] = set()


def run_in_background(fn: Callable, *args, on_success: Callable[[Any], None] | None = None,
                      on_error: Callable[[ApiError], None] | None = None, **kwargs) -> None:
    # Runs fn(*args, **kwargs) on a worker thread; callbacks run on the GUI thread
    worker = _Worker(fn, args, kwargs)
    if on_success is not None:
        worker.signals.succeeded.connect(on_success)
    if on_error is not None:
        worker.signals.failed.connect(on_error)
    _running.add(worker)
    worker.signals.finished.connect(lambda: _running.discard(worker))
    QThreadPool.globalInstance().start(worker)


# --- Time formatting ---------------------------------------------

def to_local(value: str | None) -> datetime | None:
    # API timestamps are UTC without a timezone
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).astimezone()


def format_datetime(value: str | None) -> str:
    local = to_local(value)
    return local.strftime("%Y. %m. %d. %H:%M") if local else "–"


def format_date(value: str | None) -> str:
    return date.fromisoformat(value).strftime("%Y. %m. %d.") if value else "–"


def format_window(start: str | None, end: str | None) -> str:
    # "08:00:00", "10:00:00" → "08:00–10:00"
    if not start or not end:
        return "–"
    return f"{time.fromisoformat(start):%H:%M}–{time.fromisoformat(end):%H:%M}"
