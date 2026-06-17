from pydantic import EmailStr
from sqlmodel import SQLModel


class RegisterRequest(SQLModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    tenant_slug: str


class LoginRequest(SQLModel):
    email: EmailStr
    password: str


class InviteRequest(SQLModel):
    email: EmailStr
    role: str = "tenant_member"


class AcceptInviteRequest(SQLModel):
    full_name: str | None = None
    password: str


class UserResponse(SQLModel):
    id: int
    email: str
    full_name: str | None
    role: str
    tenant_id: int | None
    is_active: bool
