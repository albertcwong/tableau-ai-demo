"""add app config and EAS JWT key to auth_configs

Revision ID: aa_add_app_config_eas
Revises: z_add_eas_sub_claim_field
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'aa_add_app_config_eas'
down_revision: Union[str, Sequence[str], None] = 'z_add_eas_sub_claim_field'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    for col_name, col_type in [
        ("backend_api_url", "VARCHAR(500)"),
        ("tableau_oauth_frontend_redirect", "VARCHAR(500)"),
        ("eas_jwt_key_pem_encrypted", "TEXT"),
    ]:
        exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'auth_configs' AND column_name = :name
            )
        """), {"name": col_name}).scalar()
        if not exists:
            col = sa.String(500) if "VARCHAR" in col_type else sa.Text()
            op.add_column("auth_configs", sa.Column(col_name, col, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    for col_name in ["backend_api_url", "tableau_oauth_frontend_redirect", "eas_jwt_key_pem_encrypted"]:
        exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'auth_configs' AND column_name = :name
            )
        """), {"name": col_name}).scalar()
        if exists:
            op.drop_column("auth_configs", col_name)
