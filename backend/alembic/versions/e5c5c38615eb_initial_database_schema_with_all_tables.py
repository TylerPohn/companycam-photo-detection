"""Initial database schema with all tables

Revision ID: e5c5c38615eb
Revises:
Create Date: 2025-11-17 17:50:42.444216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'e5c5c38615eb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, server_default='contractor'),
        sa.Column('organization_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_organization_id', 'users', ['organization_id'])

    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
    )
    op.create_index('ix_projects_organization_id', 'projects', ['organization_id'])

    # Create photos table
    op.create_table(
        'photos',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', UUID(as_uuid=True), nullable=False),
        sa.Column('s3_url', sa.Text(), nullable=False),
        sa.Column('s3_key', sa.String(500), nullable=True, unique=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(50), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('exif_data', JSONB(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
    )
    op.create_index('ix_photos_user_id', 'photos', ['user_id'])
    op.create_index('ix_photos_project_id', 'photos', ['project_id'])
    op.create_index('ix_photos_created_at', 'photos', ['created_at'])

    # Create detections table
    op.create_table(
        'detections',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('photo_id', UUID(as_uuid=True), nullable=False),
        sa.Column('detection_type', sa.String(50), nullable=False),
        sa.Column('model_version', sa.String(100), nullable=True),
        sa.Column('results', JSONB(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('user_confirmed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('user_feedback', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ondelete='CASCADE'),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='check_confidence_range'),
        sa.CheckConstraint('processing_time_ms > 0', name='check_processing_time_positive'),
    )
    op.create_index('ix_detections_photo_id', 'detections', ['photo_id'])
    op.create_index('ix_detections_detection_type', 'detections', ['detection_type'])
    op.create_index('ix_detections_created_at', 'detections', ['created_at'])
    op.create_index('ix_detections_user_confirmed', 'detections', ['user_confirmed'])

    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('photo_id', UUID(as_uuid=True), nullable=False),
        sa.Column('tag', sa.String(100), nullable=False),
        sa.Column('source', sa.String(20), nullable=False, server_default='ai'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            'confidence IS NULL OR (confidence >= 0 AND confidence <= 1)',
            name='check_tag_confidence_range'
        ),
        sa.CheckConstraint("source IN ('ai', 'user')", name='check_tag_source'),
    )
    op.create_index('ix_tags_photo_id', 'tags', ['photo_id'])
    op.create_index('ix_tags_tag', 'tags', ['tag'])


def downgrade() -> None:
    # Drop tables in reverse order to respect foreign key constraints
    op.drop_table('tags')
    op.drop_table('detections')
    op.drop_table('photos')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('organizations')
