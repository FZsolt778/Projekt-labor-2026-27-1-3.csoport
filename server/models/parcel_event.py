from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, DateTime, CheckConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.src.database import Base
from server.models.parcel import ParcelStatus

if TYPE_CHECKING:
    from server.models.parcel import Parcel
    from server.models.user import User

class ParcelEvent(Base):
    __tablename__ = "parcel_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False)

    # A csomag státusza az esemény után (futárcserénél a státusz marad, csak a courier_id változik)
    status: Mapped[ParcelStatus] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=func.now(), server_default=func.now(), nullable=False
    )

    # Az érintett futár (felvétel / kiszállítás)
    courier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Ki rögzítette az eseményt (NULL: vendég foglalás)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Pl. a sikertelen kézbesítés oka
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relációk
    parcel: Mapped["Parcel"] = relationship(back_populates="events")
    courier: Mapped[Optional["User"]] = relationship(foreign_keys=[courier_id])
    actor: Mapped[Optional["User"]] = relationship(foreign_keys=[actor_id])

    __table_args__ = (
        # Futárhoz kötött státuszoknál kötelező a futár
        CheckConstraint(
            "status NOT IN ('pickup_assigned', 'picked_up', 'delivery_assigned', "
            "'out_for_delivery', 'delivered', 'failed') OR courier_id IS NOT NULL",
            name="chk_parcel_events_courier"
        ),
        # Csomag idővonala
        Index("idx_parcel_events_parcel", parcel_id, occurred_at),
        # Futár előzmények és statisztikák
        Index("idx_parcel_events_courier", courier_id, status, occurred_at),
    )
