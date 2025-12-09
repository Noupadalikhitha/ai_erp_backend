"""
Migration script to add expense_type column to expenses table
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SessionLocal

# Ensure stdout can handle Unicode characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def migrate():
    print("Starting migration: Add expense_type column to expenses table")
    print("==================================================")
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'expenses' AND column_name = 'expense_type'
        """)).fetchone()
        
        if result:
            print("[INFO] expense_type column already exists. Skipping migration.")
        else:
            # Add expense_type column with default value
            print("Adding expense_type column...")
            db.execute(text("""
                ALTER TABLE expenses 
                ADD COLUMN expense_type VARCHAR DEFAULT 'other'
            """))
            
            # Update existing records to have 'other' as default if null
            db.execute(text("""
                UPDATE expenses 
                SET expense_type = 'other' 
                WHERE expense_type IS NULL
            """))
            
            db.commit()
            print("[SUCCESS] Migration completed successfully!")
        
        # Verify changes
        print("\nCurrent columns in expenses table:")
        result = db.execute(text("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns 
            WHERE table_name = 'expenses'
            ORDER BY ordinal_position
        """)).fetchall()
        
        for row in result:
            print(f"  {row[0]}: {row[1]} (default: {row[2]})")
        
        if any(row[0] == 'expense_type' for row in result):
            print("[SUCCESS] expense_type column successfully added!")

    except Exception as e:
        print(f"[ERROR] Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

