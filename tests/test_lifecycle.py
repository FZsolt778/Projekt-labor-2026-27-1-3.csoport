import pytest

from helpers import day
from server.models import UserRole


@pytest.fixture
def parcel(book, customer):
    return book(customer)


def tasks(client, courier, **params):
    response = client.get("/courier/tasks", headers=courier.headers, params=params)
    assert response.status_code == 200
    return [(task["task"], task["parcel"]["id"]) for task in response.json()]


def test_full_path(client, flow, parcel, courier, customer):
    pid = parcel["id"]

    flow.pickup_assigned(pid)
    assert tasks(client, courier) == [("pickup", pid)]
    flow.picked_up(pid)
    assert tasks(client, courier) == [("pickup", pid)]
    flow.in_warehouse(pid)
    assert tasks(client, courier) == []
    # No delivery time until the logistician sets it
    assert flow.get(pid)["delivery_date"] is None

    assigned = flow.delivery_assigned(pid)[0]
    assert assigned["delivery_date"] == day(3)
    assert tasks(client, courier, task="delivery") == [("delivery", pid)]
    flow.out_for_delivery(pid)
    delivered = flow.delivered(pid)
    assert delivered["status"] == "delivered"
    assert tasks(client, courier) == []

    detail = flow.get(pid)
    assert [e["status"] for e in detail["events"]] == [
        "booked", "pickup_assigned", "picked_up", "in_warehouse",
        "delivery_assigned", "out_for_delivery", "delivered",
    ]
    for milestone in ("picked_up_at", "warehouse_arrived_at", "out_for_delivery_at", "delivered_at"):
        assert detail[milestone] is not None
    assert detail["warehouse_id"] is not None
    mine = client.get(f"/parcels/my/{pid}", headers=customer.headers).json()
    assert set(mine["delivery_courier"]) == {"last_name", "first_name"}


def test_guest_tracking(client, book):
    parcel = book()
    response = client.get(f"/parcels/track/ {parcel['tracking_number'].lower()} ")
    assert response.status_code == 200
    tracked = response.json()
    assert tracked["status"] == "booked" and "id" not in tracked
    assert [e["status"] for e in tracked["events"]] == ["booked"]
    assert client.get("/parcels/track/FCNINCSILYEN").status_code == 404


def test_customer_sees_sent_and_received(client, book, make_actor):
    sender = make_actor(UserRole.CUSTOMER)
    recipient = make_actor(UserRole.CUSTOMER)
    parcel = book(sender, recipient_email=recipient.email.upper())

    def ids(actor, **params):
        page = client.get("/parcels/my", headers=actor.headers, params=params).json()
        return [item["id"] for item in page["items"]]

    assert ids(sender, direction="sent") == [parcel["id"]]
    assert ids(sender, direction="received") == []
    assert ids(recipient, direction="received") == [parcel["id"]]
    assert ids(recipient, scope="history") == []
    assert client.get(f"/parcels/my/{parcel['id']}", headers=recipient.headers).status_code == 200


def test_finished_parcel_moves_to_history(client, flow, parcel, customer):
    flow.to(parcel["id"], "delivered")
    active = client.get("/parcels/my", headers=customer.headers, params={"scope": "active"}).json()
    history = client.get("/parcels/my", headers=customer.headers, params={"scope": "history"}).json()
    assert active["total"] == 0 and history["total"] == 1


def test_stranger_gets_404(client, parcel, make_actor):
    stranger = make_actor(UserRole.CUSTOMER)
    assert client.get(f"/parcels/my/{parcel['id']}", headers=stranger.headers).status_code == 404


@pytest.mark.parametrize("action", ["pickup", "start", "deliver"])
def test_courier_cannot_touch_unassigned_parcel(client, parcel, courier, action):
    path = f"/courier/parcels/{parcel['tracking_number']}/{action}"
    assert client.post(path, headers=courier.headers).status_code == 404


def test_other_courier_cannot_act(client, flow, parcel, make_actor):
    other = make_actor(UserRole.COURIER)
    flow.pickup_assigned(parcel["id"])
    path = f"/courier/parcels/{parcel['tracking_number']}/pickup"
    assert client.post(path, headers=other.headers).status_code == 404


def test_courier_uses_the_tracking_number(client, flow, parcel, courier):
    flow.pickup_assigned(parcel["id"])
    # The numeric id is not accepted any more
    assert client.post(f"/courier/parcels/{parcel['id']}/pickup", headers=courier.headers).status_code == 404
    # Case and surrounding spaces do not matter, as in public tracking
    path = f"/courier/parcels/ {parcel['tracking_number'].lower()} /pickup"
    response = client.post(path, headers=courier.headers)
    assert response.status_code == 200 and response.json()["status"] == "picked_up"


@pytest.mark.parametrize("reached, action, status", [
    ("pickup_assigned", "start", 404),  
    ("delivery_assigned", "deliver", 409),
    ("delivery_assigned", "pickup", 409),
    ("out_for_delivery", "start", 409),
    ("delivered", "deliver", 409),
])
def test_courier_steps_in_wrong_status(client, flow, parcel, courier, reached, action, status):
    flow.to(parcel["id"], reached)
    path = f"/courier/parcels/{parcel['tracking_number']}/{action}"
    assert client.post(path, headers=courier.headers).status_code == status


