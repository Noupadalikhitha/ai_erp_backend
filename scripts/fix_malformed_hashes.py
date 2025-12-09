#!/usr/bin/env python3
"""
Fix malformed bcrypt hashes in the `users` table.

This script scans `users.hashed_password` and replaces values that are not
valid bcrypt hashes with a newly generated bcrypt hash for a temporary
password (`password123`). After running, you should force users to reset
their passwords or notify them of new credentials.

Usage (local):
  python scripts/fix_malformed_hashes.py

Be careful running this against production databases. Prefer running in a
maintenance window and change the temporary password to a secure value.
"""
import re
import sys
from pathlib import Path

# allow importing app modules
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from sqlalchemy import create_engine, text
from app.core.config import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def is_valid_bcrypt(h: str) -> bool:
    if not isinstance(h, str):
        return False
    # bcrypt hashes normally start with $2b$, $2a$, or $2y$ and are 60 chars
    return h.startswith(('$2b$', '$2a$', '$2y$')) and len(h) == 60

def fix_hashes(temporary_password: str = 'password123') -> int:
    engine = create_engine(settings.DATABASE_URL)
    updated = 0
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, email, hashed_password FROM users")).fetchall()
        if not rows:
            print('No users found.')
            return 0

        bad = []
        for row in rows:
            uid, email, h = row
            if not is_valid_bcrypt(h):
                bad.append((uid, email))

        if not bad:
            print('No malformed bcrypt hashes found.')
            return 0

        print(f'Found {len(bad)} users with malformed hashes. Replacing...')
        for uid, email in bad:
            new_hash = pwd_context.hash(temporary_password)
            conn.execute(
                text('UPDATE users SET hashed_password = :h WHERE id = :id'),
                {'h': new_hash, 'id': uid}
            )
            updated += 1

    print(f'Updated {updated} user password hashes. Temporary password: {temporary_password}')
    print('Please force password reset for affected users or notify them to change their password.')
    return updated

if __name__ == '__main__':
    count = fix_hashes()
    sys.exit(0 if count >= 0 else 1)
