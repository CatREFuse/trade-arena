"""add agent email fields

Revision ID: 8f4f8da6a4f1
Revises: 416490324e17
Create Date: 2026-03-19 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f4f8da6a4f1"
down_revision: Union[str, Sequence[str], None] = "416490324e17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("agents", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    op.create_unique_constraint("uq_agents_email", "agents", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_agents_email", "agents", type_="unique")
    op.drop_column("agents", "email_verified_at")
    op.drop_column("agents", "email")
