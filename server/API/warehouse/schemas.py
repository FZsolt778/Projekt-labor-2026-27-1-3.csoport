from datetime import date
from typing import Annotated
from pydantic import AfterValidator, Field, PositiveInt, StringConstraints, model_validator
from server.API.common import ORMModel, RequestModel, PatchModel, TimeSlot


def _unique_numbers(numbers: list[str]) -> list[str]:
    if len(set(numbers)) != len(numbers):
        raise ValueError("A lista ismétlődő csomagszámot tartalmaz")
    return numbers


# Same form as public tracking: no surrounding spaces, upper case (column length 30)
TrackingNumber = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=30)]
# Bulk operation tracking numbers, one transaction
TrackingNumberList = Annotated[list[TrackingNumber], Field(min_length=1, max_length=100), AfterValidator(_unique_numbers)]


# --- Warehouse ---------------------------------------------------

class WarehouseRead(ORMModel):
    id: int
    name: str
    capacity: int


class WarehouseUpdate(PatchModel):
    #Admin edit
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    capacity: PositiveInt | None = None


# --- Logistician operations --------------------------------------

class CheckInRequest(RequestModel):
    #Check in arrived parcels
    tracking_numbers: TrackingNumberList


class PickupAssignRequest(RequestModel):
    #Assign pickup to a courier"""
    courier_id: PositiveInt
    tracking_numbers: TrackingNumberList


class DeliveryAssignRequest(RequestModel):
    #Assign delivery to a courier (no date/slot: keep requested delivery time)
    courier_id: PositiveInt
    tracking_numbers: TrackingNumberList
    delivery_date: date | None = None
    delivery_slot: TimeSlot | None = None

    @model_validator(mode="after")
    def _delivery_pair(self):
        if (self.delivery_date is None) != (self.delivery_slot is None):
            raise ValueError("A kiszállítás napját és idősávját együtt kell megadni")
        if self.delivery_date is not None and self.delivery_date < date.today():
            raise ValueError("A kiszállítás napja nem lehet a múltban")
        return self
