"""SQLAlchemy rows for M2. Portable types only (SQLite + PostgreSQL)."""

from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ResearchRunRow(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    symbol: Mapped[str] = mapped_column(String(16))
    exchange: Mapped[str] = mapped_column(String(16))
    research_role: Mapped[str] = mapped_column(String(16))
    horizon: Mapped[str] = mapped_column(String(32))
    research_date: Mapped[date]
    data_cutoff: Mapped[date]
    framework_ref: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="created")
    lock_version: Mapped[int] = mapped_column(Integer, default=0)
    supersedes_id: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class EvidenceItemRow(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("run_id", "evidence_id"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    evidence_id: Mapped[str] = mapped_column(String(40))
    source_name: Mapped[str] = mapped_column(String(200))
    source_class: Mapped[str] = mapped_column(String(32))
    url: Mapped[str | None] = mapped_column(Text)
    published_date: Mapped[date]
    data_period_end: Mapped[date | None]
    accessed_at: Mapped[datetime]
    grade: Mapped[str] = mapped_column(String(1))
    content_hash: Mapped[str] = mapped_column(String(80))
    excerpt: Mapped[str | None] = mapped_column(Text)


class FactorProposalRow(Base):
    __tablename__ = "factor_proposals"
    __table_args__ = (UniqueConstraint("run_id", "factor"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    factor: Mapped[str] = mapped_column(String(64))
    proposed_score: Mapped[float]
    rationale: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    counter_evidence_ids: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[str] = mapped_column(String(16))
    missing_data: Mapped[list] = mapped_column(JSON)
    as_of_date: Mapped[date]
    origin: Mapped[str] = mapped_column(String(8), default="agent")


class HumanDecisionRow(Base):
    __tablename__ = "human_decisions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    action: Mapped[str] = mapped_column(String(16))
    factor: Mapped[str | None] = mapped_column(String(64))
    agent_score: Mapped[float | None]
    final_score: Mapped[float | None]
    reason: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime]


class ScoreSnapshotRow(Base):
    __tablename__ = "score_snapshots"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(8), default="draft")
    created_at: Mapped[datetime]


class ResearchVersionRow(Base):
    __tablename__ = "research_versions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime]
