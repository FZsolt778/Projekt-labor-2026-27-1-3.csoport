import pytest

from server.models import UserRole
from server.src.config import settings

MAX = settings.MAX_FAILED_DELIVERIES


@pytest.fixture
def parcel(book, customer):
    return book(customer)


def attempt(flow, parcel_id, courier=None):
    # One delivery attempt that fails
    flow.delivery_assigned(parcel_id, courier=courier)
    flow.out_for_delivery(parcel_id, courier=courier)
    return flow.fail(parcel_id, courier=courier)


def test_failed_pickup_cancels_at_once(client, flow, parcel, courier):
    flow.pickup_assigned(parcel["id"])
    result = flow.fail(parcel["id"], note="Zárva volt")
    assert result["status"] == "cancelled"

    events = flow.get(parcel["id"])["events"]
    assert [e["status"] for e in events[-2:]] == ["failed", "cancelled"]
    assert events[-2]["note"] == "Zárva volt" and events[-1]["note"] == "Sikertelen felvétel"
    assert client.get("/courier/tasks", headers=courier.headers).json() == []


def test_failed_delivery_goes_back_to_warehouse(client, flow, parcel, courier):
    flow.to(parcel["id"], "in_warehouse")
    assert attempt(flow, parcel["id"])["status"] == "failed"
    # The courier still has to bring it back
    tasks = client.get("/courier/tasks", headers=courier.headers).json()
    assert [(t["task"], t["parcel"]["status"]) for t in tasks] == [("delivery", "failed")]

    back = flow.in_warehouse(parcel["id"])[0]
    assert back["status"] == "in_warehouse"
    assert back["delivery_courier"] is None and back["out_for_delivery_at"] is None
    # It can be assigned and delivered again
    flow.delivery_assigned(parcel["id"])
    flow.out_for_delivery(parcel["id"])
    assert flow.delivered(parcel["id"])["status"] == "delivered"


def test_failed_parcel_cannot_be_delivered(client, flow, parcel, courier):
    flow.to(parcel["id"], "in_warehouse")
    attempt(flow, parcel["id"])
    assert client.post(f"/courier/parcels/{parcel['id']}/deliver", headers=courier.headers).status_code == 409


def test_fail_only_while_out_for_delivery(client, flow, parcel, courier):
    flow.to(parcel["id"], "delivery_assigned")
    response = client.post(f"/courier/parcels/{parcel['id']}/fail", headers=courier.headers, json={"note": "x"})
    assert response.status_code == 409


def test_other_courier_cannot_record_failure(client, flow, parcel, make_actor):
    other = make_actor(UserRole.COURIER)
    flow.to(parcel["id"], "out_for_delivery")
    response = client.post(f"/courier/parcels/{parcel['id']}/fail", headers=other.headers, json={"note": "x"})
    assert response.status_code == 404


def test_cancelled_after_max_failed_deliveries(flow, parcel):
    flow.to(parcel["id"], "in_warehouse")
    for n in range(1, MAX):
        assert attempt(flow, parcel["id"])["status"] == "failed", f"attempt {n}"
        flow.in_warehouse(parcel["id"])
    assert attempt(flow, parcel["id"])["status"] == "cancelled"
    assert flow.get(parcel["id"])["events"][-1]["note"] == f"{MAX} sikertelen kézbesítés"


def test_admin_courier_swap_is_not_a_failure(client, flow, parcel, admin, make_actor):
    if MAX < 2:
        pytest.skip("needs MAX_FAILED_DELIVERIES >= 2")
    other = make_actor(UserRole.COURIER)
    flow.to(parcel["id"], "in_warehouse")
    attempt(flow, parcel["id"])
    # The swap on a failed parcel also logs a "failed" event, but by the admin
    swap = client.patch(f"/parcels/{parcel['id']}/couriers", headers=admin.headers,
                        json={"delivery_courier_id": other.id})
    assert swap.status_code == 200 and swap.json()["status"] == "failed"

    result = None
    for _ in range(2, MAX):
        flow.in_warehouse(parcel["id"])
        result = attempt(flow, parcel["id"], courier=other)
    if result is not None:
        assert result["status"] == "failed"
    failed = [e for e in flow.get(parcel["id"])["events"] if e["status"] == "failed"]
    assert len(failed) == MAX

    flow.in_warehouse(parcel["id"])
    assert attempt(flow, parcel["id"], courier=other)["status"] == "cancelled"
