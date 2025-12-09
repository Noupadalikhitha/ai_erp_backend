from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)
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
    if not hashed_password:
        logger.debug("Password verification failed: empty hash provided")
        return False
    
    if not is_valid_bcrypt_hash(hashed_password):
        logger.warning(
            f"Password verification failed: malformed bcrypt hash detected "
            f"(length={len(hashed_password) if hashed_password else 0}, "
            f"starts_with={hashed_password[:7] if len(hashed_password) >= 7 else 'N/A'})"
        )
        return False
    
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError) as e:
        # Handle malformed bcrypt hash errors gracefully
        logger.warning(f"Password verification error: {str(e)}")
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


