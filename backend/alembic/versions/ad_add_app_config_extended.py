"""add app config columns to auth_configs (cors, gateway, mcp, redis)

Revision ID: ad_add_app_config_extended
Revises: ac_user_tableau_auth_preferences
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'ad_add_app_config_extended'
down_revision: Union[str, Sequence[str], None] = 'ac_user_tableau_auth_preferences'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = [
        ("cors_origins", sa.Column("cors_origins", sa.String(500), nullable=True)),
        ("gateway_enabled", sa.Column("gateway_enabled", sa.Boolean(), nullable=True)),
        ("mcp_server_name", sa.Column("mcp_server_name", sa.String(100), nullable=True)),
        ("mcp_transport", sa.Column("mcp_transport", sa.String(20), nullable=True)),
        ("mcp_log_level", sa.Column("mcp_log_level", sa.String(20), nullable=True)),
        ("redis_token_ttl", sa.Column("redis_token_ttl", sa.Integer(), nullable=True)),
    ]
    for col_name, col_def in columns:
        exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'auth_configs' AND column_name = :name
            )
        """), {"name": col_name}).scalar()
        if not exists:
            op.add_column("auth_configs", col_def)


def downgrade() -> None:
    conn = op.get_bind()
    for col_name in ["cors_origins", "gateway_enabled", "mcp_server_name", "mcp_transport", "mcp_log_level", "redis_token_ttl"]:
        exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'auth_configs' AND column_name = :name
            )
        """), {"name": col_name}).scalar()
        if exists:
            op.drop_column("auth_configs", col_name)
