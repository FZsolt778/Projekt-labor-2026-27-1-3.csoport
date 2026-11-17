from dataclasses import dataclass
from datetime import date, timedelta
from fastapi.testclient import TestClient
from server.models import User

PASSWORD = "jelszo123"
WAREHOUSE_CAPACITY = 10


@dataclass
class Actor:
    user: User
    headers: dict

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def email(self) -> str:
        return self.user.email


def day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def contact(first_name: str, email: str) -> dict:
    return {"last_name": "Minta", "first_name": first_name, "email": email,
            "postal_code": "8200", "city": "Veszprém", "street": "Egyetem utca", "house_number": "10"}


def parcel_body(*, pickup: int = 2, slot: str = "08:00-10:00", size: str = "M",
                sender_email: str = "felado@teszt.hu", recipient_email: str = "cimzett@teszt.hu") -> dict:
    # Booking request, pickup is days from today. No delivery time: the logistician sets it.
    return {"size": size, "sender": contact("Feladó", sender_email),
            "recipient": contact("Címzett", recipient_email),
            "pickup_date": day(pickup), "pickup_slot": slot}


class Flow:
    # Moves a parcel along the normal path; every step asserts success
    STEPS = ("pickup_assigned", "picked_up", "in_warehouse", "delivery_assigned", "out_for_delivery", "delivered")

    def __init__(self, client: TestClient, logistician: Actor, courier: Actor):
        self.client, self.logistician, self.courier = client, logistician, courier
        # parcel id -> tracking number: the courier and warehouse endpoints take the tracking number
        self._numbers: dict[int, str] = {}

    def _ok(self, response):
        assert response.status_code == 200, response.text
        return response.json()

    def number(self, parcel_id: int) -> str:
        if parcel_id not in self._numbers:
            self._numbers[parcel_id] = self.get(parcel_id)["tracking_number"]
        return self._numbers[parcel_id]

    def pickup_assigned(self, parcel_id: int, courier: Actor | None = None):
        courier = courier or self.courier
        return self._ok(self.client.post("/warehouse/assign-pickup", headers=self.logistician.headers,
                                         json={"courier_id": courier.id, "tracking_numbers": [self.number(parcel_id)]}))

    def picked_up(self, parcel_id: int, courier: Actor | None = None):
        courier = courier or self.courier
        return self._ok(self.client.post(f"/courier/parcels/{self.number(parcel_id)}/pickup", headers=courier.headers))

    def in_warehouse(self, parcel_id: int):
        return self._ok(self.client.post("/warehouse/check-in", headers=self.logistician.headers,
                                         json={"tracking_numbers": [self.number(parcel_id)]}))

    def delivery_assigned(self, parcel_id: int, courier: Actor | None = None, **when):
        # Default delivery time: day 3, 10:00-12:00 (the default pickup is day 2)
        courier = courier or self.courier
        when = when or {"delivery_date": day(3), "delivery_slot": "10:00-12:00"}
        body = {"courier_id": courier.id, "tracking_numbers": [self.number(parcel_id)], **when}
        return self._ok(self.client.post("/warehouse/assign-delivery", headers=self.logistician.headers, json=body))

    def out_for_delivery(self, parcel_id: int, courier: Actor | None = None):
        courier = courier or self.courier
        return self._ok(self.client.post(f"/courier/parcels/{self.number(parcel_id)}/start", headers=courier.headers))

    def delivered(self, parcel_id: int, courier: Actor | None = None):
        courier = courier or self.courier
        return self._ok(self.client.post(f"/courier/parcels/{self.number(parcel_id)}/deliver", headers=courier.headers))

    def fail(self, parcel_id: int, note: str = "Nem volt otthon", courier: Actor | None = None):
        courier = courier or self.courier
        return self._ok(self.client.post(f"/courier/parcels/{self.number(parcel_id)}/fail", headers=courier.headers,
                                         json={"note": note}))

    def to(self, parcel_id: int, target: str):
        for step in self.STEPS[: self.STEPS.index(target) + 1]:
            getattr(self, step)(parcel_id)

    def get(self, parcel_id: int) -> dict:
        return self._ok(self.client.get(f"/parcels/{parcel_id}", headers=self.logistician.headers))
