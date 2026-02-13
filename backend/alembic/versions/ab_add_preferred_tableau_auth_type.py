"""add preferred_tableau_auth_type to users

Revision ID: ab_add_preferred_tableau_auth_type
Revises: aa_add_app_config_eas
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ab_preferred_tableau_auth'
down_revision: Union[str, Sequence[str], None] = 'aa_add_app_config_eas'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'preferred_tableau_auth_type',
            sa.String(50),
            nullable=True,
            comment="Preferred Tableau auth: connected_app, connected_app_oauth, pat, standard",
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'preferred_tableau_auth_type')
