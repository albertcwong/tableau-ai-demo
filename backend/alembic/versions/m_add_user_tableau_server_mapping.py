"""add user tableau server mapping table

Revision ID: m_user_tableau_mapping
Revises: l_add_conversation_user_id
Create Date: 2026-02-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'm_user_tableau_mapping'
down_revision: Union[str, Sequence[str], None] = 'l_add_conversation_user_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    
    # Check if table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'user_tableau_server_mappings'
        )
    """)).scalar()
    
    if not table_exists:
        # Create user_tableau_server_mappings table
        conn.execute(text("""
            CREATE TABLE user_tableau_server_mappings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                tableau_server_config_id INTEGER NOT NULL,
                site_id VARCHAR(100),
                tableau_username VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                CONSTRAINT fk_user_tableau_mapping_user 
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_user_tableau_mapping_config 
                    FOREIGN KEY (tableau_server_config_id) REFERENCES tableau_server_configs(id) ON DELETE CASCADE
            )
        """))
        conn.commit()
        
        # Create indexes
        conn.execute(text("CREATE INDEX ix_user_tableau_server_mappings_id ON user_tableau_server_mappings (id)"))
        conn.execute(text("CREATE INDEX ix_user_tableau_server_mappings_user_id ON user_tableau_server_mappings (user_id)"))
        conn.execute(text("CREATE INDEX ix_user_tableau_server_mappings_tableau_server_config_id ON user_tableau_server_mappings (tableau_server_config_id)"))
        conn.execute(text("CREATE INDEX ix_user_tableau_server_mappings_created_at ON user_tableau_server_mappings (created_at)"))
        
        # Create unique constraint for user_id + tableau_server_config_id + site_id
        # Use COALESCE to treat NULL site_id as empty string for uniqueness (allows one default site mapping per user+config)
        conn.execute(text("""
            CREATE UNIQUE INDEX idx_user_tableau_mapping_unique 
            ON user_tableau_server_mappings (user_id, tableau_server_config_id, COALESCE(site_id, ''))
        """))
        
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Drop table if it exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'user_tableau_server_mappings'
        )
    """)).scalar()
    
    if table_exists:
        conn.execute(text("DROP TABLE IF EXISTS user_tableau_server_mappings CASCADE"))
        conn.commit()
