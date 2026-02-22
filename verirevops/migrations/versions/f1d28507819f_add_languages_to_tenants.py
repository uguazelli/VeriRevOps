"""add languages to tenants

Revision ID: f1d28507819f
Revises: e9b74e2511c5
Create Date: 2026-02-21 17:39:06.898145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1d28507819f'
down_revision: Union[str, Sequence[str], None] = 'e9b74e2511c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tenants', sa.Column('languages', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tenants', 'languages')
