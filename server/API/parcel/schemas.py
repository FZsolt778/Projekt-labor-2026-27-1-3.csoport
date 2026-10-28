from datetime import date, time, datetime
from enum import Enum
from typing import Annotated
from pydantic import BaseModel, PositiveInt, StringConstraints, field_validator, model_validator
from server.models import ParcelSize, ParcelStatus
from server.API.common import ORMModel, RequestModel, PatchModel, PageParams, TimeSlot, tomorrow
from server.API.contact.schemas import (
    ContactCreate, ContactRead, ContactUpdate, ContactInfoUpdate, AddressUpdate,
)
from server.API.user.schemas import UserSummary, CourierPublic


def _check_pickup_date(value: date | None) -> date | None:
    if value is not None and value < tomorrow():
        raise ValueError("A felvétel legkorábban holnapra foglalható")
    return value


def _check_delivery_pair(model: BaseModel) -> None:
    #Delivery date and slot go together (matches DB CHECK)
    if ("delivery_date" in model.model_fields_set) != ("delivery_slot" in model.model_fields_set):
        raise ValueError("A kiszállítás napját és idősávját együtt kell megadni")
    if (model.delivery_date is None) != (model.delivery_slot is None):
        raise ValueError("A kiszállítás napja és idősávja vagy mindkettő kitöltött, vagy mindkettő null")


# --- Requests ----------------------------------------------------

class ParcelCreate(RequestModel):
    #Book a parcel (guest or registered)
    size: ParcelSize
    sender: ContactCreate
    recipient: ContactCreate
    pickup_date: date
    pickup_slot: TimeSlot
    # Requested delivery, logistician may override
    delivery_date: date | None = None
    delivery_slot: TimeSlot | None = None

    _pickup_date = field_validator("pickup_date")(_check_pickup_date)

    @model_validator(mode="after")
    def _schedule(self):
        _check_delivery_pair(self)
        if self.delivery_date is None:
            return self
        if self.delivery_date < self.pickup_date:
            raise ValueError("A kiszállítás nem lehet korábban, mint a felvétel")
        if self.delivery_date == self.pickup_date and self.delivery_slot.start < self.pickup_slot.end:
            raise ValueError("Azonos napon a kiszállítási idősáv csak a felvételi idősáv után kezdődhet")
        return self


class ParcelUpdate(PatchModel):
    #Customer edit, until the day before pickup
    nullable_fields = frozenset({"delivery_date", "delivery_slot"})

    size: ParcelSize | None = None
    pickup_date: date | None = None
    pickup_slot: TimeSlot | None = None
    # Requested delivery (both null: no request)
    delivery_date: date | None = None
    delivery_slot: TimeSlot | None = None
    sender: ContactInfoUpdate | None = None
    recipient_address: AddressUpdate | None = None

    _pickup_date = field_validator("pickup_date")(_check_pickup_date)

    @model_validator(mode="after")
    def _delivery_pair(self):
        _check_delivery_pair(self)
        return self


class AdminParcelUpdate(PatchModel):
    #Admin edit (status not editable)
    nullable_fields = frozenset({"delivery_date", "delivery_slot"})

    size: ParcelSize | None = None
    pickup_date: date | None = None
    pickup_slot: TimeSlot | None = None
    delivery_date: date | None = None
    delivery_slot: TimeSlot | None = None
    sender: ContactUpdate | None = None
    recipient: ContactUpdate | None = None

    @model_validator(mode="after")
    def _delivery_pair(self):
        _check_delivery_pair(self)
        return self


class ParcelCourierUpdate(PatchModel):
    #Admin courier reassignment, any time (null: unassign)
    nullable_fields = frozenset({"pickup_courier_id", "delivery_courier_id"})

    pickup_courier_id: PositiveInt | None = None
    delivery_courier_id: PositiveInt | None = None


# --- Query params ------------------------------------------------

class ParcelDirection(str, Enum):
    SENT = "sent"
    RECEIVED = "received"


class ParcelScope(str, Enum):
    # In progress
    ACTIVE = "active"
    # Closed (delivered, cancelled)
    HISTORY = "history"


class MyParcelsParams(PageParams):
    #Own parcels (None: both)
    direction: ParcelDirection | None = None
    scope: ParcelScope | None = None


class ParcelListParams(PageParams):
    #Parcel filters (admin, logistician)
    status: ParcelStatus | None = None
    # Pickup or delivery courier
    courier_id: PositiveInt | None = None
    pickup_date: date | None = None
    delivery_date: date | None = None
    # Tracking number, sender or recipient name
    search: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None


# --- Responses ---------------------------------------------------

class ParcelEventRead(ORMModel):
    #Timeline entry, customer view
    status: ParcelStatus
    occurred_at: datetime
    note: str | None
    courier: CourierPublic | None


class ParcelEventAdminRead(ORMModel):
    #Timeline entry, internal view
    id: int
    status: ParcelStatus
    occurred_at: datetime
    note: str | None
    courier: UserSummary | None
    # Recorded by (None: guest booking)
    actor: UserSummary | None


class _ParcelFields(ORMModel):
    tracking_number: str
    size: ParcelSize
    status: ParcelStatus
    sender: ContactRead
    recipient: ContactRead
    pickup_date: date
    pickup_window_start: time
    pickup_window_end: time
    delivery_date: date | None
    delivery_window_start: time | None
    delivery_window_end: time | None
    created_at: datetime
    picked_up_at: datetime | None
    warehouse_arrived_at: datetime | None
    out_for_delivery_at: datetime | None
    delivered_at: datetime | None


class ParcelTracking(_ParcelFields):
    #Public tracking
    pickup_courier: CourierPublic | None
    delivery_courier: CourierPublic | None
    events: list[ParcelEventRead]


class ParcelRead(_ParcelFields):
    #Customer and courier view
    id: int
    pickup_courier: CourierPublic | None
    delivery_courier: CourierPublic | None


class ParcelDetail(ParcelRead):
    events: list[ParcelEventRead]


class ParcelAdminRead(_ParcelFields):
    #Admin and logistician view
    id: int
    warehouse_id: int | None
    pickup_courier: UserSummary | None
    delivery_courier: UserSummary | None


class ParcelAdminDetail(ParcelAdminRead):
    events: list[ParcelEventAdminRead]
