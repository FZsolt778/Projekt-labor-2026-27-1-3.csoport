from datetime import date
from typing import Annotated
from pydantic import AfterValidator, Field, PositiveInt, StringConstraints, model_validator
from server.API.common import ORMModel, RequestModel, PatchModel, TimeSlot


def _unique_ids(ids: list[int]) -> list[int]:
    if len(set(ids)) != len(ids):
        raise ValueError("A lista ismétlődő csomagazonosítót tartalmaz")
    return ids


# Bulk operation parcel ids, one transaction
ParcelIdList = Annotated[list[PositiveInt], Field(min_length=1, max_length=100), AfterValidator(_unique_ids)]


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
    parcel_ids: ParcelIdList


class PickupAssignRequest(RequestModel):
    #Assign pickup to a courier"""
    courier_id: PositiveInt
    parcel_ids: ParcelIdList


class DeliveryAssignRequest(RequestModel):
    #Assign delivery to a courier (no date/slot: keep requested delivery time)
    courier_id: PositiveInt
    parcel_ids: ParcelIdList
    delivery_date: date | None = None
    delivery_slot: TimeSlot | None = None

    @model_validator(mode="after")
    def _delivery_pair(self):
        if (self.delivery_date is None) != (self.delivery_slot is None):
            raise ValueError("A kiszállítás napját és idősávját együtt kell megadni")
        if self.delivery_date is not None and self.delivery_date < date.today():
            raise ValueError("A kiszállítás napja nem lehet a múltban")
        return self
