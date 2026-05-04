"""add element.description and component.text

Revision ID: 3c9d2f1b7a6a
Revises: 2a7c4f3b9e2b
Create Date: 2026-05-03 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c9d2f1b7a6a'
down_revision: Union[str, Sequence[str], None] = '2a7c4f3b9e2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('elements', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('components', sa.Column('text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('components', 'text')
    op.drop_column('elements', 'description')
