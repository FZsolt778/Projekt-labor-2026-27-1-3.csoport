from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from server.models import User, UserRole


# --- Shared helpers (used by other modules) ----------------------

def get_active_user_by_email(db: Session, email: str) -> User | None:
    # Case-insensitive, matches the uq_users_email index
    return db.scalar(
        select(User).where(func.lower(User.email) == email.lower(), User.is_active.is_(True))
    )


def get_courier_or_404(db: Session, courier_id: int) -> User:
    # Active courier, else 404
    user = db.get(User, courier_id)
    if user is None or not user.is_active or user.role != UserRole.COURIER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A futár nem található")
    return user
