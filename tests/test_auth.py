# Registration, login, tokens, password change
import pytest

from helpers import PASSWORD
from server.models import UserRole

REGISTER = {"last_name": "Jhone", "first_name": "Doe", "email": "jhon@doe.com", "password": "jelszo123"}


def login(client, email: str, password: str):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_register_creates_active_customer(client):
    response = client.post("/auth/register", json=REGISTER)
    assert response.status_code == 201
    user = response.json()
    assert (user["role"], user["is_active"], user["email"]) == ("customer", True, "jhon@doe.com")
    assert "password" not in user and "password_hash" not in user


def test_register_cannot_choose_role(client):
    response = client.post("/auth/register", json={**REGISTER, "role": "admin"})
    assert response.status_code == 422


def test_register_duplicate_email_is_case_insensitive(client):
    client.post("/auth/register", json=REGISTER)
    response = client.post("/auth/register", json={**REGISTER, "email": "Jhon@Doe.COM"})
    assert response.status_code == 409


def test_login_returns_token_and_role(client):
    client.post("/auth/register", json=REGISTER)
    response = login(client, "JHON@doe.com", "jelszo123")
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "customer" and body["token_type"] == "bearer" and body["access_token"]

    me = client.get("/users/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["id"] == body["user_id"]


@pytest.mark.parametrize("email, password", [
    ("jhon@doe.com", "rossz-jelszo"),
    ("doe@jhon.com", "jelszo123"),
])
def test_login_failure_gives_same_message(client, email, password):
    client.post("/auth/register", json=REGISTER)
    response = login(client, email, password)
    assert response.status_code == 401
    assert response.json()["detail"] == "Hibás email vagy jelszó"


def test_inactive_user_cannot_login_and_token_stops_working(client, make_actor, admin):
    user = make_actor(UserRole.CUSTOMER, email="inaktiv@teszt.hu")
    assert client.get("/users/me", headers=user.headers).status_code == 200

    assert client.delete(f"/users/{user.id}", headers=admin.headers).status_code == 204
    assert client.get("/users/me", headers=user.headers).status_code == 401
    assert login(client, "inaktiv@teszt.hu", PASSWORD).status_code == 401


def test_email_of_inactive_user_can_register_again(client, make_actor, admin):
    user = make_actor(UserRole.CUSTOMER, email="jhon@doe.com")
    client.delete(f"/users/{user.id}", headers=admin.headers)
    assert client.post("/auth/register", json=REGISTER).status_code == 201


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer nem.ervenyes.token"},
])
def test_protected_endpoint_without_valid_token(client, headers):
    assert client.get("/users/me", headers=headers).status_code == 401


def test_invalid_token_is_rejected_even_where_login_is_optional(client):
    # Booking works as a guest, but a broken token is an error, not a guest
    response = client.post("/parcels", json={}, headers={"Authorization": "Bearer nem.ervenyes.token"})
    assert response.status_code == 401


@pytest.mark.parametrize("new_password, status", [
    ("rovid", 422),        # too short
    (PASSWORD, 422),       # same as the old one
    ("ujjelszo123", 204),  # ok
])
def test_change_password_rules(client, customer, new_password, status):
    response = client.post("/auth/change-password", headers=customer.headers,
                           json={"current_password": PASSWORD, "new_password": new_password})
    assert response.status_code == status


def test_change_password_wrong_current(client, customer):
    response = client.post("/auth/change-password", headers=customer.headers,
                           json={"current_password": "rossz-jelszo", "new_password": "ujjelszo123"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Hibás jelenlegi jelszó"


def test_change_password_then_only_new_one_works(client, customer):
    client.post("/auth/change-password", headers=customer.headers,
                json={"current_password": PASSWORD, "new_password": "ujjelszo123"})
    assert login(client, customer.email, PASSWORD).status_code == 401
    assert login(client, customer.email, "ujjelszo123").status_code == 200
    # The current token stays valid
    assert client.get("/users/me", headers=customer.headers).status_code == 200
