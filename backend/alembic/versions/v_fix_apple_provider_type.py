"""fix apple provider type to apple_endor

Revision ID: v_fix_apple_provider
Revises: u_skip_ssl_verify
Create Date: 2026-02-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = 'v_fix_apple_provider'
down_revision: Union[str, Sequence[str], None] = 'u_skip_ssl_verify'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Update any 'apple' provider_type values to 'apple_endor' for backward compatibility
    conn.execute(text("""
        UPDATE provider_configs 
        SET provider_type = 'apple_endor' 
        WHERE provider_type = 'apple'
    """))


def downgrade() -> None:
    conn = op.get_bind()
    # Revert 'apple_endor' back to 'apple' (not recommended, but included for completeness)
    conn.execute(text("""
        UPDATE provider_configs 
        SET provider_type = 'apple' 
        WHERE provider_type = 'apple_endor'
    """))
