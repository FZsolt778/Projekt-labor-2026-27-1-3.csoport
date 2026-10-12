from datetime import date, timedelta
from pydantic import BaseModel, Field, model_validator
from server.API.user.schemas import UserSummary

MAX_RANGE_DAYS = 366


class StatsRangeParams(BaseModel):
    #Date range (default: last 30 days)
    from_date: date = Field(default_factory=lambda: date.today() - timedelta(days=29))
    to_date: date = Field(default_factory=date.today)

    @model_validator(mode="after")
    def _range(self):
        if self.from_date > self.to_date:
            raise ValueError("A from_date nem lehet későbbi, mint a to_date")
        if (self.to_date - self.from_date).days >= MAX_RANGE_DAYS:
            raise ValueError(f"Az időszak legfeljebb {MAX_RANGE_DAYS} nap lehet")
        return self


# --- Warehouse utilization ---------------------------------------

class SizeBreakdown(BaseModel):
    S: int = 0
    M: int = 0
    L: int = 0
    XL: int = 0


class WarehouseUtilization(BaseModel):
    #Current utilization: parcels in the warehouse vs capacity
    warehouse_id: int
    name: str
    capacity: int
    parcel_count: int
    utilization_percent: float
    by_size: SizeBreakdown


class UtilizationPoint(BaseModel):
    day: date
    # Parcels in the warehouse at end of day
    parcel_count: int
    utilization_percent: float


class WarehouseUtilizationHistory(BaseModel):
    warehouse_id: int
    name: str
    capacity: int
    from_date: date
    to_date: date
    avg_utilization_percent: float
    peak_parcel_count: int
    points: list[UtilizationPoint]


# --- Courier stats -----------------------------------------------

class DailyCount(BaseModel):
    day: date
    pickups: int
    deliveries: int
    failed: int


class CourierStats(BaseModel):
    courier: UserSummary
    pickups_count: int
    deliveries_count: int
    failed_count: int
    # Days with at least one pickup or delivery
    active_days: int
    # Deliveries per active day
    avg_deliveries_per_day: float
    # out_for_delivery_at -> delivered_at
    avg_delivery_minutes: float | None
    # picked_up_at -> delivered_at
    avg_lead_time_hours: float | None
    daily: list[DailyCount]


class CourierStatsReport(BaseModel):
    from_date: date
    to_date: date
    # All couriers combined
    avg_delivery_minutes: float | None
    avg_lead_time_hours: float | None
    daily_totals: list[DailyCount]
    couriers: list[CourierStats]
