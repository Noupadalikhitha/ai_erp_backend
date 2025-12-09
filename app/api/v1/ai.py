from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.services.ai_service import (
    generate_sql_from_natural_language,
    execute_sql_query,
    generate_natural_language_summary,
    get_conversational_response,
    forecast_sales,
    predict_stock_out_date,
    recommend_reorder_quantity,
    detect_anomalies
)

router = APIRouter()

class AIQueryRequest(BaseModel):
    query: str

class AIQueryResponse(BaseModel):
    summary: str
    success: bool
    error: Optional[str] = None

@router.post("/query", response_model=AIQueryResponse)
def process_ai_query(
    request: AIQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Process natural language query and return SQL results"""
    greetings = ["hi", "hello", "hey", "hallo", "hai"]
    if request.query.lower().strip() in greetings:
        return AIQueryResponse(
            summary="Hai! How can I help you today?",
            success=True
        )
    try:
        # Generate SQL from natural language
        sql_query = generate_sql_from_natural_language(request.query)
        
        # If it's a conversational query, return conversational response
        if not sql_query:
            summary = get_conversational_response(request.query)
            return AIQueryResponse(
                summary=summary,
                success=True
            )
        
        # Execute SQL
        results = execute_sql_query(db, sql_query)
        
        # Generate summary
        summary = generate_natural_language_summary(request.query, results)
        
        return AIQueryResponse(
            summary=summary,
            success=True
        )
    except Exception as e:
        return AIQueryResponse(
            summary=f"Error processing query: {str(e)}",
            success=False,
            error=str(e)
        )

@router.get("/forecast/sales")
def get_sales_forecast(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get sales forecast for next N days"""
    try:
        return forecast_sales(db, days)
    except Exception as e:
        return {
            "forecast": [],
            "error": str(e)
        }

@router.get("/inventory/predict-stock-out/{product_id}")
def predict_product_stock_out(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Predict when a product will run out of stock"""
    return predict_stock_out_date(db, product_id)

@router.get("/inventory/recommend-reorder/{product_id}")
def get_reorder_recommendation(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get reorder quantity recommendation"""
    return recommend_reorder_quantity(db, product_id)

@router.get("/anomalies/{entity_type}")
def get_anomalies(
    entity_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Detect anomalies in expenses or attendance"""
    if entity_type not in ["expenses", "attendance"]:
        raise HTTPException(status_code=400, detail="Entity type must be 'expenses' or 'attendance'")
    return detect_anomalies(db, entity_type)

@router.post("/summary/inventory")
def generate_inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate AI summary of inventory status"""
    try:
        from app.models.inventory import Product
        
        low_stock = db.query(Product).filter(
            Product.stock_quantity <= Product.min_stock_level
        ).count()
        
        total_products = db.query(Product).count()
        total_value = sum(p.stock_quantity * (p.cost or 0) for p in db.query(Product).all())
        
        summary = f"""
        Inventory Summary:
        - Total Products: {total_products}
        - Low Stock Items: {low_stock}
        - Total Inventory Value: ${total_value:,.2f}
        - Action Required: {'Yes' if low_stock > 0 else 'No'}
        """
        
        return {"summary": summary.strip()}
    except Exception as e:
        return {"error": str(e)}

@router.post("/summary/financial")
def generate_financial_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate AI summary of financial status"""
    try:
        from datetime import date, timedelta
        from app.models.finance import Revenue, Expense
        from sqlalchemy import func
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        total_revenue = db.query(func.sum(Revenue.amount)).filter(
            Revenue.date >= start_date
        ).scalar() or 0.0
        
        total_expenses = db.query(func.sum(Expense.amount)).filter(
            Expense.date >= start_date
        ).scalar() or 0.0
        
        net_profit = total_revenue - total_expenses
        
        summary = f"""
        Financial Summary (Last {days} days):
        - Total Revenue: ${total_revenue:,.2f}
        - Total Expenses: ${total_expenses:,.2f}
        - Net Profit: ${net_profit:,.2f}
        - Profit Margin: {(net_profit/total_revenue*100) if total_revenue > 0 else 0:.2f}%
        """
        
        return {"summary": summary.strip()}
    except Exception as e:
        return {"error": str(e)}

@router.get("/recommendations")
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get AI-powered business recommendations"""
    recommendations = []
    
    try:
        # Low stock recommendations
        from app.models.inventory import Product
        low_stock_products = db.query(Product).filter(
            Product.stock_quantity <= Product.min_stock_level
        ).limit(5).all()
        
        for product in low_stock_products:
            recommendations.append({
                "type": "inventory",
                "priority": "high",
                "message": f"Product '{product.name}' is low on stock ({product.stock_quantity} units). Consider reordering.",
                "action": f"Reorder {product.name}"
            })
        
        # Sales recommendations
        from app.models.sales import Order
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        recent_sales = db.query(func.sum(Order.total_amount)).filter(
            Order.created_at >= datetime.now() - timedelta(days=7)
        ).scalar() or 0.0
        
        if recent_sales < 1000:
            recommendations.append({
                "type": "sales",
                "priority": "medium",
                "message": "Sales have been low this week. Consider promotional campaigns.",
                "action": "Launch promotion"
            })
        
    except Exception as e:
        pass
    
    return {"recommendations": recommendations}



