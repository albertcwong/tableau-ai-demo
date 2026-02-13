"""add unique server_url constraint and ssl_cert_path column

Revision ID: ae_unique_url_ssl_cert
Revises: ad_add_app_config_extended
Create Date: 2026-02-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'ae_unique_url_ssl_cert'
down_revision: Union[str, Sequence[str], None] = 'ad_add_app_config_extended'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # First, normalize existing server_urls to lowercase and remove trailing slashes
    # This ensures the unique constraint will work correctly
    conn.execute(text("""
        UPDATE tableau_server_configs
        SET server_url = LOWER(TRIM(TRAILING '/' FROM server_url))
        WHERE server_url != LOWER(TRIM(TRAILING '/' FROM server_url))
    """))
    
    # Remove /api suffix if present
    conn.execute(text("""
        UPDATE tableau_server_configs
        SET server_url = SUBSTRING(server_url FROM 1 FOR LENGTH(server_url) - 4)
        WHERE server_url LIKE '%/api'
    """))
    
    # Add ssl_cert_path column
    exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'ssl_cert_path'
        )
    """)).scalar()
    if not exists:
        op.add_column("tableau_server_configs", sa.Column("ssl_cert_path", sa.String(500), nullable=True))
    
    # Check if unique constraint already exists
    constraint_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.table_constraints
            WHERE constraint_name = 'uq_tableau_server_config_server_url'
            AND table_name = 'tableau_server_configs'
        )
    """)).scalar()
    
    if not constraint_exists:
        # Check for duplicate server_urls before adding constraint
        duplicates = conn.execute(text("""
            SELECT server_url, COUNT(*) as count
            FROM tableau_server_configs
            GROUP BY server_url
            HAVING COUNT(*) > 1
        """)).fetchall()
        
        if duplicates:
            # If duplicates exist, we need to handle them
            # For now, raise an error with details
            dup_urls = [row[0] for row in duplicates]
            raise ValueError(
                f"Cannot add unique constraint: duplicate server URLs found: {', '.join(dup_urls)}. "
                "Please resolve duplicates manually before running this migration."
            )
        
        # Add unique constraint on server_url
        op.create_unique_constraint(
            "uq_tableau_server_config_server_url",
            "tableau_server_configs",
            ["server_url"]
        )


def downgrade() -> None:
    conn = op.get_bind()
    
    # Remove unique constraint
    constraint_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.table_constraints
            WHERE constraint_name = 'uq_tableau_server_config_server_url'
            AND table_name = 'tableau_server_configs'
        )
    """)).scalar()
    if constraint_exists:
        op.drop_constraint("uq_tableau_server_config_server_url", "tableau_server_configs", type_="unique")
    
    # Remove ssl_cert_path column
    exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'ssl_cert_path'
        )
    """)).scalar()
    if exists:
        op.drop_column("tableau_server_configs", "ssl_cert_path")
