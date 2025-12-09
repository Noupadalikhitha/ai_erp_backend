from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.core.permissions import get_user_permissions
from app.models.user import User, Role
from app.schemas.auth import Token, UserCreate, UserResponse
from app.api.v1.dependencies import get_current_user

router = APIRouter()

@router.get("/roles")
def get_roles(db: Session = Depends(get_db)):
    """
    Get all available roles for registration
    Public endpoint - no authentication required
    """
    roles = db.query(Role).all()
    return [
        {
            "id": role.id,
            "name": role.name,
            "description": role.description
        }
        for role in roles
    ]

@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user
    
    Default role is Staff (role_id=3). Only Admins can create users with higher roles.
    Users can select Manager or Staff during registration, but not Admin.
    """
    # Check if user exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Verify role exists
    role = db.query(Role).filter(Role.id == user_data.role_id).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Prevent self-registration as Admin (security)
    if role.name == "Admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin accounts can only be created by existing administrators"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role_id=user_data.role_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Load role relationship
    db.refresh(user, ["role"])
    user_response = UserResponse.from_orm(user)
    user_response.role_name = user.role.name if user.role else None
    return user_response

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login endpoint - Returns JWT token for authenticated users
    Note: OAuth2PasswordRequestForm uses 'username' field, but we accept email as username
    """
    # Use email for login (OAuth2PasswordRequestForm.username field accepts email)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Load role relationship
    db.refresh(user, ["role"])
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.name if user.role else "Staff"},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current authenticated user information"""
    db.refresh(current_user, ["role"])
    user_response = UserResponse.from_orm(current_user)
    user_response.role_name = current_user.role.name if current_user.role else None
    return user_response

@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get general dashboard KPIs - accessible to all authenticated users
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from app.models.sales import Order
    from app.models.employee import Employee
    from app.models.inventory import Product
    
    # Revenue (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    total_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= start_date
    ).scalar() or 0.0
    
    # Order count
    order_count = db.query(func.count(Order.id)).filter(
        Order.created_at >= start_date
    ).scalar()
    
    # Employee count
    employee_count = db.query(func.count(Employee.id)).filter(
        Employee.is_active == True
    ).scalar()
    
    # Low stock items
    low_stock_count = db.query(func.count(Product.id)).filter(
        Product.stock_quantity <= Product.min_stock_level,
        Product.is_active == True
    ).scalar()
    
    return {
        "kpis": {
            "total_revenue_30d": float(total_revenue),
            "order_count_30d": order_count,
            "active_employees": employee_count,
            "low_stock_items": low_stock_count
        }
    }

@router.get("/permissions")
def get_my_permissions(current_user: User = Depends(get_current_user)):
    """
    Get permissions for the current user
    Returns what modules and actions the user can access
    """
    from app.core.permissions import get_user_permissions
    permissions = get_user_permissions(current_user)
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role.name if current_user.role else "Staff",
        "permissions": permissions
    }
