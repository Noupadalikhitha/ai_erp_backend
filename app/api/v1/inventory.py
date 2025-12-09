from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.core.database import get_db
from app.models.inventory import Product, Category, Supplier, StockHistory
from app.schemas.inventory import (
    ProductCreate, ProductResponse, ProductUpdate,
    CategoryCreate, CategoryResponse, CategoryUpdate,
    SupplierCreate, SupplierResponse, SupplierUpdate
)
from app.api.v1.dependencies import get_current_user, get_current_manager_or_admin
from app.models.user import User
import os
import uuid
from datetime import datetime

router = APIRouter()

# Categories
@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all categories - requires authentication"""
    categories = db.query(Category).offset(skip).limit(limit).all()
    return categories

@router.post("/categories", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    if db.query(Category).filter(Category.name == category.name).first():
        raise HTTPException(status_code=400, detail="Category already exists")
    db_category = Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

# Suppliers
@router.get("/suppliers", response_model=List[SupplierResponse])
def get_suppliers(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all suppliers - requires authentication"""
    suppliers = db.query(Supplier).offset(skip).limit(limit).all()
    return suppliers

@router.post("/suppliers", response_model=SupplierResponse)
def create_supplier(
    supplier: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    db_supplier = Supplier(**supplier.dict())
    db.add(db_supplier)
    db.commit()
    db.refresh(db_supplier)
    return db_supplier

@router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    supplier: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Update a supplier - Manager or Admin only"""
    db_supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not db_supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    update_data = supplier.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_supplier, field, value)
    
    db.commit()
    db.refresh(db_supplier)
    return db_supplier

@router.delete("/suppliers/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Delete a supplier - Manager or Admin only"""
    db_supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not db_supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Soft delete - set is_active to False
    db_supplier.is_active = False
    db.commit()
    return {"message": "Supplier deactivated successfully"}

# Products
@router.get("/products", response_model=List[ProductResponse])
def get_products(
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Product)
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    products = query.offset(skip).limit(limit).all()
    
    result = []
    for p in products:
        p_dict = ProductResponse.from_orm(p).dict()
        p_dict["category_name"] = p.category.name if p.category else None
        p_dict["supplier_name"] = p.supplier.name if p.supplier else None
        result.append(ProductResponse(**p_dict))
    return result

@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    p_dict = ProductResponse.from_orm(product).dict()
    p_dict["category_name"] = product.category.name if product.category else None
    p_dict["supplier_name"] = product.supplier.name if product.supplier else None
    return ProductResponse(**p_dict)

@router.post("/products", response_model=ProductResponse)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    if db.query(Product).filter(Product.sku == product.sku).first():
        raise HTTPException(status_code=400, detail="SKU already exists")
    
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    # Create initial stock history
    stock_history = StockHistory(
        product_id=db_product.id,
        quantity_change=product.stock_quantity,
        previous_quantity=0,
        new_quantity=product.stock_quantity,
        reason="initial"
    )
    db.add(stock_history)
    db.commit()
    
    p_dict = ProductResponse.from_orm(db_product).dict()
    p_dict["category_name"] = db_product.category.name if db_product.category else None
    p_dict["supplier_name"] = db_product.supplier.name if db_product.supplier else None
    return ProductResponse(**p_dict)

@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product_update.dict(exclude_unset=True)
    
    # Track stock changes
    if "stock_quantity" in update_data:
        old_quantity = product.stock_quantity
        new_quantity = update_data["stock_quantity"]
        quantity_change = new_quantity - old_quantity
        
        stock_history = StockHistory(
            product_id=product.id,
            quantity_change=quantity_change,
            previous_quantity=old_quantity,
            new_quantity=new_quantity,
            reason="adjustment"
        )
        db.add(stock_history)
    
    for field, value in update_data.items():
        setattr(product, field, value)
    
    db.commit()
    db.refresh(product)
    
    p_dict = ProductResponse.from_orm(product).dict()
    p_dict["category_name"] = product.category.name if product.category else None
    p_dict["supplier_name"] = product.supplier.name if product.supplier else None
    return ProductResponse(**p_dict)

@router.get("/products/low-stock/list", response_model=List[ProductResponse])
def get_low_stock_products(db: Session = Depends(get_db)):
    products = db.query(Product).filter(
        Product.stock_quantity <= Product.min_stock_level,
        Product.is_active == True
    ).all()
    
    result = []
    for p in products:
        p_dict = ProductResponse.from_orm(p).dict()
        p_dict["category_name"] = p.category.name if p.category else None
        p_dict["supplier_name"] = p.supplier.name if p.supplier else None
        result.append(ProductResponse(**p_dict))
    return result

@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Delete a product - Manager or Admin only"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Soft delete - set is_active to False instead of hard delete
    # This preserves order history and stock history
    product.is_active = False
    db.commit()
    db.refresh(product)
    
    return {"message": "Product deactivated successfully", "product_id": product_id}

@router.get("/products/analytics/dashboard")
def get_inventory_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    total_products = db.query(func.count(Product.id)).scalar()
    low_stock_count = db.query(func.count(Product.id)).filter(
        Product.stock_quantity <= Product.min_stock_level
    ).scalar()
    total_value = db.query(func.sum(Product.stock_quantity * Product.cost)).scalar() or 0
    
    return {
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "total_inventory_value": float(total_value)
    }


# ========== AI-POWERED INVENTORY FEATURES ==========

@router.get("/ai/stock-shortage-predictions")
def get_stock_shortage_predictions(
    days_ahead: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI predicts stock shortages based on historical sales data.
    Uses sales velocity to forecast when products will run out of stock.
    """
    from app.services.ai_service import predict_stock_out_date
    
    # Get all active products with low stock or high consumption
    products = db.query(Product).filter(Product.is_active == True).all()
    
    predictions = []
    for product in products:
        if product.stock_quantity > 0:
            try:
                prediction = predict_stock_out_date(db, product.id)
                if prediction and 'predicted_stock_out_date' in prediction:
                    predictions.append({
                        "product_id": product.id,
                        "product_name": product.name,
                        "current_stock": product.stock_quantity,
                        "min_stock_level": product.min_stock_level,
                        "predicted_stock_out_date": prediction['predicted_stock_out_date'],
                        "urgency": "critical" if product.stock_quantity <= product.min_stock_level else "high" if product.stock_quantity <= (product.min_stock_level * 2) else "medium"
                    })
            except Exception as e:
                # Continue with other products if one fails
                continue
    
    # Sort by urgency and stock-out date
    predictions.sort(key=lambda x: (x['urgency'] == 'critical', x['urgency'] == 'high'), reverse=True)
    
    return {
        "total_predictions": len(predictions),
        "critical_items": sum(1 for p in predictions if p['urgency'] == 'critical'),
        "high_priority_items": sum(1 for p in predictions if p['urgency'] == 'high'),
        "predictions": predictions[:20]  # Return top 20 predictions
    }


@router.get("/ai/reorder-recommendations")
def get_reorder_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI suggests reorder quantities and optimal purchase timing.
    Analyzes sales patterns and lead times to recommend when and how much to order.
    """
    from app.services.ai_service import recommend_reorder_quantity
    
    # Get products that need reordering (below minimum stock)
    low_stock_products = db.query(Product).filter(
        Product.is_active == True,
        Product.stock_quantity <= Product.min_stock_level
    ).all()
    
    recommendations = []
    for product in low_stock_products:
        try:
            reorder_rec = recommend_reorder_quantity(db, product.id)
            if reorder_rec and 'recommended_reorder_quantity' in reorder_rec:
                recommendations.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "current_stock": product.stock_quantity,
                    "min_stock_level": product.min_stock_level,
                    "recommended_quantity": reorder_rec['recommended_reorder_quantity'],
                    "estimated_cost": float(reorder_rec['recommended_reorder_quantity'] * product.cost),
                    "supplier_name": product.supplier.name if product.supplier else "N/A",
                    "supplier_id": product.supplier_id,
                    "priority": "urgent" if product.stock_quantity <= product.min_stock_level else "soon"
                })
        except Exception as e:
            continue
    
    # Sort by priority and product name
    recommendations.sort(key=lambda x: (x['priority'] == 'urgent', x['product_name']), reverse=True)
    
    total_estimated_cost = sum(r['estimated_cost'] for r in recommendations)
    
    return {
        "total_recommendations": len(recommendations),
        "urgent_items": sum(1 for r in recommendations if r['priority'] == 'urgent'),
        "total_estimated_reorder_cost": float(total_estimated_cost),
        "recommendations": recommendations
    }


