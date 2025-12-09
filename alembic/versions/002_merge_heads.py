"""Merge conflicting migration heads

Revision ID: 002_merge_heads
Revises: 001_add_dummy_data
Create Date: 2025-12-09 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_merge_heads'
down_revision: str = '001_add_dummy_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration resolves the multiple head revisions issue
    # by being an explicit single head that depends on 001_add_dummy_data
    pass


def downgrade() -> None:
    pass
