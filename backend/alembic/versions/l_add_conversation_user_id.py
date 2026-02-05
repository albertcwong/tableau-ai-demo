"""add user_id to conversations

Revision ID: l_add_conversation_user_id
Revises: k_add_message_feedback_text
Create Date: 2026-02-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'l_add_conversation_user_id'
down_revision: Union[str, Sequence[str], None] = 'k_add_message_feedback_text'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    
    # Check if conversations table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_name = 'conversations'
        )
    """)).scalar()
    
    if table_exists:
        # Check if users table exists (required for foreign key)
        users_table_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_name = 'users'
            )
        """)).scalar()
        
        if users_table_exists:
            # Add user_id column
            user_id_exists = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'conversations' 
                    AND column_name = 'user_id'
                )
            """)).scalar()
            
            if not user_id_exists:
                # Add column first
                conn.execute(text("""
                    ALTER TABLE conversations 
                    ADD COLUMN user_id INTEGER
                """))
                
                # Add index
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_conversations_user_id 
                    ON conversations(user_id)
                """))
                
                # Add foreign key constraint
                conn.execute(text("""
                    ALTER TABLE conversations 
                    ADD CONSTRAINT fk_conversations_user_id 
                    FOREIGN KEY (user_id) 
                    REFERENCES users(id) 
                    ON DELETE SET NULL
                """))
        
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Remove foreign key constraint if it exists
    fk_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.table_constraints 
            WHERE table_name = 'conversations' 
            AND constraint_name = 'fk_conversations_user_id'
        )
    """)).scalar()
    
    if fk_exists:
        conn.execute(text("ALTER TABLE conversations DROP CONSTRAINT fk_conversations_user_id"))
    
    # Remove index if it exists
    index_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM pg_indexes 
            WHERE tablename = 'conversations' 
            AND indexname = 'ix_conversations_user_id'
        )
    """)).scalar()
    
    if index_exists:
        conn.execute(text("DROP INDEX IF EXISTS ix_conversations_user_id"))
    
    # Remove column if it exists
    user_id_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'conversations' 
            AND column_name = 'user_id'
        )
    """)).scalar()
    
    if user_id_exists:
        conn.execute(text("ALTER TABLE conversations DROP COLUMN user_id"))
    
    conn.commit()
