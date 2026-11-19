from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from server.API.deps import DbSession, CurrentUser
from server.API.auth import services
from server.API.auth.schemas import PasswordChangeRequest, RegisterRequest, TokenResponse
from server.API.user.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


# New customer account (201 Created), the response logs it in at once
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: DbSession, background_tasks: BackgroundTasks):
    return services.register(db, data, background_tasks)


# Form data: username = email, password (also used by Swagger "Authorize")
@router.post("/login", response_model=TokenResponse)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    return services.login(db, form.username, form.password)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordChangeRequest, db: DbSession, user: CurrentUser, background_tasks: BackgroundTasks):
    services.change_password(db, user, data, background_tasks)
