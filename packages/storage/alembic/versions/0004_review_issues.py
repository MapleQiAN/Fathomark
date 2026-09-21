"""review issues

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_issues",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("factor", sa.String(length=64), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"]),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("run_id", "category", "factor", "rationale"),
    )


def downgrade() -> None:
    op.drop_table("review_issues")
