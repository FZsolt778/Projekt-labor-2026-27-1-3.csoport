from typing import Annotated, Literal
from pydantic import BaseModel, StringConstraints, model_validator
from server.models import UserRole
from server.API.common import RequestModel, PasswordStr
from server.API.user.schemas import UserCreateBase

# Login uses OAuth2PasswordRequestForm (username = email), no schema needed.


class RegisterRequest(UserCreateBase):
    """Self-registration (role: customer)"""


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    # Seconds
    expires_in: int
    role: UserRole
    user_id: int


class PasswordChangeRequest(RequestModel):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    new_password: PasswordStr

    @model_validator(mode="after")
    def _different(self):
        if self.current_password == self.new_password:
            raise ValueError("Az új jelszó nem egyezhet meg a régivel")
        return self
