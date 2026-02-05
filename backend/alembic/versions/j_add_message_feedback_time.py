"""add message feedback and total_time fields

Revision ID: j_add_message_feedback_time
Revises: i_provider_type_varchar
Create Date: 2026-02-04 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'j_add_message_feedback_time'
down_revision: Union[str, Sequence[str], None] = 'i_provider_type_varchar'
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
        # Add feedback column
        feedback_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'messages' 
                AND column_name = 'feedback'
            )
        """)).scalar()
        
        if not feedback_exists:
            conn.execute(text("""
                ALTER TABLE messages 
                ADD COLUMN feedback VARCHAR(20)
            """))
        
        # Add total_time_ms column
        total_time_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'messages' 
                AND column_name = 'total_time_ms'
            )
        """)).scalar()
        
        if not total_time_exists:
            conn.execute(text("""
                ALTER TABLE messages 
                ADD COLUMN total_time_ms DOUBLE PRECISION
            """))
        
        conn.commit()


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    
    # Remove columns if they exist
    feedback_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'messages' 
            AND column_name = 'feedback'
        )
    """)).scalar()
    
    if feedback_exists:
        conn.execute(text("ALTER TABLE messages DROP COLUMN feedback"))
    
    total_time_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'messages' 
            AND column_name = 'total_time_ms'
        )
    """)).scalar()
    
    if total_time_exists:
        conn.execute(text("ALTER TABLE messages DROP COLUMN total_time_ms"))
    
    conn.commit()
