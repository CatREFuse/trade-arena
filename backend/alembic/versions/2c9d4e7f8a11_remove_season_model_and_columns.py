"""remove season model and columns

Revision ID: 2c9d4e7f8a11
Revises: 9f3a2b1c4d5e
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2c9d4e7f8a11"
down_revision: Union[str, Sequence[str], None] = "9f3a2b1c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "wallets"):
        # 历史上一个 agent 可能存在多条钱包记录，保留最近一条。
        op.execute(
            """
            DELETE FROM wallets
            WHERE id IN (
              SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                         PARTITION BY agent_id
                         ORDER BY updated_at DESC, created_at DESC, id DESC
                       ) AS rn
                FROM wallets
              ) ranked
              WHERE rn > 1
            )
            """
        )

    # drop foreign keys that still reference seasons.season_id
    inspector = sa.inspect(bind)
    if _has_table(inspector, "accounts") and _has_column(inspector, "accounts", "season_id"):
        for fk in inspector.get_foreign_keys("accounts"):
            if "season_id" in (fk.get("constrained_columns") or []) and fk.get("name"):
                op.drop_constraint(fk["name"], "accounts", type_="foreignkey")

    if _has_table(inspector, "wallets") and _has_column(inspector, "wallets", "season_id"):
        for fk in inspector.get_foreign_keys("wallets"):
            if "season_id" in (fk.get("constrained_columns") or []) and fk.get("name"):
                op.drop_constraint(fk["name"], "wallets", type_="foreignkey")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "wallets"):
        unique_names = {
            item.get("name")
            for item in inspector.get_unique_constraints("wallets")
            if item.get("name")
        }
        if "uq_wallets_season_agent" in unique_names:
            op.drop_constraint("uq_wallets_season_agent", "wallets", type_="unique")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "accounts") and _has_column(inspector, "accounts", "season_id"):
        with op.batch_alter_table("accounts") as batch_op:
            batch_op.drop_column("season_id")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "wallets") and _has_column(inspector, "wallets", "season_id"):
        with op.batch_alter_table("wallets") as batch_op:
            batch_op.drop_column("season_id")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "wallets"):
        unique_names = {
            item.get("name")
            for item in inspector.get_unique_constraints("wallets")
            if item.get("name")
        }
        if "uq_wallets_agent_id" not in unique_names:
            op.create_unique_constraint("uq_wallets_agent_id", "wallets", ["agent_id"])

    inspector = sa.inspect(bind)
    if _has_table(inspector, "seasons"):
        op.drop_table("seasons")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "seasons"):
        op.create_table(
            "seasons",
            sa.Column("id", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    op.execute(
        """
        INSERT INTO seasons (id, name, start_date, status, created_at)
        VALUES ('legacy', 'legacy', CURRENT_DATE, 'active', NOW())
        ON CONFLICT (id) DO NOTHING
        """
    )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "accounts") and not _has_column(inspector, "accounts", "season_id"):
        with op.batch_alter_table("accounts") as batch_op:
            batch_op.add_column(sa.Column("season_id", sa.String(length=20), nullable=True))

    inspector = sa.inspect(bind)
    if _has_table(inspector, "wallets") and not _has_column(inspector, "wallets", "season_id"):
        with op.batch_alter_table("wallets") as batch_op:
            batch_op.add_column(sa.Column("season_id", sa.String(length=20), nullable=True))

    if _has_table(inspector, "accounts") and _has_column(inspector, "accounts", "season_id"):
        op.execute("UPDATE accounts SET season_id = 'legacy' WHERE season_id IS NULL")
        with op.batch_alter_table("accounts") as batch_op:
            batch_op.alter_column("season_id", existing_type=sa.String(length=20), nullable=False)
            batch_op.create_foreign_key("accounts_season_id_fkey", "seasons", ["season_id"], ["id"])

    inspector = sa.inspect(bind)
    if _has_table(inspector, "wallets") and _has_column(inspector, "wallets", "season_id"):
        op.execute("UPDATE wallets SET season_id = 'legacy' WHERE season_id IS NULL")
        with op.batch_alter_table("wallets") as batch_op:
            batch_op.alter_column("season_id", existing_type=sa.String(length=20), nullable=False)
            batch_op.create_foreign_key("wallets_season_id_fkey", "seasons", ["season_id"], ["id"])

    inspector = sa.inspect(bind)
    if _has_table(inspector, "wallets"):
        unique_names = {
            item.get("name")
            for item in inspector.get_unique_constraints("wallets")
            if item.get("name")
        }
        if "uq_wallets_agent_id" in unique_names:
            op.drop_constraint("uq_wallets_agent_id", "wallets", type_="unique")
        if "uq_wallets_season_agent" not in unique_names:
            op.create_unique_constraint("uq_wallets_season_agent", "wallets", ["season_id", "agent_id"])
