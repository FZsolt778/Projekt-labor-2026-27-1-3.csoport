from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.src.database import Base

if TYPE_CHECKING:
    from server.models.parcel import Parcel

class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    parcels: Mapped[List["Parcel"]] = relationship(back_populates="warehouse")

    __table_args__ = (
        CheckConstraint("capacity > 0", name="chk_warehouses_capacity"),
    )