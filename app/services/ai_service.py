import os
import re
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.core.database import Base, engine
from app.core.config import settings

# Groq Model configuration - Using currently supported models
GROQ_MODEL_CHAT = "llama-3.3-70b-versatile"
GROQ_MODEL_SQL = "llama-3.3-70b-versatile"

# Lazy import and initialization of Groq
_groq_client = None

def get_groq_client():
    """Get or create the Groq client (lazy initialization)"""
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            import httpx
            
            # Create httpx client without proxies argument
            http_client = httpx.Client(timeout=30.0)
            _groq_client = Groq(api_key=settings.GROQ_API_KEY, http_client=http_client)
        except Exception as e:
            print(f"SDK initialization failed: {e}, attempting REST API fallback")
            # Return a flag to indicate REST API should be used
            _groq_client = "rest_api"
    return _groq_client

def call_groq_chat(messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 512, model: str = GROQ_MODEL_CHAT) -> str:
    """Call Groq API with fallback to REST if SDK fails"""
    client = get_groq_client()
    
    if client == "rest_api":
        # Use REST API directly
        import httpx
        import json
        
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            with httpx.Client(timeout=60.0) as http_client:
                response = http_client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            raise RuntimeError(f"REST API call failed: {str(e)}")
    else:
        # Use SDK
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"SDK call failed: {str(e)}")


def get_db_schema() -> str:
    """Inspects the database schema and returns a string representation."""
    inspector = inspect(engine)
    schema_str = ""
    for table_name in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns(table_name)]
        schema_str += f"- {table_name} ({', '.join(columns)})\n"
    return schema_str

def is_conversational_query(query: str) -> bool:
    """
    Check if a query is conversational.
    """
    conversational_keywords = [
        "hello", "hi", "how are you", "thank you", "thanks", "bye", "goodbye",
        "what can you do", "help", "who are you", "what is your name", "tell me a joke", "hai"
    ]
    query_cleaned = re.sub(r'[^\w\s]', '', query.lower()).strip()
    
    for keyword in conversational_keywords:
        if query_cleaned.startswith(keyword) or query_cleaned == keyword:
            return True

    return False

def get_conversational_response(query: str) -> str:
    """
    Generate a friendly, conversational response, deflecting unrelated questions.
    """
    unrelated_keywords = ["movie", "song", "weather", "capital", "sport", "game", "recipe"]
    if any(keyword in query.lower() for keyword in unrelated_keywords):
        return "I can only answer questions related to our business topics like sales, inventory, finance, and employees. How can I help you with those?"

    # Friendly greeting for simple hellos
    if query.lower().strip() in ["hi", "hello", "hai"]:
        return "Hi there! How can I help you today?"

    # Generic conversational prompt
    prompt = f"User says: '{query}'. Respond in a friendly, brief, and helpful manner. Your name is Blu. You assist with business-related questions."
    
    return call_groq_chat(
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant named Blu. Keep your responses concise and professional."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=150
    )

# SQL generation prompt template
SQL_GENERATION_PROMPT = """
You are a SQL expert. Convert the following natural language query into a PostgreSQL SELECT statement.

Database Schema:
{schema}

IMPORTANT ENUM VALUES:
- OrderStatus: 'PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED' (stored in UPPERCASE)
- ExpenseType: 'OFFICE_SUPPLIES', 'UTILITIES', 'MAINTENANCE', 'SALARIES', 'TRAVEL', 'OTHER'
- Department: 'SALES', 'MARKETING', 'HR', 'FINANCE', 'OPERATIONS'

CRITICAL RULES FOR ENUM COLUMNS:
- For OrderStatus comparisons, ALWAYS use: WHERE status = 'UPPERCASE_VALUE'::orderstatus
- PostgreSQL enum values are case-sensitive - use UPPERCASE for comparison values
- Example: WHERE status = 'DELIVERED'::orderstatus (NOT 'delivered')

Rules:
1. Only generate SELECT queries.
2. Use proper JOINs and table aliases.
3. Use aggregate functions when appropriate.
4. For date-related queries, use functions like `CURRENT_DATE`, `NOW()`, and `INTERVAL`.
5. If a query is ambiguous, generate the most likely and useful query.
6. If the query is conversational or clearly unrelated to the schema (e.g., "what is the capital of France"), return an empty string.
7. WHEN FILTERING BY ENUM VALUES, ALWAYS use the type cast syntax: 'value'::enumtype
8. Return only the SQL query, no explanations or markdown.

User Query: {query}

SQL Query:
"""

