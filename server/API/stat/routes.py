from typing import Annotated
from fastapi import APIRouter, Query

router = APIRouter(prefix="/stats", tags=["stats"])

from server.API.stat import services as StatServices
from server.API.deps import AdminUser, DbSession

@router.get("/warehouse", response_model=StatServices.WarehouseUtilization)
def get_warehouse_utilization(db: DbSession, admin: AdminUser):
    return StatServices.warehouse_utilization(db)

@router.get("/warehouse/history", response_model=StatServices.WarehouseUtilizationHistory)
def get_warehouse_history(db: DbSession, admin: AdminUser, params: Annotated[StatServices.StatsRangeParams, Query()]):
    return StatServices.warehouse_history(db, params)

@router.get("/couriers", response_model=StatServices.CourierStatsReport)
def get_courier_stats(db: DbSession, admin: AdminUser, params: Annotated[StatServices.StatsRangeParams, Query()]):
    return StatServices.courier_stats(db, params)
