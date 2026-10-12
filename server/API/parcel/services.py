import secrets
from datetime import date
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload
from server.models import Contact, Parcel, ParcelEvent, ParcelStatus, User
from server.API.common import TimeSlot, paginate
from server.API.contact.schemas import ContactCreate
from server.API.user.services import get_active_user_by_email, get_courier_or_404
from server.API.parcel.schemas import (
    AdminParcelUpdate, MyParcelsParams, ParcelCourierUpdate, ParcelCreate, ParcelDirection, ParcelListParams,
    ParcelScope, ParcelUpdate,
)

TRACKING_PREFIX = "FC"
# No ambiguous characters (0/O, 1/I)
TRACKING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# Closed, no further changes
FINAL_STATUSES = frozenset({ParcelStatus.DELIVERED, ParcelStatus.CANCELLED})
# Customer may edit / cancel in these
CUSTOMER_EDITABLE_STATUSES = frozenset({ParcelStatus.BOOKED, ParcelStatus.PICKUP_ASSIGNED})

# Milestone timestamps in process order
_MILESTONES = (
    (ParcelStatus.PICKED_UP, "picked_up_at"),
    (ParcelStatus.IN_WAREHOUSE, "warehouse_arrived_at"),
    (ParcelStatus.OUT_FOR_DELIVERY, "out_for_delivery_at"),
    (ParcelStatus.DELIVERED, "delivered_at"),
)

ADMIN_COURIER_NOTE = "Futár módosítva (admin)"

# Everything ParcelRead / ParcelAdminRead needs, avoids N+1 in lists
_LIST_OPTIONS = (
    selectinload(Parcel.sender),
    selectinload(Parcel.recipient),
    selectinload(Parcel.pickup_courier),
    selectinload(Parcel.delivery_courier),
)


# --- Shared helpers (used by other modules) ----------------------

def generate_tracking_number(db: Session) -> str:
    # Random, unguessable id, e.g. FC7K2M9QX4TB
    while True:
        tracking_number = TRACKING_PREFIX + "".join(secrets.choice(TRACKING_ALPHABET) for _ in range(10))
        if db.scalar(select(Parcel.id).where(Parcel.tracking_number == tracking_number)) is None:
            return tracking_number


def get_parcel_or_404(db: Session, parcel_id: int) -> Parcel:
    parcel = db.get(Parcel, parcel_id)
    if parcel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A csomag nem található")
    return parcel


def require_status(parcel: Parcel, *allowed: ParcelStatus) -> None:
    # 409 unless the status is one of allowed
    if parcel.status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A csomag jelenlegi állapotában ({ParcelStatus(parcel.status).value}) ez a művelet nem lehetséges",
        )


def add_event(
    db: Session,
    parcel: Parcel,
    new_status: ParcelStatus,
    *,
    actor: User | None,
    courier_id: int | None = None,
    note: str | None = None,
) -> ParcelEvent:
    # Status change + event log + milestone timestamp in one place. Does not commit.
    # - Courier-bound statuses (pickup_assigned, picked_up, delivery_assigned, out_for_delivery,
    #   delivered, failed) require courier_id (DB CHECK)
    # - Courier swap: call with the same status and the new courier_id (milestone unchanged).
    #   Then actor != courier, so stats can tell them apart: the courier's own action is actor_id == courier_id
    # - The milestone gets DB now(), same as the event's occurred_at. Later milestones are cleared
    #   (e.g. out_for_delivery_at on re-check-in), so retries still satisfy the parcels CHECKs
    if parcel.status != new_status:
        parcel.status = new_status
        for index, (milestone_status, attr) in enumerate(_MILESTONES):
            if milestone_status == new_status:
                setattr(parcel, attr, func.now())
                for _, later_attr in _MILESTONES[index + 1:]:
                    setattr(parcel, later_attr, None)
                break
    event = ParcelEvent(
        parcel=parcel,
        status=new_status,
        courier_id=courier_id,
        actor_id=actor.id if actor is not None else None,
        note=note,
    )
    db.add(event)
    return event


# --- Internal helpers --------------------------------------------

