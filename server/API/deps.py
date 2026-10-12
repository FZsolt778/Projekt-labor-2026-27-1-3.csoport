from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from server.models import User, UserRole
from server.src.database import get_db
from server.src.sec import get_current_user, get_optional_user, role_req

# Route params, e.g. def f(db: DbSession, admin: AdminUser)
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
# None for guests (no token)
OptionalUser = Annotated[User | None, Depends(get_optional_user)]

CustomerUser = Annotated[User, Depends(role_req(UserRole.CUSTOMER))]
CourierUser = Annotated[User, Depends(role_req(UserRole.COURIER))]
AdminUser = Annotated[User, Depends(role_req(UserRole.ADMIN))]
# Logistician or admin
StaffUser = Annotated[User, Depends(role_req(UserRole.LOGISTICIAN, UserRole.ADMIN))]
