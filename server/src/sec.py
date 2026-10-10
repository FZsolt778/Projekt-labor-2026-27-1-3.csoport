from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy.orm import Session
from server.src.config import settings
from server.src.database import get_db
from server.models import User, UserRole
from werkzeug.security import check_password_hash,generate_password_hash
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

def hash_pass(password: str) -> str:
    return generate_password_hash(password)

def verify_pass(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash,password)

def create_access_token(sub: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub" : str(sub),
        "role" : role,
        "iat" : now,
        "exp" : now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, 
                      settings.JWT_SECRET.get_secret_value(), 
                      algorithm=settings.JWT_ALGORITHM)

# If the token is fake or expired, Error send out 
def decode_access_token(token: str) -> dict:
    return jwt.decode(token, 
                      settings.JWT_SECRET.get_secret_value(), 
                      algorithms=[settings.JWT_ALGORITHM],
                      options={"require" : ["sub","iat","exp"]})

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

#reuse 
def _get_user_from_token(token: str, db: Session) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Érvénytelen vagy lejárt token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.InvalidAlgorithmError, ValueError):
        raise credentials_error
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def get_current_user(token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> User:
    return _get_user_from_token(token,db)

def get_optional_user(token: str | None = Depends(oauth2_optional),
                      db: Session = Depends(get_db)) -> User | None:
    if token is None: 
        return None
    return _get_user_from_token(token, db)

def role_req(*roles: UserRole):
    def chechk(user: User=Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Nincs jogosultságod ehhez a művelethez")
        return user
    return chechk