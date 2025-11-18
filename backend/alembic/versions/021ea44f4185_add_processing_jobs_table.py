"""add_processing_jobs_table

Revision ID: 021ea44f4185
Revises: d1bd209248c8
Create Date: 2025-11-17 19:00:52.327341

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '021ea44f4185'
down_revision: Union[str, None] = 'd1bd209248c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create processing_jobs table for tracking async message processing"""
    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('photo_id', sa.UUID(), nullable=False),
        sa.Column('queue_name', sa.String(length=100), nullable=True),
        sa.Column('message_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ondelete='CASCADE'),
    )

    # Create indexes for common queries
    op.create_index('ix_processing_jobs_photo_id', 'processing_jobs', ['photo_id'])
    op.create_index('ix_processing_jobs_status', 'processing_jobs', ['status'])
    op.create_index('ix_processing_jobs_message_id', 'processing_jobs', ['message_id'])
    op.create_index('ix_processing_jobs_created_at', 'processing_jobs', ['created_at'])


def downgrade() -> None:
    """Drop processing_jobs table and indexes"""
    op.drop_index('ix_processing_jobs_created_at', table_name='processing_jobs')
    op.drop_index('ix_processing_jobs_message_id', table_name='processing_jobs')
    op.drop_index('ix_processing_jobs_status', table_name='processing_jobs')
    op.drop_index('ix_processing_jobs_photo_id', table_name='processing_jobs')
    op.drop_table('processing_jobs')
