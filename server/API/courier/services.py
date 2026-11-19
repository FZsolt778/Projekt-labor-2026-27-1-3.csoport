from datetime import date, datetime, time, timedelta
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload
from server.models import Parcel, ParcelEvent, ParcelStatus, User
from server.src.config import settings
from server.API.contact.schemas import ContactRead
from server.API.parcel.schemas import ParcelRead
from server.API.parcel.services import add_event, get_by_tracking_number, require_status
from server.email.notifications import (
    notify_delivery_failed,
    notify_parcel_auto_cancelled,
    notify_parcel_delivered,
    notify_parcel_out_for_delivery,
    notify_parcel_picked_up,
    notify_pickup_failed,
)
from server.API.courier.schemas import (
    CourierHistory, CourierHistoryItem, CourierHistoryParams, CourierTask, CourierTaskParams, CourierTaskType,
    ParcelFailRequest,
)

# Every action: parcel not assigned to this courier → 404, wrong status → 409
# Courier actions: actor = courier, courier_id = courier.id

# picked_up: still has to bring it to the warehouse
PICKUP_TASK_STATUSES = (ParcelStatus.PICKUP_ASSIGNED, ParcelStatus.PICKED_UP)
# failed: has to bring it back to the warehouse
DELIVERY_TASK_STATUSES = (ParcelStatus.DELIVERY_ASSIGNED, ParcelStatus.OUT_FOR_DELIVERY, ParcelStatus.FAILED)
HISTORY_STATUSES = (ParcelStatus.PICKED_UP, ParcelStatus.DELIVERED, ParcelStatus.FAILED)

_PARCEL_READ_OPTIONS = (
    selectinload(Parcel.sender),
    selectinload(Parcel.recipient),
    selectinload(Parcel.pickup_courier),
    selectinload(Parcel.delivery_courier),
)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "A csomag nem található")


def _assigned_parcel(db: Session, courier: User, tracking_number: str, task: CourierTaskType) -> Parcel:
    # Parcel assigned to this courier for the task, else 404
    parcel = get_by_tracking_number(db, tracking_number)
    assigned_id = parcel.pickup_courier_id if task is CourierTaskType.PICKUP else parcel.delivery_courier_id
    if assigned_id != courier.id:
        raise _not_found()
    return parcel


def list_tasks(db: Session, courier: User, params: CourierTaskParams) -> list[CourierTask]:
    tasks: list[tuple[tuple, CourierTask]] = []

    if params.task in (None, CourierTaskType.PICKUP):
        stmt = select(Parcel).where(
            Parcel.pickup_courier_id == courier.id, Parcel.status.in_(PICKUP_TASK_STATUSES)
        ).options(*_PARCEL_READ_OPTIONS)
        if params.day is not None:
            stmt = stmt.where(Parcel.pickup_date == params.day)
        for parcel in db.scalars(stmt):
            key = (parcel.pickup_date, parcel.pickup_window_start, 0, parcel.id)
            tasks.append((key, CourierTask(task=CourierTaskType.PICKUP, parcel=ParcelRead.model_validate(parcel))))

    if params.task in (None, CourierTaskType.DELIVERY):
        stmt = select(Parcel).where(
            Parcel.delivery_courier_id == courier.id, Parcel.status.in_(DELIVERY_TASK_STATUSES)
        ).options(*_PARCEL_READ_OPTIONS)
        if params.day is not None:
            stmt = stmt.where(Parcel.delivery_date == params.day)
        for parcel in db.scalars(stmt):
            key = (parcel.delivery_date or date.max, parcel.delivery_window_start or time.max, 1, parcel.id)
            tasks.append((key, CourierTask(task=CourierTaskType.DELIVERY, parcel=ParcelRead.model_validate(parcel))))

    # Planned day, then slot start
    tasks.sort(key=lambda item: item[0])
    return [task for _, task in tasks]


def pickup(
    db: Session,
    courier: User,
    tracking_number: str,
    background_tasks: BackgroundTasks | None = None,
) -> Parcel:
    parcel = _assigned_parcel(db, courier, tracking_number, CourierTaskType.PICKUP)
    require_status(parcel, ParcelStatus.PICKUP_ASSIGNED)
    add_event(db, parcel, ParcelStatus.PICKED_UP, actor=courier, courier_id=courier.id)
    db.commit()
    notify_parcel_picked_up(background_tasks, parcel)
    return parcel


def start_delivery(
    db: Session,
    courier: User,
    tracking_number: str,
    background_tasks: BackgroundTasks | None = None,
) -> Parcel:
    parcel = _assigned_parcel(db, courier, tracking_number, CourierTaskType.DELIVERY)
    require_status(parcel, ParcelStatus.DELIVERY_ASSIGNED)
    add_event(db, parcel, ParcelStatus.OUT_FOR_DELIVERY, actor=courier, courier_id=courier.id)
    db.commit()
    notify_parcel_out_for_delivery(background_tasks, parcel)
    return parcel


