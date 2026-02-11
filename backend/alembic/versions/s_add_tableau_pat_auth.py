"""add tableau pat auth

Revision ID: s_add_tableau_pat_auth
Revises: r_add_endor_credential_fields
Create Date: 2026-02-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 's_add_tableau_pat_auth'
down_revision: Union[str, Sequence[str], None] = 'r_add_endor_credential_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add allow_pat_auth to tableau_server_configs
    col_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'allow_pat_auth'
        )
    """)).scalar()
    if not col_exists:
        conn.execute(text("""
            ALTER TABLE tableau_server_configs
            ADD COLUMN allow_pat_auth BOOLEAN NOT NULL DEFAULT false
        """))
        conn.execute(text("""
            COMMENT ON COLUMN tableau_server_configs.allow_pat_auth IS
            'Allow users to authenticate with Personal Access Token'
        """))
    conn.commit()

    # Create user_tableau_pats table
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'user_tableau_pats'
        )
    """)).scalar()
    if not table_exists:
        conn.execute(text("""
            CREATE TABLE user_tableau_pats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                tableau_server_config_id INTEGER NOT NULL REFERENCES tableau_server_configs(id),
                pat_name VARCHAR(255) NOT NULL,
                pat_secret TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                CONSTRAINT uq_user_tableau_pat UNIQUE (user_id, tableau_server_config_id)
            )
        """))
        conn.execute(text("CREATE INDEX ix_user_tableau_pats_id ON user_tableau_pats (id)"))
        conn.execute(text("CREATE INDEX ix_user_tableau_pats_user_id ON user_tableau_pats (user_id)"))
        conn.execute(text("CREATE INDEX ix_user_tableau_pats_config_id ON user_tableau_pats (tableau_server_config_id)"))
    conn.commit()


def downgrade() -> None:
    conn = op.get_bind()

    if conn.execute(text("""
        SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_tableau_pats')
    """)).scalar():
        conn.execute(text("DROP TABLE user_tableau_pats"))
    conn.commit()

    if conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'allow_pat_auth'
        )
    """)).scalar():
        conn.execute(text("ALTER TABLE tableau_server_configs DROP COLUMN allow_pat_auth"))
    conn.commit()
