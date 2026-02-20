"""remove_chat_messages_make_chatwoot_ids_nullable

Revision ID: ccaea338ac3a
Revises: 09fd4a8aace3
Create Date: 2026-02-19 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ccaea338ac3a'
down_revision = '09fd4a8aace3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop chat_messages
    try:
        op.drop_table('chat_messages')
    except Exception:
        pass

    # Add chatwoot_conversation_id and chatwoot_account_id to chat_sessions
    try:
        op.add_column('chat_sessions', sa.Column('chatwoot_conversation_id', sa.Integer(), nullable=True))
        op.add_column('chat_sessions', sa.Column('chatwoot_account_id', sa.Integer(), nullable=True))
        op.create_index(op.f('ix_chat_sessions_chatwoot_conversation_id'), 'chat_sessions', ['chatwoot_conversation_id'], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    # Drop columns
    try:
        op.drop_index(op.f('ix_chat_sessions_chatwoot_conversation_id'), table_name='chat_sessions')
        op.drop_column('chat_sessions', 'chatwoot_account_id')
        op.drop_column('chat_sessions', 'chatwoot_conversation_id')
    except Exception:
        pass

    # Recreate chat_messages
    try:
        op.create_table('chat_messages',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=True),
            sa.Column('role', sa.String(), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
    except Exception:
        pass
