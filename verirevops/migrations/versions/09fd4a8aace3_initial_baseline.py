"""Initial baseline

Revision ID: 09fd4a8aace3
Revises:
Create Date: 2026-02-19 17:38:54.171275

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

# revision identifiers, used by Alembic.
revision: str = '09fd4a8aace3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create tenants
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_tenants_id'), 'tenants', ['id'], unique=False)

    # Create subscriptions
    op.create_table('subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('quota_limit', sa.Integer(), nullable=False),
        sa.Column('usage_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chat_sessions
    op.create_table('chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('last_summarized_message_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chat_messages
    op.create_table('chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create rag_files
    op.create_table('rag_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create rag_chunks
    op.create_table('rag_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(3072) if Vector else sa.ARRAY(sa.Float()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['rag_files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create integration_configs
    op.create_table('integration_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('service_name', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('account_id', sa.String(), nullable=True),
        sa.Column('additional_config', sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_integration_configs_id'), 'integration_configs', ['id'], unique=False)
    op.create_index(op.f('ix_integration_configs_service_name'), 'integration_configs', ['service_name'], unique=False)

    # Create contact_mappings
    op.create_table('contact_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('chatwoot_contact_id', sa.Integer(), nullable=False),
        sa.Column('service_name', sa.String(), nullable=False),
        sa.Column('external_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contact_mappings_chatwoot_contact_id'), 'contact_mappings', ['chatwoot_contact_id'], unique=False)
    op.create_index(op.f('ix_contact_mappings_id'), 'contact_mappings', ['id'], unique=False)
    op.create_index(op.f('ix_contact_mappings_service_name'), 'contact_mappings', ['service_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_contact_mappings_service_name'), table_name='contact_mappings')
    op.drop_index(op.f('ix_contact_mappings_id'), table_name='contact_mappings')
    op.drop_index(op.f('ix_contact_mappings_chatwoot_contact_id'), table_name='contact_mappings')
    op.drop_table('contact_mappings')
    op.drop_index(op.f('ix_integration_configs_service_name'), table_name='integration_configs')
    op.drop_index(op.f('ix_integration_configs_id'), table_name='integration_configs')
    op.drop_table('integration_configs')
    op.drop_table('rag_chunks')
    op.drop_table('rag_files')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('subscriptions')
    op.drop_index(op.f('ix_tenants_id'), table_name='tenants')
    op.drop_table('tenants')

