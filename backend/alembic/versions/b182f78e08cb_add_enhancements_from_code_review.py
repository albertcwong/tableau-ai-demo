"""add_enhancements_from_code_review

Revision ID: b182f78e08cb
Revises: 7cd98763c15e
Create Date: 2026-02-01 18:54:17.172917

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b182f78e08cb'
down_revision: Union[str, Sequence[str], None] = '7cd98763c15e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum type for message roles (lowercase to match Python enum values)
    message_role_enum = sa.Enum('user', 'assistant', 'system', name='message_role')
    message_role_enum.create(op.get_bind(), checkfirst=True)
    
    # Add new columns to datasources
    op.add_column('datasources', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('datasources', sa.Column('size_bytes', sa.BigInteger(), nullable=True))
    op.add_column('datasources', sa.Column('row_count', sa.BigInteger(), nullable=True))
    op.add_column('datasources', sa.Column('extra_metadata', sa.JSON(), nullable=True))
    op.add_column('datasources', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.create_index('idx_datasource_active', 'datasources', ['is_active'], unique=False)
    op.create_index('idx_datasource_synced', 'datasources', ['last_synced_at'], unique=False)
    op.create_index(op.f('ix_datasources_is_active'), 'datasources', ['is_active'], unique=False)
    op.create_index(op.f('ix_datasources_last_synced_at'), 'datasources', ['last_synced_at'], unique=False)
    
    # Add new columns to messages
    op.add_column('messages', sa.Column('tokens_used', sa.BigInteger(), nullable=True))
    op.add_column('messages', sa.Column('extra_metadata', sa.JSON(), nullable=True))
    
    # Convert role column from VARCHAR to Enum
    # Ensure existing data is lowercase (should already be)
    op.execute("""
        UPDATE messages 
        SET role = LOWER(role) 
        WHERE role IN ('user', 'assistant', 'system', 'USER', 'ASSISTANT', 'SYSTEM')
    """)
    
    # Alter column type to enum
    op.alter_column('messages', 'role',
               existing_type=sa.VARCHAR(length=20),
               type_=message_role_enum,
               existing_nullable=False,
               postgresql_using='LOWER(role)::message_role')
    
    # Add new columns to views
    op.add_column('views', sa.Column('view_type', sa.String(length=50), nullable=True))
    op.add_column('views', sa.Column('embed_url', sa.String(length=500), nullable=True))
    op.add_column('views', sa.Column('is_published', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('views', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('views', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.create_index('idx_view_published', 'views', ['is_published'], unique=False)
    op.create_index('idx_view_synced', 'views', ['last_synced_at'], unique=False)
    op.create_index('idx_view_type', 'views', ['view_type'], unique=False)
    op.create_index(op.f('ix_views_is_published'), 'views', ['is_published'], unique=False)
    op.create_index(op.f('ix_views_last_synced_at'), 'views', ['last_synced_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes and columns from views
    op.drop_index(op.f('ix_views_last_synced_at'), table_name='views')
    op.drop_index(op.f('ix_views_is_published'), table_name='views')
    op.drop_index('idx_view_type', table_name='views')
    op.drop_index('idx_view_synced', table_name='views')
    op.drop_index('idx_view_published', table_name='views')
    op.drop_column('views', 'last_synced_at')
    op.drop_column('views', 'tags')
    op.drop_column('views', 'is_published')
    op.drop_column('views', 'embed_url')
    op.drop_column('views', 'view_type')
    
    # Convert role column back from Enum to VARCHAR
    op.alter_column('messages', 'role',
               existing_type=sa.Enum('user', 'assistant', 'system', name='message_role'),
               type_=sa.VARCHAR(length=20),
               existing_nullable=False,
               postgresql_using='role::text')
    
    # Drop enum type
    op.execute('DROP TYPE IF EXISTS message_role')
    
    # Drop columns from messages
    op.drop_column('messages', 'extra_metadata')
    op.drop_column('messages', 'tokens_used')
    
    # Drop indexes and columns from datasources
    op.drop_index(op.f('ix_datasources_last_synced_at'), table_name='datasources')
    op.drop_index(op.f('ix_datasources_is_active'), table_name='datasources')
    op.drop_index('idx_datasource_synced', table_name='datasources')
    op.drop_index('idx_datasource_active', table_name='datasources')
    op.drop_column('datasources', 'last_synced_at')
    op.drop_column('datasources', 'extra_metadata')
    op.drop_column('datasources', 'row_count')
    op.drop_column('datasources', 'size_bytes')
    op.drop_column('datasources', 'is_active')
