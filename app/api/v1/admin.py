from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.user import User, Role
from app.models.inventory import Product
from app.models.sales import Order
from app.models.employee import Employee
from app.schemas.auth import UserResponse
from app.api.v1.dependencies import get_current_active_admin

router = APIRouter()

@router.get("/dashboard")
def get_admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Get comprehensive admin dashboard with all module metrics"""
    from app.models.sales import OrderStatus
    from app.models.finance import Expense, Revenue
    from app.models.inventory import Category
    from app.models.sales import OrderItem
    
    # Date range (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    start_date_only = start_date.date()
    end_date_only = end_date.date()
    
    # ========== SALES METRICS ==========
    # Total revenue from orders (last 30 days)
    total_revenue_orders = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= start_date
    ).scalar() or 0.0
    
    # Revenue from Revenue table
    total_revenue_other = db.query(func.sum(Revenue.amount)).filter(
        Revenue.date >= start_date_only,
        Revenue.date <= end_date_only
    ).scalar() or 0.0
    
    total_revenue = float(total_revenue_orders) + float(total_revenue_other)
    
    # Order count
    order_count = db.query(func.count(Order.id)).filter(
        Order.created_at >= start_date
    ).scalar()
    
    # Orders by status
    status_counts = {}
    for status in OrderStatus:
        count = db.query(func.count(Order.id)).filter(
            Order.status == status,
            Order.created_at >= start_date
        ).scalar()
        status_counts[status.value] = count
    
    # Daily revenue trend (last 7 days)
    daily_revenue = []
    for i in range(7):
        day = end_date - timedelta(days=6-i)
        day_start = datetime.combine(day.date(), datetime.min.time())
        day_end = datetime.combine(day.date(), datetime.max.time())
        day_revenue = db.query(func.sum(Order.total_amount)).filter(
            Order.created_at >= day_start,
            Order.created_at <= day_end
        ).scalar() or 0.0
        daily_revenue.append({
            "date": day.date().isoformat(),
            "revenue": float(day_revenue)
        })
    
    # Best selling products (top 5)
    best_sellers = db.query(
        Product.name,
        func.sum(OrderItem.quantity).label("total_quantity"),
        func.sum(OrderItem.subtotal).label("total_revenue")
    ).join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.created_at >= start_date)\
     .group_by(Product.id, Product.name)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(5)\
     .all()
    
    # Category-wise sales
    category_sales = db.query(
        Category.name,
        func.sum(OrderItem.subtotal).label("total_revenue"),
        func.sum(OrderItem.quantity).label("total_quantity")
    ).join(Product, Category.id == Product.category_id)\
     .join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.created_at >= start_date)\
     .group_by(Category.id, Category.name)\
     .order_by(func.sum(OrderItem.subtotal).desc())\
     .all()
    
    # ========== INVENTORY METRICS ==========
    total_products = db.query(func.count(Product.id)).filter(
        Product.is_active == True
    ).scalar()
    
    low_stock_count = db.query(func.count(Product.id)).filter(
        Product.stock_quantity <= Product.min_stock_level,
        Product.is_active == True
    ).scalar()
    
    total_inventory_value = db.query(func.sum(Product.stock_quantity * Product.cost)).filter(
        Product.is_active == True
    ).scalar() or 0.0
    
    # Low stock products list
    low_stock_products = db.query(Product).filter(
        Product.stock_quantity <= Product.min_stock_level,
        Product.is_active == True
    ).limit(10).all()
    
    # ========== EMPLOYEE METRICS ==========
    employee_count = db.query(func.count(Employee.id)).filter(
        Employee.is_active == True
    ).scalar()
    
    # ========== FINANCE METRICS ==========
    total_expenses = db.query(func.sum(Expense.amount)).filter(
        Expense.date >= start_date_only,
        Expense.date <= end_date_only
    ).scalar() or 0.0
    
    net_profit = total_revenue - float(total_expenses)
    
    # Expenses by type
    expenses_by_type = db.query(
        Expense.expense_type,
        func.sum(Expense.amount).label("total")
    ).filter(Expense.date >= start_date_only, Expense.date <= end_date_only)\
     .group_by(Expense.expense_type)\
     .all()
    
    # ========== RECENT ACTIVITY ==========
    recent_orders = db.query(Order).order_by(
        Order.created_at.desc()
    ).limit(5).all()
    
    return {
        "kpis": {
            "total_revenue_30d": total_revenue,
            "revenue_from_orders": float(total_revenue_orders),
            "revenue_from_other": float(total_revenue_other),
            "order_count_30d": order_count,
            "active_employees": employee_count,
            "low_stock_items": low_stock_count,
            "total_products": total_products,
            "total_inventory_value": float(total_inventory_value),
            "total_expenses_30d": float(total_expenses),
            "net_profit_30d": net_profit,
            "profit_margin": (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0
        },
        "sales": {
            "orders_by_status": status_counts,
            "daily_revenue_trend": daily_revenue,
            "best_selling_products": [
                {
                    "name": name,
                    "quantity": int(total_quantity) if total_quantity else 0,
                    "revenue": float(total_revenue) if total_revenue else 0.0
                }
                for name, total_quantity, total_revenue in best_sellers
            ],
            "category_performance": [
                {
                    "category": name,
                    "revenue": float(revenue),
                    "quantity": int(quantity)
                }
                for name, revenue, quantity in category_sales
            ]
        },
        "inventory": {
            "low_stock_products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "stock_quantity": p.stock_quantity,
                    "min_stock_level": p.min_stock_level,
                    "category": p.category.name if p.category else None
                }
                for p in low_stock_products
            ]
        },
        "finance": {
            "expenses_by_type": {
                expense_type: float(total)
                for expense_type, total in expenses_by_type
            }
        },
        "recent_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "total_amount": order.total_amount,
                "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                "created_at": order.created_at.isoformat()
            }
            for order in recent_orders
        ]
    }

@router.get("/users", response_model=List[UserResponse])
def get_all_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Get all users"""
    users = db.query(User).offset(skip).limit(limit).all()
    result = []
    for user in users:
        user_dict = UserResponse.from_orm(user).dict()
        user_dict["role_name"] = user.role.name if user.role else None
        result.append(UserResponse(**user_dict))
    return result

@router.get("/roles")
def get_all_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Get all roles"""
    roles = db.query(Role).all()
    return [
        {
            "id": role.id,
            "name": role.name,
            "description": role.description
        }
        for role in roles
    ]

@router.put("/users/{user_id}/activate")
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Activate or deactivate a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"User {'activated' if user.is_active else 'deactivated'}", "is_active": user.is_active}

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Update user role - Admin only"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    user.role_id = role_id
    db.commit()
    db.refresh(user)
    
    user_dict = UserResponse.from_orm(user).dict()
    user_dict["role_name"] = user.role.name if user.role else None
    return UserResponse(**user_dict)

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Delete a user - Admin only"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@router.post("/users")
def create_user(
    user_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Create a new user - Admin only"""
    from app.core.security import get_password_hash
    from app.schemas.auth import UserCreate
    
    # Check if user exists
    if db.query(User).filter(User.email == user_data.get("email")).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Verify role exists
    role = db.query(Role).filter(Role.id == user_data.get("role_id", 2)).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Create user
    hashed_password = get_password_hash(user_data["password"])
    user = User(
        email=user_data["email"],
        hashed_password=hashed_password,
        full_name=user_data.get("full_name"),
        role_id=user_data.get("role_id", 2)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(user, ["role"])
    
    user_dict = UserResponse.from_orm(user).dict()
    user_dict["role_name"] = user.role.name if user.role else None
    return UserResponse(**user_dict)

