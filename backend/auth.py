from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr # Added EmailStr for UserCreate
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.future import select
from .models import Base, Student, Assignment, AnalysisResult

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Pydantic Models for API (User-related)
class UserCreate(BaseModel): # Moved from models.py
    email: EmailStr
    password: str
    full_name: str
    student_id: str

class UserLogin(BaseModel): # Moved from models.py
    email: EmailStr
    password: str

# SQLAlchemy-style (for internal use, not directly for API responses usually)
class UserInDB(BaseModel):
    email: str
    password_hash: str
    full_name: Optional[str] = None
    student_id: Optional[str] = None

# Hardcoded users for simplicity (as per PDF allowance)
fake_users_db = {
    "student@example.com": {
        "email": "student@example.com",
        "password_hash": pwd_context.hash("password123"),  # Hashed password
        "full_name": "Test Student",
        "student_id": "12345",
    }
}
DATABASE_URL = os.getenv("POSTGRES_URL").replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db_store: dict, email: str): # Renamed 'db' to 'db_store' to avoid confusion with AsyncSession
    if email in db_store:
        return UserInDB(**db_store[email])
    return None

def authenticate_user(fake_db: dict, email: str, password: str):
    user = get_user(fake_db, email)
    if not user or not verify_password(password, user.password_hash):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    # Fetch user from the actual database
    result = await db.execute(select(Student).where(Student.email == token_data.email))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    return user