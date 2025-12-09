from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class CustomerResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int
    unit_price: float

class OrderCreate(BaseModel):
    customer_id: int
    items: List[OrderItemCreate]
    discount: float = 0.0
    tax: float = 0.0
    notes: Optional[str] = None

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    quantity: int
    unit_price: float
    subtotal: float
    
    class Config:
        from_attributes = True

class OrderStatusUpdate(BaseModel):
    status: str

class PaymentCreate(BaseModel):
    order_id: int
    amount: float
    payment_method: str
    transaction_id: Optional[str] = None
    notes: Optional[str] = None

class PaymentResponse(BaseModel):
    id: int
    order_id: int
    amount: float
    payment_method: str
    payment_status: str
    transaction_id: Optional[str]
    notes: Optional[str]
    payment_date: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    order_number: str
    status: str
    total_amount: float
    discount: float
    tax: float
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[OrderItemResponse] = []
    total_paid: Optional[float] = 0.0
    payment_status: Optional[str] = "unpaid"
    
    class Config:
        from_attributes = True


