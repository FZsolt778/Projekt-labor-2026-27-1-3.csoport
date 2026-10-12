from typing import Annotated
from fastapi import APIRouter, Query, status
from server.API.common import Page
from server.API.deps import DbSession, OptionalUser, CustomerUser, AdminUser, StaffUser
from server.API.parcel import services
from server.API.parcel.schemas import (
    AdminParcelUpdate, MyParcelsParams, ParcelAdminDetail, ParcelAdminRead, ParcelCourierUpdate,
    ParcelCreate, ParcelDetail, ParcelListParams, ParcelRead, ParcelTracking, ParcelUpdate,
)

router = APIRouter(prefix="/parcels", tags=["parcels"])

# /track and /my must stay before /{parcel_id}, otherwise it would catch them


# --- Public ------------------------------------------------------

@router.post("", response_model=ParcelRead, status_code=status.HTTP_201_CREATED)
def create_parcel(data: ParcelCreate, db: DbSession, user: OptionalUser):
    return services.create_parcel(db, data, user)


@router.get("/track/{tracking_number}", response_model=ParcelTracking)
def track_parcel(tracking_number: str, db: DbSession):
    return services.get_by_tracking_number(db, tracking_number)


# --- Registered customer -----------------------------------------

@router.get("/my", response_model=Page[ParcelRead])
def list_my_parcels(params: Annotated[MyParcelsParams, Query()], db: DbSession, user: CustomerUser):
    return services.list_my_parcels(db, user, params)


@router.get("/my/{parcel_id}", response_model=ParcelDetail)
def get_my_parcel(parcel_id: int, db: DbSession, user: CustomerUser):
    return services.get_my_parcel(db, user, parcel_id)


@router.patch("/my/{parcel_id}", response_model=ParcelRead)
def update_my_parcel(parcel_id: int, data: ParcelUpdate, db: DbSession, user: CustomerUser):
    return services.update_my_parcel(db, user, parcel_id, data)


@router.post("/my/{parcel_id}/cancel", response_model=ParcelRead)
def cancel_my_parcel(parcel_id: int, db: DbSession, user: CustomerUser):
    return services.cancel_my_parcel(db, user, parcel_id)


# --- Admin / logistician -----------------------------------------

@router.get("", response_model=Page[ParcelAdminRead])
def list_parcels(params: Annotated[ParcelListParams, Query()], db: DbSession, staff: StaffUser):
    return services.list_parcels(db, params)


@router.get("/{parcel_id}", response_model=ParcelAdminDetail)
def get_parcel(parcel_id: int, db: DbSession, staff: StaffUser):
    return services.get_parcel_or_404(db, parcel_id)


@router.patch("/{parcel_id}", response_model=ParcelAdminRead)
def update_parcel(parcel_id: int, data: AdminParcelUpdate, db: DbSession, admin: AdminUser):
    return services.admin_update_parcel(db, admin, parcel_id, data)


@router.patch("/{parcel_id}/couriers", response_model=ParcelAdminRead)
def set_couriers(parcel_id: int, data: ParcelCourierUpdate, db: DbSession, admin: AdminUser):
    return services.admin_set_couriers(db, admin, parcel_id, data)


@router.post("/{parcel_id}/cancel", response_model=ParcelAdminRead)
def cancel_parcel(parcel_id: int, db: DbSession, admin: AdminUser):
    return services.admin_cancel_parcel(db, admin, parcel_id)


@router.delete("/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcel(parcel_id: int, db: DbSession, admin: AdminUser):
    services.delete_parcel(db, parcel_id)