def deliver(
    db: Session,
    courier: User,
    tracking_number: str,
    background_tasks: BackgroundTasks | None = None,
) -> Parcel:
    parcel = _assigned_parcel(db, courier, tracking_number, CourierTaskType.DELIVERY)
    require_status(parcel, ParcelStatus.OUT_FOR_DELIVERY)
    add_event(db, parcel, ParcelStatus.DELIVERED, actor=courier, courier_id=courier.id)
    db.commit()
    notify_parcel_delivered(background_tasks, parcel)
    return parcel


def fail(
    db: Session,
    courier: User,
    tracking_number: str,
    data: ParcelFailRequest,
    background_tasks: BackgroundTasks | None = None,
) -> Parcel:
    parcel = get_by_tracking_number(db, tracking_number)
    is_pickup_courier = parcel.pickup_courier_id == courier.id
    is_delivery_courier = parcel.delivery_courier_id == courier.id
    if not (is_pickup_courier or is_delivery_courier):
        raise _not_found()
    require_status(parcel, ParcelStatus.PICKUP_ASSIGNED, ParcelStatus.OUT_FOR_DELIVERY)

    was_pickup = parcel.status == ParcelStatus.PICKUP_ASSIGNED
    failures = 0
    if was_pickup:
        # Failed pickup: cancelled right away, the sender can book again
        if not is_pickup_courier:
            raise _not_found()
        add_event(db, parcel, ParcelStatus.FAILED, actor=courier, courier_id=courier.id, note=data.note)
        add_event(db, parcel, ParcelStatus.CANCELLED, actor=courier, note="Sikertelen felvétel")
    else:
        if not is_delivery_courier:
            raise _not_found()
        add_event(db, parcel, ParcelStatus.FAILED, actor=courier, courier_id=courier.id, note=data.note)
        db.flush()
        # Courier-recorded failures only, admin swaps are excluded
        failures = db.scalar(
            select(func.count())
            .select_from(ParcelEvent)
            .where(
                ParcelEvent.parcel_id == parcel.id,
                ParcelEvent.status == ParcelStatus.FAILED,
                ParcelEvent.actor_id == ParcelEvent.courier_id,
            )
        )
        if failures >= settings.MAX_FAILED_DELIVERIES:
            add_event(db, parcel, ParcelStatus.CANCELLED, actor=courier, note=f"{failures} sikertelen kézbesítés")
    db.commit()
    if was_pickup:
        notify_pickup_failed(background_tasks, parcel, reason=data.note)
    elif failures >= settings.MAX_FAILED_DELIVERIES:
        notify_parcel_auto_cancelled(
            background_tasks, parcel, reason=data.note, max_attempts=settings.MAX_FAILED_DELIVERIES
        )
    else:
        notify_delivery_failed(
            background_tasks,
            parcel,
            reason=data.note,
            attempt=failures,
            max_attempts=settings.MAX_FAILED_DELIVERIES,
        )
    return parcel


def _history_task(event: ParcelEvent) -> CourierTaskType:
    if event.status == ParcelStatus.PICKED_UP:
        return CourierTaskType.PICKUP
    if event.status == ParcelStatus.DELIVERED:
        return CourierTaskType.DELIVERY
    # Failed: a pickup failure never got picked up
    return CourierTaskType.PICKUP if event.parcel.picked_up_at is None else CourierTaskType.DELIVERY


def get_history(db: Session, courier: User, params: CourierHistoryParams) -> CourierHistory:
    from_date, to_date = params.period.bounds(params.day or date.today())
    start = datetime.combine(from_date, time.min)
    end = datetime.combine(to_date + timedelta(days=1), time.min)

    # Courier's own events only, admin swaps are excluded
    events = db.scalars(
        select(ParcelEvent)
        .where(
            ParcelEvent.courier_id == courier.id,
            ParcelEvent.actor_id == courier.id,
            ParcelEvent.status.in_(HISTORY_STATUSES),
            ParcelEvent.occurred_at >= start,
            ParcelEvent.occurred_at < end,
        )
        .options(
            joinedload(ParcelEvent.parcel).joinedload(Parcel.sender),
            joinedload(ParcelEvent.parcel).joinedload(Parcel.recipient),
        )
        .order_by(ParcelEvent.occurred_at, ParcelEvent.id)
    ).all()

    items = []
    for event in events:
        parcel = event.parcel
        task = _history_task(event)
        contact = parcel.sender if task is CourierTaskType.PICKUP else parcel.recipient
        items.append(CourierHistoryItem(
            parcel_id=parcel.id,
            tracking_number=parcel.tracking_number,
            size=parcel.size,
            task=task,
            status=event.status,
            occurred_at=event.occurred_at,
            note=event.note,
            contact=ContactRead.model_validate(contact),
        ))

    return CourierHistory(
        period=params.period,
        from_date=from_date,
        to_date=to_date,
        pickups_count=sum(1 for e in events if e.status == ParcelStatus.PICKED_UP),
        deliveries_count=sum(1 for e in events if e.status == ParcelStatus.DELIVERED),
        failed_count=sum(1 for e in events if e.status == ParcelStatus.FAILED),
        items=items,
    )
