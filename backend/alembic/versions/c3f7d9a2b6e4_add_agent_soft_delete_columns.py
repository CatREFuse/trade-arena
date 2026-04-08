"""add agent soft delete columns

Revision ID: c3f7d9a2b6e4
Revises: 2c9d4e7f8a11
Create Date: 2026-04-08 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3f7d9a2b6e4"
down_revision: Union[str, Sequence[str], None] = "2c9d4e7f8a11"
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
    if not _has_table(inspector, "agents"):
        return

    with op.batch_alter_table("agents") as batch_op:
        if not _has_column(inspector, "agents", "is_deleted"):
            batch_op.add_column(
                sa.Column(
                    "is_deleted",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                )
            )
        if not _has_column(inspector, "agents", "deleted_at"):
            batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        if not _has_column(inspector, "agents", "deleted_by"):
            batch_op.add_column(sa.Column("deleted_by", sa.String(length=100), nullable=True))
        if not _has_column(inspector, "agents", "delete_reason"):
            batch_op.add_column(sa.Column("delete_reason", sa.Text(), nullable=True))

    inspector = sa.inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes("agents") if item.get("name")}
    if "ix_agents_is_deleted" not in indexes:
        op.create_index("ix_agents_is_deleted", "agents", ["is_deleted"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "agents"):
        return

    indexes = {item["name"] for item in inspector.get_indexes("agents") if item.get("name")}
    if "ix_agents_is_deleted" in indexes:
        op.drop_index("ix_agents_is_deleted", table_name="agents")

    inspector = sa.inspect(bind)
    with op.batch_alter_table("agents") as batch_op:
        if _has_column(inspector, "agents", "delete_reason"):
            batch_op.drop_column("delete_reason")
        if _has_column(inspector, "agents", "deleted_by"):
            batch_op.drop_column("deleted_by")
        if _has_column(inspector, "agents", "deleted_at"):
            batch_op.drop_column("deleted_at")
        if _has_column(inspector, "agents", "is_deleted"):
            batch_op.drop_column("is_deleted")
