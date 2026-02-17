"""rename auth0_tableau_metadata_field to tableau_username_field

Revision ID: ba_rename_tableau_username_field
Revises: z_add_max_rows_to_agent_configs
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = 'ba_rename_tableau_username_field'
down_revision: Union[str, Sequence[str], None] = 'af_add_apple_endor_verify_ssl'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    col_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'auth_configs'
            AND column_name = 'tableau_username_field'
        )
    """)).scalar()
    if not col_exists:
        op.add_column('auth_configs',
            sa.Column('tableau_username_field', sa.String(255), nullable=True,
                     comment='IdP claim/field path for Tableau username (e.g. app_metadata.tableau_username)'))
    old_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'auth_configs'
            AND column_name = 'auth0_tableau_metadata_field'
        )
    """)).scalar()
    if old_exists:
        conn.execute(text("""
            UPDATE auth_configs SET tableau_username_field = auth0_tableau_metadata_field
            WHERE auth0_tableau_metadata_field IS NOT NULL
        """))
        op.drop_column('auth_configs', 'auth0_tableau_metadata_field')


def downgrade() -> None:
    conn = op.get_bind()
    old_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'auth_configs'
            AND column_name = 'auth0_tableau_metadata_field'
        )
    """)).scalar()
    if not old_exists:
        op.add_column('auth_configs',
            sa.Column('auth0_tableau_metadata_field', sa.String(255), nullable=True))
        conn.execute(text("""
            UPDATE auth_configs SET auth0_tableau_metadata_field = tableau_username_field
            WHERE tableau_username_field IS NOT NULL
        """))
    op.drop_column('auth_configs', 'tableau_username_field')
