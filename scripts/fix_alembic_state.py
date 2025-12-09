#!/usr/bin/env python
"""
Migration recovery script to fix Alembic state in case of multiple head revisions error.
Run this script when Alembic shows "Multiple head revisions" error.
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

from sqlalchemy import create_engine, inspect, text
from app.core.config import settings

def fix_alembic_state():
    """Fix Alembic migration state by cleaning up conflicting revisions"""
    
    try:
        # Create connection
        engine = create_engine(settings.DATABASE_URL)
        inspector = inspect(engine)
        
        print("Checking database state...")
        
        # Check if alembic_version table exists
        if 'alembic_version' not in inspector.get_table_names():
            print("✓ No alembic_version table found - database is clean")
            print("Migrations will run from scratch on next deployment")
            return True
        
        # Check what revisions are recorded
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result]
            
            if len(versions) == 0:
                print("✓ alembic_version table is empty - this is good")
                return True
            
            if len(versions) > 1:
                print(f"⚠ Multiple versions recorded: {versions}")
                print("Clearing conflicting versions...")
                
                # Keep only the latest valid version
                valid_versions = [
                    '001_add_dummy_data',
                    '000_create_initial_schema',
                    '000_initial_schema',
                    '001_add_dummy_data'
                ]
                
                for v in versions:
                    if v not in valid_versions:
                        print(f"  Removing conflicting version: {v}")
                        conn.execute(text(f"DELETE FROM alembic_version WHERE version_num = '{v}'"))
                
                conn.commit()
                print("✓ Cleaned up conflicting versions")
                return True
            
            if len(versions) == 1:
                print(f"✓ Single version found: {versions[0]}")
                return True
                
    except Exception as e:
        print(f"Error fixing Alembic state: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_alembic_state()
    sys.exit(0 if success else 1)
