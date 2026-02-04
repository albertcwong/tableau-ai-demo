"""add uppercase message roles

Revision ID: c_add_uppercase_message_roles
Revises: b182f78e08cb
Create Date: 2026-02-03 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c_add_uppercase_message_roles'
down_revision: Union[str, Sequence[str], None] = 'b182f78e08cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update message_role enum to use uppercase values."""
    # Convert existing lowercase values to uppercase
    op.execute("""
        UPDATE messages 
        SET role = UPPER(role::text)::message_role
        WHERE role::text IN ('user', 'assistant', 'system')
    """)
    
    # Drop the existing enum and recreate with uppercase values
    op.execute("ALTER TYPE message_role RENAME TO message_role_old")
    
    # Create new enum with uppercase values only
    op.execute("CREATE TYPE message_role AS ENUM ('USER', 'ASSISTANT', 'SYSTEM')")
    
    # Update the column to use the new enum
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN role TYPE message_role 
        USING UPPER(role::text)::message_role
    """)
    
    # Drop the old enum
    op.execute("DROP TYPE message_role_old")


def downgrade() -> None:
    """Revert to lowercase-only enum."""
    # Convert all uppercase to lowercase first
    op.execute("""
        UPDATE messages 
        SET role = LOWER(role::text)
        WHERE role::text IN ('USER', 'ASSISTANT', 'SYSTEM')
    """)
    
    # Drop the current enum
    op.execute("ALTER TYPE message_role RENAME TO message_role_temp")
    
    # Recreate with lowercase only
    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system')")
    
    # Update the column
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN role TYPE message_role 
        USING LOWER(role::text)::message_role
    """)
    
    # Drop temp enum
    op.execute("DROP TYPE message_role_temp")
