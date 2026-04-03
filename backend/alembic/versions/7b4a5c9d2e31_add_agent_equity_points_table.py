"""add agent equity points table

Revision ID: 7b4a5c9d2e31
Revises: 2c9d4e7f8a11
Create Date: 2026-04-02 18:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7b4a5c9d2e31"
down_revision = "2c9d4e7f8a11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_equity_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.String(length=30), nullable=False),
        sa.Column("point_time", sa.DateTime(), nullable=False),
        sa.Column("equity_cny", sa.Numeric(18, 6), nullable=False),
        sa.Column("return_pct", sa.Numeric(12, 6), nullable=False),
        sa.Column("cash_cny", sa.Numeric(18, 6), nullable=False),
        sa.Column("position_value_cny", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "point_time", name="uq_agent_equity_points_agent_time"),
    )
    op.create_index(
        "ix_agent_equity_points_point_time",
        "agent_equity_points",
        ["point_time"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_equity_points_point_time", table_name="agent_equity_points")
    op.drop_table("agent_equity_points")
