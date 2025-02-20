from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import List, Optional
from datetime import datetime
import logging
from passlib.context import CryptContext
from ..models.user import (
    User,
    UserCreate,
    UserUpdate,
    UserLogin,
    UserResponse,
    TokenResponse,
    PasswordReset,
    PasswordChange,
    UserFilter,
    UserSort,
    UserStats
)
from ..services.database import DatabaseService
from ..middleware.auth import AuthMiddleware

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

# Initialize services
database = DatabaseService()
auth = AuthMiddleware()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

@router.post("/register", response_model=TokenResponse)
async def register(user_create: UserCreate) -> TokenResponse:
    """Register new user"""
    try:
        # Check if email exists
        existing = await database.get_user_by_email(user_create.email)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Create user
        user = User(
            email=user_create.email,
            name=user_create.name,
            roles=user_create.roles,
            hashed_password=get_password_hash(user_create.password)
        )
        
        # Save user
        user = await database.create_user(user)
        
        # Create token
        token = auth.create_token(
            user.id,
            user.email,
            user.name,
            user.roles
        )
        
        # Create response
        return TokenResponse(
            access_token=token,
            expires_in=auth.token_expiry * 3600,
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                roles=user.roles,
                created_at=user.created_at,
                last_login=user.last_login
            )
        )
        
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Registration failed"
        )

@router.post("/login", response_model=TokenResponse)
async def login(user_login: UserLogin) -> TokenResponse:
    """Login user"""
    try:
        # Get user
        user = await database.get_user_by_email(user_login.email)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not verify_password(user_login.password, user.hashed_password):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        await database.update_user(user)
        
        # Create token
        token = auth.create_token(
            user.id,
            user.email,
            user.name,
            user.roles
        )
        
        # Create response
        return TokenResponse(
            access_token=token,
            expires_in=auth.token_expiry * 3600,
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                roles=user.roles,
                created_at=user.created_at,
                last_login=user.last_login
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Login failed"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request) -> TokenResponse:
    """Refresh token"""
    try:
        # Get current token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing authentication token"
            )
        
        token = auth_header.split(" ")[1]
        
        # Refresh token
        new_token = auth.refresh_token(token)
        
        # Get user
        user = await database.get_user(request.state.user["id"])
        
        # Create response
        return TokenResponse(
            access_token=new_token,
            expires_in=auth.token_expiry * 3600,
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                roles=user.roles,
                created_at=user.created_at,
                last_login=user.last_login
            )
        )
        
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Token refresh failed"
        )

@router.post("/reset-password")
async def reset_password(reset: PasswordReset):
    """Request password reset"""
    try:
        # Get user
        user = await database.get_user_by_email(reset.email)
        if not user:
            # Return success even if user doesn't exist
            return {"status": "success"}
        
        # TODO: Send password reset email
        logger.info(f"Password reset requested for {reset.email}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Password reset failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Password reset failed"
        )

@router.post("/change-password")
async def change_password(request: Request, change: PasswordChange):
    """Change password"""
    try:
        # Get user
        user = await database.get_user(request.state.user["id"])
        
        # Verify old password
        if not verify_password(change.old_password, user.hashed_password):
            raise HTTPException(
                status_code=401,
                detail="Invalid current password"
            )
        
        # Update password
        user.hashed_password = get_password_hash(change.new_password)
        user.updated_at = datetime.utcnow()
        
        # Save changes
        await database.update_user(user)
        
        return {"status": "success"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Password change failed"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user(request: Request) -> UserResponse:
    """Get current user"""
    try:
        user = await database.get_user(request.state.user["id"])
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            roles=user.roles,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except Exception as e:
        logger.error(f"Failed to get current user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get user"
        )

@router.put("/me", response_model=UserResponse)
async def update_current_user(request: Request, update: UserUpdate) -> UserResponse:
    """Update current user"""
    try:
        # Get user
        user = await database.get_user(request.state.user["id"])
        
        # Update fields
        if update.email:
            user.email = update.email
        if update.name:
            user.name = update.name
        if update.password:
            user.hashed_password = get_password_hash(update.password)
        if update.roles and auth.is_admin(request):
            user.roles = update.roles
            
        user.updated_at = datetime.utcnow()
        
        # Save changes
        user = await database.update_user(user)
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            roles=user.roles,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except Exception as e:
        logger.error(f"Failed to update user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update user"
        )

@router.delete("/me")
async def delete_current_user(request: Request):
    """Delete current user"""
    try:
        await database.delete_user(request.state.user["id"])
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Failed to delete user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete user"
        )

# Admin routes
@router.get("/users", response_model=List[UserResponse])
@auth.require_roles(["admin"])
async def list_users(
    request: Request,
    email: Optional[str] = Query(None, description="Filter by email"),
    name: Optional[str] = Query(None, description="Filter by name"),
    role: Optional[str] = Query(None, description="Filter by role"),
    sort_by: Optional[str] = Query("email", description="Sort field"),
    ascending: bool = Query(True, description="Sort direction")
) -> List[UserResponse]:
    """List users (admin only)"""
    try:
        # Get users
        users = await database.list_users()
        
        # Apply filter
        filter = UserFilter(
            email=email,
            name=name,
            role=role
        )
        filtered = filter.apply(users)
        
        # Apply sort
        sort = UserSort(field=sort_by, ascending=ascending)
        sorted_users = sort.apply(filtered)
        
        # Convert to response models
        return [
            UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                roles=user.roles,
                created_at=user.created_at,
                last_login=user.last_login
            )
            for user in sorted_users
        ]
        
    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list users"
        )

@router.get("/stats", response_model=UserStats)
@auth.require_roles(["admin"])
async def get_user_stats(request: Request) -> UserStats:
    """Get user statistics (admin only)"""
    try:
        users = await database.list_users()
        return UserStats.from_users(users)
        
    except Exception as e:
        logger.error(f"Failed to get user stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get user stats"
        )
