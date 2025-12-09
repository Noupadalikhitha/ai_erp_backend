from fastapi import APIRouter
from app.api.v1 import auth, inventory, sales, employee, finance, admin, ai

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(sales.router, prefix="/sales", tags=["Sales"])
api_router.include_router(employee.router, prefix="/employees", tags=["Employees"])
api_router.include_router(finance.router, prefix="/finance", tags=["Finance"])
api_router.include_router(finance.ai_router, prefix="/finance/ai", tags=["Finance AI"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI Assistant"])



