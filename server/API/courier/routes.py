from typing import Annotated
from fastapi import APIRouter, Query
from server.API.courier.schemas import CourierTask, CourierTaskParams
from server.API.deps import DbSession, CourierUser
from server.API.courier import services as CourierServices
from server.API.parcel.schemas import ParcelRead

router = APIRouter(prefix="/courier", tags=["courier"])

@router.get("/tasks", response_model=list[CourierTask])
def list_tasks(db: DbSession, courier: CourierUser, data: Annotated[CourierTaskParams, Query()]):
    return CourierServices.list_tasks(db, courier, data)

# The courier identifies the parcel by its tracking number (case and surrounding spaces do not matter)
@router.post("/parcels/{tracking_number}/pickup", response_model=ParcelRead)
def pickup(db: DbSession, courier: CourierUser, tracking_number: str):
    return CourierServices.pickup(db, courier, tracking_number)

@router.post("/parcels/{tracking_number}/start", response_model=ParcelRead)
def start_delivery(db: DbSession, courier: CourierUser, tracking_number: str):
    return CourierServices.start_delivery(db, courier, tracking_number)

@router.post("/parcels/{tracking_number}/deliver", response_model=ParcelRead)
def deliver(db: DbSession, courier: CourierUser, tracking_number: str):
    return CourierServices.deliver(db, courier, tracking_number)

@router.post("/parcels/{tracking_number}/fail", response_model=ParcelRead)
def fail(db: DbSession, courier: CourierUser, tracking_number: str, data: CourierServices.ParcelFailRequest):
    return CourierServices.fail(db, courier, tracking_number, data)

@router.get("/history", response_model=CourierServices.CourierHistory)
def get_history(db: DbSession, courier: CourierUser, params: Annotated[CourierServices.CourierHistoryParams, Query()]):
    return CourierServices.get_history(db, courier, params)