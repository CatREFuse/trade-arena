"""add wallets and trade fx audit fields

Revision ID: 9f3a2b1c4d5e
Revises: 0a5b9c7d4e21
Create Date: 2026-04-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f3a2b1c4d5e"
down_revision: Union[str, Sequence[str], None] = "0a5b9c7d4e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("season_id", sa.String(length=20), nullable=False),
        sa.Column("agent_id", sa.String(length=30), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=5),
            nullable=False,
            server_default=sa.text("'CNY'"),
        ),
        sa.Column("initial_cash", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("cash", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("season_id", "agent_id", name="uq_wallets_season_agent"),
    )

    op.add_column(
        "trades",
        sa.Column("fx_rate", sa.Numeric(precision=18, scale=8), nullable=True),
    )
    op.add_column(
        "trades",
        sa.Column("fx_pair", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "trades",
        sa.Column("amount_cny", sa.Numeric(precision=15, scale=2), nullable=True),
    )
    op.add_column(
        "trades",
        sa.Column("fee_cny", sa.Numeric(precision=15, scale=2), nullable=True),
    )
    op.add_column(
        "trades",
        sa.Column("cash_after_cny", sa.Numeric(precision=15, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trades", "cash_after_cny")
    op.drop_column("trades", "fee_cny")
    op.drop_column("trades", "amount_cny")
    op.drop_column("trades", "fx_pair")
    op.drop_column("trades", "fx_rate")
    op.drop_table("wallets")
