from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class AdminAuthenticatedUser(BaseModel):
    id: int
    username: str
    role_name: str


class AdminLoginData(BaseModel):
    session_token: str
    expires_at_utc: str
    user: AdminAuthenticatedUser


class AdminLogoutData(BaseModel):
    revoked: bool = True


class AdminPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)
    confirm_new_password: str = Field(min_length=1, max_length=200)


class AdminPasswordChangeData(BaseModel):
    relogin_required: bool = True
    revoked_session_count: int = Field(ge=1)


class AdminSessionContext(BaseModel):
    session_id: int
    admin_user_id: int
    username: str
    role_name: str
    session_version: int
    expires_at_utc: str
