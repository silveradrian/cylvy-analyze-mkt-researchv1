"""
Authentication and authorization system
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from loguru import logger

from app.core.config import settings
from app.core.database import db_pool
from app.models.user import User, UserRole
from app.core.exceptions import AuthenticationError, AuthorizationError


# Security setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


class AuthService:
    """Authentication service"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None):
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[User]:
        """Get user by email"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1 AND is_active = true",
                email
            )
            
            if row:
                return User(**dict(row))
            return None
    
    @staticmethod
    async def get_user_by_id(user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1 AND is_active = true",
                user_id
            )
            
            if row:
                return User(**dict(row))
            return None
    
    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = await AuthService.get_user_by_email(email)
        if not user:
            return None
        
        if not AuthService.verify_password(password, user.hashed_password):
            return None
        
        # Update last login
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login = $1 WHERE id = $2",
                datetime.utcnow(),
                user.id
            )
        
        return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user"""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token")
        
        # Get user from database
        user = await AuthService.get_user_by_id(UUID(user_id))
        if user is None:
            raise AuthenticationError("User not found")
        
        return user
        
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise AuthenticationError("Invalid token")
    except ValueError as e:
        logger.warning(f"Invalid user ID format: {e}")
        raise AuthenticationError("Invalid token format")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise AuthenticationError("Authentication failed")


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_role(required_roles: List[UserRole]):
    """Dependency to require specific user roles"""
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in required_roles:
            raise AuthorizationError(f"Required role: {required_roles}")
        return current_user
    
    return check_role


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise AuthorizationError("Admin role required")
    return current_user


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require superadmin role"""
    if current_user.role != UserRole.SUPERADMIN:
        raise AuthorizationError("Superadmin role required")
    return current_user
