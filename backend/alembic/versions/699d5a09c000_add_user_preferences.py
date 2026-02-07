"""add_user_preferences

Revision ID: 699d5a09c000
Revises: 14b767a79488
Create Date: 2026-02-06 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '699d5a09c000'
down_revision: Union[str, None] = '14b767a79488'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('preferred_provider', sa.String(length=50), nullable=True, comment="Preferred AI provider (e.g., 'openai', 'anthropic')"))
    op.add_column('users', sa.Column('preferred_model', sa.String(length=100), nullable=True, comment="Preferred AI model (e.g., 'gpt-4', 'claude-3-opus')"))
    op.add_column('users', sa.Column('preferred_agent_type', sa.String(length=50), nullable=True, comment="Preferred agent type ('general', 'vizql', 'summary')"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'preferred_agent_type')
    op.drop_column('users', 'preferred_model')
    op.drop_column('users', 'preferred_provider')
