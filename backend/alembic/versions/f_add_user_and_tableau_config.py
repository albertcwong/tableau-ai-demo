"""add user and tableau server config tables

Revision ID: f_add_user_and_tableau_config
Revises: e_add_conversation_name
Create Date: 2026-02-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'f_add_user_and_tableau_config'
down_revision: Union[str, Sequence[str], None] = 'e_add_conversation_name'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    
    # Create user_role enum if it doesn't exist using raw SQL
    enum_exists = conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role')")).scalar()
    if not enum_exists:
        conn.execute(text("CREATE TYPE user_role AS ENUM ('ADMIN', 'USER')"))
        conn.commit()
    
    # Check if users table exists
    users_exists = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users')"
    )).scalar()
    
    if not users_exists:
        # Create users table using raw SQL to avoid SQLAlchemy trying to create the enum
        conn.execute(text("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role user_role NOT NULL DEFAULT 'USER',
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """))
        conn.commit()
        
        # Create indexes if they don't exist
        indexes = ['ix_users_id', 'ix_users_username', 'ix_users_is_active', 'idx_user_username_active']
        for idx_name in indexes:
            idx_exists = conn.execute(text(
                f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{idx_name}')"
            )).scalar()
            if not idx_exists:
                if idx_name == 'ix_users_id':
                    conn.execute(text(f"CREATE INDEX {idx_name} ON users (id)"))
                elif idx_name == 'ix_users_username':
                    # Username already has UNIQUE constraint which creates an index
                    pass
                elif idx_name == 'ix_users_is_active':
                    conn.execute(text(f"CREATE INDEX {idx_name} ON users (is_active)"))
                elif idx_name == 'idx_user_username_active':
                    conn.execute(text(f"CREATE INDEX {idx_name} ON users (username, is_active)"))
        conn.commit()
    else:
        # Table exists, but check if indexes exist and create missing ones
        indexes_to_create = [
            ('ix_users_id', 'CREATE INDEX ix_users_id ON users (id)'),
            ('ix_users_is_active', 'CREATE INDEX ix_users_is_active ON users (is_active)'),
            ('idx_user_username_active', 'CREATE INDEX idx_user_username_active ON users (username, is_active)')
        ]
        for idx_name, create_sql in indexes_to_create:
            idx_exists = conn.execute(text(
                f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{idx_name}')"
            )).scalar()
            if not idx_exists:
                conn.execute(text(create_sql))
        conn.commit()
    
    # Check if tableau_server_configs table exists
    configs_exists = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tableau_server_configs')"
    )).scalar()
    
    if not configs_exists:
        # Create tableau_server_configs table using raw SQL
        conn.execute(text("""
            CREATE TABLE tableau_server_configs (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                server_url VARCHAR(500) NOT NULL,
                site_id VARCHAR(100),
                client_id VARCHAR(255) NOT NULL,
                client_secret VARCHAR(500) NOT NULL,
                secret_id VARCHAR(255),
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """))
        conn.commit()
        
        # Create indexes if they don't exist
        indexes_to_create = [
            ('ix_tableau_server_configs_id', 'CREATE INDEX ix_tableau_server_configs_id ON tableau_server_configs (id)'),
            ('ix_tableau_server_configs_is_active', 'CREATE INDEX ix_tableau_server_configs_is_active ON tableau_server_configs (is_active)'),
            ('idx_tableau_config_server_site', 'CREATE INDEX idx_tableau_config_server_site ON tableau_server_configs (server_url, site_id)'),
            ('idx_tableau_config_active', 'CREATE INDEX idx_tableau_config_active ON tableau_server_configs (is_active)')
        ]
        for idx_name, create_sql in indexes_to_create:
            idx_exists = conn.execute(text(
                f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{idx_name}')"
            )).scalar()
            if not idx_exists:
                conn.execute(text(create_sql))
        conn.commit()
    else:
        # Table exists, but check if indexes exist and create missing ones
        indexes_to_create = [
            ('ix_tableau_server_configs_id', 'CREATE INDEX ix_tableau_server_configs_id ON tableau_server_configs (id)'),
            ('ix_tableau_server_configs_is_active', 'CREATE INDEX ix_tableau_server_configs_is_active ON tableau_server_configs (is_active)'),
            ('idx_tableau_config_server_site', 'CREATE INDEX idx_tableau_config_server_site ON tableau_server_configs (server_url, site_id)'),
            ('idx_tableau_config_active', 'CREATE INDEX idx_tableau_config_active ON tableau_server_configs (is_active)')
        ]
        for idx_name, create_sql in indexes_to_create:
            idx_exists = conn.execute(text(
                f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{idx_name}')"
            )).scalar()
            if not idx_exists:
                conn.execute(text(create_sql))
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_tableau_config_active', table_name='tableau_server_configs')
    op.drop_index('idx_tableau_config_server_site', table_name='tableau_server_configs')
    op.drop_index(op.f('ix_tableau_server_configs_is_active'), table_name='tableau_server_configs')
    op.drop_index(op.f('ix_tableau_server_configs_id'), table_name='tableau_server_configs')
    
    # Drop tables
    op.drop_table('tableau_server_configs')
    
    op.drop_index('idx_user_username_active', table_name='users')
    op.drop_index(op.f('ix_users_is_active'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
    
    # Drop enum if it exists
    conn = op.get_bind()
    result = conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role')")).scalar()
    if result:
        sa.Enum(name='user_role').drop(conn, checkfirst=False)
