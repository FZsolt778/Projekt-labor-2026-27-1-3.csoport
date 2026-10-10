from datetime import date, time, datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String, ForeignKey, Date, Time, DateTime, 
    CheckConstraint, Index, func, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.src.database import Base

if TYPE_CHECKING:
    from server.models.contact import Contact
    from server.models.warehouse import Warehouse
    from server.models.user import User
    from server.models.parcel_event import ParcelEvent

class ParcelSize(str, Enum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"

class ParcelStatus(str, Enum):
    BOOKED = "booked"
    PICKUP_ASSIGNED = "pickup_assigned"
    PICKED_UP = "picked_up"
    IN_WAREHOUSE = "in_warehouse"
    DELIVERY_ASSIGNED = "delivery_assigned"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tracking_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    size: Mapped[ParcelSize] = mapped_column(String(2), nullable=False)
    status: Mapped[ParcelStatus] = mapped_column(
        String(30), default=ParcelStatus.BOOKED, server_default=text("'booked'"), nullable=False, index=True
    )

    # 1:1 kapcsolatok a contact snapshotokkal
    sender_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), unique=True, nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), unique=True, nullable=False)

    warehouse_id: Mapped[Optional[int]] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    pickup_courier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    delivery_courier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Tervezett felvétel
    pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    pickup_window_start: Mapped[time] = mapped_column(Time, nullable=False)
    pickup_window_end: Mapped[time] = mapped_column(Time, nullable=False)

    # Tervezett kiszállítás
    delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    delivery_window_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    delivery_window_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    # Mérföldkövek
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=func.now(), server_default=func.now(), nullable=False
    )
    picked_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    warehouse_arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    out_for_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    # Relációk
    sender: Mapped["Contact"] = relationship(back_populates="sent_parcel", foreign_keys=[sender_id])
    recipient: Mapped["Contact"] = relationship(back_populates="received_parcel", foreign_keys=[recipient_id])
    warehouse: Mapped[Optional["Warehouse"]] = relationship(back_populates="parcels")
    pickup_courier: Mapped[Optional["User"]] = relationship(
        back_populates="pickup_parcels", foreign_keys=[pickup_courier_id]
    )
    delivery_courier: Mapped[Optional["User"]] = relationship(
        back_populates="delivery_parcels", foreign_keys=[delivery_courier_id]
    )
    # Állapotnapló, rögzítési sorrendben
    events: Mapped[List["ParcelEvent"]] = relationship(
        back_populates="parcel", cascade="all, delete-orphan", passive_deletes=True,
        order_by="ParcelEvent.id"
    )

    __table_args__ = (
        CheckConstraint("sender_id <> recipient_id", name="chk_parcels_sender_recipient_diff"),
        CheckConstraint("pickup_window_start < pickup_window_end", name="chk_parcels_pickup_window"),
        CheckConstraint(
            "(delivery_date IS NULL AND delivery_window_start IS NULL AND delivery_window_end IS NULL) OR "
            "(delivery_date IS NOT NULL AND delivery_window_start IS NOT NULL AND delivery_window_end IS NOT NULL "
            "AND delivery_window_start < delivery_window_end)",
            name="chk_parcels_delivery_window"
        ),
        CheckConstraint("delivery_date IS NULL OR delivery_date >= pickup_date", name="chk_parcels_delivery_after_pickup"),
        CheckConstraint("delivery_courier_id IS NULL OR delivery_date IS NOT NULL", name="chk_parcels_delivery_courier_assigned"),
        CheckConstraint("picked_up_at IS NULL OR picked_up_at >= created_at", name="chk_parcels_picked_up_order"),
        CheckConstraint(
            "warehouse_arrived_at IS NULL OR (picked_up_at IS NOT NULL AND warehouse_arrived_at >= picked_up_at)",
            name="chk_parcels_warehouse_order"
        ),
        CheckConstraint(
            "out_for_delivery_at IS NULL OR (warehouse_arrived_at IS NOT NULL AND out_for_delivery_at >= warehouse_arrived_at)",
            name="chk_parcels_out_delivery_order"
        ),
        CheckConstraint(
            "delivered_at IS NULL OR (out_for_delivery_at IS NOT NULL AND delivered_at >= out_for_delivery_at)",
            name="chk_parcels_delivered_order"
        ),
        # Speciális indexek futár statisztikákhoz
        Index("idx_parcels_pickup_courier", pickup_courier_id, picked_up_at),
        Index("idx_parcels_delivery_courier", delivery_courier_id, delivered_at),
    )