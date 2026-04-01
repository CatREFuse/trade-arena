"""allow shared account api_token

Revision ID: 0a5b9c7d4e21
Revises: 8f4f8da6a4f1
Create Date: 2026-04-01 10:41:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0a5b9c7d4e21"
down_revision: Union[str, Sequence[str], None] = "8f4f8da6a4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Registration creates US/CN twin accounts for one agent with the same api_token.
    # Keep lookup performance with a non-unique index instead of a unique constraint.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'accounts_api_token_key'
            ) THEN
                ALTER TABLE accounts DROP CONSTRAINT accounts_api_token_key;
            END IF;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_accounts_api_token ON accounts (api_token)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_accounts_api_token")
    op.create_unique_constraint("accounts_api_token_key", "accounts", ["api_token"])
