import re

import pytest

from server.main import app
from server.models import UserRole

PUBLIC = "public"        
LOGGED_IN = "logged_in"  
STAFF = {"logistician", "admin"}
ADMIN = {"admin"}
CUSTOMER = {"customer"}
COURIER = {"courier"}

ENDPOINTS = [
    ("GET", "/health", PUBLIC),
    ("POST", "/auth/register", PUBLIC),
    ("POST", "/auth/login", PUBLIC),
    ("POST", "/auth/change-password", LOGGED_IN),
    ("GET", "/users/me", LOGGED_IN),
    ("PATCH", "/users/me", LOGGED_IN),
    ("GET", "/users", ADMIN),
    ("POST", "/users", ADMIN),
    ("GET", "/users/999", ADMIN),
    ("PATCH", "/users/999", ADMIN),
    ("DELETE", "/users/999", ADMIN),
    ("POST", "/parcels", PUBLIC),
    ("GET", "/parcels/track/FCNINCSILYEN", PUBLIC),
    ("GET", "/parcels/my", CUSTOMER),
    ("GET", "/parcels/my/999", CUSTOMER),
    ("PATCH", "/parcels/my/999", CUSTOMER),
    ("POST", "/parcels/my/999/cancel", CUSTOMER),
    ("GET", "/parcels", STAFF),
    ("GET", "/parcels/999", STAFF),
    ("PATCH", "/parcels/999", ADMIN),
    ("PATCH", "/parcels/999/couriers", ADMIN),
    ("POST", "/parcels/999/cancel", ADMIN),
    ("DELETE", "/parcels/999", ADMIN),
    ("GET", "/courier/tasks", COURIER),
    ("POST", "/courier/parcels/999/pickup", COURIER),
    ("POST", "/courier/parcels/999/start", COURIER),
    ("POST", "/courier/parcels/999/deliver", COURIER),
    ("POST", "/courier/parcels/999/fail", COURIER),
    ("GET", "/courier/history", COURIER),
    ("GET", "/warehouse", STAFF),
    ("PATCH", "/warehouse", ADMIN),
    ("GET", "/warehouse/couriers", STAFF),
    ("POST", "/warehouse/check-in", STAFF),
    ("POST", "/warehouse/assign-pickup", STAFF),
    ("POST", "/warehouse/assign-delivery", STAFF),
    ("GET", "/stats/warehouse", ADMIN),
    ("GET", "/stats/warehouse/history", ADMIN),
    ("GET", "/stats/couriers", ADMIN),
]
ROLES = [None, "customer", "courier", "logistician", "admin"]


def _allowed(rule, role: str | None) -> bool:
    if rule == PUBLIC:
        return True
    if rule == LOGGED_IN:
        return role is not None
    return role in rule


CASES = [
    pytest.param(method, path, rule, role, id=f"{method} {path} as {role or 'guest'}")
    for method, path, rule in ENDPOINTS
    for role in ROLES
]


@pytest.mark.parametrize("method, path, rule, role", CASES)
def test_role_check(client, make_actor, method, path, rule, role):
    headers = make_actor(UserRole(role)).headers if role else {}
    body = {"json": {}} if method in ("POST", "PATCH") else {}
    status = client.request(method, path, headers=headers, **body).status_code

    if _allowed(rule, role):
        assert status not in (401, 403), status
    else:
        assert status == (401 if role is None else 403)


def _shape(path: str) -> str:
    # "/users/{user_id}" and "/users/999" -> "/users/{}"
    return re.sub(r"\{[^}]+\}|999|FCNINCSILYEN", "{}", path)


def test_matrix_covers_every_endpoint():
    #OpenAPI description every endpoints
    routes = {
        (method.upper(), _shape(path))
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    listed = {(method, _shape(path)) for method, path, _ in ENDPOINTS}
    assert routes == listed
