"""add message feedback_text field

Revision ID: k_add_message_feedback_text
Revises: j_add_message_feedback_time
Create Date: 2026-02-05 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'k_add_message_feedback_text'
down_revision: Union[str, Sequence[str], None] = 'j_add_message_feedback_time'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    
    # Check if messages table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_name = 'messages'
        )
    """)).scalar()
    
    if table_exists:
        # Add feedback_text column
        feedback_text_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'messages' 
                AND column_name = 'feedback_text'
            )
        """)).scalar()
        
        if not feedback_text_exists:
            conn.execute(text("""
                ALTER TABLE messages 
                ADD COLUMN feedback_text TEXT
            """))
        
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Remove column if it exists
    feedback_text_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'messages' 
            AND column_name = 'feedback_text'
        )
    """)).scalar()
    
    if feedback_text_exists:
        conn.execute(text("ALTER TABLE messages DROP COLUMN feedback_text"))
    
    conn.commit()
