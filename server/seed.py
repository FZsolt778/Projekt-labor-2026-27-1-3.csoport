import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from getpass import getpass
from sqlalchemy import select
from sqlalchemy.orm import Session
from server.models import User, UserRole, Warehouse
from server.src.config import settings
from server.src.database import DBSession
from server.src.sec import hash_pass
from server.API.user.services import get_active_user_by_email

WAREHOUSE_NAME = "Központi raktár"
WAREHOUSE_CAPACITY = 500


def seed_warehouse(db: Session) -> None:
    if db.scalar(select(Warehouse.id).limit(1)) is not None:
        print("Raktár már létezik, kihagyva")
        return
    db.add(Warehouse(name=WAREHOUSE_NAME, capacity=WAREHOUSE_CAPACITY))
    print(f"Raktár létrehozva: {WAREHOUSE_NAME} ({WAREHOUSE_CAPACITY} csomag)")


def seed_admin(db: Session) -> None:
    has_admin = db.scalar(
        select(User.id).where(User.role == UserRole.ADMIN, User.is_active.is_(True)).limit(1)
    )
    if has_admin is not None:
        print("Aktív admin már létezik, kihagyva")
        return

    email = settings.ADMIN_EMAIL
    if not email:
        raise SystemExit("Hiányzik az ADMIN_EMAIL a .env fájlból")
    if get_active_user_by_email(db, email) is not None:
        raise SystemExit(f"A(z) {email} címmel már van aktív, nem admin felhasználó")

    password = settings.ADMIN_PASSWORD.get_secret_value() if settings.ADMIN_PASSWORD else ""
    if not password:
        password = getpass(f"Jelszó a(z) {email} adminhoz: ")
    if len(password) < 8:
        raise SystemExit("A jelszó legalább 8 karakter legyen")

    db.add(User(
        last_name="Admin",
        first_name="Rendszer",
        email=email,
        password_hash=hash_pass(password),
        role=UserRole.ADMIN,
    ))
    print(f"Admin létrehozva: {email}")


def main() -> None:
    with DBSession() as db:
        seed_warehouse(db)
        seed_admin(db)
        db.commit()


if __name__ == "__main__":
    main()