def _new_contact(data: ContactCreate, user_id: int | None) -> Contact:
    return Contact(user_id=user_id, **data.model_dump())


def _apply(target: object, changes: dict) -> None:
    for field, value in changes.items():
        setattr(target, field, value)


def _slot_window(slot: TimeSlot | None) -> tuple:
    return (slot.start, slot.end) if slot is not None else (None, None)


def _contains(term: str) -> str:
    # LIKE pattern with % and _ escaped (used with escape="\\")
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _get_own_parcel(db: Session, user: User, parcel_id: int) -> Parcel:
    # Sender or recipient, else 404
    parcel = db.get(Parcel, parcel_id)
    if parcel is None or user.id not in (parcel.sender.user_id, parcel.recipient.user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A csomag nem található")
    return parcel


def _get_editable_parcel(db: Session, user: User, parcel_id: int) -> Parcel:
    # Sender only, before pickup, until the day before the pickup date
    parcel = _get_own_parcel(db, user, parcel_id)
    if parcel.sender.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Csak a feladó módosíthatja a csomagot")
    require_status(parcel, *CUSTOMER_EDITABLE_STATUSES)
    if date.today() >= parcel.pickup_date:
        raise HTTPException(status.HTTP_409_CONFLICT, "A csomag legkésőbb a felvétel előtti napon módosítható")
    return parcel


# --- Public / customer -------------------------------------------

def create_parcel(db: Session, data: ParcelCreate, user: User | None) -> Parcel:
    recipient_user = get_active_user_by_email(db, data.recipient.email)
    pickup_start, pickup_end = _slot_window(data.pickup_slot)
    delivery_start, delivery_end = _slot_window(data.delivery_slot)
    parcel = Parcel(
        tracking_number=generate_tracking_number(db),
        size=data.size,
        sender=_new_contact(data.sender, user.id if user is not None else None),
        recipient=_new_contact(data.recipient, recipient_user.id if recipient_user is not None else None),
        pickup_date=data.pickup_date,
        pickup_window_start=pickup_start,
        pickup_window_end=pickup_end,
        delivery_date=data.delivery_date,
        delivery_window_start=delivery_start,
        delivery_window_end=delivery_end,
    )
    db.add(parcel)
    add_event(db, parcel, ParcelStatus.BOOKED, actor=user)
    db.commit()
    return parcel


def get_by_tracking_number(db: Session, tracking_number: str) -> Parcel:
    parcel = db.scalar(select(Parcel).where(Parcel.tracking_number == tracking_number.strip().upper()))
    if parcel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A csomag nem található")
    return parcel


def list_my_parcels(db: Session, user: User, params: MyParcelsParams) -> dict:
    own_contacts = select(Contact.id).where(Contact.user_id == user.id)
    sent = Parcel.sender_id.in_(own_contacts)
    received = Parcel.recipient_id.in_(own_contacts)
    if params.direction is ParcelDirection.SENT:
        condition = sent
    elif params.direction is ParcelDirection.RECEIVED:
        condition = received
    else:
        condition = or_(sent, received)

    stmt = select(Parcel).where(condition).options(*_LIST_OPTIONS)
    if params.scope is ParcelScope.ACTIVE:
        stmt = stmt.where(Parcel.status.not_in(FINAL_STATUSES))
    elif params.scope is ParcelScope.HISTORY:
        stmt = stmt.where(Parcel.status.in_(FINAL_STATUSES))
    return paginate(db, stmt.order_by(Parcel.created_at.desc(), Parcel.id.desc()), params)


def get_my_parcel(db: Session, user: User, parcel_id: int) -> Parcel:
    return _get_own_parcel(db, user, parcel_id)


def update_my_parcel(db: Session, user: User, parcel_id: int, data: ParcelUpdate) -> Parcel:
    parcel = _get_editable_parcel(db, user, parcel_id)

    old_pickup = (parcel.pickup_date, parcel.pickup_window_start, parcel.pickup_window_end)
    new_date = data.pickup_date or parcel.pickup_date
    new_start, new_end = (
        _slot_window(data.pickup_slot) if data.pickup_slot is not None
        else (parcel.pickup_window_start, parcel.pickup_window_end)
    )
    # The requested delivery must still come after the pickup
    if parcel.delivery_date is not None:
        if parcel.delivery_date < new_date or (
            parcel.delivery_date == new_date and parcel.delivery_window_start < new_end
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "A felvétel nem lehet a kért kiszállítás után",
            )

    if data.size is not None:
        parcel.size = data.size
    if data.sender is not None:
        _apply(parcel.sender, data.sender.model_dump(exclude_unset=True))
    if data.recipient_address is not None:
        _apply(parcel.recipient, data.recipient_address.model_dump())
    parcel.pickup_date, parcel.pickup_window_start, parcel.pickup_window_end = new_date, new_start, new_end

    # The assigned courier may not work on the new date, the logistician assigns again
    if (new_date, new_start, new_end) != old_pickup and parcel.pickup_courier_id is not None:
        parcel.pickup_courier_id = None
        add_event(db, parcel, ParcelStatus.BOOKED, actor=user, note="Felvételi időpont módosítva")
    db.commit()
    return parcel


def cancel_my_parcel(db: Session, user: User, parcel_id: int) -> Parcel:
    parcel = _get_editable_parcel(db, user, parcel_id)
    add_event(db, parcel, ParcelStatus.CANCELLED, actor=user)
    db.commit()
    return parcel


# --- Admin / logistician -----------------------------------------

def list_parcels(db: Session, params: ParcelListParams) -> dict:
    stmt = select(Parcel).options(*_LIST_OPTIONS)
    if params.status is not None:
        stmt = stmt.where(Parcel.status == params.status)
    if params.courier_id is not None:
        stmt = stmt.where(or_(
            Parcel.pickup_courier_id == params.courier_id, Parcel.delivery_courier_id == params.courier_id
        ))
    if params.pickup_date is not None:
        stmt = stmt.where(Parcel.pickup_date == params.pickup_date)
    if params.delivery_date is not None:
        stmt = stmt.where(Parcel.delivery_date == params.delivery_date)
    if params.search is not None:
        pattern = _contains(params.search)
        sender, recipient = aliased(Contact), aliased(Contact)
        names = [
            expr.ilike(pattern, escape="\\")
            for contact in (sender, recipient)
            for expr in (contact.last_name + " " + contact.first_name, contact.first_name + " " + contact.last_name)
        ]
        stmt = (
            stmt.join(sender, Parcel.sender_id == sender.id)
            .join(recipient, Parcel.recipient_id == recipient.id)
            .where(or_(Parcel.tracking_number.ilike(pattern, escape="\\"), *names))
        )
    return paginate(db, stmt.order_by(Parcel.created_at.desc(), Parcel.id.desc()), params)


def admin_update_parcel(db: Session, admin: User, parcel_id: int, data: AdminParcelUpdate) -> Parcel:
    # Any time, status unchanged, no event
    parcel = get_parcel_or_404(db, parcel_id)
    fields = data.model_fields_set

    new_pickup_date = data.pickup_date or parcel.pickup_date
    new_delivery_date = data.delivery_date if "delivery_date" in fields else parcel.delivery_date
    if "delivery_date" in fields and data.delivery_date is None and parcel.delivery_courier_id is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Kiszállító futár van hozzárendelve, a kiszállítás időpontja nem törölhető",
        )
    if new_delivery_date is not None and new_delivery_date < new_pickup_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A kiszállítás nem lehet korábban, mint a felvétel")

    if data.size is not None:
        parcel.size = data.size
    parcel.pickup_date = new_pickup_date
    if data.pickup_slot is not None:
        parcel.pickup_window_start, parcel.pickup_window_end = _slot_window(data.pickup_slot)
    if "delivery_date" in fields:
        parcel.delivery_date = data.delivery_date
        parcel.delivery_window_start, parcel.delivery_window_end = _slot_window(data.delivery_slot)
    if data.sender is not None:
        _apply(parcel.sender, data.sender.model_dump(exclude_unset=True))
    if data.recipient is not None:
        recipient_changes = data.recipient.model_dump(exclude_unset=True)
        _apply(parcel.recipient, recipient_changes)
        # New recipient email: link to the matching registered user, as at booking
        if "email" in recipient_changes:
            recipient_user = get_active_user_by_email(db, recipient_changes["email"])
            parcel.recipient.user_id = recipient_user.id if recipient_user is not None else None
    db.commit()
    return parcel