def sanitize_sql(query: str) -> str:
    """Remove dangerous SQL operations and ensure it's a SELECT statement."""
    query = query.strip()
    if not query.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    
    # Check for dangerous keywords with word boundaries to avoid false positives
    # (e.g., 'PROCESSING' contains 'CREATE' but is not a SQL command)
    dangerous_keywords = ['DELETE', 'DROP', 'TRUNCATE', 'UPDATE', 'INSERT', 'ALTER', 'EXEC', 'EXECUTE']
    query_upper = query.upper()
    
    for keyword in dangerous_keywords:
        # Use word boundaries to avoid matching keywords inside strings or other identifiers
        pattern = rf'\b{keyword}\b'
        if re.search(pattern, query_upper):
            raise ValueError(f"Dangerous SQL operation detected: {keyword}")
            
    return query

def normalize_enum_values(sql: str) -> str:
    """
    Normalize enum values in SQL queries to match database enum definitions.
    PostgreSQL enums are case-sensitive and stored in UPPERCASE.
    Converts common variations to proper UPPERCASE enum values and adds type casts.
    """
    # First, normalize case variations to UPPERCASE
    enum_mappings = {
        # OrderStatus variations - convert to UPPERCASE
        r"'delivered'": "'DELIVERED'",
        r"'Delivered'": "'DELIVERED'",
        r"'DELIVERED'": "'DELIVERED'",
        r"'pending'": "'PENDING'",
        r"'Pending'": "'PENDING'",
        r"'PENDING'": "'PENDING'",
        r"'processing'": "'PROCESSING'",
        r"'Processing'": "'PROCESSING'",
        r"'PROCESSING'": "'PROCESSING'",
        r"'shipped'": "'SHIPPED'",
        r"'Shipped'": "'SHIPPED'",
        r"'SHIPPED'": "'SHIPPED'",
        r"'cancelled'": "'CANCELLED'",
        r"'Cancelled'": "'CANCELLED'",
        r"'CANCELLED'": "'CANCELLED'",
    }
    
    result = sql
    for pattern, replacement in enum_mappings.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    # Now add type casts for enum comparisons, but avoid double-casting
    # For OrderStatus: convert = 'VALUE' to = 'VALUE'::orderstatus (but not if already has ::)
    orderstatus_values = ['PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED']
    for value in orderstatus_values:
        # Match status = 'VALUE' that doesn't already have :: after it
        pattern = rf"(status\s*=\s*)'{value}'(?!::)"
        replacement = rf"\1'{value}'::orderstatus"
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        # Handle IN clause - add casts to bare enum values
        pattern = rf"(IN\s*\([^)]*?)'{value}'(?!::)([^)]*\))"
        replacement = rf"\1'{value}'::orderstatus\2"
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result

def generate_sql_from_natural_language(query: str) -> str:
    """Generate SQL from natural language using Groq."""
    db_schema = get_db_schema()
    prompt = SQL_GENERATION_PROMPT.format(schema=db_schema, query=query)
    
    sql = call_groq_chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1024,
        model=GROQ_MODEL_SQL
    )
    
    sql = re.sub(r'```sql\n?', '', sql)
    sql = re.sub(r'```\n?', '', sql)
    sql = sql.strip().replace(';', '')
    
    if not sql:
        return ""

    # Normalize enum values before sanitizing
    sql = normalize_enum_values(sql)
    return sanitize_sql(sql)

def execute_sql_query(db: Session, sql: str) -> List[Dict]:
    """Execute SQL query and return results."""
    try:
        result = db.execute(text(sql))
        columns = result.keys()
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        raise ValueError(f"Error executing SQL: {str(e)}")

