"""add idp_claims to users for generic claim resolution (Connected App)

Revision ID: bc_add_user_email
Revises: bb_drop_uq_user_tableau_pat
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text, Column
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'bc_add_user_email'
down_revision: Union[str, Sequence[str], None] = 'bb_drop_uq_user_tableau_pat'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if not conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'idp_claims'
        )
    """)).scalar():
        op.add_column('users', Column('idp_claims', JSONB, nullable=True))
    if conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'email'
        )
    """)).scalar():
        op.drop_column('users', 'email')


def downgrade() -> None:
    conn = op.get_bind()
    if conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'idp_claims'
        )
    """)).scalar():
        op.drop_column('users', 'idp_claims')
