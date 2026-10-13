from datetime import date, datetime, timedelta
from enum import Enum
from pydantic import BaseModel
from server.models import ParcelSize, ParcelStatus
from server.API.common import RequestModel, NoteStr
from server.API.contact.schemas import ContactRead
from server.API.parcel.schemas import ParcelRead


class CourierTaskType(str, Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"


class HistoryPeriod(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

    def bounds(self, day: date) -> tuple[date, date]:
        #First and last day of the period containing day (week: Mon-Sun)
        if self is HistoryPeriod.DAY:
            return day, day
        if self is HistoryPeriod.WEEK:
            start = day - timedelta(days=day.weekday())
            return start, start + timedelta(days=6)
        start = day.replace(day=1)
        next_month = (start + timedelta(days=32)).replace(day=1)
        return start, next_month - timedelta(days=1)


# --- Requests ----------------------------------------------------

class ParcelFailRequest(RequestModel):
    #Failed pickup / delivery
    note: NoteStr


# --- Query params ------------------------------------------------

class CourierTaskParams(BaseModel):
    #Current courier tasks
    task: CourierTaskType | None = None
    # Planned day (pickup_date or delivery_date)
    day: date | None = None


class CourierHistoryParams(BaseModel):
    period: HistoryPeriod = HistoryPeriod.DAY
    # Any day in the period (None: today)
    day: date | None = None


# --- Responses ---------------------------------------------------

class CourierTask(BaseModel):
    task: CourierTaskType
    parcel: ParcelRead


class CourierHistoryItem(BaseModel):
    #Completed pickup / delivery (picked_up, delivered or failed event)
    parcel_id: int
    tracking_number: str
    size: ParcelSize
    task: CourierTaskType
    status: ParcelStatus
    occurred_at: datetime
    note: str | None
    # Sender for pickups, recipient for deliveries
    contact: ContactRead


class CourierHistory(BaseModel):
    period: HistoryPeriod
    from_date: date
    to_date: date
    pickups_count: int
    deliveries_count: int
    failed_count: int
    items: list[CourierHistoryItem]
