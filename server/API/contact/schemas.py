from server.API.common import (
    ORMModel, RequestModel, PatchModel,
    NameStr, EmailAddress, PhoneStr,
    PostalCode, CityStr, StreetStr, HouseNumberStr,
)

# Contact = per-parcel sender/recipient snapshot, embedded in parcel schemas.


class ContactCreate(RequestModel):
    last_name: NameStr
    first_name: NameStr
    email: EmailAddress
    phone: PhoneStr | None = None
    postal_code: PostalCode
    city: CityStr
    street: StreetStr
    house_number: HouseNumberStr


class ContactUpdate(PatchModel):
    #Admin: any field
    nullable_fields = frozenset({"phone"})

    last_name: NameStr | None = None
    first_name: NameStr | None = None
    email: EmailAddress | None = None
    phone: PhoneStr | None = None
    postal_code: PostalCode | None = None
    city: CityStr | None = None
    street: StreetStr | None = None
    house_number: HouseNumberStr | None = None


class ContactInfoUpdate(PatchModel):
    #Customer: sender contact info
    nullable_fields = frozenset({"phone"})

    email: EmailAddress | None = None
    phone: PhoneStr | None = None


class AddressUpdate(RequestModel):
    #Customer: recipient address, always complete
    postal_code: PostalCode
    city: CityStr
    street: StreetStr
    house_number: HouseNumberStr


class ContactRead(ORMModel):
    last_name: str
    first_name: str
    email: str
    phone: str | None
    postal_code: str
    city: str
    street: str
    house_number: str
