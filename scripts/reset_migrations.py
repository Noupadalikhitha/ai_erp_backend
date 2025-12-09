#!/usr/bin/env python
"""
Clean migration history and reinitialize for fresh deployment.
This handles the case where old migration entries exist in alembic_version table.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(dotenv_path=env_path)

from sqlalchemy import create_engine, text
from app.core.config import settings

def reset_migrations():
    """Reset Alembic migration state for fresh deployment"""
    
    try:
        engine = create_engine(settings.DATABASE_URL)
        
        print("Resetting Alembic migration state...")
        
        with engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'alembic_version'
                )
            """))
            
            table_exists = result.scalar()
            
            if table_exists:
                # Clear all versions
                conn.execute(text("DELETE FROM alembic_version"))
                print("✓ Cleared alembic_version table")
                conn.commit()
            else:
                print("✓ alembic_version table doesn't exist yet")
        
        print("\nMigration state reset complete.")
        print("Run 'alembic upgrade head' to apply all migrations.\n")
        return True
        
    except Exception as e:
        print(f"Error resetting migrations: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = reset_migrations()
    sys.exit(0 if success else 1)
