"""remove_site_id_from_user_tableau_mapping

Revision ID: 14b767a79488
Revises: 7494e4ec5486
Create Date: 2026-02-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '14b767a79488'
down_revision: Union[str, Sequence[str], None] = '7494e4ec5486'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    
    # Check if site_id column exists
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'user_tableau_server_mappings'
            AND column_name = 'site_id'
        )
    """)).scalar()
    
    if column_exists:
        # Drop the unique constraint that includes site_id
        conn.execute(text("""
            DROP INDEX IF EXISTS idx_user_tableau_mapping_unique
        """))
        
        # Remove site_id column
        conn.execute(text("""
            ALTER TABLE user_tableau_server_mappings 
            DROP COLUMN site_id
        """))
        
        # Recreate unique constraint without site_id
        # One mapping per user per Connected App (site comes from config)
        conn.execute(text("""
            CREATE UNIQUE INDEX idx_user_tableau_mapping_unique 
            ON user_tableau_server_mappings (user_id, tableau_server_config_id)
        """))
        
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Check if site_id column exists
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'user_tableau_server_mappings'
            AND column_name = 'site_id'
        )
    """)).scalar()
    
    if not column_exists:
        # Drop the unique constraint
        conn.execute(text("""
            DROP INDEX IF EXISTS idx_user_tableau_mapping_unique
        """))
        
        # Add site_id column back
        conn.execute(text("""
            ALTER TABLE user_tableau_server_mappings 
            ADD COLUMN site_id VARCHAR(100)
        """))
        
        # Recreate unique constraint with site_id
        conn.execute(text("""
            CREATE UNIQUE INDEX idx_user_tableau_mapping_unique 
            ON user_tableau_server_mappings (user_id, tableau_server_config_id, COALESCE(site_id, ''))
        """))
        
        conn.commit()
