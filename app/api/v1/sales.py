from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.sales import Order, OrderItem, Customer, OrderStatus, Payment
from app.models.inventory import Product, StockHistory
from app.schemas.sales import (
    OrderCreate, OrderResponse, OrderStatusUpdate,
    CustomerCreate, CustomerResponse,
    PaymentCreate, PaymentResponse
)
from app.api.v1.dependencies import get_current_user, get_current_manager_or_admin
from app.models.user import User
import uuid

router = APIRouter()

# Customers
@router.get("/customers", response_model=List[CustomerResponse])
def get_customers(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all customers - requires authentication"""
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers

@router.post("/customers", response_model=CustomerResponse)
def create_customer(
    customer: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_customer = Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

# Orders
@router.get("/orders", response_model=List[OrderResponse])
def get_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    orders = query.order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
    
    result = []
    for order in orders:
        order_dict = OrderResponse.from_orm(order).dict()
        order_dict["customer_name"] = order.customer.name if order.customer else None
        order_dict["items"] = [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product.name if item.product else None,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.subtotal
            }
            for item in order.items
        ]
        # Calculate total paid and payment status
        total_paid = db.query(func.sum(Payment.amount)).filter(
            Payment.order_id == order.id,
            Payment.payment_status == "completed"
        ).scalar() or 0.0
        order_dict["total_paid"] = float(total_paid)
        order_dict["payment_status"] = "paid" if total_paid >= order.total_amount else "partial" if total_paid > 0 else "unpaid"
        result.append(OrderResponse(**order_dict))
    return result

@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order_dict = OrderResponse.from_orm(order).dict()
    order_dict["customer_name"] = order.customer.name if order.customer else None
    order_dict["items"] = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else None,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal
        }
        for item in order.items
    ]
    return OrderResponse(**order_dict)

@router.post("/orders", response_model=OrderResponse)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Generate order number
    order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    # Calculate total
    total_amount = 0.0
    order_items = []
    
    for item_data in order_data.items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item_data.product_id} not found")
        if product.stock_quantity < item_data.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {product.name}"
            )
        
        subtotal = item_data.quantity * item_data.unit_price
        total_amount += subtotal
        
        order_items.append({
            "product_id": item_data.product_id,
            "quantity": item_data.quantity,
            "unit_price": item_data.unit_price,
            "subtotal": subtotal
        })
    
    total_amount = total_amount - order_data.discount + order_data.tax
    
    # Create order
    order = Order(
        customer_id=order_data.customer_id,
        order_number=order_number,
        total_amount=total_amount,
        discount=order_data.discount,
        tax=order_data.tax,
        notes=order_data.notes
    )
    db.add(order)
    db.flush()
    
    # Create order items and update stock
    for item_data in order_items:
        order_item = OrderItem(
            order_id=order.id,
            **item_data
        )
        db.add(order_item)
        
        # Update product stock
        product = db.query(Product).filter(Product.id == item_data["product_id"]).first()
        old_quantity = product.stock_quantity
        product.stock_quantity -= item_data["quantity"]
        new_quantity = product.stock_quantity
        
        # Create stock history
        stock_history = StockHistory(
            product_id=product.id,
            quantity_change=-item_data["quantity"],
            previous_quantity=old_quantity,
            new_quantity=new_quantity,
            reason="sale"
        )
        db.add(stock_history)
    
    db.commit()
    db.refresh(order)
    
    order_dict = OrderResponse.from_orm(order).dict()
    order_dict["customer_name"] = order.customer.name if order.customer else None
    order_dict["items"] = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else None,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal
        }
        for item in order.items
    ]
    return OrderResponse(**order_dict)

@router.put("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Update order status - Manager or Admin only"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Validate status transition
    valid_statuses = [s.value for s in OrderStatus]
    if status_update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    
    # Validate status workflow: pending → processing → shipped → delivered
    status_flow = ["pending", "processing", "shipped", "delivered", "cancelled"]
    current_index = status_flow.index(order.status.value) if order.status.value in status_flow else -1
    new_index = status_flow.index(status_update.status) if status_update.status in status_flow else -1
    
    if new_index < current_index and status_update.status != "cancelled":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change status from {order.status.value} to {status_update.status}. Valid transitions: {status_flow[current_index+1:] if current_index >= 0 else status_flow}"
        )
    
    order.status = OrderStatus(status_update.status)
    order.updated_at = datetime.now()
    db.commit()
    db.refresh(order)
    
    order_dict = OrderResponse.from_orm(order).dict()
    order_dict["customer_name"] = order.customer.name if order.customer else None
    order_dict["items"] = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else None,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal
        }
        for item in order.items
    ]
    total_paid = db.query(func.sum(Payment.amount)).filter(
        Payment.order_id == order.id,
        Payment.payment_status == "completed"
    ).scalar() or 0.0
    order_dict["total_paid"] = float(total_paid)
    order_dict["payment_status"] = "paid" if total_paid >= order.total_amount else "partial" if total_paid > 0 else "unpaid"
    return OrderResponse(**order_dict)

@router.post("/payments", response_model=PaymentResponse)
def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a payment for an order"""
    order = db.query(Order).filter(Order.id == payment.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if payment amount exceeds remaining balance
    total_paid = db.query(func.sum(Payment.amount)).filter(
        Payment.order_id == payment.order_id,
        Payment.payment_status == "completed"
    ).scalar() or 0.0
    remaining = order.total_amount - total_paid
    
    if payment.amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount (${payment.amount}) exceeds remaining balance (${remaining:.2f})"
        )
    
    db_payment = Payment(
        order_id=payment.order_id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        transaction_id=payment.transaction_id,
        notes=payment.notes,
        payment_status="completed"
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

@router.get("/orders/{order_id}/payments", response_model=List[PaymentResponse])
def get_order_payments(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all payments for an order"""
    payments = db.query(Payment).filter(Payment.order_id == order_id).all()
    return payments

@router.get("/orders/reports/daily")
def get_daily_sales_report(
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily sales report"""
    from datetime import date as date_type
    if date:
        report_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        report_date = date_type.today()
    
    start_datetime = datetime.combine(report_date, datetime.min.time())
    end_datetime = datetime.combine(report_date, datetime.max.time())
    
    orders = db.query(Order).filter(
        Order.created_at >= start_datetime,
        Order.created_at <= end_datetime
    ).all()
    
    total_revenue = sum(order.total_amount for order in orders)
    order_count = len(orders)
    
    # Orders by status
    status_counts = {}
    for status in OrderStatus:
        status_counts[status.value] = len([o for o in orders if o.status == status])
    
    # Category-wise performance
    from app.models.inventory import Product, Category
    category_sales = db.query(
        Category.name,
        func.sum(OrderItem.subtotal).label("total_revenue"),
        func.sum(OrderItem.quantity).label("total_quantity")
    ).join(Product, Category.id == Product.category_id)\
     .join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.created_at >= start_datetime, Order.created_at <= end_datetime)\
     .group_by(Category.id, Category.name)\
     .all()
    
    return {
        "date": report_date.isoformat(),
        "total_revenue": float(total_revenue),
        "order_count": order_count,
        "status_breakdown": status_counts,
        "category_performance": [
            {
                "category": name,
                "revenue": float(revenue),
                "quantity": int(quantity)
            }
            for name, revenue, quantity in category_sales
        ],
        "orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer.name if order.customer else None,
                "status": order.status.value,
                "total_amount": order.total_amount,
                "created_at": order.created_at.isoformat()
            }
            for order in orders
        ]
    }

