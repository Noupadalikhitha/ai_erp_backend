"""Add dummy data for development and testing

Revision ID: 001_add_dummy_data
Revises: 000_create_initial_schema
Create Date: 2025-12-09 00:00:00.000000

"""
from typing import Sequence, Union
from datetime import date, datetime, timedelta
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_add_dummy_data'
down_revision: str = '000_create_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a connection to insert data
    conn = op.get_bind()
    
    # 1. Insert Roles
    roles_data = [
        ('Admin', 'Administrator role with full access'),
        ('Manager', 'Manager role with limited admin access'),
        ('Staff', 'Staff role with basic access'),
    ]
    
    conn.execute(sa.text("""
        INSERT INTO roles (name, description, created_at) 
        VALUES (:name, :description, NOW())
        ON CONFLICT (name) DO NOTHING
    """), [{"name": r[0], "description": r[1]} for r in roles_data])
    
    # Get role IDs for reference
    role_admin = conn.execute(sa.text("SELECT id FROM roles WHERE name = 'Admin'")).scalar()
    role_manager = conn.execute(sa.text("SELECT id FROM roles WHERE name = 'Manager'")).scalar()
    role_staff = conn.execute(sa.text("SELECT id FROM roles WHERE name = 'Staff'")).scalar()
    
    # 2. Insert Users (using hashed passwords)
    users_data = [
        ('admin@erp.com', 'Admin User', role_admin),
        ('manager@erp.com', 'Manager User', role_manager),
        ('staff@erp.com', 'Staff User', role_staff),
        ('john.doe@erp.com', 'John Doe', role_staff),
        ('jane.smith@erp.com', 'Jane Smith', role_manager),
    ]

    # Generate bcrypt hashes using passlib to ensure compatibility with application
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    password_map = {
        'admin@erp.com': 'admin123',
        'manager@erp.com': 'manager123',
        'staff@erp.com': 'staff123',
        'john.doe@erp.com': 'password123',
        'jane.smith@erp.com': 'password123',
    }

    hashed_map = {email: pwd_context.hash(pw) for email, pw in password_map.items()}

    for email, full_name, role_id in users_data:
        hashed_password = hashed_map.get(email) or pwd_context.hash('password123')
        conn.execute(sa.text("""
            INSERT INTO users (email, hashed_password, full_name, is_active, role_id, created_at)
            VALUES (:email, :hashed_password, :full_name, true, :role_id, NOW())
            ON CONFLICT (email) DO NOTHING
        """), {
            "email": email,
            "hashed_password": hashed_password,
            "full_name": full_name,
            "role_id": role_id
        })
    
    # 3. Insert Categories
    categories_data = [
        ('Electronics', 'Electronic devices and components'),
        ('Clothing', 'Apparel and fashion items'),
        ('Food & Beverages', 'Food products and drinks'),
        ('Furniture', 'Home and office furniture'),
        ('Books', 'Books and publications'),
        ('Sports & Outdoors', 'Sports equipment and outdoor gear'),
    ]
    
    for name, description in categories_data:
        conn.execute(sa.text("""
            INSERT INTO categories (name, description, created_at)
            VALUES (:name, :description, NOW())
            ON CONFLICT (name) DO NOTHING
        """), {"name": name, "description": description})
    
    # 4. Insert Suppliers
    suppliers_data = [
        ('TechSupply Co.', 'contact@techsupply.com', '+1-555-0101', '123 Tech Street, San Francisco, CA 94102', True),
        ('Global Fashion Ltd.', 'info@globalfashion.com', '+1-555-0102', '456 Fashion Ave, New York, NY 10001', True),
        ('Fresh Foods Inc.', 'sales@freshfoods.com', '+1-555-0103', '789 Farm Road, Austin, TX 78701', True),
        ('Furniture World', 'hello@furnitureworld.com', '+1-555-0104', '321 Design Blvd, Los Angeles, CA 90001', True),
        ('Book Publishers LLC', 'orders@bookpub.com', '+1-555-0105', '654 Library Lane, Boston, MA 02101', True),
    ]
    
    for name, email, phone, address, is_active in suppliers_data:
        conn.execute(sa.text("""
            INSERT INTO suppliers (name, email, phone, address, is_active, created_at)
            VALUES (:name, :email, :phone, :address, :is_active, NOW())
        """), {"name": name, "email": email, "phone": phone, "address": address, "is_active": is_active})
    
    # 5. Insert Products
    products_data = [
        # Electronics
        ('Laptop Pro 15', 'High-performance laptop with 16GB RAM', 'ELEC-LAP-001', 'Electronics', 'TechSupply Co.', 1299.99, 800.00, 25, 5),
        ('Wireless Mouse', 'Ergonomic wireless mouse', 'ELEC-MOU-002', 'Electronics', 'TechSupply Co.', 29.99, 12.00, 150, 20),
        ('USB-C Cable', 'Fast charging USB-C cable', 'ELEC-CAB-003', 'Electronics', 'TechSupply Co.', 19.99, 5.00, 300, 50),
        ('Smartphone X', 'Latest smartphone with 128GB storage', 'ELEC-PHO-004', 'Electronics', 'TechSupply Co.', 899.99, 550.00, 40, 10),
        # Clothing
        ('Cotton T-Shirt', 'Comfortable cotton t-shirt', 'CLOT-TSH-001', 'Clothing', 'Global Fashion Ltd.', 24.99, 8.00, 200, 30),
        ('Denim Jeans', 'Classic blue denim jeans', 'CLOT-JEA-002', 'Clothing', 'Global Fashion Ltd.', 59.99, 25.00, 80, 15),
        ('Winter Jacket', 'Warm winter jacket', 'CLOT-JAC-003', 'Clothing', 'Global Fashion Ltd.', 129.99, 60.00, 45, 10),
        # Food & Beverages
        ('Organic Coffee Beans', 'Premium organic coffee beans', 'FOOD-COF-001', 'Food & Beverages', 'Fresh Foods Inc.', 15.99, 7.00, 100, 20),
        ('Green Tea', 'Premium green tea leaves', 'FOOD-TEA-002', 'Food & Beverages', 'Fresh Foods Inc.', 12.99, 5.00, 150, 25),
        # Furniture
        ('Office Chair', 'Ergonomic office chair', 'FURN-CHA-001', 'Furniture', 'Furniture World', 299.99, 150.00, 30, 5),
        ('Desk Lamp', 'Modern LED desk lamp', 'FURN-LAM-002', 'Furniture', 'Furniture World', 49.99, 20.00, 60, 10),
        # Books
        ('Python Programming', 'Learn Python programming', 'BOOK-PYT-001', 'Books', 'Book Publishers LLC', 39.99, 15.00, 50, 10),
        ('Web Development Guide', 'Complete web development guide', 'BOOK-WEB-002', 'Books', 'Book Publishers LLC', 34.99, 12.00, 40, 8),
    ]
    
    for name, description, sku, category_name, supplier_name, price, cost, stock, min_stock in products_data:
        conn.execute(sa.text("""
            INSERT INTO products (name, description, sku, category_id, supplier_id, price, cost, stock_quantity, min_stock_level, is_active, created_at)
            SELECT :name, :description, :sku, c.id, s.id, :price, :cost, :stock, :min_stock, true, NOW()
            FROM categories c, suppliers s
            WHERE c.name = :category_name AND s.name = :supplier_name
            ON CONFLICT (sku) DO NOTHING
        """), {
            "name": name, "description": description, "sku": sku, "category_name": category_name,
            "supplier_name": supplier_name, "price": price, "cost": cost, "stock": stock, "min_stock": min_stock
        })
    
    # 6. Insert Customers
    customers_data = [
        ('ABC Corporation', 'contact@abccorp.com', '+1-555-1001', '100 Business Park, Chicago, IL 60601'),
        ('XYZ Industries', 'info@xyzind.com', '+1-555-1002', '200 Industrial Way, Detroit, MI 48201'),
        ('Tech Solutions Inc.', 'sales@techsol.com', '+1-555-1003', '300 Innovation Drive, Seattle, WA 98101'),
        ('Retail Plus', 'orders@retailplus.com', '+1-555-1004', '400 Commerce Street, Miami, FL 33101'),
        ('Global Trading Co.', 'contact@globaltrade.com', '+1-555-1005', '500 Trade Center, Houston, TX 77001'),
    ]
    
    for name, email, phone, address in customers_data:
        conn.execute(sa.text("""
            INSERT INTO customers (name, email, phone, address, created_at)
            VALUES (:name, :email, :phone, :address, NOW())
            ON CONFLICT DO NOTHING
        """), {"name": name, "email": email, "phone": phone, "address": address})
    
    # 7. Insert Employees
    employees_data = [
        ('EMP001', 'Michael', 'Johnson', 'michael.johnson@erp.com', '+1-555-2001', 'Software Engineer', 'IT', date(2022, 1, 15), 85000.00, True),
        ('EMP002', 'Sarah', 'Williams', 'sarah.williams@erp.com', '+1-555-2002', 'Sales Manager', 'Sales', date(2021, 6, 20), 75000.00, True),
        ('EMP003', 'David', 'Brown', 'david.brown@erp.com', '+1-555-2003', 'Accountant', 'Finance', date(2023, 3, 10), 65000.00, True),
        ('EMP004', 'Emily', 'Davis', 'emily.davis@erp.com', '+1-555-2004', 'HR Specialist', 'Human Resources', date(2022, 9, 5), 60000.00, True),
        ('EMP005', 'Robert', 'Miller', 'robert.miller@erp.com', '+1-555-2005', 'Warehouse Manager', 'Operations', date(2021, 11, 12), 70000.00, True),
    ]
    
    for emp_id, first_name, last_name, email, phone, position, department, hire_date, salary, is_active in employees_data:
        conn.execute(sa.text("""
            INSERT INTO employees (employee_id, first_name, last_name, email, phone, position, department, hire_date, salary, is_active, created_at)
            VALUES (:employee_id, :first_name, :last_name, :email, :phone, :position, :department, :hire_date, :salary, :is_active, NOW())
            ON CONFLICT (employee_id) DO NOTHING
        """), {
            "employee_id": emp_id, "first_name": first_name, "last_name": last_name, "email": email,
            "phone": phone, "position": position, "department": department, "hire_date": hire_date,
            "salary": salary, "is_active": is_active
        })
    
    # 8. Insert Budget Categories
    budget_categories_data = [
        ('Office Supplies', 'Office equipment and supplies', 5000.00),
        ('Marketing', 'Marketing and advertising expenses', 10000.00),
        ('Travel', 'Business travel expenses', 8000.00),
        ('Utilities', 'Electricity, water, internet', 3000.00),
        ('Maintenance', 'Equipment and facility maintenance', 4000.00),
    ]
    
    for name, description, monthly_budget in budget_categories_data:
        conn.execute(sa.text("""
            INSERT INTO budget_categories (name, description, monthly_budget, created_at)
            VALUES (:name, :description, :monthly_budget, NOW())
            ON CONFLICT (name) DO NOTHING
        """), {"name": name, "description": description, "monthly_budget": monthly_budget})
    
    # 9. Insert Orders (simplified - just a few to avoid complexity)
    conn.execute(sa.text("""
        INSERT INTO orders (customer_id, order_number, status, total_amount, discount, tax, created_at)
        SELECT c.id, 'ORD-2025-0001', 'PENDING'::orderstatus, 2500.00, 250.00, 180.00, NOW()
        FROM customers c WHERE c.name = 'ABC Corporation'
        ON CONFLICT DO NOTHING
    """))
    
    conn.execute(sa.text("""
        INSERT INTO orders (customer_id, order_number, status, total_amount, discount, tax, created_at)
        SELECT c.id, 'ORD-2025-0002', 'DELIVERED'::orderstatus, 1500.00, 100.00, 110.00, NOW()
        FROM customers c WHERE c.name = 'XYZ Industries'
        ON CONFLICT DO NOTHING
    """))
    
    # 10. Insert Notifications
    conn.execute(sa.text("""
        INSERT INTO notifications (user_id, title, message, type, is_read, created_at)
        SELECT u.id, 'Welcome to ERP System', 'Welcome! Your account has been created.', 'info', false, NOW()
        FROM users u WHERE u.email = 'admin@erp.com'
        ON CONFLICT DO NOTHING
    """))
    
    conn.commit()


