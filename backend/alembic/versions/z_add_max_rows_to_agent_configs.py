"""add max_rows to agent_configs

Revision ID: z_add_max_rows_to_agent_configs
Revises: y_add_connected_app_oauth
Create Date: 2026-02-13 14:44:40.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'z_add_max_rows_to_agent_configs'
down_revision: Union[str, Sequence[str], None] = 'ae_unique_url_ssl_cert'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add max_rows column to agent_configs
    op.add_column('agent_configs', sa.Column('max_rows', sa.Integer(), nullable=True, comment='Summary-specific: max rows per view for REST API data fetch'))
    
    # Seed summary settings row with default max_rows=5000 if it doesn't exist
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    now_str = now.strftime('%Y-%m-%d %H:%M:%S.%f')
    
    # Check if summary settings row exists, if not create it
    op.execute(text(f"""
        INSERT INTO agent_configs (agent_name, version, is_enabled, is_default, max_rows, created_at, updated_at)
        SELECT 'summary', 'settings', true, false, 5000, '{now_str}', '{now_str}'
        WHERE NOT EXISTS (
            SELECT 1 FROM agent_configs 
            WHERE agent_name = 'summary' AND version = 'settings'
        )
    """))
    
    # Update existing summary settings row to have default max_rows if null
    op.execute(text("""
        UPDATE agent_configs 
        SET max_rows = 5000 
        WHERE agent_name = 'summary' AND version = 'settings' AND max_rows IS NULL
    """))


def downgrade() -> None:
    # Remove max_rows column
    op.drop_column('agent_configs', 'max_rows')
