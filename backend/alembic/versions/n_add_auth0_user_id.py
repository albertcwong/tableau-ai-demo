"""add_auth0_user_id

Revision ID: n_add_auth0_user_id
Revises: 699d5a09c000
Create Date: 2026-02-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'n_add_auth0_user_id'
down_revision: Union[str, Sequence[str], None] = '699d5a09c000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auth0_user_id column to users table."""
    conn = op.get_bind()
    
    # Check if auth0_user_id column already exists
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'users' 
            AND column_name = 'auth0_user_id'
        )
    """)).scalar()
    
    if not column_exists:
        # Add auth0_user_id column
        op.add_column('users', sa.Column('auth0_user_id', sa.String(255), nullable=True))
        
        # Create unique index
        op.create_index('ix_users_auth0_user_id', 'users', ['auth0_user_id'], unique=True)
        
        # Make password_hash nullable (for Auth0 users)
        op.alter_column('users', 'password_hash', nullable=True)
    else:
        print("Column auth0_user_id already exists, skipping migration")


def downgrade() -> None:
    """Remove auth0_user_id column from users table."""
    conn = op.get_bind()
    
    # Check if auth0_user_id column exists
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'users' 
            AND column_name = 'auth0_user_id'
        )
    """)).scalar()
    
    if column_exists:
        # Drop index first
        op.drop_index('ix_users_auth0_user_id', table_name='users')
        
        # Drop column
        op.drop_column('users', 'auth0_user_id')
        
        # Note: We don't make password_hash NOT NULL again as there might be Auth0 users
        # If you need to enforce NOT NULL, do it manually after ensuring no Auth0 users exist
