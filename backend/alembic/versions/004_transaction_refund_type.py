"""transaction refund type and composite uniqueness on prediction

Revision ID: 004
Revises: 003
Create Date: 2026-03-30
"""

from alembic import op


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE transactiontype ADD VALUE 'REFUND'")
    op.drop_constraint("uq_transactions_prediction_id", "transactions", type_="unique")
    op.create_unique_constraint(
        "uq_transactions_prediction_id_type",
        "transactions",
        ["prediction_id", "type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_transactions_prediction_id_type", "transactions", type_="unique")
    op.create_unique_constraint("uq_transactions_prediction_id", "transactions", ["prediction_id"])
