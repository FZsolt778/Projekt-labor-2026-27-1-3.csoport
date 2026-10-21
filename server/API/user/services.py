from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from server.models import Parcel, ParcelStatus, User, UserRole
from server.API.user.schemas import AdminUserCreate, AdminUserUpdate, UserListParams, UserUpdateMe

from server.API.common import paginate
from server.src.sec import hash_pass

PICKUP_OPEN_STATUSES = frozenset({
    ParcelStatus.PICKUP_ASSIGNED,
    ParcelStatus.PICKED_UP,
})

DELIVERY_OPEN_STATUSES = frozenset({
    ParcelStatus.DELIVERY_ASSIGNED,
    ParcelStatus.OUT_FOR_DELIVERY,
    ParcelStatus.FAILED,
})


def _check_email_unique(db: Session, email: str, exclude_user_id: int | None = None) -> None:
    query = select(User).where(User.email == email, User.is_active.is_(True))
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    if db.scalar(query) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Az email cím már foglalt egy másik aktív felhasználónál",
        )


def has_open_parcels(db: Session, user_id: int) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(Parcel)
        .where(
            or_(
                (Parcel.pickup_courier_id == user_id) & Parcel.status.in_(PICKUP_OPEN_STATUSES),
                (Parcel.delivery_courier_id == user_id) & Parcel.status.in_(DELIVERY_OPEN_STATUSES),
            )
        )
    )
    return (count or 0) > 0


def update_me(db: Session, user: User, data: UserUpdateMe) -> User:
    changes = data.model_dump(exclude_unset=True)
    if "email" in changes and changes["email"] != user.email:
        _check_email_unique(db, changes["email"], exclude_user_id=user.id)

    for field, value in changes.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, params: UserListParams) -> dict:
    query = select(User)

    if params.role is not None:
        query = query.where(User.role == params.role)
    if params.is_active is not None:
        query = query.where(User.is_active.is_(params.is_active))
    if params.search:
        pattern = f"%{params.search}%"
        query = query.where(
            or_(
                User.last_name.ilike(pattern),
                User.first_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )

    query = query.order_by(User.last_name, User.first_name, User.id)
    return paginate(db, query, params)


def create_user(db: Session, data: AdminUserCreate) -> User:
    _check_email_unique(db, data.email)

    user_data = data.model_dump(exclude={"password"})
    new_user = User(
        **user_data,
        password_hash=hash_pass(data.password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Felhasználó nem található",
        )
    return user


def get_courier_or_404(db: Session, courier_id: int) -> User:
    """A warehouse/services.py által használt segédfüggvény aktív futár lekéréséhez."""
    courier = db.scalar(
        select(User).where(
            User.id == courier_id,
            User.role == UserRole.COURIER,
            User.is_active.is_(True),
        )
    )
    if courier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Futár nem található",
        )
    return courier


def admin_update_user(db: Session, admin: User, user_id: int, data: AdminUserUpdate) -> User:
    user = get_user_or_404(db, user_id)
    changes = data.model_dump(exclude_unset=True)

    target_email = changes.get("email", user.email)
    email_changed = "email" in changes and changes["email"] != user.email
    reactivating = changes.get("is_active") is True and not user.is_active

    if email_changed or reactivating:
        _check_email_unique(db, target_email, exclude_user_id=user.id)

    if admin.id == user.id:
        if "role" in changes and changes["role"] != user.role:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Az adminisztrátor a saját szerepkörét nem módosíthatja",
            )
        if changes.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Az adminisztrátor saját magát nem inaktiválhatja",
            )

    if user.role == UserRole.COURIER:
        deactivating = changes.get("is_active") is False
        changing_role = "role" in changes and changes["role"] != UserRole.COURIER
        if (deactivating or changing_role) and has_open_parcels(db, user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A futárnak folyamatban lévő csomagjai vannak, előbb át kell rendelni őket",
            )

    if "password" in changes:
        user.password_hash = hash_pass(changes.pop("password"))

    for field, value in changes.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, admin: User, user_id: int) -> None:
    user = get_user_or_404(db, user_id)

    if admin.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Az adminisztrátor saját magát nem törölheti",
        )

    if user.role == UserRole.COURIER and has_open_parcels(db, user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A futárnak folyamatban lévő csomagjai vannak, nem inaktiválható",
        )

    user.is_active = False
    db.commit()
