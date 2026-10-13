from datetime import date, time, timedelta
from enum import Enum
from typing import Annotated, ClassVar, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")

# --- Base classes ------------------------------------------------

class ORMModel(BaseModel):
    # Response base, buildable from ORM objects
    model_config = ConfigDict(from_attributes=True)


class RequestModel(BaseModel):
    # Request body base, rejects unknown fields
    model_config = ConfigDict(extra="forbid")


class PatchModel(RequestModel):
    # PATCH base: only sent fields change (model_dump(exclude_unset=True)),
    # null allowed only for nullable_fields
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_null(self):
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in self.nullable_fields:
                raise ValueError(f"A(z) '{name}' mező nem lehet null")
        return self


# --- Pagination --------------------------------------------------

class PageParams(BaseModel):
    # Pagination query params
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class Page(BaseModel, Generic[T]):
    # Paginated list response
    items: list[T]
    total: int
    limit: int
    offset: int


def paginate(db: Session, stmt: Select, params: PageParams) -> dict:
    # Paginated query; the route's response_model (Page[...]) converts the ORM items.
    # stmt needs an order_by for stable pages.
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.scalars(stmt.limit(params.limit).offset(params.offset)).all()
    return {"items": items, "total": total, "limit": params.limit, "offset": params.offset}


# --- Shared field types (match DB column lengths) ----------------

NameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
EmailAddress = Annotated[EmailStr, StringConstraints(max_length=100)]
PhoneStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20, pattern=r"^\+?[0-9][0-9 /-]{5,18}$")]
PasswordStr = Annotated[str, StringConstraints(min_length=8, max_length=128)]
PostalCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[1-9][0-9]{3}$")]
CityStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
StreetStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
HouseNumberStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]

NoteStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


# --- Time slots --------------------------------------------------

class TimeSlot(str, Enum):
    # Fixed 2-hour pickup / delivery slots, stored as start and end time
    S08_10 = "08:00-10:00"
    S10_12 = "10:00-12:00"
    S12_14 = "12:00-14:00"
    S14_16 = "14:00-16:00"
    S16_18 = "16:00-18:00"
    S18_20 = "18:00-20:00"

    @property
    def start(self) -> time:
        return time.fromisoformat(self.value.split("-")[0])

    @property
    def end(self) -> time:
        return time.fromisoformat(self.value.split("-")[1])


def tomorrow() -> date:
    return date.today() + timedelta(days=1)
