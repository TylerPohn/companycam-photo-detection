"""add_password_hash_to_users

Revision ID: d1bd209248c8
Revises: c543a6160afc
Create Date: 2025-11-17 18:46:54.152180

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1bd209248c8'
down_revision: Union[str, None] = 'c543a6160afc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password_hash column to users table
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))

    # Set a default password hash for existing users (they will need to reset password)
    # Using bcrypt hash of "ChangeMe123!" as temporary password
    op.execute(
        "UPDATE users SET password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqgdOwjuji' "
        "WHERE password_hash IS NULL"
    )

    # Make password_hash non-nullable
    op.alter_column('users', 'password_hash', nullable=False)


def downgrade() -> None:
    # Remove password_hash column from users table
    op.drop_column('users', 'password_hash')
