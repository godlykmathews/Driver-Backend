from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db

# Standard library imports
import os
import hashlib
import logging

# Password hashing
# Use Argon2 as the primary scheme - it can handle passwords of any length
# Keep bcrypt schemes in the list for backward compatibility with existing password hashes
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt_sha256", "bcrypt"], 
    deprecated="auto",
    # Argon2 parameters - adjust as needed for your server resources
    argon2__time_cost=2,         # Number of iterations
    argon2__memory_cost=102400,  # 100MB
    argon2__parallelism=8        # Number of parallel threads
)

# Add logging for password-related issues
logger = logging.getLogger(__name__)

# JWT token scheme
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    # Log password length for debugging
    password_bytes = plain_password.encode('utf-8')
    password_length = len(password_bytes)
    logger.info(f"Password verification attempt with length: {password_length} bytes")
    
    try:
        # With Argon2 as the primary scheme, we can verify passwords of any length
        # The CryptContext will automatically use the right algorithm based on the hash format
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Log password length for debugging
    password_bytes = password.encode('utf-8')
    password_length = len(password_bytes)
    logger.info(f"Password hash request with length: {password_length} bytes")
    
    try:
        # Use Argon2 for new password hashes - it handles passwords of any length
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Password hashing error with Argon2: {str(e)}")
        try:
            # Fall back to PBKDF2 if Argon2 fails for some reason
            salt = os.urandom(32)  # A 32-byte salt
            key = hashlib.pbkdf2_hmac(
                'sha256',  # Hash algorithm
                password.encode('utf-8'),  # Convert to bytes
                salt,  # Provide the salt
                100000,  # 100,000 iterations (adjust as needed)
                dklen=32  # Get a 32-byte key
            )
            # Format: algorithm$iterations$salt$hash
            return f"$pbkdf2-sha256$100000${salt.hex()}${key.hex()}"
        except Exception as inner_e:
            logger.error(f"Fallback hashing error: {str(inner_e)}")
            raise


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    """Authenticate a user by email and password."""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.secret_key, 
            algorithms=[settings.algorithm]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    
    return user


def get_current_active_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Get the current active user."""
    # Note: Your User model doesn't have is_active field, so we'll check if user exists
    return current_user


def get_current_admin_user(current_user: models.User = Depends(get_current_active_user)) -> models.User:
    """Get the current admin user."""
    if current_user.role not in [models.UserRole.admin, models.UserRole.super_admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user


def get_current_driver_admin_user(current_user: models.User = Depends(get_current_active_user)) -> models.User:
    """Get the current user if they are a driver, admin, or super admin."""
    if current_user.role not in [models.UserRole.driver, models.UserRole.admin, models.UserRole.super_admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Driver, admin, or super admin access required."
        )
    return current_user


def get_current_driver_user(current_user: models.User = Depends(get_current_active_user)) -> models.User:
    """Get the current driver user."""
    if current_user.role != models.UserRole.driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Driver access required."
        )
    return current_user


def get_current_super_admin(current_user: models.User = Depends(get_current_active_user)) -> models.User:
    """Get the current super admin user."""
    if current_user.role != models.UserRole.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Super admin access required."
        )
    return current_user


def create_user_token(user: models.User, db: Session) -> str:
    """Create a token for a user with all necessary data."""
    token_data = {
        "sub": user.email,
        "role": user.role.value,
        "user_id": user.user_id,
    }

    # Add branch info based on role
    if user.role == models.UserRole.admin and user.branch_id:
        token_data["branch_id"] = user.branch_id

    elif user.role == models.UserRole.driver:
        # Collect all branch IDs for this driver
        driver_branches = db.query(models.DriverBranch.branch_id).filter(
            models.DriverBranch.driver_id == user.user_id
        ).all()
        token_data["branch_ids"] = [b[0] for b in driver_branches]

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    return create_access_token(data=token_data, expires_delta=access_token_expires)
