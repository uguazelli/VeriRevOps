"""add custom_prompt to tenants

Revision ID: e9b74e2511c5
Revises: 43fff4508da9
Create Date: 2026-02-21 16:56:30.172586

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9b74e2511c5'
down_revision: Union[str, Sequence[str], None] = '43fff4508da9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tenants', sa.Column('custom_prompt', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tenants', 'custom_prompt')
