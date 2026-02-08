"""add_auth_config

Revision ID: o_add_auth_config
Revises: n_add_auth0_user_id
Create Date: 2026-02-07 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'o_add_auth_config'
down_revision: Union[str, Sequence[str], None] = 'n_add_auth0_user_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auth_configs table for dynamic authentication configuration."""
    conn = op.get_bind()
    
    # Check if auth_configs table already exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'auth_configs'
        )
    """)).scalar()
    
    if not table_exists:
        # Create auth_configs table
        op.create_table(
            'auth_configs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('enable_password_auth', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('enable_oauth_auth', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('auth0_domain', sa.String(255), nullable=True),
            sa.Column('auth0_audience', sa.String(255), nullable=True),
            sa.Column('auth0_issuer', sa.String(255), nullable=True),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes
        op.create_index('ix_auth_configs_id', 'auth_configs', ['id'])
        op.create_index('idx_auth_config_active', 'auth_configs', ['enable_password_auth', 'enable_oauth_auth'])
        op.create_index('ix_auth_configs_updated_at', 'auth_configs', ['updated_at'])
        op.create_index('ix_auth_configs_created_at', 'auth_configs', ['created_at'])
        
        # Insert default config (password auth enabled, OAuth disabled)
        conn.execute(text("""
            INSERT INTO auth_configs (enable_password_auth, enable_oauth_auth, created_at, updated_at)
            VALUES (true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """))
    else:
        print("Table auth_configs already exists, skipping migration")


def downgrade() -> None:
    """Remove auth_configs table."""
    conn = op.get_bind()
    
    # Check if auth_configs table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'auth_configs'
        )
    """)).scalar()
    
    if table_exists:
        # Drop indexes
        op.drop_index('ix_auth_configs_created_at', table_name='auth_configs')
        op.drop_index('ix_auth_configs_updated_at', table_name='auth_configs')
        op.drop_index('idx_auth_config_active', table_name='auth_configs')
        op.drop_index('ix_auth_configs_id', table_name='auth_configs')
        
        # Drop table
        op.drop_table('auth_configs')
