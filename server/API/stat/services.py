from collections import defaultdict
from datetime import date, datetime, time, timedelta
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from server.models import Parcel, ParcelEvent, ParcelSize, ParcelStatus, User, UserRole
from server.API.user.schemas import UserSummary
from server.API.warehouse.services import IN_WAREHOUSE_STATUSES, get_warehouse
from server.API.stat.schemas import (
    CourierStats, CourierStatsReport, DailyCount, SizeBreakdown, StatsRangeParams, UtilizationPoint,
    WarehouseUtilization, WarehouseUtilizationHistory,
)

# Aggregation runs in Python on filtered rows, so it works on any DB
# Percentages and averages rounded to 1 decimal

COURIER_STATUSES = (ParcelStatus.PICKED_UP, ParcelStatus.DELIVERED, ParcelStatus.FAILED)


def _days(from_date: date, to_date: date) -> list[date]:
    return [from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)]


def _range_bounds(params: StatsRangeParams) -> tuple[datetime, datetime]:
    # [from_date 00:00, to_date + 1 00:00)
    return (
        datetime.combine(params.from_date, time.min),
        datetime.combine(params.to_date + timedelta(days=1), time.min),
    )


def _percent(count: int, capacity: int) -> float:
    return round(count / capacity * 100, 1)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def warehouse_utilization(db: Session) -> WarehouseUtilization:
    warehouse = get_warehouse(db)
    rows = db.execute(
        select(Parcel.size, func.count())
        .where(Parcel.warehouse_id == warehouse.id, Parcel.status.in_(IN_WAREHOUSE_STATUSES))
        .group_by(Parcel.size)
    ).all()
    by_size = {ParcelSize(size).value: count for size, count in rows}
    parcel_count = sum(by_size.values())
    return WarehouseUtilization(
        warehouse_id=warehouse.id,
        name=warehouse.name,
        capacity=warehouse.capacity,
        parcel_count=parcel_count,
        utilization_percent=_percent(parcel_count, warehouse.capacity),
        by_size=SizeBreakdown(**by_size),
    )


def warehouse_history(db: Session, params: StatsRangeParams) -> WarehouseUtilizationHistory:
    # Replays the event log: a parcel is inside at end of day if its last event by then
    # has a status in IN_WAREHOUSE_STATUSES (milestones are overwritten on retries, events are not).
    # Percentages use the current capacity, its history is not stored.
    warehouse = get_warehouse(db)
    _, end = _range_bounds(params)
    events = db.execute(
        select(ParcelEvent.parcel_id, ParcelEvent.status, ParcelEvent.occurred_at)
        .join(Parcel, Parcel.id == ParcelEvent.parcel_id)
        .where(Parcel.warehouse_id == warehouse.id, ParcelEvent.occurred_at < end)
        .order_by(ParcelEvent.occurred_at, ParcelEvent.id)
    ).all()

    last_status: dict[int, str] = {}
    inside = 0
    index = 0
    points = []
    for day in _days(params.from_date, params.to_date):
        day_end = datetime.combine(day + timedelta(days=1), time.min)
        while index < len(events) and events[index].occurred_at < day_end:
            parcel_id, new_status, _ = events[index]
            was_inside = last_status.get(parcel_id) in IN_WAREHOUSE_STATUSES
            inside += (new_status in IN_WAREHOUSE_STATUSES) - was_inside
            last_status[parcel_id] = new_status
            index += 1
        points.append(UtilizationPoint(
            day=day, parcel_count=inside, utilization_percent=_percent(inside, warehouse.capacity)
        ))

    return WarehouseUtilizationHistory(
        warehouse_id=warehouse.id,
        name=warehouse.name,
        capacity=warehouse.capacity,
        from_date=params.from_date,
        to_date=params.to_date,
        avg_utilization_percent=_mean([p.utilization_percent for p in points]),
        peak_parcel_count=max(p.parcel_count for p in points),
        points=points,
    )


