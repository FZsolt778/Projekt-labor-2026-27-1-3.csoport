from typing import Annotated
from fastapi import APIRouter, Query, status
from server.API.common import Page
from server.API.deps import DbSession, CurrentUser, AdminUser
from server.API.user import services
from server.API.user.schemas import AdminUserCreate, AdminUserUpdate, UserListParams, UserRead, UserUpdateMe

router = APIRouter(prefix="/users", tags=["users"])


# --- Own profile -------------------------------------------------

@router.get("/me", response_model=UserRead)
def get_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserRead)
def update_me(data: UserUpdateMe, db: DbSession, user: CurrentUser):
    return services.update_me(db, user, data)


# --- Admin -------------------------------------------------------

@router.get("", response_model=Page[UserRead])
def list_users(params: Annotated[UserListParams, Query()], db: DbSession, admin: AdminUser):
    return services.list_users(db, params)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(data: AdminUserCreate, db: DbSession, admin: AdminUser):
    return services.create_user(db, data)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: DbSession, admin: AdminUser):
    return services.get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, data: AdminUserUpdate, db: DbSession, admin: AdminUser):
    return services.admin_update_user(db, admin, user_id, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DbSession, admin: AdminUser):
    services.deactivate_user(db, admin, user_id)
