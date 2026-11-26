from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from server.models import Parcel, ParcelStatus, User, UserRole, Warehouse
from server.API.parcel.services import add_event
from server.API.user.services import get_courier_or_404
from server.API.warehouse.schemas import CheckInRequest, DeliveryAssignRequest, PickupAssignRequest, WarehouseUpdate
from server.email.notifications import (
    notify_delivery_assigned,
    notify_parcel_in_warehouse,
    notify_parcel_schedule_updated,
    notify_pickup_assigned,
)

IN_WAREHOUSE_STATUSES = frozenset({ParcelStatus.IN_WAREHOUSE, ParcelStatus.DELIVERY_ASSIGNED})


def _load_parcels(db: Session, tracking_numbers: list[str]) -> list[Parcel]:
    parcels = db.scalars(
        select(Parcel).where(Parcel.tracking_number.in_(tracking_numbers)).with_for_update()
    ).all()
    by_number = {parcel.tracking_number: parcel for parcel in parcels}
    missing = [number for number in tracking_numbers if number not in by_number]
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Nem található csomag: {', '.join(missing)}",
        )
    return [by_number[number] for number in tracking_numbers]


def _require_statuses(parcels: list[Parcel], *allowed: ParcelStatus) -> None:
    wrong = [parcel for parcel in parcels if parcel.status not in allowed]
    if wrong:
        details = ", ".join(f"{p.tracking_number} ({ParcelStatus(p.status).label})" for p in wrong)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ezek a csomagok jelenlegi állapotukban nem kezelhetők így: {details}",
        )


def get_warehouse(db: Session) -> Warehouse:
    warehouse = db.scalar(select(Warehouse).order_by(Warehouse.id).limit(1))
    if warehouse is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Nincs raktár, futtasd a seed szkriptet")
    return warehouse


def count_in_warehouse(db: Session, warehouse_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Parcel)
        .where(Parcel.warehouse_id == warehouse_id, Parcel.status.in_(IN_WAREHOUSE_STATUSES))
    )


def update_warehouse(db: Session, data: WarehouseUpdate) -> Warehouse:
    warehouse = get_warehouse(db)
    changes = data.model_dump(exclude_unset=True)
    if "capacity" in changes:
        current = count_in_warehouse(db, warehouse.id)
        if changes["capacity"] < current:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"A kapacitás nem lehet kisebb a raktárban lévő csomagok számánál ({current})",
            )
    for field, value in changes.items():
        setattr(warehouse, field, value)
    db.commit()
    return warehouse


def list_couriers(db: Session) -> list[User]:
    return list(db.scalars(
        select(User)
        .where(User.role == UserRole.COURIER, User.is_active.is_(True))
        .order_by(User.last_name, User.first_name, User.id)
    ))


def check_in(
    db: Session,
    actor: User,
    data: CheckInRequest,
    background_tasks: BackgroundTasks | None = None,
) -> list[Parcel]:
    parcels = _load_parcels(db, data.tracking_numbers)
    _require_statuses(parcels, ParcelStatus.PICKED_UP, ParcelStatus.FAILED)

    warehouse = get_warehouse(db)
    db.refresh(warehouse, with_for_update=True)
    current = count_in_warehouse(db, warehouse.id)
    if current + len(parcels) > warehouse.capacity:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Nincs elég hely a raktárban (szabad hely: {max(warehouse.capacity - current, 0)})",
        )

    failed_ids = {p.id for p in parcels if p.status == ParcelStatus.FAILED}
    for parcel in parcels:
        if parcel.status == ParcelStatus.PICKED_UP:
            courier_id = parcel.pickup_courier_id
        else:
            courier_id = parcel.delivery_courier_id
            parcel.delivery_courier_id = None
        parcel.warehouse_id = warehouse.id
        add_event(db, parcel, ParcelStatus.IN_WAREHOUSE, actor=actor, courier_id=courier_id)
    db.commit()
    for parcel in parcels:
        notify_parcel_in_warehouse(
            background_tasks, parcel, returned_after_failure=(parcel.id in failed_ids)
        )
    return parcels


def assign_pickup(
    db: Session,
    actor: User,
    data: PickupAssignRequest,
    background_tasks: BackgroundTasks | None = None,
) -> list[Parcel]:
    courier = get_courier_or_404(db, data.courier_id)
    parcels = _load_parcels(db, data.tracking_numbers)
    _require_statuses(parcels, ParcelStatus.BOOKED, ParcelStatus.PICKUP_ASSIGNED)

    newly_assigned: list[Parcel] = []
    for parcel in parcels:
        if parcel.status == ParcelStatus.PICKUP_ASSIGNED and parcel.pickup_courier_id == courier.id:
            continue
        if parcel.status == ParcelStatus.BOOKED:
            newly_assigned.append(parcel)
        parcel.pickup_courier_id = courier.id
        add_event(db, parcel, ParcelStatus.PICKUP_ASSIGNED, actor=actor, courier_id=courier.id)
    db.commit()
    for parcel in newly_assigned:
        notify_pickup_assigned(background_tasks, parcel)
    return parcels


def assign_delivery(
    db: Session,
    actor: User,
    data: DeliveryAssignRequest,
    background_tasks: BackgroundTasks | None = None,
) -> list[Parcel]:
    courier = get_courier_or_404(db, data.courier_id)
    parcels = _load_parcels(db, data.tracking_numbers)
    _require_statuses(parcels, ParcelStatus.IN_WAREHOUSE, ParcelStatus.DELIVERY_ASSIGNED)

    too_early = [p.tracking_number for p in parcels if data.delivery_date < p.pickup_date]
    if too_early:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"A kiszállítás napja nem lehet korábbi a felvételnél: {', '.join(too_early)}",
        )

    new_window = (data.delivery_date, data.delivery_slot.start, data.delivery_slot.end)
    initial_assigned: list[Parcel] = []
    rescheduled: list[Parcel] = []
    for parcel in parcels:
        current_window = (parcel.delivery_date, parcel.delivery_window_start, parcel.delivery_window_end)
        unchanged = (
            parcel.status == ParcelStatus.DELIVERY_ASSIGNED
            and parcel.delivery_courier_id == courier.id
            and new_window == current_window
        )
        if unchanged:
            continue
        if parcel.status == ParcelStatus.IN_WAREHOUSE:
            initial_assigned.append(parcel)
        elif new_window != current_window:
            rescheduled.append(parcel)
        parcel.delivery_date, parcel.delivery_window_start, parcel.delivery_window_end = new_window
        parcel.delivery_courier_id = courier.id
        add_event(db, parcel, ParcelStatus.DELIVERY_ASSIGNED, actor=actor, courier_id=courier.id)
    db.commit()
    for parcel in initial_assigned:
        notify_delivery_assigned(background_tasks, parcel)
    for parcel in rescheduled:
        notify_parcel_schedule_updated(background_tasks, parcel, notify_sender=True, notify_recipient=True)
    return parcels
