"""add skip_ssl_verify to tableau_server_configs

Revision ID: u_skip_ssl_verify
Revises: t_tableau_creds_optional
Create Date: 2026-02-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = 'u_skip_ssl_verify'
down_revision: Union[str, Sequence[str], None] = 't_tableau_creds_optional'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    col_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'skip_ssl_verify'
        )
    """)).scalar()
    if not col_exists:
        conn.execute(text("""
            ALTER TABLE tableau_server_configs
            ADD COLUMN skip_ssl_verify BOOLEAN NOT NULL DEFAULT false
        """))
        conn.execute(text("""
            COMMENT ON COLUMN tableau_server_configs.skip_ssl_verify IS
            'Skip SSL certificate verification for Tableau API calls'
        """))


def downgrade() -> None:
    conn = op.get_bind()
    col_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'skip_ssl_verify'
        )
    """)).scalar()
    if col_exists:
        conn.execute(text("ALTER TABLE tableau_server_configs DROP COLUMN skip_ssl_verify"))