@router.get("/orders/reports/weekly")
def get_weekly_sales_report(
    week_start: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get weekly sales report"""
    from datetime import date as date_type, timedelta
    if week_start:
        start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    else:
        today = date_type.today()
        start_date = today - timedelta(days=today.weekday())
    
    end_date = start_date + timedelta(days=6)
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    orders = db.query(Order).filter(
        Order.created_at >= start_datetime,
        Order.created_at <= end_datetime
    ).all()
    
    total_revenue = sum(order.total_amount for order in orders)
    order_count = len(orders)
    
    # Daily breakdown
    daily_revenue = {}
    for i in range(7):
        day = start_date + timedelta(days=i)
        day_orders = [o for o in orders if o.created_at.date() == day]
        daily_revenue[day.isoformat()] = sum(o.total_amount for o in day_orders)
    
    # Category-wise performance
    from app.models.inventory import Product, Category
    category_sales = db.query(
        Category.name,
        func.sum(OrderItem.subtotal).label("total_revenue"),
        func.sum(OrderItem.quantity).label("total_quantity")
    ).join(Product, Category.id == Product.category_id)\
     .join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.created_at >= start_datetime, Order.created_at <= end_datetime)\
     .group_by(Category.id, Category.name)\
     .all()
    
    return {
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "total_revenue": float(total_revenue),
        "order_count": order_count,
        "daily_revenue": daily_revenue,
        "category_performance": [
            {
                "category": name,
                "revenue": float(revenue),
                "quantity": int(quantity)
            }
            for name, revenue, quantity in category_sales
        ]
    }

@router.get("/orders/reports/monthly")
def get_monthly_sales_report(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get monthly sales report"""
    from datetime import date as date_type
    if year and month:
        start_date = date_type(year, month, 1)
        if month == 12:
            end_date = date_type(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date_type(year, month + 1, 1) - timedelta(days=1)
    else:
        today = date_type.today()
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = date_type(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date_type(today.year, today.month + 1, 1) - timedelta(days=1)
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    orders = db.query(Order).filter(
        Order.created_at >= start_datetime,
        Order.created_at <= end_datetime
    ).all()
    
    total_revenue = sum(order.total_amount for order in orders)
    order_count = len(orders)
    
    # Weekly breakdown
    weekly_revenue = {}
    current_week_start = start_date
    week_num = 1
    while current_week_start <= end_date:
        week_end = min(current_week_start + timedelta(days=6), end_date)
        week_orders = [o for o in orders if current_week_start <= o.created_at.date() <= week_end]
        weekly_revenue[f"Week {week_num}"] = sum(o.total_amount for o in week_orders)
        current_week_start += timedelta(days=7)
        week_num += 1
    
    # Category-wise performance
    from app.models.inventory import Product, Category
    category_sales = db.query(
        Category.name,
        func.sum(OrderItem.subtotal).label("total_revenue"),
        func.sum(OrderItem.quantity).label("total_quantity")
    ).join(Product, Category.id == Product.category_id)\
     .join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.created_at >= start_datetime, Order.created_at <= end_datetime)\
     .group_by(Category.id, Category.name)\
     .all()
    
    return {
        "year": start_date.year,
        "month": start_date.month,
        "month_name": start_date.strftime("%B"),
        "total_revenue": float(total_revenue),
        "order_count": order_count,
        "weekly_revenue": weekly_revenue,
        "category_performance": [
            {
                "category": name,
                "revenue": float(revenue),
                "quantity": int(quantity)
            }
            for name, revenue, quantity in category_sales
        ]
    }

@router.get("/orders/analytics/dashboard")
def get_sales_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Total sales
    total_sales = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= start_date
    ).scalar() or 0.0
    
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
    
    # Best selling products
    from app.models.inventory import Product
    from app.models.sales import OrderItem
    
    best_sellers = db.query(
        Product.name,
        func.sum(OrderItem.quantity).label("total_quantity"),
        func.sum(OrderItem.subtotal).label("total_revenue")
    ).join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.created_at >= start_date)\
     .group_by(Product.id, Product.name)\
     .order_by(desc(func.sum(OrderItem.quantity)))\
     .limit(10)\
     .all()
    
    # Category-wise performance
    from app.models.inventory import Category
    category_sales = db.query(
        Category.name,
        func.sum(OrderItem.subtotal).label("total_revenue"),
        func.sum(OrderItem.quantity).label("total_quantity")
    ).join(Product, Category.id == Product.category_id)\
     .join(OrderItem, Product.id == OrderItem.product_id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.created_at >= start_date)\
     .group_by(Category.id, Category.name)\
     .order_by(desc(func.sum(OrderItem.subtotal)))\
     .all()
    
    # Daily revenue trend (last 7 days)
    daily_trend = []
    for i in range(7):
        day = start_date + timedelta(days=days - 7 + i)
        day_start = datetime.combine(day.date(), datetime.min.time())
        day_end = datetime.combine(day.date(), datetime.max.time())
        day_revenue = db.query(func.sum(Order.total_amount)).filter(
            Order.created_at >= day_start,
            Order.created_at <= day_end
        ).scalar() or 0.0
        daily_trend.append({
            "date": day.date().isoformat(),
            "revenue": float(day_revenue)
        })
    
    return {
        "total_sales": float(total_sales),
        "order_count": order_count,
        "period_days": days,
        "status_breakdown": status_counts,
        "best_selling_products": [
            {
                "name": name,
                "total_quantity": int(total_quantity) if total_quantity else 0,
                "total_revenue": float(total_revenue) if total_revenue else 0.0
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
        ],
        "daily_trend": daily_trend
    }


# AI SALES FEATURES

@router.get("/ai/sales-trends")
def get_sales_trends(
    days_ahead: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI predicts upcoming sales trends.
    Analyzes historical sales patterns and predicts future trends.
    """
    from app.services.ai_service import call_groq_chat, GROQ_MODEL_CHAT
    from datetime import datetime, timedelta
    
    try:
        # Get historical sales data (last 90 days)
        days_back = 90
        date_threshold = datetime.now() - timedelta(days=days_back)
        
        # Daily sales aggregation
        daily_sales = db.query(
            func.date(Order.created_at).label("date"),
            func.count(Order.id).label("order_count"),
            func.sum(Order.total_amount).label("daily_revenue")
        ).filter(Order.created_at >= date_threshold).group_by(
            func.date(Order.created_at)
        ).order_by(func.date(Order.created_at)).all()
        
        # Calculate trend metrics
        if len(daily_sales) >= 2:
            recent_avg = sum([s.daily_revenue or 0 for s in daily_sales[-30:]]) / min(30, len(daily_sales)) if daily_sales else 0
            older_avg = sum([s.daily_revenue or 0 for s in daily_sales[:-30]]) / max(1, len(daily_sales) - 30) if daily_sales else 0
            trend_direction = "increasing" if recent_avg > older_avg else "decreasing"
            trend_percentage = ((recent_avg - older_avg) / max(older_avg, 1)) * 100
        else:
            recent_avg = 0
            older_avg = 0
            trend_direction = "stable"
            trend_percentage = 0
        
        # Get top trending products
        trending_products = db.query(
            Product.name,
            func.sum(OrderItem.quantity).label("total_qty"),
            func.sum(OrderItem.subtotal).label("total_revenue")
        ).join(OrderItem).join(Order).filter(
            Order.created_at >= date_threshold
        ).group_by(Product.id, Product.name).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(5).all()
        
        # Prepare data for AI analysis
        trend_data = {
            "period_days": days_back,
            "average_daily_revenue": float(recent_avg),
            "previous_average": float(older_avg),
            "trend_direction": trend_direction,
            "trend_percentage": round(trend_percentage, 2),
            "total_orders_analyzed": len(daily_sales),
            "top_products": [
                {
                    "product": name,
                    "quantity_sold": int(qty) if qty else 0,
                    "revenue": float(revenue) if revenue else 0.0
                }
                for name, qty, revenue in trending_products
            ]
        }
        
        # AI Analysis prompt
        prompt = f"""
        Based on the following sales data from the last {days_back} days, predict sales trends for the next {days_ahead} days:
        
        Historical Data:
        - Average Daily Revenue (Recent 30 days): ${trend_data['average_daily_revenue']:,.2f}
        - Previous 30-day Average: ${trend_data['previous_average']:,.2f}
        - Trend Direction: {trend_data['trend_direction']}
        - Trend Change: {trend_data['trend_percentage']}%
        - Total Orders Analyzed: {trend_data['total_orders_analyzed']}
        
        Top Selling Products:
        {chr(10).join([f"- {p['product']}: {p['quantity_sold']} units (${p['revenue']:,.2f})" for p in trend_data['top_products']])}
        
        Predict:
        1. Expected sales trend for next {days_ahead} days
        2. Estimated revenue growth or decline
        3. Key factors driving the trend
        4. Product categories expected to perform well
        5. Recommendations for sales strategy
        
        Keep predictions concise and data-driven.
        """
        
        try:
            ai_prediction = call_groq_chat(
                messages=[
                    {"role": "system", "content": "You are a sales analytics expert. Provide data-driven sales predictions based on historical trends."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600,
                model=GROQ_MODEL_CHAT
            )
        except Exception:
            ai_prediction = f"Based on recent trends, sales are {trend_direction} by {abs(trend_percentage):.1f}%. Monitor top products: {', '.join([p['product'] for p in trend_data['top_products'][:3]])}"
        
        return {
            "trend_analysis": trend_data,
            "days_ahead": days_ahead,
            "ai_prediction": ai_prediction,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing sales trends: {str(e)}")


@router.get("/ai/best-sellers")
def get_best_sellers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI identifies best-selling products and categories.
    Analyzes sales data to highlight top performers across products and categories.
    """
    from app.services.ai_service import call_groq_chat, GROQ_MODEL_CHAT
    from datetime import datetime, timedelta
    
    try:
        # Get sales data for last 60 days
        date_threshold = datetime.now() - timedelta(days=60)
        
        # Best selling products
        best_products = db.query(
            Product.id,
            Product.name,
            Product.category_id,
            func.sum(OrderItem.quantity).label("total_qty"),
            func.sum(OrderItem.subtotal).label("total_revenue"),
            func.avg(OrderItem.unit_price).label("avg_price")
        ).join(OrderItem).join(Order).filter(
            Order.created_at >= date_threshold
        ).group_by(Product.id, Product.name, Product.category_id).order_by(
            func.sum(OrderItem.subtotal).desc()
        ).limit(10).all()
        
        # Best performing categories
        best_categories = db.query(
            Product.category_id.label("category"),
            func.count(OrderItem.id).label("sales_count"),
            func.sum(OrderItem.quantity).label("total_qty"),
            func.sum(OrderItem.subtotal).label("total_revenue")
        ).join(OrderItem).join(Order).filter(
            Order.created_at >= date_threshold
        ).group_by(Product.category_id).order_by(
            func.sum(OrderItem.subtotal).desc()
        ).limit(5).all()
        
        # Calculate growth rates
        date_threshold_older = datetime.now() - timedelta(days=120)
        older_revenue = db.query(func.sum(OrderItem.subtotal)).join(Order).filter(
            Order.created_at < date_threshold,
            Order.created_at >= date_threshold_older
        ).scalar() or 0
        
        recent_revenue = db.query(func.sum(OrderItem.subtotal)).join(Order).filter(
            Order.created_at >= date_threshold
        ).scalar() or 0
        
        growth_rate = ((recent_revenue - older_revenue) / max(older_revenue, 1)) * 100
        
        # Prepare data
        analysis_data = {
            "period_days": 60,
            "top_products": [
                {
                    "id": pid,
                    "name": name,
                    "category_id": cat_id,
                    "quantity_sold": int(qty) if qty else 0,
                    "revenue": float(rev) if rev else 0.0,
                    "avg_unit_price": float(price) if price else 0.0
                }
                for pid, name, cat_id, qty, rev, price in best_products
            ],
            "top_categories": [
                {
                    "category_id": cat_id,
                    "sales_count": int(cnt) if cnt else 0,
                    "total_qty": int(qty) if qty else 0,
                    "revenue": float(rev) if rev else 0.0
                }
                for cat_id, cnt, qty, rev in best_categories
            ],
            "growth_rate": round(growth_rate, 2),
            "recent_period_revenue": float(recent_revenue),
            "previous_period_revenue": float(older_revenue)
        }
        
        # AI Analysis
        prompt = f"""
        Analyze the following best-seller data from the last 60 days:
        
        Top 10 Products (by revenue):
        {chr(10).join([f"- {p['name']}: {p['quantity_sold']} units, ${p['revenue']:,.2f}" for p in analysis_data['top_products']])}
        
        Top Categories:
        {chr(10).join([f"- Category {c['category_id']}: {c['sales_count']} sales, ${c['revenue']:,.2f}" for c in analysis_data['top_categories']])}
        
        Performance Metrics:
        - Growth Rate (vs previous 60 days): {analysis_data['growth_rate']}%
        - Recent Period Revenue: ${analysis_data['recent_period_revenue']:,.2f}
        
        Provide:
        1. Key insights about top performers
        2. Why these products/categories are succeeding
        3. Revenue concentration analysis
        4. Cross-selling opportunities
        5. Inventory recommendations for best sellers
        
        Be concise and actionable.
        """
        
        try:
            ai_insights = call_groq_chat(
                messages=[
                    {"role": "system", "content": "You are a retail analyst. Provide insights on best-selling products and categories."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600,
                model=GROQ_MODEL_CHAT
            )
        except Exception:
            top_3_products = ', '.join([p['name'] for p in analysis_data['top_products'][:3]])
            ai_insights = f"Top performers are: {top_3_products}. These products drive {analysis_data['recent_period_revenue']:.0f} in revenue."
        
        return {
            "analysis": analysis_data,
            "ai_insights": ai_insights,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing best sellers: {str(e)}")


@router.post("/ai/underperformers")
def get_underperformers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI highlights underperforming items with actionable suggestions.
    Identifies low-performing products and provides recommendations.
    """
    from app.services.ai_service import call_groq_chat, GROQ_MODEL_CHAT
    from datetime import datetime, timedelta
    
    try:
        # Get all products with sales data (last 90 days)
        date_threshold = datetime.now() - timedelta(days=90)
        
        all_products_sales = db.query(
            Product.id,
            Product.name,
            Product.stock_quantity,
            Product.min_stock_level,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("total_qty"),
            func.coalesce(func.sum(OrderItem.subtotal), 0).label("total_revenue"),
            func.coalesce(func.count(OrderItem.id), 0).label("sale_count")
        ).outerjoin(OrderItem).outerjoin(Order, Order.id == OrderItem.order_id).filter(
            (Order.created_at >= date_threshold) | (Order.id.is_(None))
        ).group_by(Product.id, Product.name, Product.stock_quantity, Product.min_stock_level).all()
        
        # Calculate average revenue per product
        avg_revenue_per_product = sum([p.total_revenue for p in all_products_sales]) / max(len(all_products_sales), 1)
        
        # Identify underperformers (below average sales)
        underperformers = []
        for product in all_products_sales:
            if product.total_revenue < avg_revenue_per_product * 0.5 and product.stock_quantity > 0:
                underperformers.append({
                    "id": product.id,
                    "name": product.name,
                    "current_stock": product.stock_quantity,
                    "min_stock_level": product.min_stock_level,
                    "total_qty_sold": int(product.total_qty),
                    "total_revenue": float(product.total_revenue),
                    "sale_count": int(product.sale_count),
                    "revenue_vs_avg": float(product.total_revenue - avg_revenue_per_product)
                })
        
        # Sort by revenue
        underperformers.sort(key=lambda x: x['total_revenue'])
        underperformers = underperformers[:15]  # Top 15 underperformers
        
        # Calculate metrics
        total_products = len(all_products_sales)
        underperforming_pct = (len(underperformers) / max(total_products, 1)) * 100
        
        metrics = {
            "total_products": total_products,
            "underperformers_count": len(underperformers),
            "underperforming_percentage": round(underperforming_pct, 2),
            "average_revenue_per_product": float(avg_revenue_per_product),
            "underperformers": underperformers
        }
        
        # AI Analysis and Recommendations
        prompt = f"""
        Analyze the following underperforming products (bottom 15 by revenue over last 90 days):
        
        Top Underperformers:
        {chr(10).join([f"- {u['name']}: {u['total_qty_sold']} units sold, ${u['total_revenue']:.2f} revenue, {u['sale_count']} transactions" for u in underperformers[:10]])}
        
        Context:
        - Total Products: {metrics['total_products']}
        - Average Revenue per Product: ${metrics['average_revenue_per_product']:,.2f}
        - Underperforming Items: {metrics['underperformers_count']} ({metrics['underperforming_percentage']:.1f}%)
        
        For each product, provide:
        1. Why the product might be underperforming (quality, pricing, visibility, demand)
        2. Actionable recommendations (pricing adjustment, promotion, bundling, discontinue)
        3. Suggested marketing strategy or placement changes
        4. Target customer segment that might benefit
        5. Inventory management recommendations (reduce stock vs push sales)
        
        Prioritize recommendations by potential impact.
        """
        
        try:
            ai_recommendations = call_groq_chat(
                messages=[
                    {"role": "system", "content": "You are a retail business consultant. Provide specific, actionable recommendations for improving underperforming product sales."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800,
                model=GROQ_MODEL_CHAT
            )
        except Exception:
            top_underperformers = ', '.join([u['name'] for u in underperformers[:3]])
            ai_recommendations = f"Consider reviewing: {top_underperformers}. Consider pricing adjustments, promotions, or discontinuation."
        
        return {
            "metrics": metrics,
            "ai_recommendations": ai_recommendations,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing underperformers: {str(e)}")
