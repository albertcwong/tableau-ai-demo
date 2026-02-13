"""add tableau connected app oauth (OAuth 2.0 Trust)

Revision ID: y_add_connected_app_oauth
Revises: x_add_agent_configs
Create Date: 2026-02-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = 'y_add_connected_app_oauth'
down_revision: Union[str, Sequence[str], None] = 'x_add_agent_configs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    cols = [
        ("allow_connected_app_oauth", "BOOLEAN NOT NULL DEFAULT false"),
        ("eas_issuer_url", "VARCHAR(500)"),
        ("eas_client_id", "VARCHAR(255)"),
        ("eas_client_secret", "VARCHAR(500)"),
        ("eas_authorization_endpoint", "VARCHAR(500)"),
        ("eas_token_endpoint", "VARCHAR(500)"),
    ]
    for col_name, col_type in cols:
        exists = conn.execute(text(f"""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tableau_server_configs' AND column_name = '{col_name}'
            )
        """)).scalar()
        if not exists:
            conn.execute(text(f"""
                ALTER TABLE tableau_server_configs
                ADD COLUMN {col_name} {col_type}
            """))
    conn.commit()


def downgrade() -> None:
    conn = op.get_bind()
    cols = [
        "allow_connected_app_oauth", "eas_issuer_url", "eas_client_id",
        "eas_client_secret", "eas_authorization_endpoint", "eas_token_endpoint",
    ]
    for col_name in cols:
        exists = conn.execute(text(f"""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tableau_server_configs' AND column_name = '{col_name}'
            )
        """)).scalar()
        if exists:
            conn.execute(text(f"ALTER TABLE tableau_server_configs DROP COLUMN {col_name}"))
    conn.commit()
