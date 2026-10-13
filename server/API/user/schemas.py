from typing import Annotated
from pydantic import BaseModel, StringConstraints, model_validator
from server.models import UserRole
from server.API.common import (
    ORMModel, RequestModel, PatchModel, PageParams,
    NameStr, EmailAddress, PhoneStr, PasswordStr,
    PostalCode, CityStr, StreetStr, HouseNumberStr,
)

ADDRESS_FIELDS = ("postal_code", "city", "street", "house_number")


def check_address_fields(model: BaseModel) -> None:
    #Address fields go together: all set or all null
    sent = [name for name in ADDRESS_FIELDS if name in model.model_fields_set]
    if not sent:
        return
    if len(sent) != len(ADDRESS_FIELDS):
        raise ValueError("A cím mezőit (postal_code, city, street, house_number) együtt kell megadni")
    values = [getattr(model, name) for name in ADDRESS_FIELDS]
    if any(v is None for v in values) and any(v is not None for v in values):
        raise ValueError("A cím mezői vagy mind kitöltöttek, vagy mind üresek")


# --- Requests ----------------------------------------------------

class UserCreateBase(RequestModel):
    #Shared user creation fields (registration, admin)
    last_name: NameStr
    first_name: NameStr
    email: EmailAddress
    password: PasswordStr
    phone: PhoneStr | None = None
    postal_code: PostalCode | None = None
    city: CityStr | None = None
    street: StreetStr | None = None
    house_number: HouseNumberStr | None = None

    @model_validator(mode="after")
    def _address_complete(self):
        check_address_fields(self)
        return self


class AdminUserCreate(UserCreateBase):
    #Admin creates a user, e.g. courier or logistician
    role: UserRole


class UserUpdateMe(PatchModel):
    #Own profile edit
    nullable_fields = frozenset({"phone", *ADDRESS_FIELDS})

    last_name: NameStr | None = None
    first_name: NameStr | None = None
    email: EmailAddress | None = None
    phone: PhoneStr | None = None
    postal_code: PostalCode | None = None
    city: CityStr | None = None
    street: StreetStr | None = None
    house_number: HouseNumberStr | None = None

    @model_validator(mode="after")
    def _address_complete(self):
        check_address_fields(self)
        return self


class AdminUserUpdate(UserUpdateMe):
    #Admin edit of any user (is_active=false: delete)
    role: UserRole | None = None
    is_active: bool | None = None
    password: PasswordStr | None = None


class UserListParams(PageParams):
    #User filters (admin)
    role: UserRole | None = None
    is_active: bool | None = None
    # Name or email fragment
    search: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None


# --- Responses ---------------------------------------------------

class UserRead(ORMModel):
    id: int
    last_name: str
    first_name: str
    email: str
    phone: str | None
    postal_code: str | None
    city: str | None
    street: str | None
    house_number: str | None
    role: UserRole
    is_active: bool


class UserSummary(ORMModel):
    #Short user info, internal views (admin, logistician)
    id: int
    last_name: str
    first_name: str
    phone: str | None
    role: UserRole


class CourierPublic(ORMModel):
    #Courier for customers: name only
    last_name: str
    first_name: str
