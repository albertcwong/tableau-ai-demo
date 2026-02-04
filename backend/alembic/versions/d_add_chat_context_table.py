"""add chat context table

Revision ID: d_add_chat_context
Revises: 7cd98763c15e
Create Date: 2026-02-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd_add_chat_context'
down_revision: Union[str, Sequence[str], None] = 'c_add_uppercase_message_roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'chat_contexts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('object_id', sa.String(length=255), nullable=False),
        sa.Column('object_type', sa.String(length=50), nullable=False),
        sa.Column('object_name', sa.String(length=255), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_contexts_id'), 'chat_contexts', ['id'], unique=False)
    op.create_index(op.f('ix_chat_contexts_added_at'), 'chat_contexts', ['added_at'], unique=False)
    op.create_index('idx_context_conversation_object', 'chat_contexts', ['conversation_id', 'object_id', 'object_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_context_conversation_object', table_name='chat_contexts')
    op.drop_index(op.f('ix_chat_contexts_added_at'), table_name='chat_contexts')
    op.drop_index(op.f('ix_chat_contexts_id'), table_name='chat_contexts')
    op.drop_table('chat_contexts')
