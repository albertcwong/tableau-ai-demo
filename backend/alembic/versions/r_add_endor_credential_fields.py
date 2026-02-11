"""add endor credential fields

Revision ID: r_add_endor_credential_fields
Revises: q_add_auth0_tableau_metadata
Create Date: 2026-02-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'r_add_endor_credential_fields'
down_revision: Union[str, Sequence[str], None] = 'q_add_auth0_tableau_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    
    # Check if provider_configs table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_name = 'provider_configs'
        )
    """)).scalar()
    
    if table_exists:
        # Add new Endor credential columns if they don't exist
        columns_to_add = [
            ('apple_endor_app_id', 'VARCHAR(255)', 'Apple Endor App ID for A3 token generation'),
            ('apple_endor_app_password', 'VARCHAR(500)', 'Apple Endor App Password for A3 token generation'),
            ('apple_endor_other_app', 'INTEGER', 'Apple Endor otherApp parameter (default: 199323)'),
            ('apple_endor_context', 'VARCHAR(100)', "Apple Endor context parameter (default: ''endor'')"),
            ('apple_endor_one_time_token', 'BOOLEAN', 'Apple Endor oneTimeToken flag'),
        ]
        
        for col_name, col_type, col_comment in columns_to_add:
            col_exists = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'provider_configs' 
                    AND column_name = '{col_name}'
                )
            """)).scalar()
            
            if not col_exists:
                conn.execute(text(f"""
                    ALTER TABLE provider_configs 
                    ADD COLUMN {col_name} {col_type}
                """))
                
                # Add comment if PostgreSQL
                if col_comment:
                    conn.execute(text(f"""
                        COMMENT ON COLUMN provider_configs.{col_name} IS '{col_comment}'
                    """))
        
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Check if provider_configs table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_name = 'provider_configs'
        )
    """)).scalar()
    
    if table_exists:
        # Remove Endor credential columns
        columns_to_remove = [
            'apple_endor_app_id',
            'apple_endor_app_password',
            'apple_endor_other_app',
            'apple_endor_context',
            'apple_endor_one_time_token',
        ]
        
        for col_name in columns_to_remove:
            col_exists = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'provider_configs' 
                    AND column_name = '{col_name}'
                )
            """)).scalar()
            
            if col_exists:
                conn.execute(text(f"""
                    ALTER TABLE provider_configs 
                    DROP COLUMN {col_name}
                """))
        
        conn.commit()
