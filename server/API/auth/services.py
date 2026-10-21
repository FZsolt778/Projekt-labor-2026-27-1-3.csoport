from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import User, UserRole
from server.API.auth.schemas import PasswordChangeRequest, RegisterRequest, TokenResponse

from server.src.config import settings
from server.src.sec import hash_pass, verify_pass, create_access_token


def register(db: Session, data: RegisterRequest) -> User:
    existing_user = db.scalar(
        select(User).where(User.email == data.email, User.is_active.is_(True))
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email cím már foglalt egy aktív felhasználónál!",
        )

    user_data = data.model_dump(exclude={"password"})
    new_user = User(
        **user_data,
        password_hash=hash_pass(data.password),
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def login(db: Session, email: str, password: str) -> TokenResponse:
    user = db.scalar(
        select(User).where(User.email == email, User.is_active.is_(True))
    )
    if not user or not verify_pass(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hibás email vagy jelszó",
        )

    access_token = create_access_token(user.id, user.role)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        role=user.role,
        user_id=user.id,
    )


def change_password(db: Session, user: User, data: PasswordChangeRequest) -> None:
    if not verify_pass(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hibás jelenlegi jelszó",
        )

    user.password_hash = hash_pass(data.new_password)
    db.commit()