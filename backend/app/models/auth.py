"""
Authentication related Pydantic models
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    full_name: Optional[str] = None
    role: str = Field(default="client", pattern="^(client|admin|superadmin)$")
    client_id: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    """Model for creating a new user"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Model for updating a user"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    role: Optional[str] = Field(None, pattern="^(client|admin|superadmin)$")
    client_id: Optional[str] = None
    is_active: Optional[bool] = None


class User(UserBase):
    """User model returned by API"""
    id: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Data encoded in JWT token"""
    sub: str  # User ID
    email: str
    role: str
    client_id: Optional[str] = None
    exp: int