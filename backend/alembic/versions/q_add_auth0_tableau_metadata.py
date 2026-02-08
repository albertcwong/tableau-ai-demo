"""add_auth0_tableau_metadata

Revision ID: q_add_auth0_tableau_metadata
Revises: p_add_auth0_client_credentials
Create Date: 2026-02-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'q_add_auth0_tableau_metadata'
down_revision: Union[str, Sequence[str], None] = 'p_add_auth0_client_credentials'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auth0_tableau_metadata_field to auth_configs and tableau_username to users."""
    conn = op.get_bind()
    
    # Add auth0_tableau_metadata_field to auth_configs
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'auth_configs'
            AND column_name = 'auth0_tableau_metadata_field'
        )
    """)).scalar()
    
    if not column_exists:
        op.add_column('auth_configs', 
            sa.Column('auth0_tableau_metadata_field', sa.String(255), nullable=True,
                     comment='Auth0 metadata field name to extract Tableau username (e.g., "app_metadata.tableau_username" or "tableau_username")'))
        print("Added auth0_tableau_metadata_field column to auth_configs table")
    else:
        print("Column auth0_tableau_metadata_field already exists, skipping migration")
    
    # Add tableau_username to users
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'users'
            AND column_name = 'tableau_username'
        )
    """)).scalar()
    
    if not column_exists:
        op.add_column('users',
            sa.Column('tableau_username', sa.String(255), nullable=True,
                     comment='Tableau username extracted from Auth0 metadata'))
        print("Added tableau_username column to users table")
    else:
        print("Column tableau_username already exists, skipping migration")


def downgrade() -> None:
    """Remove auth0_tableau_metadata_field and tableau_username columns."""
    conn = op.get_bind()
    
    # Remove tableau_username from users
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'users'
            AND column_name = 'tableau_username'
        )
    """)).scalar()
    
    if column_exists:
        op.drop_column('users', 'tableau_username')
        print("Removed tableau_username column from users table")
    
    # Remove auth0_tableau_metadata_field from auth_configs
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'auth_configs'
            AND column_name = 'auth0_tableau_metadata_field'
        )
    """)).scalar()
    
    if column_exists:
        op.drop_column('auth_configs', 'auth0_tableau_metadata_field')
        print("Removed auth0_tableau_metadata_field column from auth_configs table")
