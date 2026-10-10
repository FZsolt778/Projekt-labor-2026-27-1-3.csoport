from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from server.src.database import Base

if TYPE_CHECKING:
    from server.models.user import User
    from server.models.parcel import Parcel

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(4), nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    street: Mapped[str] = mapped_column(String(100), nullable=False)
    house_number: Mapped[str] = mapped_column(String(20), nullable=False)


    user: Mapped[Optional["User"]] = relationship(back_populates="contacts")
    sent_parcel: Mapped[Optional["Parcel"]] = relationship(
        back_populates="sender", foreign_keys="Parcel.sender_id", uselist=False
    )
    received_parcel: Mapped[Optional["Parcel"]] = relationship(
        back_populates="recipient", foreign_keys="Parcel.recipient_id", uselist=False
    )