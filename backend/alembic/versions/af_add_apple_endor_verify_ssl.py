"""add apple_endor_verify_ssl to provider_configs

Revision ID: af_add_apple_endor_verify_ssl
Revises: ae_unique_url_ssl_cert
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'af_add_apple_endor_verify_ssl'
down_revision: Union[str, Sequence[str], None] = 'z_add_max_rows_to_agent_configs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    col_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'provider_configs' AND column_name = 'apple_endor_verify_ssl'
        )
    """)).scalar()
    if not col_exists:
        op.add_column(
            'provider_configs',
            sa.Column('apple_endor_verify_ssl', sa.Boolean(), nullable=True,
                     comment='Disable SSL verification for idmsac.corp.apple.com (corp certs)')
        )


def downgrade() -> None:
    op.drop_column('provider_configs', 'apple_endor_verify_ssl')
