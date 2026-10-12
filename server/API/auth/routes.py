from typing import Annotated
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from server.API.deps import DbSession, CurrentUser
from server.API.auth import services
from server.API.auth.schemas import PasswordChangeRequest, RegisterRequest, TokenResponse
from server.API.user.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: DbSession):
    return services.register(db, data)


# Form data: username = email, password (also used by Swagger "Authorize")
@router.post("/login", response_model=TokenResponse)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    return services.login(db, form.username, form.password)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordChangeRequest, db: DbSession, user: CurrentUser):
    services.change_password(db, user, data)
