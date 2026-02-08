"""add_auth0_client_credentials

Revision ID: p_add_auth0_client_credentials
Revises: o_add_auth_config
Create Date: 2026-02-07 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'p_add_auth0_client_credentials'
down_revision: Union[str, Sequence[str], None] = 'o_add_auth_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auth0_client_id and auth0_client_secret to auth_configs table."""
    conn = op.get_bind()
    
    # Check if columns already exist
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'auth_configs'
            AND column_name = 'auth0_client_id'
        )
    """)).scalar()
    
    if not column_exists:
        # Add auth0_client_id column
        op.add_column('auth_configs', 
            sa.Column('auth0_client_id', sa.String(255), nullable=True, 
                     comment='Auth0 SPA client ID (public, safe to store in DB)'))
        
        # Add auth0_client_secret column (for server-side token exchange if needed)
        op.add_column('auth_configs',
            sa.Column('auth0_client_secret', sa.String(512), nullable=True,
                     comment='Auth0 client secret (for server-side token exchange, optional for SPAs)'))
        
        print("Added auth0_client_id and auth0_client_secret columns to auth_configs table")
    else:
        print("Columns auth0_client_id and auth0_client_secret already exist, skipping migration")


def downgrade() -> None:
    """Remove auth0_client_id and auth0_client_secret columns."""
    conn = op.get_bind()
    
    # Check if columns exist
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'auth_configs'
            AND column_name = 'auth0_client_id'
        )
    """)).scalar()
    
    if column_exists:
        op.drop_column('auth_configs', 'auth0_client_secret')
        op.drop_column('auth_configs', 'auth0_client_id')
        print("Removed auth0_client_id and auth0_client_secret columns from auth_configs table")
    else:
        print("Columns auth0_client_id and auth0_client_secret do not exist, skipping downgrade")
