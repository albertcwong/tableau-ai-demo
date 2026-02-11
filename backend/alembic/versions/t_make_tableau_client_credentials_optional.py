"""make tableau client_id and client_secret optional

Revision ID: t_tableau_creds_optional
Revises: s_add_tableau_pat_auth
Create Date: 2026-02-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = 't_tableau_creds_optional'
down_revision: Union[str, Sequence[str], None] = 's_add_tableau_pat_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE tableau_server_configs ALTER COLUMN client_id DROP NOT NULL"))
    conn.execute(text("ALTER TABLE tableau_server_configs ALTER COLUMN client_secret DROP NOT NULL"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("""
        UPDATE tableau_server_configs SET client_id = '' WHERE client_id IS NULL
    """))
    conn.execute(text("""
        UPDATE tableau_server_configs SET client_secret = '' WHERE client_secret IS NULL
    """))
    conn.execute(text("ALTER TABLE tableau_server_configs ALTER COLUMN client_id SET NOT NULL"))
    conn.execute(text("ALTER TABLE tableau_server_configs ALTER COLUMN client_secret SET NOT NULL"))
