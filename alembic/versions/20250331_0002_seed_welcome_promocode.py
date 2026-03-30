"""seed WELCOME promocode (один раз на пользователя)

Revision ID: 20250331_0002
Revises: 20250330_0001
Create Date: 2025-03-31

Повторная активация тем же пользователем → 409 (запись в promocode_redemptions).
max_activations NULL — без глобального лимита (удобно для демо разным пользователям).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20250331_0002"
down_revision: Union[str, None] = "20250330_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO promocodes (code, kind, value, expires_at, max_activations, activations_count)
        VALUES (
            'WELCOME',
            'fixed_credits'::promocodetype,
            50,
            NULL,
            NULL,
            0
        )
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM promocodes WHERE code = 'WELCOME'")
