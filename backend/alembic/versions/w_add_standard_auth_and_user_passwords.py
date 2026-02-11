"""add standard auth and user tableau passwords

Revision ID: w_add_standard_auth
Revises: v_fix_apple_provider
Create Date: 2026-02-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = 'w_add_standard_auth'
down_revision: Union[str, Sequence[str], None] = 'v_fix_apple_provider'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add allow_standard_auth to tableau_server_configs
    col_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'allow_standard_auth'
        )
    """)).scalar()
    if not col_exists:
        conn.execute(text("""
            ALTER TABLE tableau_server_configs
            ADD COLUMN allow_standard_auth BOOLEAN NOT NULL DEFAULT false
        """))
        conn.execute(text("""
            COMMENT ON COLUMN tableau_server_configs.allow_standard_auth IS
            'Allow users to authenticate with username and password'
        """))
    conn.commit()

    # Create user_tableau_passwords table
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'user_tableau_passwords'
        )
    """)).scalar()
    if not table_exists:
        conn.execute(text("""
            CREATE TABLE user_tableau_passwords (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                tableau_server_config_id INTEGER NOT NULL REFERENCES tableau_server_configs(id),
                tableau_username VARCHAR(255) NOT NULL,
                password_encrypted TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                CONSTRAINT uq_user_tableau_password UNIQUE (user_id, tableau_server_config_id)
            )
        """))
        conn.execute(text("CREATE INDEX ix_user_tableau_passwords_id ON user_tableau_passwords (id)"))
        conn.execute(text("CREATE INDEX ix_user_tableau_passwords_user_id ON user_tableau_passwords (user_id)"))
        conn.execute(text("CREATE INDEX ix_user_tableau_passwords_config_id ON user_tableau_passwords (tableau_server_config_id)"))
    conn.commit()


def downgrade() -> None:
    conn = op.get_bind()

    if conn.execute(text("""
        SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_tableau_passwords')
    """)).scalar():
        conn.execute(text("DROP TABLE user_tableau_passwords"))
    conn.commit()

    if conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'allow_standard_auth'
        )
    """)).scalar():
        conn.execute(text("ALTER TABLE tableau_server_configs DROP COLUMN allow_standard_auth"))
    conn.commit()