def _set_pickup_courier(db: Session, admin: User, parcel: Parcel, courier_id: int | None) -> None:
    current = ParcelStatus(parcel.status)
    if courier_id is None:
        require_status(parcel, ParcelStatus.PICKUP_ASSIGNED)
        parcel.pickup_courier_id = None
        add_event(db, parcel, ParcelStatus.BOOKED, actor=admin, note=ADMIN_COURIER_NOTE)
        return

    courier = get_courier_or_404(db, courier_id)
    require_status(parcel, ParcelStatus.BOOKED, ParcelStatus.PICKUP_ASSIGNED, ParcelStatus.PICKED_UP)
    if current is not ParcelStatus.BOOKED and parcel.pickup_courier_id == courier.id:
        return
    new_status = ParcelStatus.PICKUP_ASSIGNED if current is ParcelStatus.BOOKED else current
    parcel.pickup_courier_id = courier.id
    add_event(db, parcel, new_status, actor=admin, courier_id=courier.id, note=ADMIN_COURIER_NOTE)


def _set_delivery_courier(db: Session, admin: User, parcel: Parcel, courier_id: int | None) -> None:
    current = ParcelStatus(parcel.status)
    if courier_id is None:
        require_status(parcel, ParcelStatus.DELIVERY_ASSIGNED)
        parcel.delivery_courier_id = None
        # Back to in_warehouse, but this is not a new arrival: keep the arrival time
        arrived_at = parcel.warehouse_arrived_at
        add_event(db, parcel, ParcelStatus.IN_WAREHOUSE, actor=admin, note=ADMIN_COURIER_NOTE)
        parcel.warehouse_arrived_at = arrived_at
        return

    courier = get_courier_or_404(db, courier_id)
    require_status(
        parcel, ParcelStatus.IN_WAREHOUSE, ParcelStatus.DELIVERY_ASSIGNED,
        ParcelStatus.OUT_FOR_DELIVERY, ParcelStatus.FAILED,
    )
    if current is ParcelStatus.IN_WAREHOUSE and parcel.delivery_date is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Előbb add meg a kiszállítás napját és idősávját")
    if current is not ParcelStatus.IN_WAREHOUSE and parcel.delivery_courier_id == courier.id:
        return
    new_status = ParcelStatus.DELIVERY_ASSIGNED if current is ParcelStatus.IN_WAREHOUSE else current
    parcel.delivery_courier_id = courier.id
    add_event(db, parcel, new_status, actor=admin, courier_id=courier.id, note=ADMIN_COURIER_NOTE)


