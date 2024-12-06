from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from nova.app.core.config import settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

ALGORITHM = "HS256"

async def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_admin_token(api_key: str = Security(API_KEY_HEADER)) -> bool:
    """Verify admin API key"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = jwt.decode(api_key, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            raise credentials_exception
        return True
    except JWTError:
        raise credentials_exception

def create_admin_token() -> str:
    """Create an admin token for testing/setup"""
    return jwt.encode(
        {
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(days=1)
        },
        settings.SECRET_KEY,
        algorithm=ALGORITHM
    )