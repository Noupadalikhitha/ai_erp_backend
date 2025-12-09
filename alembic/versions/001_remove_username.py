"""remove username column

Revision ID: 001_remove_username
Revises: 
Create Date: 2024-12-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_remove_username'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop username column from users table
    op.drop_index('ix_users_username', table_name='users', if_exists=True)
    op.drop_column('users', 'username')


def downgrade() -> None:
    # Add username column back
    op.add_column('users', sa.Column('username', sa.String(), nullable=False))
    op.create_index('ix_users_username', 'users', ['username'], unique=True)