def _daily_counts(days: list[date], counts: dict[date, list[int]]) -> list[DailyCount]:
    return [
        DailyCount(day=day, pickups=counts[day][0], deliveries=counts[day][1], failed=counts[day][2])
        for day in days
    ]


def courier_stats(db: Session, params: StatsRangeParams) -> CourierStatsReport:
    start, end = _range_bounds(params)
    days = _days(params.from_date, params.to_date)
    in_range = and_(
        ParcelEvent.occurred_at >= start,
        ParcelEvent.occurred_at < end,
        # Courier's own actions only, admin swaps are excluded
        ParcelEvent.actor_id == ParcelEvent.courier_id,
    )

    # courier_id → day → [pickups, deliveries, failed]
    per_courier: dict[int, dict[date, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    totals: dict[date, list[int]] = defaultdict(lambda: [0, 0, 0])
    column = {ParcelStatus.PICKED_UP: 0, ParcelStatus.DELIVERED: 1, ParcelStatus.FAILED: 2}
    for courier_id, event_status, occurred_at in db.execute(
        select(ParcelEvent.courier_id, ParcelEvent.status, ParcelEvent.occurred_at)
        .where(in_range, ParcelEvent.status.in_(COURIER_STATUSES))
    ):
        col = column[ParcelStatus(event_status)]
        per_courier[courier_id][occurred_at.date()][col] += 1
        totals[occurred_at.date()][col] += 1

    # Delivery times of parcels delivered in the range, from the final milestones
    delivery_minutes: dict[int, list[float]] = defaultdict(list)
    lead_hours: dict[int, list[float]] = defaultdict(list)
    for courier_id, picked_up_at, out_at, delivered_at in db.execute(
        select(ParcelEvent.courier_id, Parcel.picked_up_at, Parcel.out_for_delivery_at, Parcel.delivered_at)
        .join(Parcel, Parcel.id == ParcelEvent.parcel_id)
        .where(in_range, ParcelEvent.status == ParcelStatus.DELIVERED)
    ):
        if delivered_at is None:
            continue
        if out_at is not None:
            delivery_minutes[courier_id].append((delivered_at - out_at).total_seconds() / 60)
        if picked_up_at is not None:
            lead_hours[courier_id].append((delivered_at - picked_up_at).total_seconds() / 3600)

    # Active couriers, plus anyone with courier events in the range
    couriers = db.scalars(
        select(User)
        .where(or_(
            and_(User.role == UserRole.COURIER, User.is_active.is_(True)),
            User.id.in_(list(per_courier)),
        ))
        .order_by(User.last_name, User.first_name, User.id)
    ).all()

    courier_rows = []
    for courier in couriers:
        counts = per_courier.get(courier.id, {})
        pickups = sum(c[0] for c in counts.values())
        deliveries = sum(c[1] for c in counts.values())
        failed = sum(c[2] for c in counts.values())
        active_days = sum(1 for c in counts.values() if any(c))
        courier_rows.append(CourierStats(
            courier=UserSummary.model_validate(courier),
            pickups_count=pickups,
            deliveries_count=deliveries,
            failed_count=failed,
            active_days=active_days,
            avg_deliveries_per_day=round(deliveries / active_days, 1) if active_days else 0.0,
            avg_delivery_minutes=_mean(delivery_minutes.get(courier.id, [])),
            avg_lead_time_hours=_mean(lead_hours.get(courier.id, [])),
            daily=_daily_counts(days, defaultdict(lambda: [0, 0, 0], counts)),
        ))

    return CourierStatsReport(
        from_date=params.from_date,
        to_date=params.to_date,
        avg_delivery_minutes=_mean([m for values in delivery_minutes.values() for m in values]),
        avg_lead_time_hours=_mean([h for values in lead_hours.values() for h in values]),
        daily_totals=_daily_counts(days, totals),
        couriers=courier_rows,
    )
