"""store model feature schema

Revision ID: 003
Revises: 002
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ml_models", sa.Column("feature_names", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ml_models", "feature_names")