def downgrade() -> None:
    # Delete all dummy data in reverse order
    conn = op.get_bind()
    
    # Delete notifications first (no FK constraints to this table from others)
    conn.execute(sa.text("DELETE FROM notifications WHERE title LIKE 'Welcome to ERP%'"))
    
    # Delete orders and related data
    conn.execute(sa.text("DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE order_number LIKE 'ORD-2025%')"))
    conn.execute(sa.text("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_number LIKE 'ORD-2025%')"))
    conn.execute(sa.text("DELETE FROM orders WHERE order_number LIKE 'ORD-2025%'"))
    
    # Delete other data
    conn.execute(sa.text("DELETE FROM expenses WHERE description LIKE 'Expense #%'"))
    conn.execute(sa.text("DELETE FROM budget_categories WHERE name IN ('Office Supplies', 'Marketing', 'Travel', 'Utilities', 'Maintenance')"))
    conn.execute(sa.text("DELETE FROM payroll WHERE created_at > NOW() - INTERVAL '1 year'"))
    conn.execute(sa.text("DELETE FROM performance WHERE employee_id IN (SELECT id FROM employees WHERE employee_id LIKE 'EMP%')"))
    conn.execute(sa.text("DELETE FROM attendance WHERE employee_id IN (SELECT id FROM employees WHERE employee_id LIKE 'EMP%')"))
    conn.execute(sa.text("DELETE FROM employees WHERE employee_id LIKE 'EMP%'"))
    conn.execute(sa.text("DELETE FROM stock_history WHERE product_id IN (SELECT id FROM products WHERE sku LIKE '%LAP%' OR sku LIKE '%MOU%')"))
    conn.execute(sa.text("DELETE FROM products WHERE sku LIKE 'ELEC-%' OR sku LIKE 'CLOT-%' OR sku LIKE 'FOOD-%' OR sku LIKE 'FURN-%' OR sku LIKE 'BOOK-%'"))
    conn.execute(sa.text("DELETE FROM customers WHERE email LIKE '%@abc%' OR email LIKE '%@xyz%' OR email LIKE '%@tech%' OR email LIKE '%@retail%' OR email LIKE '%@global%'"))
    conn.execute(sa.text("DELETE FROM suppliers WHERE name IN ('TechSupply Co.', 'Global Fashion Ltd.', 'Fresh Foods Inc.', 'Furniture World', 'Book Publishers LLC')"))
    conn.execute(sa.text("DELETE FROM categories WHERE name IN ('Electronics', 'Clothing', 'Food & Beverages', 'Furniture', 'Books', 'Sports & Outdoors')"))
    conn.execute(sa.text("DELETE FROM users WHERE email IN ('admin@erp.com', 'manager@erp.com', 'staff@erp.com', 'john.doe@erp.com', 'jane.smith@erp.com')"))
    conn.execute(sa.text("DELETE FROM roles WHERE name IN ('Admin', 'Manager', 'Staff')"))
    
    conn.commit()