def generate_natural_language_summary(query: str, results: List[Dict]) -> str:
    """Generate natural language summary of query results."""
    if not results:
        return "I couldn't find any data for your request. Please try asking in a different way."
        
    try:
        results_summary = str(results[:5]) # Limit sample size
        prompt = f"""
        User's original query: "{query}"
        Query Results (sample): {results_summary}
        Total results found: {len(results)}
        
        Provide a clear, concise, and natural language summary of these results.
        - Interpret the data and explain what it means in a business context.
        - If it's a number, explain what it represents (e.g., "The total sales for the last week were...").
        - Do not just repeat the data. Summarize the key insights.
        - Keep the tone professional and helpful.
        - Do not mention that you are summarizing data or showing results. Just give the answer.
        """
        
        return call_groq_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=512
        )
    except Exception as e:
        return f"Found {len(results)} results, but couldn't summarize them due to an error."

def get_data_response(db: Session, query: str) -> str:
    """
    Generates a data-driven response by converting a natural language query to SQL,
    executing it, and summarizing the results.
    """
    try:
        sql_query = generate_sql_from_natural_language(query)
        if not sql_query:
            # If no SQL was generated, it might be a complex conversational query
            # that is_conversational_query missed.
            return get_conversational_response(query)
            
        results = execute_sql_query(db, sql_query)
        summary = generate_natural_language_summary(query, results)
        return summary
    except ValueError as ve:
        # This could be a sanitization error or other controlled error
        return f"I'm sorry, there was an issue processing your request. ({str(ve)})"
    except Exception as e:
        # General unexpected errors
        return f"An unexpected error occurred. Please try again. ({str(e)})"

def forecast_sales(db: Session, days: int) -> Dict:
    """Placeholder for sales forecast"""
    # In a real implementation, you would use a time series model (e.g., ARIMA, Prophet)
    # This is a dummy implementation
    last_30_days_sales = np.random.randint(50, 200, size=30)
    future_sales = last_30_days_sales.mean() + np.random.randn(days) * 20
    
    forecast_dates = [datetime.now().date() + timedelta(days=i) for i in range(days)]
    
    return {
        "forecast": [
            {"date": d.isoformat(), "predicted_sales": max(0, s)}
            for d, s in zip(forecast_dates, future_sales)
        ],
        "confidence_interval": 0.95
    }

def predict_stock_out_date(db: Session, product_id: int) -> Dict:
    """Placeholder for predicting stock-out date"""
    # Dummy implementation
    # In a real implementation, you'd analyze sales velocity
    from app.models.inventory import Product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or product.stock_quantity <= 0:
        return {"product_id": product_id, "predicted_stock_out_date": "Out of stock"}
    
    sales_per_day = np.random.uniform(1, 5) # Dummy sales rate
    days_left = product.stock_quantity / sales_per_day
    
    stock_out_date = datetime.now().date() + timedelta(days=days_left)
    
    return {
        "product_id": product_id,
        "product_name": product.name,
        "predicted_stock_out_date": stock_out_date.isoformat(),
        "current_stock": product.stock_quantity
    }

def recommend_reorder_quantity(db: Session, product_id: int) -> Dict:
    """Placeholder for reorder quantity recommendation"""
    # Dummy implementation
    from app.models.inventory import Product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return {"error": "Product not found"}
        
    safety_stock = 50 # Dummy value
    lead_time_demand = 100 # Dummy value
    
    reorder_point = product.min_stock_level or 20
    recommended_quantity = max(0, reorder_point + safety_stock - product.stock_quantity + lead_time_demand)
    
    return {
        "product_id": product_id,
        "product_name": product.name,
        "current_stock": product.stock_quantity,
        "recommended_reorder_quantity": int(recommended_quantity)
    }

def detect_anomalies(db: Session, entity_type: str) -> Dict:
    """Placeholder for anomaly detection"""
    # Dummy implementation using standard deviation
    if entity_type == "expenses":
        from app.models.finance import Expense
        data = db.query(Expense.amount).all()
        amounts = [d[0] for d in data]
        
    elif entity_type == "attendance":
        # Assuming you have an attendance model
        amounts = np.random.randint(80, 100, size=50) # Dummy attendance percentages
        
    else:
        return {"error": "Invalid entity type"}

    mean = np.mean(amounts)
    std_dev = np.std(amounts)
    anomalies = [a for a in amounts if a > mean + 2 * std_dev or a < mean - 2 * std_dev]
    
    return {
        "entity_type": entity_type,
        "anomalies_detected": len(anomalies),
        "summary": f"Detected {len(anomalies)} anomalies from {len(amounts)} records."
    }