"""
User models for authentication and authorization
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, EmailStr


class UserRole(str, Enum):
    """User roles"""
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.VIEWER
    is_active: bool = True


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update model"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class User(UserBase):
    """Complete user model"""
    id: UUID
    hashed_password: str
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserInDB(User):
    """User model as stored in database"""
    pass


class UserPublic(BaseModel):
    """Public user information (no sensitive data)"""
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
