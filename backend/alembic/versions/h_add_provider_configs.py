"""add provider_configs table

Revision ID: h_add_provider_configs
Revises: g_add_api_version
Create Date: 2026-02-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'h_add_provider_configs'
down_revision: Union[str, Sequence[str], None] = 'g_add_api_version'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    
    # Create provider_type enum if it doesn't exist
    enum_exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'provider_type')")).scalar()
    if not enum_exists:
        conn.execute(text("CREATE TYPE provider_type AS ENUM ('openai', 'anthropic', 'salesforce', 'vertex', 'apple_endor')"))
        conn.commit()
    
    # Check if provider_configs table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_name = 'provider_configs'
        )
    """)).scalar()
    
    if not table_exists:
        # Create provider_configs table
        conn.execute(text("""
            CREATE TABLE provider_configs (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                provider_type provider_type NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                api_key VARCHAR(500),
                salesforce_client_id VARCHAR(255),
                salesforce_private_key_path VARCHAR(500),
                salesforce_username VARCHAR(255),
                salesforce_models_api_url VARCHAR(500),
                vertex_project_id VARCHAR(255),
                vertex_location VARCHAR(100),
                vertex_service_account_path VARCHAR(500),
                apple_endor_endpoint VARCHAR(500)
            )
        """))
        conn.commit()
        
        # Create indexes
        indexes = [
            ('ix_provider_configs_id', 'CREATE INDEX ix_provider_configs_id ON provider_configs (id)'),
            ('ix_provider_configs_provider_type', 'CREATE INDEX ix_provider_configs_provider_type ON provider_configs (provider_type)'),
            ('ix_provider_configs_is_active', 'CREATE INDEX ix_provider_configs_is_active ON provider_configs (is_active)'),
            ('ix_provider_configs_created_at', 'CREATE INDEX ix_provider_configs_created_at ON provider_configs (created_at)'),
            ('idx_provider_config_type_active', 'CREATE INDEX idx_provider_config_type_active ON provider_configs (provider_type, is_active)'),
        ]
        
        for idx_name, idx_sql in indexes:
            idx_exists = conn.execute(text(
                f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{idx_name}')"
            )).scalar()
            if not idx_exists:
                conn.execute(text(idx_sql))
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Drop provider_configs table if it exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_name = 'provider_configs'
        )
    """)).scalar()
    
    if table_exists:
        conn.execute(text("DROP TABLE provider_configs"))
        conn.commit()
    
    # Drop provider_type enum if it exists and no other tables use it
    enum_exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'provider_type')")).scalar()
    if enum_exists:
        # Check if any other tables use this enum
        enum_in_use = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE udt_name = 'provider_type'
            )
        """)).scalar()
        
        if not enum_in_use:
            conn.execute(text("DROP TYPE provider_type"))
            conn.commit()
