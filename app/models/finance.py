from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class BudgetCategory(Base):
    __tablename__ = "budget_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    monthly_budget = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    expenses = relationship("Expense", back_populates="category")

class Revenue(Base):
    __tablename__ = "revenue"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)  # 'sales', 'services', 'other'
    amount = Column(Float, nullable=False)
    description = Column(Text)
    date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
class ExpenseType(str, enum.Enum):
    BILLS = "bills"
    PURCHASES = "purchases"
    PAYROLL = "payroll"
    UTILITIES = "utilities"
    OTHER = "other"

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("budget_categories.id"))
    expense_type = Column(String, default="other")  # bills, purchases, payroll, utilities, other
    amount = Column(Float, nullable=False)
    description = Column(Text)
    vendor = Column(String)
    date = Column(Date, nullable=False)
    receipt_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    category = relationship("BudgetCategory", back_populates="expenses")


