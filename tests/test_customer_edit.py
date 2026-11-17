from datetime import date

import pytest

from helpers import day
from server.models import Parcel, UserRole


@pytest.fixture
def parcel(book, customer):
    return book(customer)


@pytest.fixture
def edit(client, customer, parcel):
    def _edit(body, actor=None):
        actor = actor or customer
        return client.patch(f"/parcels/my/{parcel['id']}", headers=actor.headers, json=body)
    return _edit


def test_edit_size_address_and_sender(edit):
    address = {"postal_code": "1111", "city": "Budapest", "street": "Fő utca", "house_number": "1"}
    response = edit({"size": "L", "recipient_address": address,
                     "sender": {"email": "uj@teszt.hu", "phone": "+36 30 123 4567"}})
    assert response.status_code == 200
    body = response.json()
    assert body["size"] == "L"
    assert (body["recipient"]["city"], body["recipient"]["last_name"]) == ("Budapest", "Minta")
    assert (body["sender"]["email"], body["sender"]["phone"]) == ("uj@teszt.hu", "+36 30 123 4567")


def test_recipient_address_must_be_complete(edit):
    assert edit({"recipient_address": {"city": "Budapest"}}).status_code == 422


def test_only_sender_may_edit(client, book, customer, make_actor):
    recipient = make_actor(UserRole.CUSTOMER)
    parcel = book(customer, recipient_email=recipient.email)
    response = client.patch(f"/parcels/my/{parcel['id']}", headers=recipient.headers, json={"size": "L"})
    assert response.status_code == 403
    assert client.post(f"/parcels/my/{parcel['id']}/cancel", headers=recipient.headers).status_code == 403


def test_stranger_and_guest_parcels_are_not_found(client, book, edit, make_actor):
    stranger = make_actor(UserRole.CUSTOMER)
    assert edit({"size": "L"}, actor=stranger).status_code == 404
    guest_parcel = book()
    response = client.patch(f"/parcels/my/{guest_parcel['id']}", headers=stranger.headers, json={"size": "L"})
    assert response.status_code == 404


def test_deadline_is_the_day_before_pickup(client, db, parcel, edit, customer):
    # Pickup tomorrow: still editable today
    assert edit({"pickup_date": day(1)}).status_code == 200
    # Pickup today (set directly, booking would not allow it): too late
    db.get(Parcel, parcel["id"]).pickup_date = date.today()
    db.commit()
    response = edit({"size": "L"})
    assert response.status_code == 409
    assert response.json()["detail"] == "A csomag legkésőbb a felvétel előtti napon módosítható"
    assert client.post(f"/parcels/my/{parcel['id']}/cancel", headers=customer.headers).status_code == 409


def test_not_editable_after_pickup(flow, parcel, edit):
    flow.to(parcel["id"], "picked_up")
    assert edit({"size": "L"}).status_code == 409


def test_pickup_change_detaches_courier(flow, parcel, edit):
    flow.pickup_assigned(parcel["id"])
    # Other fields keep the courier
    kept = edit({"size": "S"}).json()
    assert (kept["status"], kept["pickup_courier"] is not None) == ("pickup_assigned", True)

    moved = edit({"pickup_slot": "12:00-14:00"}).json()
    assert (moved["status"], moved["pickup_courier"]) == ("booked", None)
    assert flow.get(parcel["id"])["events"][-1]["note"] == "Felvételi időpont módosítva"


def test_cancel(client, flow, parcel, customer, courier):
    flow.pickup_assigned(parcel["id"])
    response = client.post(f"/parcels/my/{parcel['id']}/cancel", headers=customer.headers)
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert client.get("/courier/tasks", headers=courier.headers).json() == []
    assert client.post(f"/parcels/my/{parcel['id']}/cancel", headers=customer.headers).status_code == 409


# --- Delivery time: set by the logistician, not by the customer ----

def test_customer_cannot_set_delivery_time(edit):
    response = edit({"delivery_date": day(3), "delivery_slot": "10:00-12:00"})
    assert response.status_code == 422
    assert "extra_forbidden" in response.text


def test_pickup_cannot_move_after_a_delivery_time_set_by_admin(client, admin, parcel, edit):
    response = client.patch(f"/parcels/{parcel['id']}", headers=admin.headers,
                            json={"delivery_date": day(3), "delivery_slot": "10:00-12:00"})
    assert response.status_code == 200
    response = edit({"pickup_date": day(4)})
    assert response.status_code == 422
    assert response.json()["detail"] == "A felvétel nem lehet a megadott kiszállítás után"
