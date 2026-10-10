from enum import Enum
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.src.database import Base

if TYPE_CHECKING:
    from server.models.contact import Contact
    from server.models.parcel import Parcel

class UserRole(str, Enum):
    CUSTOMER = "customer"
    COURIER = "courier"
    LOGISTICIAN = "logistician"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    street: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    house_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[UserRole] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)


    contacts: Mapped[List["Contact"]] = relationship(back_populates="user")
    pickup_parcels: Mapped[List["Parcel"]] = relationship(
        back_populates="pickup_courier", foreign_keys="Parcel.pickup_courier_id"
    )
    delivery_parcels: Mapped[List["Parcel"]] = relationship(
        back_populates="delivery_courier", foreign_keys="Parcel.delivery_courier_id"
    )

    __table_args__ = (
        # Egyedi index kisbetűs emailre, csak aktív felhasználókra
        Index(
            "uq_users_email",
            func.lower(email),
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
        ),
    )