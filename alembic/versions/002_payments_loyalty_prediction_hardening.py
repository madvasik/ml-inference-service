"""payments loyalty prediction hardening

Revision ID: 002
Revises: 001
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


loyalty_tier_enum = sa.Enum("NONE", "BRONZE", "SILVER", "GOLD", name="loyaltytier")
payment_status_enum = sa.Enum("PENDING", "CONFIRMED", "FAILED", name="paymentstatus")


def upgrade() -> None:
    bind = op.get_bind()
    loyalty_tier_enum.create(bind, checkfirst=True)
    payment_status_enum.create(bind, checkfirst=True)

    op.execute("ALTER TYPE predictionstatus ADD VALUE IF NOT EXISTS 'PROCESSING'")

    op.add_column("users", sa.Column("loyalty_tier", loyalty_tier_enum, nullable=False, server_default="NONE"))
    op.add_column("users", sa.Column("loyalty_discount_percent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("loyalty_updated_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("predictions", sa.Column("task_id", sa.String(), nullable=True))
    op.add_column("predictions", sa.Column("base_cost", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("predictions", sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("predictions", sa.Column("discount_amount", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("predictions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("predictions", sa.Column("failure_reason", sa.String(), nullable=True))
    op.create_index("ix_predictions_task_id", "predictions", ["task_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("status", payment_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_payments_id", "payments", ["id"], unique=False)
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)

    op.create_table(
        "loyalty_tier_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tier", loyalty_tier_enum, nullable=False),
        sa.Column("monthly_threshold", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tier"),
    )
    op.create_index("ix_loyalty_tier_rules_id", "loyalty_tier_rules", ["id"], unique=False)

    op.bulk_insert(
        sa.table(
            "loyalty_tier_rules",
            sa.column("tier", loyalty_tier_enum),
            sa.column("monthly_threshold", sa.Integer()),
            sa.column("discount_percent", sa.Integer()),
            sa.column("priority", sa.Integer()),
            sa.column("is_active", sa.Boolean()),
        ),
        [
            {"tier": "BRONZE", "monthly_threshold": 50, "discount_percent": 5, "priority": 1, "is_active": True},
            {"tier": "SILVER", "monthly_threshold": 200, "discount_percent": 10, "priority": 2, "is_active": True},
            {"tier": "GOLD", "monthly_threshold": 500, "discount_percent": 20, "priority": 3, "is_active": True},
        ],
    )

    op.add_column("transactions", sa.Column("prediction_id", sa.Integer(), nullable=True))
    op.add_column("transactions", sa.Column("payment_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_transactions_prediction_id", "transactions", "predictions", ["prediction_id"], ["id"])
    op.create_foreign_key("fk_transactions_payment_id", "transactions", "payments", ["payment_id"], ["id"])
    op.create_index("ix_transactions_prediction_id", "transactions", ["prediction_id"], unique=False)
    op.create_index("ix_transactions_payment_id", "transactions", ["payment_id"], unique=False)
    op.create_unique_constraint("uq_transactions_prediction_id", "transactions", ["prediction_id"])
    op.create_unique_constraint("uq_transactions_payment_id", "transactions", ["payment_id"])


def downgrade() -> None:
    op.drop_constraint("uq_transactions_payment_id", "transactions", type_="unique")
    op.drop_constraint("uq_transactions_prediction_id", "transactions", type_="unique")
    op.drop_index("ix_transactions_payment_id", table_name="transactions")
    op.drop_index("ix_transactions_prediction_id", table_name="transactions")
    op.drop_constraint("fk_transactions_payment_id", "transactions", type_="foreignkey")
    op.drop_constraint("fk_transactions_prediction_id", "transactions", type_="foreignkey")
    op.drop_column("transactions", "payment_id")
    op.drop_column("transactions", "prediction_id")

    op.drop_index("ix_loyalty_tier_rules_id", table_name="loyalty_tier_rules")
    op.drop_table("loyalty_tier_rules")

    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_index("ix_payments_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_predictions_task_id", table_name="predictions")
    op.drop_column("predictions", "failure_reason")
    op.drop_column("predictions", "completed_at")
    op.drop_column("predictions", "discount_amount")
    op.drop_column("predictions", "discount_percent")
    op.drop_column("predictions", "base_cost")
    op.drop_column("predictions", "task_id")

    op.drop_column("users", "loyalty_updated_at")
    op.drop_column("users", "loyalty_discount_percent")
    op.drop_column("users", "loyalty_tier")

    payment_status_enum.drop(op.get_bind(), checkfirst=True)
    loyalty_tier_enum.drop(op.get_bind(), checkfirst=True)
