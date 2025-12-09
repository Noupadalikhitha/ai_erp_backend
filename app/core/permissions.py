"""
Role-based permissions system for ERP modules
"""
from typing import List
from app.models.user import User

# Define permissions for each role
ROLE_PERMISSIONS = {
    "Admin": {
        "inventory": ["view", "create", "edit", "delete"],
        "sales": ["view", "create", "edit", "delete"],
        "employees": ["view", "create", "edit", "delete"],
        "finance": ["view", "create", "edit", "delete"],
        "admin": ["view", "create", "edit", "delete"],
        "ai": ["view", "use"],
    },
    "Manager": {
        "inventory": ["view", "create", "edit"],
        "sales": ["view", "create", "edit"],
        "employees": ["view", "create", "edit"],
        "finance": ["view", "create", "edit"],
        "admin": [],  # No admin access
        "ai": ["view", "use"],
    },
    "Staff": {
        "inventory": ["view"],
        "sales": ["view", "create"],
        "employees": ["view"],
        "finance": ["view"],
        "admin": [],  # No admin access
        "ai": ["view", "use"],
    },
}

def has_permission(user: User, module: str, action: str) -> bool:
    """
    Check if user has permission for a specific action in a module
    
    Args:
        user: User object
        module: Module name (inventory, sales, employees, finance, admin, ai)
        action: Action type (view, create, edit, delete, use)
    
    Returns:
        bool: True if user has permission, False otherwise
    """
    if not user.is_active:
        return False
    
    role_name = user.role.name if user.role else "Staff"
    permissions = ROLE_PERMISSIONS.get(role_name, {})
    module_permissions = permissions.get(module, [])
    
    return action in module_permissions

def get_user_permissions(user: User) -> dict:
    """
    Get all permissions for a user
    
    Args:
        user: User object
    
    Returns:
        dict: Dictionary of module -> list of allowed actions
    """
    if not user.is_active:
        return {}
    
    role_name = user.role.name if user.role else "Staff"
    return ROLE_PERMISSIONS.get(role_name, {}).copy()

def require_permission(module: str, action: str):
    """
    Decorator to require specific permission for an endpoint
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get current_user from kwargs
            current_user = kwargs.get('current_user')
            if not current_user:
                # Try to get from args (if passed as dependency)
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break
            
            if not current_user or not has_permission(current_user, module, action):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {action} on {module}"
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator



