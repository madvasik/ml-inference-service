"""initial schema

Revision ID: 20250330_0001
Revises:
Create Date: 2025-03-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250330_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "admin", name="userrole"),
            nullable=False,
        ),
        sa.Column("balance_credits", sa.Integer(), nullable=False),
        sa.Column("pending_topup_discount_percent", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "promocodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("fixed_credits", "percent_next_topup", name="promocodetype"),
            nullable=False,
        ),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_activations", sa.Integer(), nullable=True),
        sa.Column("activations_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_promocodes_code"), "promocodes", ["code"], unique=False)

    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ml_models_owner_id"), "ml_models", ["owner_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("amount_money", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("credits_granted", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "completed", "failed", name="paymentstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f("ix_payments_user_id"), "payments", ["user_id"], unique=False)

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "debit_prediction",
                "credit_topup",
                "credit_promo",
                "adjustment",
                name="transactionkind",
            ),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("reference", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_credit_transactions_user_id"), "credit_transactions", ["user_id"], unique=False)

    op.create_table(
        "prediction_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ml_model_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "success", "failed", name="predictionjobstatus"),
            nullable=False,
        ),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ml_model_id"], ["ml_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prediction_jobs_ml_model_id"), "prediction_jobs", ["ml_model_id"], unique=False)
    op.create_index(op.f("ix_prediction_jobs_user_id"), "prediction_jobs", ["user_id"], unique=False)

    op.create_table(
        "promocode_redemptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("promocode_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["promocode_id"], ["promocodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "promocode_id", name="uq_user_promocode"),
    )
    op.create_index(op.f("ix_promocode_redemptions_promocode_id"), "promocode_redemptions", ["promocode_id"], unique=False)
    op.create_index(op.f("ix_promocode_redemptions_user_id"), "promocode_redemptions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_promocode_redemptions_user_id"), table_name="promocode_redemptions")
    op.drop_index(op.f("ix_promocode_redemptions_promocode_id"), table_name="promocode_redemptions")
    op.drop_table("promocode_redemptions")
    op.drop_index(op.f("ix_prediction_jobs_user_id"), table_name="prediction_jobs")
    op.drop_index(op.f("ix_prediction_jobs_ml_model_id"), table_name="prediction_jobs")
    op.drop_table("prediction_jobs")
    op.drop_index(op.f("ix_credit_transactions_user_id"), table_name="credit_transactions")
    op.drop_table("credit_transactions")
    op.drop_index(op.f("ix_payments_user_id"), table_name="payments")
    op.drop_table("payments")
    op.drop_index(op.f("ix_ml_models_owner_id"), table_name="ml_models")
    op.drop_table("ml_models")
    op.drop_index(op.f("ix_promocodes_code"), table_name="promocodes")
    op.drop_table("promocodes")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    sa.Enum(name="predictionjobstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="paymentstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="transactionkind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="promocodetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
