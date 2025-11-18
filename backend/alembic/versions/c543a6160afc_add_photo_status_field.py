"""add_photo_status_field

Revision ID: c543a6160afc
Revises: e5c5c38615eb
Create Date: 2025-11-17 18:25:46.368186

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c543a6160afc'
down_revision: Union[str, None] = 'e5c5c38615eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type
    op.execute("CREATE TYPE photostatus AS ENUM ('pending_upload', 'uploaded', 'processing', 'completed', 'failed')")

    # Add status column to photos table
    op.add_column('photos', sa.Column('status', sa.Enum('pending_upload', 'uploaded', 'processing', 'completed', 'failed', name='photostatus'), nullable=False, server_default='pending_upload'))

    # Create index on status column
    op.create_index(op.f('ix_photos_status'), 'photos', ['status'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_photos_status'), table_name='photos')

    # Drop column
    op.drop_column('photos', 'status')

    # Drop enum type
    op.execute("DROP TYPE photostatus")
