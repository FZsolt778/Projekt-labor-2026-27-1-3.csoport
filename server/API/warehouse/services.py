from datetime import date
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from server.models import Parcel, ParcelStatus, User, UserRole, Warehouse
from server.API.parcel.services import add_event
from server.API.user.services import get_courier_or_404
from server.API.warehouse.schemas import CheckInRequest, DeliveryAssignRequest, PickupAssignRequest, WarehouseUpdate

# Bulk ops: validate every parcel first, then modify (all or nothing):
# missing id → 404, wrong status → 409

# Physically in the warehouse (also used by stat)
IN_WAREHOUSE_STATUSES = frozenset({ParcelStatus.IN_WAREHOUSE, ParcelStatus.DELIVERY_ASSIGNED})


def _load_parcels(db: Session, parcel_ids: list[int]) -> list[Parcel]:
    # Locked rows in request order, missing id → 404
    parcels = db.scalars(select(Parcel).where(Parcel.id.in_(parcel_ids)).with_for_update()).all()
    by_id = {parcel.id: parcel for parcel in parcels}
    missing = [parcel_id for parcel_id in parcel_ids if parcel_id not in by_id]
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Nem található csomag: {', '.join(map(str, missing))}",
        )
    return [by_id[parcel_id] for parcel_id in parcel_ids]


def _require_statuses(parcels: list[Parcel], *allowed: ParcelStatus) -> None:
    # 409 listing every parcel not in allowed
    wrong = [parcel for parcel in parcels if parcel.status not in allowed]
    if wrong:
        details = ", ".join(f"{p.tracking_number} ({ParcelStatus(p.status).value})" for p in wrong)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ezek a csomagok jelenlegi állapotukban nem kezelhetők így: {details}",
        )


def get_warehouse(db: Session) -> Warehouse:
    # The single warehouse (lowest id)
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
    # Active couriers, the logistician picks from these
    return list(db.scalars(
        select(User)
        .where(User.role == UserRole.COURIER, User.is_active.is_(True))
        .order_by(User.last_name, User.first_name, User.id)
    ))


def check_in(db: Session, actor: User, data: CheckInRequest) -> list[Parcel]:
    parcels = _load_parcels(db, data.parcel_ids)
    _require_statuses(parcels, ParcelStatus.PICKED_UP, ParcelStatus.FAILED)

    warehouse = get_warehouse(db)
    # Lock serializes concurrent check-ins for the capacity check
    db.refresh(warehouse, with_for_update=True)
    current = count_in_warehouse(db, warehouse.id)
    if current + len(parcels) > warehouse.capacity:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Nincs elég hely a raktárban (szabad hely: {max(warehouse.capacity - current, 0)})",
        )

    for parcel in parcels:
        if parcel.status == ParcelStatus.PICKED_UP:
            courier_id = parcel.pickup_courier_id
        else:
            # Failed delivery, the courier brought it back
            courier_id = parcel.delivery_courier_id
            parcel.delivery_courier_id = None
        parcel.warehouse_id = warehouse.id
        add_event(db, parcel, ParcelStatus.IN_WAREHOUSE, actor=actor, courier_id=courier_id)
    db.commit()
    return parcels


def assign_pickup(db: Session, actor: User, data: PickupAssignRequest) -> list[Parcel]:
    courier = get_courier_or_404(db, data.courier_id)
    parcels = _load_parcels(db, data.parcel_ids)
    # Locked after pickup
    _require_statuses(parcels, ParcelStatus.BOOKED, ParcelStatus.PICKUP_ASSIGNED)

    for parcel in parcels:
        if parcel.status == ParcelStatus.PICKUP_ASSIGNED and parcel.pickup_courier_id == courier.id:
            continue
        parcel.pickup_courier_id = courier.id
        add_event(db, parcel, ParcelStatus.PICKUP_ASSIGNED, actor=actor, courier_id=courier.id)
    db.commit()
    return parcels


def assign_delivery(db: Session, actor: User, data: DeliveryAssignRequest) -> list[Parcel]:
    courier = get_courier_or_404(db, data.courier_id)
    parcels = _load_parcels(db, data.parcel_ids)
    # Locked after the courier started
    _require_statuses(parcels, ParcelStatus.IN_WAREHOUSE, ParcelStatus.DELIVERY_ASSIGNED)

    if data.delivery_date is not None:
        too_early = [p.tracking_number for p in parcels if data.delivery_date < p.pickup_date]
        if too_early:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"A kiszállítás napja nem lehet korábbi a felvételnél: {', '.join(too_early)}",
            )
    else:
        # Keep the requested delivery time, it must exist and not be in the past
        today = date.today()
        missing = [p.tracking_number for p in parcels if p.delivery_date is None or p.delivery_date < today]
        if missing:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Add meg a kiszállítás napját és idősávját ezeknél a csomagoknál: {', '.join(missing)}",
            )

    for parcel in parcels:
        new_window = None
        if data.delivery_date is not None:
            new_window = (data.delivery_date, data.delivery_slot.start, data.delivery_slot.end)
        current_window = (parcel.delivery_date, parcel.delivery_window_start, parcel.delivery_window_end)
        unchanged = (
            parcel.status == ParcelStatus.DELIVERY_ASSIGNED
            and parcel.delivery_courier_id == courier.id
            and new_window in (None, current_window)
        )
        if unchanged:
            continue
        if new_window is not None:
            parcel.delivery_date, parcel.delivery_window_start, parcel.delivery_window_end = new_window
        parcel.delivery_courier_id = courier.id
        add_event(db, parcel, ParcelStatus.DELIVERY_ASSIGNED, actor=actor, courier_id=courier.id)
    db.commit()
    return parcels
