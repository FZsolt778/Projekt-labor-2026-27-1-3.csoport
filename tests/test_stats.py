from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import select

from helpers import WAREHOUSE_CAPACITY
from server.models import Parcel, ParcelEvent, UserRole

D = date.today() - timedelta(days=10)  # delivery day, in the past

TIMES = {
    "booked": (D - timedelta(days=2), time(8, 0)),
    "pickup_assigned": (D - timedelta(days=2), time(9, 0)),
    "picked_up": (D - timedelta(days=1), time(10, 0)),
    "in_warehouse": (D - timedelta(days=1), time(15, 0)),
    "delivery_assigned": (D - timedelta(days=1), time(16, 0)),
    "out_for_delivery": (D, time(10, 0)),
    "delivered": (D, time(10, 30)),
}
MILESTONES = {"booked": "created_at", "picked_up": "picked_up_at", "in_warehouse": "warehouse_arrived_at",
              "out_for_delivery": "out_for_delivery_at", "delivered": "delivered_at"}


def at(status: str) -> datetime:
    return datetime.combine(*TIMES[status])


def set_times(db, parcel_id: int, times: dict[str, datetime]) -> None:
    # Moves the events (and the matching milestones) of a parcel to the given times
    parcel = db.get(Parcel, parcel_id)
    for event in db.scalars(select(ParcelEvent).where(ParcelEvent.parcel_id == parcel_id)):
        if event.status in times:
            event.occurred_at = times[event.status]
    for status, attr in MILESTONES.items():
        if status in times:
            setattr(parcel, attr, times[status])
    db.commit()


@pytest.fixture
def delivered(db, flow, book):
    parcel = book()
    flow.to(parcel["id"], "delivered")
    set_times(db, parcel["id"], {status: at(status) for status in TIMES})
    return parcel


def courier_stats(client, admin, from_date: date, to_date: date) -> dict:
    response = client.get("/stats/couriers", headers=admin.headers,
                          params={"from_date": from_date.isoformat(), "to_date": to_date.isoformat()})
    assert response.status_code == 200
    return response.json()


def test_courier_stats(client, admin, courier, delivered):
    report = courier_stats(client, admin, D - timedelta(days=2), D)
    row = next(r for r in report["couriers"] if r["courier"]["id"] == courier.id)
    assert (row["pickups_count"], row["deliveries_count"], row["failed_count"]) == (1, 1, 0)
    assert row["active_days"] == 2
    assert row["avg_deliveries_per_day"] == 0.5
    assert row["avg_delivery_minutes"] == 30.0  # out for delivery 10:00 -> delivered 10:30
    assert row["avg_lead_time_hours"] == 24.5   # picked up D-1 10:00 -> delivered D 10:30
    assert [(d["pickups"], d["deliveries"], d["failed"]) for d in row["daily"]] == [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    assert [d["day"] for d in report["daily_totals"]] == [(D - timedelta(days=n)).isoformat() for n in (2, 1, 0)]
    assert (report["avg_delivery_minutes"], report["avg_lead_time_hours"]) == (30.0, 24.5)


def test_courier_stats_outside_the_range(client, admin, courier, delivered):
    report = courier_stats(client, admin, D + timedelta(days=1), D + timedelta(days=3))
    row = next(r for r in report["couriers"] if r["courier"]["id"] == courier.id)
    assert (row["deliveries_count"], row["active_days"], row["avg_delivery_minutes"]) == (0, 0, None)


def test_admin_swap_does_not_count_for_the_courier(client, flow, book, admin, make_actor):
    other = make_actor(UserRole.COURIER)
    parcel = book()
    flow.to(parcel["id"], "picked_up")
    # The admin moves the picked-up parcel to another courier: a "picked_up" event by the admin
    client.patch(f"/parcels/{parcel['id']}/couriers", headers=admin.headers, json={"pickup_courier_id": other.id})
    today = date.today()
    report = courier_stats(client, admin, today - timedelta(days=1), today + timedelta(days=1))
    pickups = {r["courier"]["id"]: r["pickups_count"] for r in report["couriers"]}
    assert pickups == {flow.courier.id: 1, other.id: 0}


def test_warehouse_history(client, admin, delivered):
    response = client.get("/stats/warehouse/history", headers=admin.headers, params={
        "from_date": (D - timedelta(days=2)).isoformat(), "to_date": D.isoformat()})
    assert response.status_code == 200
    history = response.json()
    # In from D-1 15:00 (check-in) until D 10:00 (out for delivery)
    assert [p["parcel_count"] for p in history["points"]] == [0, 1, 0]
    assert history["peak_parcel_count"] == 1
    assert history["points"][1]["utilization_percent"] == round(100 / WAREHOUSE_CAPACITY, 1)
    assert history["avg_utilization_percent"] == round(100 / WAREHOUSE_CAPACITY / 3, 1)


def test_warehouse_now(client, flow, book, admin):
    for size in ("M", "M", "XL"):
        flow.to(book(size=size)["id"], "in_warehouse")
    flow.to(book()["id"], "out_for_delivery")  # left the warehouse
    response = client.get("/stats/warehouse", headers=admin.headers)
    assert response.status_code == 200
    now = response.json()
    assert now["parcel_count"] == 3
    assert now["by_size"] == {"S": 0, "M": 2, "L": 0, "XL": 1}
    assert now["utilization_percent"] == round(3 / WAREHOUSE_CAPACITY * 100, 1)


def history(client, courier, **params) -> dict:
    response = client.get("/courier/history", headers=courier.headers, params=params)
    assert response.status_code == 200
    return response.json()


def test_courier_history_by_day(client, courier, delivered):
    pickup_day = history(client, courier, day=(D - timedelta(days=1)).isoformat())
    assert (pickup_day["pickups_count"], pickup_day["deliveries_count"]) == (1, 0)
    assert pickup_day["items"][0]["task"] == "pickup"
    assert pickup_day["items"][0]["contact"]["first_name"] == "Feladó"

    delivery_day = history(client, courier, day=D.isoformat())
    assert (delivery_day["pickups_count"], delivery_day["deliveries_count"]) == (0, 1)
    assert delivery_day["items"][0]["contact"]["first_name"] == "Címzett"
    assert delivery_day["items"][0]["parcel_id"] == delivered["id"]


def test_courier_history_week_is_monday_to_sunday(client, courier, delivered):
    week = history(client, courier, period="week", day=D.isoformat())
    monday = D - timedelta(days=D.weekday())
    assert (week["from_date"], week["to_date"]) == (monday.isoformat(), (monday + timedelta(days=6)).isoformat())
    assert week["deliveries_count"] == 1
    assert week["pickups_count"] == (1 if D - timedelta(days=1) >= monday else 0)


def test_courier_history_month(client, courier, delivered):
    month = history(client, courier, period="month", day=D.isoformat())
    assert month["from_date"] == D.replace(day=1).isoformat()
    assert month["deliveries_count"] == 1


def test_courier_history_shows_failure_reason(client, db, flow, book, courier):
    parcel = book()
    flow.to(parcel["id"], "out_for_delivery")
    flow.fail(parcel["id"], note="Nem volt otthon")
    set_times(db, parcel["id"], {"failed": datetime.combine(D, time(12, 0))})
    day_report = history(client, courier, day=D.isoformat())
    assert day_report["failed_count"] == 1
    assert (day_report["items"][0]["status"], day_report["items"][0]["note"]) == ("failed", "Nem volt otthon")
