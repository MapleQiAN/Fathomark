"""metric observations

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_observations",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("metric", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("basis", sa.String(length=16), nullable=False),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("evidence_id", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"]),
        sa.ForeignKeyConstraint(
            ["run_id", "evidence_id"],
            ["evidence_items.run_id", "evidence_items.evidence_id"],
        ),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("run_id", "metric", "data_date", "evidence_id", "basis"),
    )


def downgrade() -> None:
    op.drop_table("metric_observations")
