"""Crear extension pgvector si no existe

Revision ID: 799346040a50
Revises: a1b2c3d4e5f6
Create Date: 2025-07-28 03:23:12.658204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '799346040a50'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")



def downgrade() -> None:
    """Downgrade schema."""
    pass
