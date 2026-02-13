"""add eas_sub_claim_field for configurable OAuth 2.0 Trust sub claim

Revision ID: z_add_eas_sub_claim_field
Revises: y_add_connected_app_oauth
Create Date: 2026-02-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = 'z_add_eas_sub_claim_field'
down_revision: Union[str, Sequence[str], None] = 'y_add_connected_app_oauth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'eas_sub_claim_field'
        )
    """)).scalar()
    if not exists:
        conn.execute(text("""
            ALTER TABLE tableau_server_configs
            ADD COLUMN eas_sub_claim_field VARCHAR(100)
        """))
    conn.commit()


def downgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'eas_sub_claim_field'
        )
    """)).scalar()
    if exists:
        conn.execute(text("ALTER TABLE tableau_server_configs DROP COLUMN eas_sub_claim_field"))
    conn.commit()
