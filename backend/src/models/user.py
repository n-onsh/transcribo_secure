from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict
from datetime import datetime
import uuid

class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    name: Optional[str] = None
    roles: List[str] = Field(default_factory=lambda: ["user"])

class UserCreate(UserBase):
    """User creation model"""
    password: str

class UserUpdate(BaseModel):
    """User update model"""
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    password: Optional[str] = None
    roles: Optional[List[str]] = None

class User(UserBase):
    """User model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    settings: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)

    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    """User login model"""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """User response model"""
    id: str
    email: EmailStr
    name: Optional[str]
    roles: List[str]
    created_at: datetime
    last_login: Optional[datetime]

class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class PasswordReset(BaseModel):
    """Password reset model"""
    email: EmailStr

class PasswordChange(BaseModel):
    """Password change model"""
    old_password: str
    new_password: str

class UserFilter(BaseModel):
    """User filter model"""
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    def apply(self, users: List[User]) -> List[User]:
        """Apply filter to users"""
        filtered = users
        
        if self.email:
            filtered = [u for u in filtered if self.email.lower() in u.email.lower()]
            
        if self.name:
            filtered = [u for u in filtered if u.name and self.name.lower() in u.name.lower()]
            
        if self.role:
            filtered = [u for u in filtered if self.role in u.roles]
            
        if self.created_after:
            filtered = [u for u in filtered if u.created_at >= self.created_after]
            
        if self.created_before:
            filtered = [u for u in filtered if u.created_at <= self.created_before]
            
        return filtered

class UserSort(BaseModel):
    """User sort model"""
    field: str = Field(default="email")  # email, name, created_at
    ascending: bool = Field(default=True)

    def apply(self, users: List[User]) -> List[User]:
        """Apply sort to users"""
        return sorted(
            users,
            key=lambda u: getattr(u, self.field),
            reverse=not self.ascending
        )

class UserStats(BaseModel):
    """User statistics model"""
    total_users: int
    users_by_role: Dict[str, int]
    active_users: int  # logged in within last 30 days
    new_users: int  # created within last 30 days
    
    @classmethod
    def from_users(cls, users: List[User]) -> "UserStats":
        """Generate statistics from users"""
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)
        
        by_role = {}
        for user in users:
            for role in user.roles:
                by_role[role] = by_role.get(role, 0) + 1
        
        return cls(
            total_users=len(users),
            users_by_role=by_role,
            active_users=sum(
                1 for u in users
                if u.last_login and u.last_login >= thirty_days_ago
            ),
            new_users=sum(
                1 for u in users
                if u.created_at >= thirty_days_ago
            )
        )
