#!/usr/bin/env python3
"""scripts/fix_malformed_hashes.py

Improved CLI for detecting and optionally repairing malformed bcrypt hashes
in the `users.hashed_password` column.

Features:
- `--dry-run` : report affected rows without modifying the database
- `--password` : set temporary password used when repairing (default: password123)
- `--csv` : write affected users to a CSV file with columns `id,email`

Usage:
  python scripts/fix_malformed_hashes.py --dry-run
  python scripts/fix_malformed_hashes.py --password S3cur3P@ss --csv bad_users.csv

Be cautious running this on production. Prefer maintenance windows and
notify users to change their password after repairs.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Tuple

# allow importing app modules
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text
from app.core.config import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def is_valid_bcrypt(h: str | None) -> bool:
    if not isinstance(h, str):
        return False
    # bcrypt hashes normally start with $2b$, $2a$, or $2y$ and are 60 chars
    return h.startswith(('$2b$', '$2a$', '$2y$')) and len(h) == 60


def find_bad_hashes(engine) -> List[Tuple[int, str]]:
    """Return list of tuples (id, email) for rows with malformed hashes."""
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, email, hashed_password FROM users")).fetchall()
    bad: List[Tuple[int, str]] = []
    for uid, email, h in rows:
        if not is_valid_bcrypt(h):
            bad.append((uid, email))
    return bad


def repair_hashes(engine, bad: List[Tuple[int, str]], temporary_password: str) -> int:
    updated = 0
    new_hash = pwd_context.hash(temporary_password)
    with engine.begin() as conn:
        for uid, _ in bad:
            conn.execute(
                text('UPDATE users SET hashed_password = :h WHERE id = :id'),
                {'h': new_hash, 'id': uid}
            )
            updated += 1
    return updated


def write_csv(path: Path, bad: List[Tuple[int, str]]):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'email'])
        writer.writerows(bad)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Detect and repair malformed bcrypt hashes')
    parser.add_argument('--dry-run', action='store_true', help='Only report affected rows')
    parser.add_argument('--password', type=str, default='password123', help='Temporary password to set when repairing')
    parser.add_argument('--csv', type=Path, help='Write affected users to this CSV file')
    args = parser.parse_args(argv)

    engine = create_engine(settings.DATABASE_URL)

    bad = find_bad_hashes(engine)
    if not bad:
        print('No malformed bcrypt hashes found.')
        return 0

    print(f'Found {len(bad)} users with malformed bcrypt hashes.')
    if args.csv:
        write_csv(args.csv, bad)
        print(f'Wrote affected users to {args.csv}')

    if args.dry_run:
        # Print sample rows and exit
        for uid, email in bad[:50]:
            print(f'id={uid}, email={email}')
        if len(bad) > 50:
            print(f'... and {len(bad)-50} more rows')
        return 0

    # Repair
    updated = repair_hashes(engine, bad, args.password)
    print(f'Updated {updated} user password hashes. Temporary password: {args.password}')
    print('Please force password reset for affected users or notify them to change their password.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
