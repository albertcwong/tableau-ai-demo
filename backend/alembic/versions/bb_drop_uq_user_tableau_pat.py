"""drop uq_user_tableau_pat to allow multiple PATs per user per config

Revision ID: bb_drop_uq_user_tableau_pat
Revises: ba_rename_tableau_username_field
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = 'bb_drop_uq_user_tableau_pat'
down_revision: Union[str, Sequence[str], None] = 'ba_rename_tableau_username_field'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # PostgreSQL: drop constraint if exists
    conn.execute(text("""
        ALTER TABLE user_tableau_pats
        DROP CONSTRAINT IF EXISTS uq_user_tableau_pat
    """))


def downgrade() -> None:
    op.create_unique_constraint(
        'uq_user_tableau_pat',
        'user_tableau_pats',
        ['user_id', 'tableau_server_config_id'],
    )
