"""add user_tableau_auth_preferences table

Revision ID: ac_user_tableau_auth_preferences
Revises: ab_preferred_tableau_auth
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'ac_user_tableau_auth_preferences'
down_revision: Union[str, Sequence[str], None] = 'ab_preferred_tableau_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'user_tableau_auth_preferences'
        )
    """)).scalar()
    
    if not exists:
        op.create_table(
            'user_tableau_auth_preferences',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('tableau_server_config_id', sa.Integer(), nullable=False),
            sa.Column('preferred_auth_type', sa.String(50), nullable=False, comment="Preferred Tableau auth: connected_app, connected_app_oauth, pat, standard"),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_user_tableau_auth_pref_user'),
            sa.ForeignKeyConstraint(['tableau_server_config_id'], ['tableau_server_configs.id'], name='fk_user_tableau_auth_pref_config'),
            sa.PrimaryKeyConstraint('id', name='pk_user_tableau_auth_preferences'),
        )
        op.create_index('ix_user_tableau_auth_preferences_id', 'user_tableau_auth_preferences', ['id'])
        op.create_index('ix_user_tableau_auth_preferences_user_id', 'user_tableau_auth_preferences', ['user_id'])
        op.create_index('ix_user_tableau_auth_preferences_config_id', 'user_tableau_auth_preferences', ['tableau_server_config_id'])
        op.create_unique_constraint('uq_user_tableau_auth_preference', 'user_tableau_auth_preferences', ['user_id', 'tableau_server_config_id'])


def downgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'user_tableau_auth_preferences'
        )
    """)).scalar()
    
    if exists:
        op.drop_constraint('uq_user_tableau_auth_preference', 'user_tableau_auth_preferences', type_='unique')
        op.drop_index('ix_user_tableau_auth_preferences_config_id', table_name='user_tableau_auth_preferences')
        op.drop_index('ix_user_tableau_auth_preferences_user_id', table_name='user_tableau_auth_preferences')
        op.drop_index('ix_user_tableau_auth_preferences_id', table_name='user_tableau_auth_preferences')
        op.drop_table('user_tableau_auth_preferences')
