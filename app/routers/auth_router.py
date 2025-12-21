from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app import schemas, auth
from app.database import get_db
from app.config import settings
from app.models import User, DriverBranch, Branch

router = APIRouter()


@router.post("/login", response_model=schemas.LoginResponse)
async def login(
    login_data: schemas.LoginRequest,
    db: Session = Depends(get_db)
):
    """Authenticate user and return access token with user info."""
    # Use email or username (treating username as email for now)
    user = auth.authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user's branches
    branches = []
    if user.role.value == "admin" and user.branch_id:
        # Admin has one branch
        branch = db.query(Branch).filter(Branch.branch_id == user.branch_id).first()
        if branch:
            branches = [branch.name]
    elif user.role.value == "driver":
        # Driver can have multiple branches
        driver_branches = db.query(DriverBranch).join(Branch).filter(
            DriverBranch.driver_id == user.user_id
        ).all()
        branches = [db.query(Branch).filter(Branch.branch_id == db_branch.branch_id).first().name 
                   for db_branch in driver_branches]
    
    # Create token with user data
    access_token = auth.create_user_token(user, db)
    
    # Create user info
    user_info = schemas.UserInfo(
        id=str(user.user_id),
        email=user.email,  
        name=user.name,  
        role=user.role.value,
        branches=branches,
        is_active=True  # Assuming active if they can login
    )
    
    return schemas.LoginResponse(
        token=access_token,
        user=user_info
    )


@router.post("/logout", response_model=schemas.LogoutResponse)
async def logout(
    current_user: User = Depends(auth.get_current_user)
):
    """Logout user (invalidate token - for now just return success)."""
    # In a real implementation, you would add the token to a blacklist
    return schemas.LogoutResponse(message="Logged out successfully")


@router.post("/register", response_model=schemas.UserResponse)
async def register(
    user: schemas.UserCreate,
    current_user: User = Depends(auth.get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Register a new user. Only super admin and admin can register users. Admin cannot register super admin."""
    
    # Check if admin is trying to register a super admin
    if current_user.role.value == "admin" and user.role == "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch admins cannot register super admin users"
        )
    
    # Check if user already exists
    db_user = db.query(auth.models.User).filter(
        auth.models.User.email == user.email
    ).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = auth.get_password_hash(user.password)
    db_user = auth.models.User(
        name=user.name,
        email=user.email,
        password_hash=hashed_password,
        role=user.role,
        branch_id=user.branch_id
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@router.post("/refresh", response_model=schemas.Token)
async def refresh_token(
    current_user: auth.models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Refresh the access token."""
    access_token = auth.create_user_token(current_user, db)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": current_user.user_id,
        "role": current_user.role.value,
        "branch_id": current_user.branch_id
    }


@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: auth.models.User = Depends(auth.get_current_user)
):
    """Get current user information."""
    return current_user