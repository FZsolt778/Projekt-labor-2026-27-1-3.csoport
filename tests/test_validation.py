import pytest
from helpers import contact, day, parcel_body
from server.models import UserRole


# --- Booking -----------------------------------------------------

def test_valid_booking(client):
    response = client.post("/parcels", json=parcel_body())
    assert response.status_code == 201
    parcel = response.json()
    assert parcel["status"] == "booked"
    assert parcel["tracking_number"].startswith("FC") and len(parcel["tracking_number"]) == 12
    assert (parcel["pickup_window_start"], parcel["pickup_window_end"]) == ("08:00:00", "10:00:00")


@pytest.mark.parametrize("changes", [{"pickup_date": day(0)}, {"pickup_date": day(-1)}])
def test_pickup_is_tomorrow_at_the_earliest(client, changes):
    response = client.post("/parcels", json=parcel_body() | changes)
    assert response.status_code == 422
    assert "legkorábban holnapra" in response.text


def test_booking_has_no_delivery_time(client):
    response = client.post("/parcels", json=parcel_body())
    assert response.status_code == 201
    assert response.json()["delivery_date"] is None


@pytest.mark.parametrize("changes", [
    {"delivery_date": day(3), "delivery_slot": "10:00-12:00"},
    {"delivery_date": day(3)},
])
def test_booking_rejects_a_delivery_time(client, changes):
    # The logistician sets it at assignment
    response = client.post("/parcels", json=parcel_body() | changes)
    assert response.status_code == 422
    assert "extra_forbidden" in response.text


@pytest.mark.parametrize("changes", [
    {"size": "XXL"},
    {"pickup_slot": "07:00-09:00"},
    {"pickup_date": "2026-13-01"},
    {"status": "delivered"},  # unknown field
])
def test_booking_rejects_bad_fields(client, changes):
    assert client.post("/parcels", json=parcel_body() | changes).status_code == 422


@pytest.mark.parametrize("field, value, status", [
    ("postal_code", "0123", 422),
    ("postal_code", "123", 422),
    ("postal_code", "12345", 422),
    ("postal_code", "8200", 201),
    ("phone", "abc", 422),
    ("phone", "12", 422),
    ("phone", "+36 30 123 4567", 201),
    ("phone", "06-88/123-456", 201),
    ("email", "nem-email", 422),
    ("last_name", "x" * 51, 422),
    ("house_number", "", 422),
])
def test_contact_field_formats(client, field, value, status):
    body = parcel_body()
    body["recipient"] = contact("Címzett", "cimzett@teszt.hu") | {field: value}
    assert client.post("/parcels", json=body).status_code == status


@pytest.mark.parametrize("missing", ["sender", "recipient", "size", "pickup_date", "pickup_slot"])
def test_booking_required_fields(client, missing):
    body = parcel_body()
    del body[missing]
    assert client.post("/parcels", json=body).status_code == 422


# --- Registration and profile -----------------------------------

REGISTER = {"last_name": "Kiss", "first_name": "Anna", "email": "anna@teszt.hu", "password": "jelszo123"}
ADDRESS = {"postal_code": "8200", "city": "Veszprém", "street": "Egyetem utca", "house_number": "10"}


def test_register_with_full_address(client):
    assert client.post("/auth/register", json=REGISTER | ADDRESS).status_code == 201


@pytest.mark.parametrize("partial", [
    {"postal_code": "8200"},
    {"postal_code": "8200", "city": "Veszprém", "street": "Egyetem utca"},
])
def test_register_address_all_or_nothing(client, partial):
    response = client.post("/auth/register", json=REGISTER | partial)
    assert response.status_code == 422
    assert "együtt kell megadni" in response.text


def test_profile_phone_can_be_cleared(client, customer):
    client.patch("/users/me", headers=customer.headers, json={"phone": "+36 30 123 4567"})
    response = client.patch("/users/me", headers=customer.headers, json={"phone": None})
    assert response.status_code == 200 and response.json()["phone"] is None


def test_profile_required_field_cannot_be_null(client, customer):
    response = client.patch("/users/me", headers=customer.headers, json={"last_name": None})
    assert response.status_code == 422
    assert "nem lehet null" in response.text


