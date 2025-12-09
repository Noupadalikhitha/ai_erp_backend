"""Initialize database with default roles"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import SessionLocal, engine, Base
from app.models.user import Role

def init_db():
    """Create tables and default roles"""
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Create default roles if they don't exist
        roles = [
            {"name": "Admin", "description": "Full system access"},
            {"name": "Manager", "description": "Management access"},
            {"name": "Staff", "description": "Standard user access"}
        ]
        
        for role_data in roles:
            existing = db.query(Role).filter(Role.name == role_data["name"]).first()
            if not existing:
                role = Role(**role_data)
                db.add(role)
        
        db.commit()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()

