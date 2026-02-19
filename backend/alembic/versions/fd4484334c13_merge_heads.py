"""merge_heads

Revision ID: fd4484334c13
Revises: ag_add_provider_verify_ssl, bc_add_user_email
Create Date: 2026-02-18 17:53:49.798811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd4484334c13'
down_revision: Union[str, Sequence[str], None] = ('ag_add_provider_verify_ssl', 'bc_add_user_email')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
