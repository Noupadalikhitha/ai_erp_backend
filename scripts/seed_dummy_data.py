"""Seed database with dummy data for all tables"""
import sys
import os
from pathlib import Path

# Add parent directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(dotenv_path=env_path)

from datetime import datetime, date, timedelta
from random import randint, choice, uniform
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, Role
from app.models.inventory import Category, Supplier, Product, StockHistory
from app.models.sales import Customer, Order, OrderItem, OrderStatus
from app.models.employee import Employee, Attendance, Performance, Payroll, AttendanceStatus
from app.models.finance import BudgetCategory, Revenue, Expense
from app.models.notification import Notification

def seed_dummy_data():
    """Populate all tables with dummy data"""
    db = SessionLocal()
    
    try:
        print("Starting dummy data seeding...")
        
        # Get roles
        admin_role = db.query(Role).filter(Role.name == "Admin").first()
        manager_role = db.query(Role).filter(Role.name == "Manager").first()
        staff_role = db.query(Role).filter(Role.name == "Staff").first()
        
        if not admin_role or not manager_role or not staff_role:
            print("ERROR: Roles not found. Please run init_db.py first.")
            return
        
        # 1. Users
        print("Creating users...")
        users_data = [
            {"email": "admin@erp.com", "full_name": "Admin User", "role": admin_role, "password": "admin123"},
            {"email": "manager@erp.com", "full_name": "Manager User", "role": manager_role, "password": "manager123"},
            {"email": "staff@erp.com", "full_name": "Staff User", "role": staff_role, "password": "staff123"},
            {"email": "john.doe@erp.com", "full_name": "John Doe", "role": staff_role, "password": "password123"},
            {"email": "jane.smith@erp.com", "full_name": "Jane Smith", "role": manager_role, "password": "password123"},
        ]
        
        users = []
        for user_data in users_data:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if not existing:
                user = User(
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    hashed_password=get_password_hash(user_data["password"]),
                    role_id=user_data["role"].id,
                    is_active=True
                )
                db.add(user)
                users.append(user)
            else:
                users.append(existing)
        
        db.commit()
        print(f"Created {len(users)} users")
        
        # 2. Categories
        print("Creating categories...")
        categories_data = [
            {"name": "Electronics", "description": "Electronic devices and components"},
            {"name": "Clothing", "description": "Apparel and fashion items"},
            {"name": "Food & Beverages", "description": "Food products and drinks"},
            {"name": "Furniture", "description": "Home and office furniture"},
            {"name": "Books", "description": "Books and publications"},
            {"name": "Sports & Outdoors", "description": "Sports equipment and outdoor gear"},
        ]
        
        categories = []
        for cat_data in categories_data:
            existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
            if not existing:
                category = Category(**cat_data)
                db.add(category)
                categories.append(category)
            else:
                categories.append(existing)
        
        db.commit()
        print(f"Created {len(categories)} categories")
        
        # 3. Suppliers
        print("Creating suppliers...")
        suppliers_data = [
            {"name": "TechSupply Co.", "email": "contact@techsupply.com", "phone": "+1-555-0101", 
             "address": "123 Tech Street, San Francisco, CA 94102", "is_active": True},
            {"name": "Global Fashion Ltd.", "email": "info@globalfashion.com", "phone": "+1-555-0102",
             "address": "456 Fashion Ave, New York, NY 10001", "is_active": True},
            {"name": "Fresh Foods Inc.", "email": "sales@freshfoods.com", "phone": "+1-555-0103",
             "address": "789 Farm Road, Austin, TX 78701", "is_active": True},
            {"name": "Furniture World", "email": "hello@furnitureworld.com", "phone": "+1-555-0104",
             "address": "321 Design Blvd, Los Angeles, CA 90001", "is_active": True},
            {"name": "Book Publishers LLC", "email": "orders@bookpub.com", "phone": "+1-555-0105",
             "address": "654 Library Lane, Boston, MA 02101", "is_active": True},
        ]
        
        suppliers = []
        for sup_data in suppliers_data:
            existing = db.query(Supplier).filter(Supplier.name == sup_data["name"]).first()
            if not existing:
                supplier = Supplier(**sup_data)
                db.add(supplier)
                suppliers.append(supplier)
            else:
                suppliers.append(existing)
        
        db.commit()
        print(f"Created {len(suppliers)} suppliers")
        
        # 4. Products
        print("Creating products...")
        products_data = [
            # Electronics
            {"name": "Laptop Pro 15", "description": "High-performance laptop with 16GB RAM", 
             "sku": "ELEC-LAP-001", "category": categories[0], "supplier": suppliers[0],
             "price": 1299.99, "cost": 800.00, "stock_quantity": 25, "min_stock_level": 5},
            {"name": "Wireless Mouse", "description": "Ergonomic wireless mouse", 
             "sku": "ELEC-MOU-002", "category": categories[0], "supplier": suppliers[0],
             "price": 29.99, "cost": 12.00, "stock_quantity": 150, "min_stock_level": 20},
            {"name": "USB-C Cable", "description": "Fast charging USB-C cable", 
             "sku": "ELEC-CAB-003", "category": categories[0], "supplier": suppliers[0],
             "price": 19.99, "cost": 5.00, "stock_quantity": 300, "min_stock_level": 50},
            {"name": "Smartphone X", "description": "Latest smartphone with 128GB storage", 
             "sku": "ELEC-PHO-004", "category": categories[0], "supplier": suppliers[0],
             "price": 899.99, "cost": 550.00, "stock_quantity": 40, "min_stock_level": 10},
            
            # Clothing
            {"name": "Cotton T-Shirt", "description": "Comfortable cotton t-shirt", 
             "sku": "CLOT-TSH-001", "category": categories[1], "supplier": suppliers[1],
             "price": 24.99, "cost": 8.00, "stock_quantity": 200, "min_stock_level": 30},
            {"name": "Denim Jeans", "description": "Classic blue denim jeans", 
             "sku": "CLOT-JEA-002", "category": categories[1], "supplier": suppliers[1],
             "price": 59.99, "cost": 25.00, "stock_quantity": 80, "min_stock_level": 15},
            {"name": "Winter Jacket", "description": "Warm winter jacket", 
             "sku": "CLOT-JAC-003", "category": categories[1], "supplier": suppliers[1],
             "price": 129.99, "cost": 60.00, "stock_quantity": 45, "min_stock_level": 10},
            
            # Food & Beverages
            {"name": "Organic Coffee Beans", "description": "Premium organic coffee beans", 
             "sku": "FOOD-COF-001", "category": categories[2], "supplier": suppliers[2],
             "price": 15.99, "cost": 7.00, "stock_quantity": 100, "min_stock_level": 20},
            {"name": "Green Tea", "description": "Premium green tea leaves", 
             "sku": "FOOD-TEA-002", "category": categories[2], "supplier": suppliers[2],
             "price": 12.99, "cost": 5.00, "stock_quantity": 150, "min_stock_level": 25},
            
            # Furniture
            {"name": "Office Chair", "description": "Ergonomic office chair", 
             "sku": "FURN-CHA-001", "category": categories[3], "supplier": suppliers[3],
             "price": 299.99, "cost": 150.00, "stock_quantity": 30, "min_stock_level": 5},
            {"name": "Desk Lamp", "description": "Modern LED desk lamp", 
             "sku": "FURN-LAM-002", "category": categories[3], "supplier": suppliers[3],
             "price": 49.99, "cost": 20.00, "stock_quantity": 60, "min_stock_level": 10},
            
            # Books
            {"name": "Python Programming", "description": "Learn Python programming", 
             "sku": "BOOK-PYT-001", "category": categories[4], "supplier": suppliers[4],
             "price": 39.99, "cost": 15.00, "stock_quantity": 50, "min_stock_level": 10},
            {"name": "Web Development Guide", "description": "Complete web development guide", 
             "sku": "BOOK-WEB-002", "category": categories[4], "supplier": suppliers[4],
             "price": 34.99, "cost": 12.00, "stock_quantity": 40, "min_stock_level": 8},
        ]
        
        products = []
        for prod_data in products_data:
            existing = db.query(Product).filter(Product.sku == prod_data["sku"]).first()
            if not existing:
                product = Product(
                    name=prod_data["name"],
                    description=prod_data["description"],
                    sku=prod_data["sku"],
                    category_id=prod_data["category"].id,
                    supplier_id=prod_data["supplier"].id,
                    price=prod_data["price"],
                    cost=prod_data["cost"],
                    stock_quantity=prod_data["stock_quantity"],
                    min_stock_level=prod_data["min_stock_level"],
                    is_active=True
                )
                db.add(product)
                products.append(product)
            else:
                products.append(existing)
        
        # Update some products to have low stock for testing
        db.commit()
        if products:
            # Make first 3 products have low stock
            for i, product in enumerate(products[:3]):
                product.stock_quantity = product.min_stock_level - randint(1, 5)
                db.add(product)
            db.commit()
        
        db.commit()
        print(f"Created {len(products)} products")
        
        # 5. Stock History
        print("Creating stock history...")
        for product in products[:5]:  # Add history for first 5 products
            for i in range(3):
                stock_history = StockHistory(
                    product_id=product.id,
                    quantity_change=randint(10, 50),
                    previous_quantity=product.stock_quantity - randint(10, 50),
                    new_quantity=product.stock_quantity,
                    reason=choice(["purchase", "sale", "adjustment"])
                )
                db.add(stock_history)
        
        db.commit()
        print("Created stock history records")
        
        # 6. Customers
        print("Creating customers...")
        customers_data = [
            {"name": "ABC Corporation", "email": "contact@abccorp.com", "phone": "+1-555-1001",
             "address": "100 Business Park, Chicago, IL 60601"},
            {"name": "XYZ Industries", "email": "info@xyzind.com", "phone": "+1-555-1002",
             "address": "200 Industrial Way, Detroit, MI 48201"},
            {"name": "Tech Solutions Inc.", "email": "sales@techsol.com", "phone": "+1-555-1003",
             "address": "300 Innovation Drive, Seattle, WA 98101"},
            {"name": "Retail Plus", "email": "orders@retailplus.com", "phone": "+1-555-1004",
             "address": "400 Commerce Street, Miami, FL 33101"},
            {"name": "Global Trading Co.", "email": "contact@globaltrade.com", "phone": "+1-555-1005",
             "address": "500 Trade Center, Houston, TX 77001"},
        ]
        
        customers = []
        for cust_data in customers_data:
            existing = db.query(Customer).filter(Customer.email == cust_data["email"]).first()
            if not existing:
                customer = Customer(**cust_data)
                db.add(customer)
                customers.append(customer)
            else:
                customers.append(existing)
        
        db.commit()
        print(f"Created {len(customers)} customers")
        
        # 7. Orders and Order Items
        print("Creating orders...")
        order_statuses = [OrderStatus.PENDING, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
        
        for i in range(15):
            customer = choice(customers)
            order_date = datetime.now() - timedelta(days=randint(0, 60))
            order_number = f"ORD-{order_date.strftime('%Y%m%d')}-{str(i+1).zfill(4)}"
            
            # Create order items
            num_items = randint(1, 4)
            selected_products = [choice(products) for _ in range(num_items)]
            
            total_amount = 0.0
            order_items = []
            for product in selected_products:
                quantity = randint(1, 5)
                unit_price = product.price
                subtotal = quantity * unit_price
                total_amount += subtotal
                
                order_item = OrderItem(
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal
                )
                order_items.append(order_item)
            
            discount = round(total_amount * uniform(0, 0.1), 2)  # 0-10% discount
            tax = round((total_amount - discount) * 0.08, 2)  # 8% tax
            
            order = Order(
                customer_id=customer.id,
                order_number=order_number,
                status=choice(order_statuses),
                total_amount=round(total_amount - discount + tax, 2),
                discount=discount,
                tax=tax,
                notes=f"Order #{i+1}",
                created_at=order_date
            )
            db.add(order)
            db.flush()  # Get order ID
            
            # Link order items to order
            for item in order_items:
                item.order_id = order.id
                db.add(item)
            
            # Update product stock
            for product, item in zip(selected_products, order_items):
                product.stock_quantity -= item.quantity
        
        db.commit()
        print("Created 15 orders with order items")
        
        # 8. Employees
        print("Creating employees...")
        employees_data = [
            {"employee_id": "EMP001", "first_name": "Michael", "last_name": "Johnson",
             "email": "michael.johnson@erp.com", "phone": "+1-555-2001",
             "position": "Software Engineer", "department": "IT", 
             "hire_date": date(2022, 1, 15), "salary": 85000.00, "is_active": True},
            {"employee_id": "EMP002", "first_name": "Sarah", "last_name": "Williams",
             "email": "sarah.williams@erp.com", "phone": "+1-555-2002",
             "position": "Sales Manager", "department": "Sales",
             "hire_date": date(2021, 6, 20), "salary": 75000.00, "is_active": True},
            {"employee_id": "EMP003", "first_name": "David", "last_name": "Brown",
             "email": "david.brown@erp.com", "phone": "+1-555-2003",
             "position": "Accountant", "department": "Finance",
             "hire_date": date(2023, 3, 10), "salary": 65000.00, "is_active": True},
            {"employee_id": "EMP004", "first_name": "Emily", "last_name": "Davis",
             "email": "emily.davis@erp.com", "phone": "+1-555-2004",
             "position": "HR Specialist", "department": "Human Resources",
             "hire_date": date(2022, 9, 5), "salary": 60000.00, "is_active": True},
            {"employee_id": "EMP005", "first_name": "Robert", "last_name": "Miller",
             "email": "robert.miller@erp.com", "phone": "+1-555-2005",
             "position": "Warehouse Manager", "department": "Operations",
             "hire_date": date(2021, 11, 12), "salary": 70000.00, "is_active": True},
        ]
        
        employees = []
        for emp_data in employees_data:
            existing = db.query(Employee).filter(Employee.employee_id == emp_data["employee_id"]).first()
            if not existing:
                employee = Employee(**emp_data)
                db.add(employee)
                employees.append(employee)
            else:
                employees.append(existing)
        
        db.commit()
        print(f"Created {len(employees)} employees")
        
        # 9. Attendance
        print("Creating attendance records...")
        attendance_statuses = [AttendanceStatus.PRESENT, AttendanceStatus.PRESENT, 
                               AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.LEAVE]
        
        for employee in employees:
            for i in range(20):  # Last 20 days
                att_date = date.today() - timedelta(days=i)
                status = choice(attendance_statuses)
                
                check_in = None
                check_out = None
                hours_worked = None
                
                if status == AttendanceStatus.PRESENT or status == AttendanceStatus.LATE:
                    check_in = datetime.combine(att_date, datetime.min.time().replace(hour=9, minute=randint(0, 30)))
                    check_out = datetime.combine(att_date, datetime.min.time().replace(hour=17, minute=randint(0, 30)))
                    hours_worked = 8.0
                elif status == AttendanceStatus.LEAVE:
                    hours_worked = 0.0
                
                attendance = Attendance(
                    employee_id=employee.id,
                    date=att_date,
                    status=status,
                    check_in=check_in,
                    check_out=check_out,
                    hours_worked=hours_worked
                )
                db.add(attendance)
        
        db.commit()
        print("Created attendance records")
        
        # 10. Performance
        print("Creating performance records...")
        for employee in employees:
            for i in range(2):  # 2 reviews per employee
                review_date = date.today() - timedelta(days=randint(30, 180))
                performance = Performance(
                    employee_id=employee.id,
                    review_date=review_date,
                    rating=randint(3, 5),
                    goals_achieved=randint(7, 10),
                    goals_total=10,
                    comments=f"Performance review for {employee.first_name} {employee.last_name}"
                )
                db.add(performance)
        
        db.commit()
        print("Created performance records")
        
        # 11. Payroll
        print("Creating payroll records...")
        for employee in employees:
            for i in range(3):  # Last 3 months
                period_end = date.today().replace(day=1) - timedelta(days=1) - timedelta(days=30*i)
                period_start = period_end.replace(day=1)
                
                base_salary = employee.salary
                bonuses = round(uniform(0, 2000), 2)
                deductions = round(uniform(500, 1500), 2)
                net_salary = base_salary + bonuses - deductions
                
                payroll = Payroll(
                    employee_id=employee.id,
                    pay_period_start=period_start,
                    pay_period_end=period_end,
                    base_salary=base_salary,
                    bonuses=bonuses,
                    deductions=deductions,
                    net_salary=net_salary,
                    status=choice(["paid", "pending"])
                )
                db.add(payroll)
        
        db.commit()
        print("Created payroll records")
        
        # 12. Budget Categories
        print("Creating budget categories...")
        budget_categories_data = [
            {"name": "Office Supplies", "description": "Office equipment and supplies", "monthly_budget": 5000.00},
            {"name": "Marketing", "description": "Marketing and advertising expenses", "monthly_budget": 10000.00},
            {"name": "Travel", "description": "Business travel expenses", "monthly_budget": 8000.00},
            {"name": "Utilities", "description": "Electricity, water, internet", "monthly_budget": 3000.00},
            {"name": "Maintenance", "description": "Equipment and facility maintenance", "monthly_budget": 4000.00},
        ]
        
        budget_categories = []
        for cat_data in budget_categories_data:
            existing = db.query(BudgetCategory).filter(BudgetCategory.name == cat_data["name"]).first()
            if not existing:
                category = BudgetCategory(**cat_data)
                db.add(category)
                budget_categories.append(category)
            else:
                budget_categories.append(existing)
        
        db.commit()
        print(f"Created {len(budget_categories)} budget categories")
        
        # 13. Expenses
        print("Creating expenses...")
        expense_vendors = ["Office Depot", "Amazon Business", "Staples", "FedEx", "Local Vendor"]
        
        for i in range(30):
            expense_date = date.today() - timedelta(days=randint(0, 90))
            category = choice(budget_categories)
            
            expense = Expense(
                category_id=category.id,
                amount=round(uniform(50, 2000), 2),
                description=f"Expense #{i+1} - {category.name}",
                vendor=choice(expense_vendors),
                date=expense_date
            )
            db.add(expense)
        
        db.commit()
        print("Created 30 expense records")
        
        # 14. Revenue
        print("Creating revenue records...")
        revenue_sources = ["sales", "services", "other"]
        
        for i in range(25):
            revenue_date = date.today() - timedelta(days=randint(0, 90))
            
            revenue = Revenue(
                source=choice(revenue_sources),
                amount=round(uniform(1000, 50000), 2),
                description=f"Revenue from {choice(revenue_sources)}",
                date=revenue_date
            )
            db.add(revenue)
        
        db.commit()
        print("Created 25 revenue records")
        
        # 15. Notifications
        print("Creating notifications...")
        notification_types = ["info", "warning", "error", "success"]
        notification_titles = [
            "New Order Received",
            "Low Stock Alert",
            "Payment Received",
            "System Update",
            "Meeting Reminder",
        ]
        
        for user in users[:3]:  # Notifications for first 3 users
            for i in range(5):
                notification = Notification(
                    user_id=user.id,
                    title=choice(notification_titles),
                    message=f"Notification message #{i+1} for {user.full_name}",
                    type=choice(notification_types),
                    is_read=choice([True, False])
                )
                db.add(notification)
        
        db.commit()
        print("Created notification records")
        
        print("\n" + "="*50)
        print("DUMMY DATA SEEDING COMPLETED SUCCESSFULLY!")
        print("="*50)
        print("\nTest Accounts Created:")
        print("  Admin:   admin@erp.com / admin123")
        print("  Manager: manager@erp.com / manager123")
        print("  Staff:   staff@erp.com / staff123")
        print("\nSummary:")
        print(f"  - {len(users)} users")
        print(f"  - {len(categories)} categories")
        print(f"  - {len(suppliers)} suppliers")
        print(f"  - {len(products)} products")
        print(f"  - {len(customers)} customers")
        print(f"  - 15 orders")
        print(f"  - {len(employees)} employees")
        print(f"  - {len(budget_categories)} budget categories")
        print(f"  - 30 expenses")
        print(f"  - 25 revenue records")
        print("="*50)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_dummy_data()

