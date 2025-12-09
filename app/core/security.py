from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def is_valid_bcrypt_hash(hashed_password: str) -> bool:
    """
    Validate that a string is a properly formatted bcrypt hash.
    Bcrypt hashes should start with $2b$, $2a$, or $2y$ and be exactly 60 characters long.
    """
    if not isinstance(hashed_password, str):
        return False
    return hashed_password.startswith(('$2b$', '$2a$', '$2y$')) and len(hashed_password) == 60

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    Returns False if the hash is malformed or verification fails.
    """
    if not hashed_password or not is_valid_bcrypt_hash(hashed_password):
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        # Handle malformed bcrypt hash errors gracefully
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