def test_wrong_status_message_names_the_status_in_hungarian(client, flow, parcel, courier):
    flow.to(parcel["id"], "out_for_delivery")
    response = client.post(f"/courier/parcels/{parcel['tracking_number']}/start", headers=courier.headers)
    assert response.status_code == 409
    assert "(Kiszállítás alatt)" in response.json()["detail"]
    assert "out_for_delivery" not in response.json()["detail"]


def test_every_status_has_a_hungarian_label():
    from server.models import ParcelStatus
    labels = [status.label for status in ParcelStatus]
    assert all(labels) and len(set(labels)) == len(labels)


def test_logistician_cannot_reassign_pickup_after_pickup(client, flow, parcel, logistician, make_actor):
    other = make_actor(UserRole.COURIER)
    flow.to(parcel["id"], "picked_up")
    response = client.post("/warehouse/assign-pickup", headers=logistician.headers,
                           json={"courier_id": other.id, "tracking_numbers": [parcel["tracking_number"]]})
    assert response.status_code == 409


def test_logistician_cannot_reassign_delivery_after_start(client, flow, parcel, logistician, make_actor):
    other = make_actor(UserRole.COURIER)
    flow.to(parcel["id"], "out_for_delivery")
    response = client.post("/warehouse/assign-delivery", headers=logistician.headers,
                           json={"courier_id": other.id, "tracking_numbers": [parcel["tracking_number"]],
                                 "delivery_date": day(3), "delivery_slot": "10:00-12:00"})
    assert response.status_code == 409


def test_logistician_can_reassign_before_start(client, flow, parcel, make_actor):
    other = make_actor(UserRole.COURIER)
    flow.to(parcel["id"], "delivery_assigned")
    reassigned = flow.delivery_assigned(parcel["id"], courier=other)[0]
    assert reassigned["delivery_courier"]["id"] == other.id
    assert reassigned["status"] == "delivery_assigned"


def test_check_in_twice_is_rejected(client, flow, parcel, logistician):
    flow.to(parcel["id"], "in_warehouse")
    response = client.post("/warehouse/check-in", headers=logistician.headers,
                           json={"tracking_numbers": [parcel["tracking_number"]]})
    assert response.status_code == 409


def test_admin_swaps_courier_after_start(client, flow, parcel, admin, make_actor):
    other = make_actor(UserRole.COURIER)
    flow.to(parcel["id"], "out_for_delivery")
    response = client.patch(f"/parcels/{parcel['id']}/couriers", headers=admin.headers,
                            json={"delivery_courier_id": other.id})
    assert response.status_code == 200
    assert response.json()["status"] == "out_for_delivery"
    assert response.json()["delivery_courier"]["id"] == other.id
    path = f"/courier/parcels/{parcel['tracking_number']}/deliver"
    assert client.post(path, headers=flow.courier.headers).status_code == 404
    assert client.post(path, headers=other.headers).status_code == 200


def test_admin_unassigns_pickup_courier(client, flow, parcel, admin):
    flow.pickup_assigned(parcel["id"])
    response = client.patch(f"/parcels/{parcel['id']}/couriers", headers=admin.headers,
                            json={"pickup_courier_id": None})
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["pickup_courier"]) == ("booked", None)


def test_admin_cannot_change_closed_parcel(client, flow, parcel, admin, make_actor):
    other = make_actor(UserRole.COURIER)
    flow.to(parcel["id"], "delivered")
    response = client.patch(f"/parcels/{parcel['id']}/couriers", headers=admin.headers,
                            json={"delivery_courier_id": other.id})
    assert response.status_code == 409
    assert client.post(f"/parcels/{parcel['id']}/cancel", headers=admin.headers).status_code == 409


def test_admin_cancels_parcel_in_warehouse(client, flow, parcel, admin):
    flow.to(parcel["id"], "in_warehouse")
    response = client.post(f"/parcels/{parcel['id']}/cancel", headers=admin.headers)
    assert response.status_code == 200 and response.json()["status"] == "cancelled"


def test_admin_edits_parcel_any_time(client, flow, parcel, admin):
    flow.to(parcel["id"], "out_for_delivery")
    response = client.patch(f"/parcels/{parcel['id']}", headers=admin.headers, json={"size": "XL"})
    assert response.status_code == 200
    assert (response.json()["size"], response.json()["status"]) == ("XL", "out_for_delivery")


def test_admin_cannot_clear_delivery_time_with_courier(client, flow, parcel, admin):
    flow.to(parcel["id"], "delivery_assigned")
    response = client.patch(f"/parcels/{parcel['id']}", headers=admin.headers,
                            json={"delivery_date": None, "delivery_slot": None})
    assert response.status_code == 409


def test_admin_deletes_parcel(client, flow, parcel, admin):
    flow.to(parcel["id"], "in_warehouse")
    assert client.delete(f"/parcels/{parcel['id']}", headers=admin.headers).status_code == 204
    assert client.get(f"/parcels/track/{parcel['tracking_number']}").status_code == 404
    assert client.get(f"/parcels/{parcel['id']}", headers=admin.headers).status_code == 404
