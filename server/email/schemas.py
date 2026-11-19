from dataclasses import dataclass
from datetime import date, time
from server.models import Contact, Parcel, ParcelSize, ParcelStatus, User


def _format_window(day: date | None, start: time | None, end: time | None) -> str | None:
    if day is None or start is None or end is None:
        return None
    return f"{day.isoformat()} {start.strftime('%H:%M')}–{end.strftime('%H:%M')}"


@dataclass(frozen=True, slots=True)
class ContactSnapshot:
    "Session-independent contact info extracted for background email rendering."

    full_name: str
    email: str
    phone: str | None
    address_line: str

    @classmethod
    def from_contact(cls, contact: Contact) -> "ContactSnapshot":
        return cls(
            full_name=f"{contact.last_name} {contact.first_name}",
            email=contact.email,
            phone=contact.phone,
            address_line=f"{contact.postal_code} {contact.city}, {contact.street} {contact.house_number}",
        )


@dataclass(frozen=True, slots=True)
class ParcelEmailSnapshot:
    "Session-independent parcel state extracted right after db.commit()."

    tracking_number: str
    size: str
    status: str
    sender: ContactSnapshot
    recipient: ContactSnapshot
    pickup_window: str
    delivery_window: str | None

    @classmethod
    def from_parcel(cls, parcel: Parcel) -> "ParcelEmailSnapshot":
        return cls(
            tracking_number=parcel.tracking_number,
            size=ParcelSize(parcel.size).value,
            status=ParcelStatus(parcel.status).value,
            sender=ContactSnapshot.from_contact(parcel.sender),
            recipient=ContactSnapshot.from_contact(parcel.recipient),
            pickup_window=_format_window(
                parcel.pickup_date, parcel.pickup_window_start, parcel.pickup_window_end
            ) or "",
            delivery_window=_format_window(
                parcel.delivery_date, parcel.delivery_window_start, parcel.delivery_window_end
            ),
        )


@dataclass(frozen=True, slots=True)
class UserEmailSnapshot:
    "Session-independent user info extracted right after db.commit()."

    email: str
    full_name: str

    @classmethod
    def from_user(cls, user: User) -> "UserEmailSnapshot":
        return cls(
            email=user.email,
            full_name=f"{user.last_name} {user.first_name}",
        )
