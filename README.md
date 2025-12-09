# AI-Powered ERP System - Backend

A full-stack Enterprise Resource Planning (ERP) system with integrated AI capabilities, built with FastAPI and PostgreSQL.

## Overview

This backend application provides comprehensive ERP functionality including:
- **Employee Management** - Track employees, roles, and organizational structure
- **Finance Management** - Handle accounting, expenses, and financial reporting
- **Inventory Management** - Manage stock, products, and warehouse operations
- **Sales Management** - Process orders, track sales, and manage customers
- **AI Integration** - Leverage AI for analytics, forecasting, and intelligent recommendations
- **Authentication & Authorization** - Secure role-based access control
- **Admin Controls** - System administration and user management

## Tech Stack

- **Framework**: FastAPI 0.104.1
- **Server**: Uvicorn
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Authentication**: JWT with Python-Jose and bcrypt
- **AI/ML**: Groq, FAISS, Pandas, Scikit-learn, StatsModels
- **Validation**: Pydantic V2
- **File Processing**: Pillow, ReportLab
- **Vector Database**: pgvector

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── admin.py          # Admin endpoints
│   │       ├── ai.py             # AI service endpoints
│   │       ├── auth.py           # Authentication endpoints
│   │       ├── employee.py        # Employee management
│   │       ├── finance.py         # Finance operations
│   │       ├── inventory.py       # Inventory management
│   │       ├── sales.py           # Sales operations
│   │       └── dependencies.py    # FastAPI dependencies
│   ├── core/
│   │   ├── config.py             # Configuration settings
│   │   ├── database.py           # Database connection
│   │   ├── permissions.py        # Permission logic
│   │   └── security.py           # Security utilities
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── employee.py
│   │   ├── finance.py
│   │   ├── inventory.py
│   │   ├── sales.py
│   │   └── notification.py
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/
│   │   └── ai_service.py         # AI service logic
│   └── main.py                   # FastAPI app setup
├── alembic/                      # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── scripts/                      # Utility scripts
│   ├── init_db.py               # Initialize database
│   ├── seed_dummy_data.py        # Seed test data
│   └── migrate_*.py              # Migration scripts
├── requirements.txt              # Python dependencies
├── run.py                        # Application entry point
├── alembic.ini                   # Alembic configuration
├── Dockerfile                    # Container configuration
└── README.md                     # This file
```

## Installation

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- pip or conda

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   Create a `.env` file in the root directory with the following variables:
   ```env
   # Database
   DATABASE_URL=postgresql://user:password@localhost:5432/erp_db
   
   # Security
   SECRET_KEY=your-secret-key-here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   
   # AI Service
   GROQ_API_KEY=your-groq-api-key
   
   # Email (optional)
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   EMAIL_FROM=your-email@example.com
   ```

5. **Initialize database**
   ```bash
   python scripts/init_db.py
   ```

6. **Run migrations**
   ```bash
   alembic upgrade head
   ```

7. **Seed test data (optional)**
   ```bash
   python scripts/seed_dummy_data.py
   ```

## Running the Application

### Development Mode
```bash
python run.py
```

The API will be available at `http://localhost:8000`

### Production Mode
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once the application is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - User logout

### Employees
- `GET /api/v1/employees` - List employees
- `POST /api/v1/employees` - Create employee
- `GET /api/v1/employees/{id}` - Get employee details
- `PUT /api/v1/employees/{id}` - Update employee
- `DELETE /api/v1/employees/{id}` - Delete employee

### Finance
- `GET /api/v1/finance/expenses` - List expenses
- `POST /api/v1/finance/expenses` - Create expense
- `GET /api/v1/finance/reports` - Financial reports

### Inventory
- `GET /api/v1/inventory/products` - List products
- `POST /api/v1/inventory/products` - Create product
- `GET /api/v1/inventory/stock` - Check stock levels

### Sales
- `GET /api/v1/sales/orders` - List orders
- `POST /api/v1/sales/orders` - Create order
- `GET /api/v1/sales/analytics` - Sales analytics

### AI Services
- `POST /api/v1/ai/analyze` - AI analysis
- `POST /api/v1/ai/predict` - Predictions
- `GET /api/v1/ai/insights` - AI insights

### Admin
- `GET /api/v1/admin/users` - Manage users
- `POST /api/v1/admin/users/{id}/permissions` - Set permissions

## Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback to previous migration:
```bash
alembic downgrade -1
```

## Docker

Build and run with Docker:

```bash
# Build image
docker build -t erp-backend .

# Run container
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:password@db:5432/erp_db" \
  -e SECRET_KEY="your-secret-key" \
  erp-backend
```

## Testing

Run unit tests:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=app --cov-report=html
```

## Features

### Authentication & Security
- JWT-based authentication
- Password hashing with bcrypt
- Role-based access control (RBAC)
- Permission-based authorization

### Database
- SQLAlchemy ORM for data models
- Alembic for version control of schema
- PostgreSQL with pgvector for AI capabilities

### AI Integration
- Groq API integration for AI processing
- FAISS for similarity search
- Predictive analytics with scikit-learn
- Statistical analysis with StatsModels

### Data Processing
- Pandas for data manipulation
- Pillow for image processing
- ReportLab for PDF generation
- NumPy for numerical operations

## Best Practices

- Always use migrations for database schema changes
- Validate input using Pydantic schemas
- Use dependency injection for database connections
- Implement proper error handling and logging
- Follow RESTful API conventions
- Use CORS middleware carefully in production

## Troubleshooting

### Database Connection Issues
- Verify PostgreSQL is running
- Check DATABASE_URL environment variable
- Ensure database user has proper permissions

### Migration Errors
- Check alembic/versions for conflicting migrations
- Use `alembic current` to see current revision
- Review migration scripts for SQL syntax errors

### Import Errors
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`
- Check Python version compatibility

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and migrations
4. Submit a pull request

## License

[Add your license here]

## Support

For issues, questions, or contributions, please create an issue in the repository.

## Changelog

### Version 1.0.0
- Initial release with core ERP functionality
- AI integration with Groq API
- PostgreSQL database with SQLAlchemy ORM
- JWT authentication and RBAC
