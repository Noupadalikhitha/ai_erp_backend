from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, date, timedelta
from app.core.database import get_db
from app.models.finance import Revenue, Expense, BudgetCategory
from app.models.sales import Order
from app.schemas.finance import (
    ExpenseCreate, ExpenseResponse, ExpenseUpdate,
    RevenueCreate, RevenueResponse,
    FinancialSummary, ProfitLossReport,
    FinancialForecast, AbnormalExpense, FinancialReport, ForecastDataPoint
)
from app.api.v1.dependencies import get_current_user, get_current_manager_or_admin
from app.models.user import User

router = APIRouter()
ai_router = APIRouter()

@ai_router.get("/forecasts", response_model=FinancialForecast)
def get_financial_forecasts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """
    AI-powered revenue and cash flow forecasts.
    """
    # This is a mock implementation. In a real scenario, you'd use a time series model.
    today = date.today()
    revenue_forecast = [
        ForecastDataPoint(date=today + timedelta(days=30 * i), value=10000 * (1 + 0.1 * i), series='revenue')
        for i in range(1, 7)
    ]
    cash_flow_forecast = [
        ForecastDataPoint(date=today + timedelta(days=30 * i), value=5000 * (1 + 0.08 * i), series='cash_flow')
        for i in range(1, 7)
    ]
    
    return FinancialForecast(
        revenue_forecast=revenue_forecast,
        cash_flow_forecast=cash_flow_forecast
    )

@ai_router.get("/abnormal-expenses", response_model=List[AbnormalExpense])
def get_abnormal_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """
    AI-identified abnormal or unusually high expenses.
    """
    # Mock implementation: Flag top 5 highest expenses in the last 30 days as 'abnormal'
    thirty_days_ago = date.today() - timedelta(days=30)
    
    unusually_high_expenses = db.query(Expense)\
        .filter(Expense.date >= thirty_days_ago)\
        .order_by(desc(Expense.amount))\
        .limit(5)\
        .all()

    return [
        AbnormalExpense(
            id=exp.id,
            date=exp.date,
            amount=exp.amount,
            description=exp.description,
            reason=f"Amount is significantly higher than average for '{exp.expense_type}' expenses."
        ) for exp in unusually_high_expenses
    ]

@ai_router.post("/generate-report", response_model=FinancialReport)
async def generate_financial_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """
    AI-generated audit-ready financial summaries and PDF reports.
    This is a mock endpoint that simulates PDF generation.
    """
    # In a real implementation, you would:
    # 1. Gather the required financial data.
    # 2. Use a library like ReportLab or WeasyPrint to generate a PDF.
    # 3. Upload the PDF to a storage service (like S3) and get a URL.
    
    # For now, return a mock response.
    file_name = f"financial_summary_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    mock_file_url = f"/static/reports/{file_name}" # Placeholder URL
    
    return FinancialReport(
        file_name=file_name,
        file_url=mock_file_url,
        generated_at=datetime.now()
    )

# Expenses
@router.get("/expenses", response_model=List[ExpenseResponse])
def get_expenses(
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.orm import joinedload
    query = db.query(Expense).options(joinedload(Expense.category))
    if category_id:
        query = query.filter(Expense.category_id == category_id)
    if start_date:
        query = query.filter(Expense.date >= start_date)
    if end_date:
        query = query.filter(Expense.date <= end_date)
    
    expenses = query.order_by(desc(Expense.date)).offset(skip).limit(limit).all()
    
    result = []
    for expense in expenses:
        expense_dict = ExpenseResponse.from_orm(expense).dict()
        expense_dict["category_name"] = expense.category.name if expense.category else None
        result.append(ExpenseResponse(**expense_dict))
    return result

@router.post("/expenses", response_model=ExpenseResponse)
def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create expense - supports all types: bills, purchases, payroll, utilities, other"""
    from sqlalchemy.orm import joinedload
    expense_data = expense.dict()
    db_expense = Expense(**expense_data)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    # Load category relationship
    db.refresh(db_expense, ["category"])
    
    expense_dict = ExpenseResponse.from_orm(db_expense).dict()
    expense_dict["category_name"] = db_expense.category.name if db_expense.category else None
    return ExpenseResponse(**expense_dict)

@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    expense_update: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Update expense - Manager or Admin only"""
    from sqlalchemy.orm import joinedload
    expense = db.query(Expense).options(joinedload(Expense.category)).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Get update data, excluding unset fields
    update_data = expense_update.dict(exclude_unset=True)
    
    # Update each field
    for field, value in update_data.items():
        # Handle None values for optional fields
        if value is None and field in ['category_id', 'description', 'vendor']:
            setattr(expense, field, None)
        else:
            setattr(expense, field, value)
    
    db.commit()
    db.refresh(expense, ["category"])
    
    expense_dict = ExpenseResponse.from_orm(expense).dict()
    expense_dict["category_name"] = expense.category.name if expense.category else None
    return ExpenseResponse(**expense_dict)

@router.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"message": "Expense deleted"}

