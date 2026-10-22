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

@router.post("/parcels/{parcel_id}/pickup", response_model=ParcelRead)
def pickup(db: DbSession, courier: CourierUser, parcel_id: int):
    return CourierServices.pickup(db, courier, parcel_id)

@router.post("/parcels/{parcel_id}/start", response_model=ParcelRead)
def start_delivery(db: DbSession, courier: CourierUser, parcel_id: int):
    return CourierServices.start_delivery(db, courier, parcel_id)

@router.post("/parcels/{parcel_id}/deliver", response_model=ParcelRead)
def deliver(db: DbSession, courier: CourierUser, parcel_id: int):
    return CourierServices.deliver(db, courier, parcel_id)

@router.post("/parcels/{parcel_id}/fail", response_model=ParcelRead)
def fail(db: DbSession, courier: CourierUser, parcel_id: int, data: CourierServices.ParcelFailRequest):
    return CourierServices.fail(db, courier, parcel_id, data)

@router.get("/history", response_model=CourierServices.CourierHistory)
def get_history(db: DbSession, courier: CourierUser, params: Annotated[CourierServices.CourierHistoryParams, Query()]):
    return CourierServices.get_history(db, courier, params)