def admin_set_couriers(db: Session, admin: User, parcel_id: int, data: ParcelCourierUpdate) -> Parcel:
    # Any time (the logistician lock does not apply here), but not on closed parcels
    parcel = get_parcel_or_404(db, parcel_id)
    if parcel.status in FINAL_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Lezárt csomag futárai nem módosíthatók")
    if "pickup_courier_id" in data.model_fields_set:
        _set_pickup_courier(db, admin, parcel, data.pickup_courier_id)
    if "delivery_courier_id" in data.model_fields_set:
        _set_delivery_courier(db, admin, parcel, data.delivery_courier_id)
    db.commit()
    return parcel


def admin_cancel_parcel(db: Session, admin: User, parcel_id: int) -> Parcel:
    parcel = get_parcel_or_404(db, parcel_id)
    if parcel.status in FINAL_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "A csomag már lezárult")
    add_event(db, parcel, ParcelStatus.CANCELLED, actor=admin)
    db.commit()
    return parcel


def delete_parcel(db: Session, parcel_id: int) -> None:
    # Hard delete: events go by DB cascade, the two contacts are deleted after the parcel
    parcel = get_parcel_or_404(db, parcel_id)
    contacts = (parcel.sender, parcel.recipient)
    db.delete(parcel)
    db.flush()
    for contact in contacts:
        db.delete(contact)
    db.commit()
