"""step_runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-19 12:07:58.668089

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "step_runs",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("step", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=True),
        sa.Column("provider_version", sa.String(length=40), nullable=True),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["research_runs.id"],
        ),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("run_id", "step"),
    )


def downgrade() -> None:
    op.drop_table("step_runs")