def test_profile_address_cleared_together(client, customer):
    client.patch("/users/me", headers=customer.headers, json=ADDRESS)
    cleared = {name: None for name in ADDRESS}
    response = client.patch("/users/me", headers=customer.headers, json=cleared)
    assert response.status_code == 200 and response.json()["city"] is None
    half = {"postal_code": None, "city": None}
    assert client.patch("/users/me", headers=customer.headers, json=half).status_code == 422


def test_profile_role_cannot_be_changed(client, customer):
    assert client.patch("/users/me", headers=customer.headers, json={"role": "admin"}).status_code == 422


# --- Warehouse and courier requests -----------------------------

@pytest.mark.parametrize("tracking_numbers, message", [
    ([], "at least 1"),
    (["FC1", " fc1 "], "ismétlődő"),  # duplicate after normalizing
    ([f"FC{i}" for i in range(101)], "at most 100"),
    (["   "], "at least 1 character"),
    (["F" * 31], "at most 30 characters"),
])
def test_bulk_tracking_number_list(client, logistician, tracking_numbers, message):
    response = client.post("/warehouse/check-in", headers=logistician.headers,
                           json={"tracking_numbers": tracking_numbers})
    assert response.status_code == 422
    assert message in response.text


def test_bulk_old_parcel_id_field_is_rejected(client, logistician):
    response = client.post("/warehouse/check-in", headers=logistician.headers, json={"parcel_ids": [1]})
    assert response.status_code == 422


@pytest.mark.parametrize("when", [
    {"delivery_date": day(3)},
    {"delivery_slot": "10:00-12:00"},
    {"delivery_date": day(-1), "delivery_slot": "10:00-12:00"},
])
def test_assign_delivery_date_rules(client, logistician, courier, when):
    body = {"courier_id": courier.id, "tracking_numbers": ["FC1"], **when}
    assert client.post("/warehouse/assign-delivery", headers=logistician.headers, json=body).status_code == 422


@pytest.mark.parametrize("note", ["", "   ", "x" * 256])
def test_failed_attempt_needs_a_reason(client, courier, note):
    response = client.post("/courier/parcels/FCNINCSILYEN/fail", headers=courier.headers, json={"note": note})
    assert response.status_code == 422


def test_failed_attempt_without_body(client, courier):
    assert client.post("/courier/parcels/FCNINCSILYEN/fail", headers=courier.headers).status_code == 422


@pytest.mark.parametrize("params", [{"period": "year"}, {"day": "nem-datum"}])
def test_courier_history_params(client, courier, params):
    assert client.get("/courier/history", headers=courier.headers, params=params).status_code == 422


# --- Query params ------------------------------------------------

@pytest.mark.parametrize("params, status", [
    ({"limit": 0}, 422),
    ({"limit": 101}, 422),
    ({"offset": -1}, 422),
    ({"limit": 100, "offset": 0}, 200),
    ({"status": "elveszett"}, 422),
])
def test_paging_and_filters(client, logistician, params, status):
    assert client.get("/parcels", headers=logistician.headers, params=params).status_code == status


@pytest.mark.parametrize("params, status", [
    ({"from_date": day(0), "to_date": day(-1)}, 422),
    ({"from_date": day(-366), "to_date": day(0)}, 422),
    ({"from_date": day(-365), "to_date": day(0)}, 200),
    ({}, 200),
])
def test_stats_date_range(client, admin, params, status):
    assert client.get("/stats/couriers", headers=admin.headers, params=params).status_code == status


def test_admin_creates_user_with_role(client, admin):
    response = client.post("/users", headers=admin.headers, json=REGISTER | {"role": "courier"})
    assert response.status_code == 201 and response.json()["role"] == "courier"
    bad_role = REGISTER | {"email": "masik@teszt.hu", "role": "fonok"}
    assert client.post("/users", headers=admin.headers, json=bad_role).status_code == 422


def test_admin_cannot_create_duplicate_email(client, admin, make_actor):
    make_actor(UserRole.CUSTOMER, email="anna@teszt.hu")
    response = client.post("/users", headers=admin.headers, json=REGISTER | {"role": "courier"})
    assert response.status_code == 409
