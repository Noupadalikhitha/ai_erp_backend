from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    # Load user with role relationship
    from sqlalchemy.orm import joinedload
    user = db.query(User).options(joinedload(User.role)).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Ensure role is loaded
    if not user.role:
        raise HTTPException(status_code=400, detail="User role not found")
    
    return user

def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require Admin role"""
    role_name = current_user.role.name if current_user.role else None
    if role_name != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. You don't have permission to access this resource."
        )
    return current_user

def get_current_manager_or_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require Manager or Admin role"""
    role_name = current_user.role.name if current_user.role else None
    if role_name not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or Admin access required. You don't have permission to perform this action."
        )
    return current_user

def require_permission_dependency(module: str, action: str):
    """Dependency factory for permission-based access control"""
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        from app.core.permissions import has_permission
        if not has_permission(current_user, module, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: You don't have permission to {action} {module}"
            )
        return current_user
    return permission_checker

