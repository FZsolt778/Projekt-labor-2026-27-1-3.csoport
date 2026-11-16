from helpers import day
from server.models import UserRole


def check_in(client, logistician, *parcel_ids):
    return client.post("/warehouse/check-in", headers=logistician.headers, json={"parcel_ids": list(parcel_ids)})


def set_capacity(client, admin, capacity):
    return client.patch("/warehouse", headers=admin.headers, json={"capacity": capacity})


def test_check_in_is_all_or_nothing(client, flow, book, logistician):
    ready, not_ready = book(), book()
    flow.to(ready["id"], "picked_up")
    response = check_in(client, logistician, ready["id"], not_ready["id"])
    assert response.status_code == 409
    assert f"{not_ready['tracking_number']} (booked)" in response.json()["detail"]
    assert ready["tracking_number"] not in response.json()["detail"]
    # Nothing changed
    assert flow.get(ready["id"])["status"] == "picked_up"


def test_missing_parcel_id_lists_every_missing_one(client, flow, book, logistician):
    ready = book()
    flow.to(ready["id"], "picked_up")
    response = check_in(client, logistician, ready["id"], 998, 999)
    assert response.status_code == 404
    assert response.json()["detail"] == "Nem található csomag: 998, 999"
    assert flow.get(ready["id"])["status"] == "picked_up"


def test_capacity_limit(client, flow, book, logistician, admin):
    assert set_capacity(client, admin, 1).status_code == 200
    first, second = book(), book()
    flow.to(first["id"], "picked_up")
    flow.to(second["id"], "picked_up")

    response = check_in(client, logistician, first["id"], second["id"])
    assert response.status_code == 409
    assert response.json()["detail"] == "Nincs elég hely a raktárban (szabad hely: 1)"
    assert check_in(client, logistician, first["id"]).status_code == 200
    assert check_in(client, logistician, second["id"]).json()["detail"].endswith("(szabad hely: 0)")

    # Assigned parcels are still inside, after the courier leaves the place is free again
    flow.delivery_assigned(first["id"])
    assert check_in(client, logistician, second["id"]).status_code == 409
    flow.out_for_delivery(first["id"])
    assert check_in(client, logistician, second["id"]).status_code == 200


def test_capacity_cannot_go_below_current_count(client, flow, book, admin):
    for parcel in (book(), book()):
        flow.to(parcel["id"], "in_warehouse")
    response = set_capacity(client, admin, 1)
    assert response.status_code == 409
    assert "(2)" in response.json()["detail"]
    assert set_capacity(client, admin, 2).status_code == 200
    assert set_capacity(client, admin, 0).status_code == 422


def test_warehouse_data(client, logistician, admin):
    response = client.get("/warehouse", headers=logistician.headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Teszt raktár"
    renamed = client.patch("/warehouse", headers=admin.headers, json={"name": "Központi raktár"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "Központi raktár"


def test_assign_pickup_needs_an_active_courier(client, book, logistician, make_actor):
    parcel = book()
    inactive = make_actor(UserRole.COURIER, is_active=False)
    for user_id in (logistician.id, inactive.id, 999):
        response = client.post("/warehouse/assign-pickup", headers=logistician.headers,
                               json={"courier_id": user_id, "parcel_ids": [parcel["id"]]})
        assert response.status_code == 404
        assert response.json()["detail"] == "Futár nem található"


def test_assign_pickup_many_at_once(client, book, logistician, courier):
    ids = [book()["id"] for _ in range(3)]
    response = client.post("/warehouse/assign-pickup", headers=logistician.headers,
                           json={"courier_id": courier.id, "parcel_ids": ids})
    assert response.status_code == 200
    assert {p["status"] for p in response.json()} == {"pickup_assigned"}
    assert len(client.get("/courier/tasks", headers=courier.headers).json()) == 3


def test_reassign_pickup_before_pickup(flow, book, make_actor):
    parcel = book()
    other = make_actor(UserRole.COURIER)
    flow.pickup_assigned(parcel["id"])
    flow.pickup_assigned(parcel["id"])  # same courier again: no new event
    assert len(flow.get(parcel["id"])["events"]) == 2
    moved = flow.pickup_assigned(parcel["id"], courier=other)[0]
    assert moved["pickup_courier"]["id"] == other.id
    assert len(flow.get(parcel["id"])["events"]) == 3


def test_assign_delivery_overrides_requested_time(flow, book):
    parcel = book()
    flow.to(parcel["id"], "in_warehouse")
    assigned = flow.delivery_assigned(parcel["id"], delivery_date=day(5), delivery_slot="14:00-16:00")[0]
    assert assigned["delivery_date"] == day(5)
    assert (assigned["delivery_window_start"], assigned["delivery_window_end"]) == ("14:00:00", "16:00:00")


def test_assign_delivery_not_before_pickup(client, flow, book, logistician, courier):
    parcel = book(pickup=3, delivery=4)
    flow.to(parcel["id"], "in_warehouse")
    response = client.post("/warehouse/assign-delivery", headers=logistician.headers, json={
        "courier_id": courier.id, "parcel_ids": [parcel["id"]],
        "delivery_date": day(2), "delivery_slot": "10:00-12:00"})
    assert response.status_code == 422
    assert "nem lehet korábbi a felvételnél" in response.json()["detail"]


def test_assign_delivery_needs_a_time_without_request(client, flow, book, logistician, courier):
    parcel = book(delivery=None)
    flow.to(parcel["id"], "in_warehouse")
    response = client.post("/warehouse/assign-delivery", headers=logistician.headers,
                           json={"courier_id": courier.id, "parcel_ids": [parcel["id"]]})
    assert response.status_code == 422
    assert parcel["tracking_number"] in response.json()["detail"]
    # With a date and slot it works
    assert flow.delivery_assigned(parcel["id"], delivery_date=day(4), delivery_slot="08:00-10:00")


def test_courier_list_shows_active_couriers_only(client, logistician, make_actor):
    active = make_actor(UserRole.COURIER)
    make_actor(UserRole.COURIER, is_active=False)
    make_actor(UserRole.CUSTOMER)
    response = client.get("/warehouse/couriers", headers=logistician.headers)
    assert [user["id"] for user in response.json()] == [active.id]
    assert set(response.json()[0]) == {"id", "last_name", "first_name", "phone", "role"}


def test_parcel_list_filters(client, flow, book, logistician, courier):
    booked = book(recipient_email="kovacs@teszt.hu")
    assigned = book()
    flow.pickup_assigned(assigned["id"])

    def ids(**params):
        response = client.get("/parcels", headers=logistician.headers, params=params)
        assert response.status_code == 200
        return {item["id"] for item in response.json()["items"]}

    assert ids() == {booked["id"], assigned["id"]}
    assert ids(status="booked") == {booked["id"]}
    assert ids(courier_id=courier.id) == {assigned["id"]}
    assert ids(search=booked["tracking_number"][2:8].lower()) == {booked["id"]}
    assert ids(search="MINTA FELAD") == {booked["id"], assigned["id"]}
    assert ids(pickup_date=day(2)) == {booked["id"], assigned["id"]}
    assert ids(pickup_date=day(9)) == set()


def test_parcel_list_paging(client, book, logistician):
    for _ in range(3):
        book()
    page = client.get("/parcels", headers=logistician.headers, params={"limit": 2, "offset": 2}).json()
    assert (page["total"], page["limit"], page["offset"], len(page["items"])) == (3, 2, 2, 1)
