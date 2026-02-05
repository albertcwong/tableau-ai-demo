"""change provider_type from enum to varchar

Revision ID: i_provider_type_varchar
Revises: h_add_provider_configs
Create Date: 2026-02-04 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'i_provider_type_varchar'
down_revision: Union[str, Sequence[str], None] = 'h_add_provider_configs'
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
        # Change provider_type column from enum to VARCHAR
        conn.execute(text("""
            ALTER TABLE provider_configs 
            ALTER COLUMN provider_type TYPE VARCHAR(20) 
            USING provider_type::text
        """))
        
        # Check if constraint already exists
        constraint_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 
                FROM pg_constraint 
                WHERE conname = 'provider_type_check'
            )
        """)).scalar()
        
        # Add check constraint only if it doesn't exist
        if not constraint_exists:
            conn.execute(text("""
                ALTER TABLE provider_configs 
                ADD CONSTRAINT provider_type_check 
                CHECK (provider_type IN ('openai', 'anthropic', 'salesforce', 'vertex', 'apple_endor'))
            """))
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Remove check constraint
    conn.execute(text("""
        ALTER TABLE provider_configs 
        DROP CONSTRAINT IF EXISTS provider_type_check
    """))
    
    # Change back to enum type (assuming enum still exists)
    enum_exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'provider_type')")).scalar()
    if enum_exists:
        conn.execute(text("""
            ALTER TABLE provider_configs 
            ALTER COLUMN provider_type TYPE provider_type 
            USING provider_type::provider_type
        """))
        conn.commit()
