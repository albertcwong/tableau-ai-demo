"""add agent configs and migrate preferred_agent_type

Revision ID: x_add_agent_configs
Revises: w_add_standard_auth
Create Date: 2026-02-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'x_add_agent_configs'
down_revision: Union[str, Sequence[str], None] = 'w_add_standard_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create agent_configs table
    op.create_table(
        'agent_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.String(length=50), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=text('true')),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=text('false')),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('max_build_retries', sa.Integer(), nullable=True),
        sa.Column('max_execution_retries', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_name', 'version', name='uq_agent_config_name_version'),
    )
    op.create_index(op.f('ix_agent_configs_id'), 'agent_configs', ['id'], unique=False)
    op.create_index(op.f('ix_agent_configs_agent_name'), 'agent_configs', ['agent_name'], unique=False)
    op.create_index(op.f('ix_agent_configs_is_enabled'), 'agent_configs', ['is_enabled'], unique=False)
    op.create_index(op.f('ix_agent_configs_is_default'), 'agent_configs', ['is_default'], unique=False)
    op.create_index(op.f('ix_agent_configs_created_at'), 'agent_configs', ['created_at'], unique=False)
    op.create_index('idx_agent_config_name_default', 'agent_configs', ['agent_name', 'is_default'], unique=False)

    # Seed initial data
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    now_str = now.strftime('%Y-%m-%d %H:%M:%S.%f')
    
    # Insert VizQL versions
    op.execute(text(f"""
        INSERT INTO agent_configs (agent_name, version, is_enabled, is_default, description, created_at, updated_at)
        VALUES 
        ('vizql', 'v1', true, false, 'Original multi-node graph', '{now_str}', '{now_str}'),
        ('vizql', 'v2', true, false, 'Tool-use pattern', '{now_str}', '{now_str}'),
        ('vizql', 'v3', true, true, 'Streamlined 4-node graph', '{now_str}', '{now_str}')
    """))
    
    # Insert VizQL settings (agent-level config)
    op.execute(text(f"""
        INSERT INTO agent_configs (agent_name, version, is_enabled, is_default, max_build_retries, max_execution_retries, created_at, updated_at)
        VALUES ('vizql', 'settings', true, false, 3, 3, '{now_str}', '{now_str}')
    """))
    
    # Insert Summary version
    op.execute(text(f"""
        INSERT INTO agent_configs (agent_name, version, is_enabled, is_default, description, created_at, updated_at)
        VALUES ('summary', 'v1', true, true, 'Multi-view export and summarization', '{now_str}', '{now_str}')
    """))

    # Migrate User.preferred_agent_type: 'general' -> 'vizql' or null
    op.execute(text("""
        UPDATE users 
        SET preferred_agent_type = 'vizql' 
        WHERE preferred_agent_type = 'general'
    """))


def downgrade() -> None:
    # Revert User.preferred_agent_type migration (can't reliably restore 'general' since we don't know original)
    # Just set to null for safety
    op.execute(text("""
        UPDATE users 
        SET preferred_agent_type = NULL 
        WHERE preferred_agent_type = 'vizql'
    """))
    
    # Drop agent_configs table
    op.drop_index('idx_agent_config_name_default', table_name='agent_configs')
    op.drop_index(op.f('ix_agent_configs_created_at'), table_name='agent_configs')
    op.drop_index(op.f('ix_agent_configs_is_default'), table_name='agent_configs')
    op.drop_index(op.f('ix_agent_configs_is_enabled'), table_name='agent_configs')
    op.drop_index(op.f('ix_agent_configs_agent_name'), table_name='agent_configs')
    op.drop_index(op.f('ix_agent_configs_id'), table_name='agent_configs')
    op.drop_constraint('uq_agent_config_name_version', 'agent_configs', type_='unique')
    op.drop_table('agent_configs')
