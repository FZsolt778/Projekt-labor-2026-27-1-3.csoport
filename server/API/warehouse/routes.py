from fastapi import APIRouter
from server.API.warehouse import services
from server.API.parcel.schemas import ParcelAdminRead
from server.API.deps import AdminUser, DbSession, StaffUser
from server.API.warehouse.schemas import CheckInRequest, DeliveryAssignRequest, PickupAssignRequest, WarehouseRead, WarehouseUpdate
from server.API.user.schemas import UserSummary

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.get("", response_model=WarehouseRead)
def get_warehouse(db: DbSession, staff: StaffUser):
    return services.get_warehouse(db)

@router.patch("", response_model=WarehouseRead)
def update_warehouse(data: WarehouseUpdate, db: DbSession, staff: AdminUser):
    return services.update_warehouse(db, data)

@router.get("/couriers", response_model=list[UserSummary])
def list_couriers(db: DbSession, staff: StaffUser):
    return services.list_couriers(db)

@router.post("/check-in", response_model=list[ParcelAdminRead])
def check_in(data: CheckInRequest, db: DbSession, staff: StaffUser):
    return services.check_in(db, staff, data)

@router.post("/assign-pickup", response_model=list[ParcelAdminRead])
def assign_pickup(data: PickupAssignRequest, db: DbSession, staff: StaffUser):
    return services.assign_pickup(db, staff, data)

@router.post("/assign-delivery", response_model=list[ParcelAdminRead])
def assign_delivery(data: DeliveryAssignRequest, db: DbSession, staff: StaffUser):
    return services.assign_delivery(db, staff, data)