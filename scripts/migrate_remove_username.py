"""Migration script to remove username column from users table"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    """Remove username column from users table"""
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Drop index if exists
                print("Dropping username index...")
                conn.execute(text("DROP INDEX IF EXISTS ix_users_username"))
                
                # Drop username column
                print("Dropping username column...")
                conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS username"))
                
                # Commit transaction
                trans.commit()
                print("[SUCCESS] Migration completed successfully!")
                
                # Verify
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    ORDER BY column_name
                """))
                columns = [row[0] for row in result]
                print(f"\nCurrent columns in users table: {', '.join(columns)}")
                
                if 'username' in columns:
                    print("[WARNING] Username column still exists!")
                else:
                    print("[SUCCESS] Username column successfully removed!")
                    
            except Exception as e:
                trans.rollback()
                print(f"[ERROR] Error during migration: {e}")
                raise
                
    except Exception as e:
        print(f"[ERROR] Connection error: {e}")
        print(f"Database URL: {settings.DATABASE_URL.split('@')[0]}@...")
        raise

if __name__ == "__main__":
    print("Starting migration: Remove username column")
    print("=" * 50)
    migrate()

