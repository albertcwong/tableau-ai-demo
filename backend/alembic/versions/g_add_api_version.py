"""add api_version to tableau_server_configs

Revision ID: g_add_api_version
Revises: f_add_user_and_tableau_config
Create Date: 2026-02-04 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'g_add_api_version'
down_revision: Union[str, Sequence[str], None] = 'f_add_user_and_tableau_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    
    # Check if api_version column exists
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'tableau_server_configs' 
            AND column_name = 'api_version'
        )
    """)).scalar()
    
    if not column_exists:
        # Add api_version column with default value
        conn.execute(text("""
            ALTER TABLE tableau_server_configs 
            ADD COLUMN api_version VARCHAR(20) DEFAULT '3.15'
        """))
        conn.commit()
        
        # Update existing rows to have the default value
        conn.execute(text("""
            UPDATE tableau_server_configs 
            SET api_version = '3.15' 
            WHERE api_version IS NULL
        """))
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Check if api_version column exists before dropping
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'tableau_server_configs' 
            AND column_name = 'api_version'
        )
    """)).scalar()
    
    if column_exists:
        conn.execute(text("""
            ALTER TABLE tableau_server_configs 
            DROP COLUMN api_version
        """))
        conn.commit()
