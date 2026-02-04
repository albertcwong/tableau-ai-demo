"""add name column to conversations table

Revision ID: e_add_conversation_name
Revises: d_add_chat_context
Create Date: 2026-02-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e_add_conversation_name'
down_revision: Union[str, Sequence[str], None] = 'd_add_chat_context'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add name column to conversations table
    op.add_column('conversations', sa.Column('name', sa.String(length=255), nullable=True, comment='User-assigned or auto-generated thread name'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove name column from conversations table
    op.drop_column('conversations', 'name')