@router.post("/ai/inventory-summary")
def get_inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI generates monthly inventory summaries in natural language.
    Provides insights on inventory health, stock levels, and recommendations.
    """
    from app.services.ai_service import call_groq_chat, GROQ_MODEL_CHAT
    from datetime import datetime
    
    try:
        # Gather inventory statistics
        total_products = db.query(func.count(Product.id)).filter(Product.is_active == True).scalar()
        low_stock_count = db.query(func.count(Product.id)).filter(
            Product.is_active == True,
            Product.stock_quantity <= Product.min_stock_level
        ).scalar()
        total_inventory_value = db.query(func.sum(Product.stock_quantity * Product.cost)).filter(
            Product.is_active == True
        ).scalar() or 0.0
        
        # Get average stock level
        avg_stock = db.query(func.avg(Product.stock_quantity)).filter(
            Product.is_active == True
        ).scalar() or 0
        
        # Create summary data
        summary_data = {
            "total_active_products": total_products,
            "low_stock_items": low_stock_count,
            "total_inventory_value": float(total_inventory_value),
            "average_stock_level": float(avg_stock),
            "month": datetime.now().strftime("%B %Y")
        }
        
        # Generate natural language summary
        prompt = f"""
        Create a professional monthly inventory summary based on this data:
        
        Month: {summary_data['month']}
        Total Active Products: {summary_data['total_active_products']}
        Low Stock Items: {summary_data['low_stock_items']}
        Total Inventory Value: ${summary_data['total_inventory_value']:,.2f}
        Average Stock Level: {summary_data['average_stock_level']:.0f} units
        
        Provide:
        1. Brief overview of inventory health
        2. Key concerns (if any low stock items)
        3. 2-3 actionable recommendations
        
        Keep it concise but professional (2-3 paragraphs).
        """
        
        try:
            summary_text = call_groq_chat(
                messages=[
                    {"role": "system", "content": "You are a professional inventory analyst. Generate concise, actionable inventory summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500,
                model=GROQ_MODEL_CHAT
            )
        except Exception as e:
            summary_text = f"Unable to generate AI summary at this time. However, your inventory shows {summary_data['low_stock_items']} items below minimum stock level out of {summary_data['total_active_products']} total products."
        
        return {
            "month": summary_data['month'],
            "statistics": summary_data,
            "ai_summary": summary_text,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating inventory summary: {str(e)}")