# Revenue
@router.get("/revenue", response_model=List[RevenueResponse])
def get_revenue(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Revenue)
    if start_date:
        query = query.filter(Revenue.date >= start_date)
    if end_date:
        query = query.filter(Revenue.date <= end_date)
    
    revenue = query.order_by(desc(Revenue.date)).offset(skip).limit(limit).all()
    return revenue

@router.post("/revenue", response_model=RevenueResponse)
def create_revenue(
    revenue: RevenueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_revenue = Revenue(**revenue.dict())
    db.add(db_revenue)
    db.commit()
    db.refresh(db_revenue)
    return db_revenue

# Budget Categories
@router.get("/budget-categories")
def get_budget_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    categories = db.query(BudgetCategory).all()
    return [
        {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "monthly_budget": cat.monthly_budget
        }
        for cat in categories
    ]

@router.post("/budget-categories")
def create_budget_category(
    category_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    category = BudgetCategory(**category_data)
    db.add(category)
    db.commit()
    db.refresh(category)
    return {
        "id": category.id,
        "name": category.name,
        "monthly_budget": category.monthly_budget
    }

# Financial Summary
@router.get("/summary", response_model=FinancialSummary)
def get_financial_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not start_date:
        start_date = date.today().replace(day=1)  # First day of current month
    if not end_date:
        end_date = date.today()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Revenue from Orders (completed/delivered orders)
    from app.models.sales import OrderStatus
    revenue_from_orders = db.query(func.sum(Order.total_amount)).filter(
        Order.status == OrderStatus.DELIVERED,
        Order.created_at >= start_datetime,
        Order.created_at <= end_datetime
    ).scalar() or 0.0
    
    # Revenue from Revenue table
    revenue_from_other = db.query(func.sum(Revenue.amount)).filter(
        Revenue.date >= start_date,
        Revenue.date <= end_date
    ).scalar() or 0.0
    
    total_revenue = float(revenue_from_orders) + float(revenue_from_other)
    
    total_expenses = db.query(func.sum(Expense.amount)).filter(
        Expense.date >= start_date,
        Expense.date <= end_date
    ).scalar() or 0.0
    
    net_profit = total_revenue - total_expenses
    
    return FinancialSummary(
        total_revenue=total_revenue,
        total_expenses=float(total_expenses),
        net_profit=float(net_profit),
        period_start=start_date,
        period_end=end_date
    )

@router.get("/dashboard")
def get_finance_dashboard(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from datetime import datetime
    from app.models.sales import Order
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Revenue from Revenue table
    revenue_from_table = db.query(func.sum(Revenue.amount)).filter(
        Revenue.date >= start_date
    ).scalar() or 0.0
    
    # Revenue from Orders (sales) - convert datetime to date for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    revenue_from_orders = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= start_datetime,
        Order.created_at <= end_datetime
    ).scalar() or 0.0
    
    # Total revenue = Revenue table + Orders
    total_revenue = float(revenue_from_table) + float(revenue_from_orders)
    
    # Expenses
    total_expenses = db.query(func.sum(Expense.amount)).filter(
        Expense.date >= start_date
    ).scalar() or 0.0
    
    # Expenses by category
    expenses_by_category = db.query(
        BudgetCategory.name,
        func.sum(Expense.amount).label("total")
    ).join(Expense, BudgetCategory.id == Expense.category_id)\
     .filter(Expense.date >= start_date)\
     .group_by(BudgetCategory.id, BudgetCategory.name)\
     .all()
    
    # Expenses by type
    expenses_by_type = db.query(
        Expense.expense_type,
        func.sum(Expense.amount).label("total")
    ).filter(Expense.date >= start_date)\
     .group_by(Expense.expense_type)\
     .all()
    
    return {
        "period_days": days,
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses),
        "net_profit": float(total_revenue - total_expenses),
        "revenue_from_orders": float(revenue_from_orders),
        "revenue_from_other": float(revenue_from_table),
        "expenses_by_category": [
            {"category": name, "amount": float(total)}
            for name, total in expenses_by_category
        ],
        "expenses_by_type": {
            expense_type: float(total)
            for expense_type, total in expenses_by_type
        }
    }

@router.get("/reports/month-end", response_model=ProfitLossReport)
def get_month_end_report(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get month-end financial report with expenses vs revenue and P&L"""
    from datetime import date as date_type
    
    if year and month:
        period_start = date_type(year, month, 1)
        if month == 12:
            period_end = date_type(year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date_type(year, month + 1, 1) - timedelta(days=1)
    else:
        today = date_type.today()
        period_start = today.replace(day=1)
        if today.month == 12:
            period_end = date_type(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date_type(today.year, today.month + 1, 1) - timedelta(days=1)
    
    start_datetime = datetime.combine(period_start, datetime.min.time())
    end_datetime = datetime.combine(period_end, datetime.max.time())
    
    # Revenue from Orders (completed/delivered orders only)
    from app.models.sales import OrderStatus
    revenue_from_orders = db.query(func.sum(Order.total_amount)).filter(
        Order.status == OrderStatus.DELIVERED,
        Order.created_at >= start_datetime,
        Order.created_at <= end_datetime
    ).scalar() or 0.0
    
    # Revenue from Revenue table
    revenue_from_other = db.query(func.sum(Revenue.amount)).filter(
        Revenue.date >= period_start,
        Revenue.date <= period_end
    ).scalar() or 0.0
    
    total_revenue = float(revenue_from_orders) + float(revenue_from_other)
    
    # Total Expenses
    total_expenses = db.query(func.sum(Expense.amount)).filter(
        Expense.date >= period_start,
        Expense.date <= period_end
    ).scalar() or 0.0
    
    # Expenses by type
    expenses_by_type_query = db.query(
        Expense.expense_type,
        func.sum(Expense.amount).label("total")
    ).filter(Expense.date >= period_start, Expense.date <= period_end)\
     .group_by(Expense.expense_type)\
     .all()
    
    expenses_by_type = {
        expense_type: float(total)
        for expense_type, total in expenses_by_type_query
    }
    
    # Expenses by category
    expenses_by_category_query = db.query(
        BudgetCategory.name,
        func.sum(Expense.amount).label("total")
    ).join(Expense, BudgetCategory.id == Expense.category_id)\
     .filter(Expense.date >= period_start, Expense.date <= period_end)\
     .group_by(BudgetCategory.id, BudgetCategory.name)\
     .all()
    
    expenses_by_category = [
        {"category": name, "amount": float(total)}
        for name, total in expenses_by_category_query
    ]
    
    # Calculate profit metrics
    net_profit = total_revenue - total_expenses
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0
    
    # Operating expenses (all expenses except cost of goods sold)
    operating_expenses = total_expenses  # For now, all expenses are operating
    
    return ProfitLossReport(
        period_start=period_start,
        period_end=period_end,
        total_revenue=total_revenue,
        revenue_from_orders=float(revenue_from_orders),
        revenue_from_other=float(revenue_from_other),
        total_expenses=float(total_expenses),
        expenses_by_type=expenses_by_type,
        expenses_by_category=expenses_by_category,
        net_profit=net_profit,
        profit_margin=round(profit_margin, 2),
        operating_expenses=float(operating_expenses)
    )

@router.get("/reports/profit-loss", response_model=ProfitLossReport)
def get_profit_loss_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get profit & loss report for any date range - automatically calculated"""
    from datetime import date as date_type
    
    if not start_date:
        start_date = date_type.today().replace(day=1)  # First day of current month
    if not end_date:
        end_date = date_type.today()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Revenue from Orders (completed/delivered orders only)
    from app.models.sales import OrderStatus
    revenue_from_orders = db.query(func.sum(Order.total_amount)).filter(
        Order.status == OrderStatus.DELIVERED,
        Order.created_at >= start_datetime,
        Order.created_at <= end_datetime
    ).scalar() or 0.0
    
    # Revenue from Revenue table
    revenue_from_other = db.query(func.sum(Revenue.amount)).filter(
        Revenue.date >= start_date,
        Revenue.date <= end_date
    ).scalar() or 0.0
    
    total_revenue = float(revenue_from_orders) + float(revenue_from_other)
    
    # Total Expenses
    total_expenses = db.query(func.sum(Expense.amount)).filter(
        Expense.date >= start_date,
        Expense.date <= end_date
    ).scalar() or 0.0
    
    # Expenses by type
    expenses_by_type_query = db.query(
        Expense.expense_type,
        func.sum(Expense.amount).label("total")
    ).filter(Expense.date >= start_date, Expense.date <= end_date)\
     .group_by(Expense.expense_type)\
     .all()
    
    expenses_by_type = {
        expense_type: float(total) if total else 0.0
        for expense_type, total in expenses_by_type_query
    }
    
    # Expenses by category
    expenses_by_category_query = db.query(
        BudgetCategory.name,
        func.sum(Expense.amount).label("total")
    ).join(Expense, BudgetCategory.id == Expense.category_id)\
     .filter(Expense.date >= start_date, Expense.date <= end_date)\
     .group_by(BudgetCategory.id, BudgetCategory.name)\
     .all()
    
    expenses_by_category = [
        {"category": name, "amount": float(total) if total else 0.0}
        for name, total in expenses_by_category_query
    ]
    
    # Calculate profit metrics
    net_profit = total_revenue - total_expenses
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0
    
    # Operating expenses
    operating_expenses = total_expenses
    
    return ProfitLossReport(
        period_start=start_date,
        period_end=end_date,
        total_revenue=total_revenue,
        revenue_from_orders=float(revenue_from_orders),
        revenue_from_other=float(revenue_from_other),
        total_expenses=float(total_expenses),
        expenses_by_type=expenses_by_type,
        expenses_by_category=expenses_by_category,
        net_profit=net_profit,
        profit_margin=round(profit_margin, 2),
        operating_expenses=float(operating_expenses)
    )

