"""All DB access for research runs. No web imports here."""

import uuid
from datetime import UTC, datetime

from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot
from fathomark_core.snapshot import ScoreSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session

from fathomark_storage.models import (
    EvidenceItemRow,
    FactorProposalRow,
    HumanDecisionRow,
    ResearchRunRow,
    ResearchVersionRow,
    ScoreSnapshotRow,
)
from fathomark_storage.state_machine import RunState, transition


class ConcurrencyError(RuntimeError):
    def __init__(self, expected: int, actual: int):
        super().__init__(f"lock_version conflict: expected {expected}, actual {actual}")
        self.expected = expected
        self.actual = actual


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


class RunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_run(self, *, idem_key: str, scope: ScopeSnapshot):
        existing = self.session.scalar(
            select(ResearchRunRow).where(ResearchRunRow.idempotency_key == idem_key)
        )
        if existing is not None:
            return existing, False
        now = datetime.now(UTC)
        row = ResearchRunRow(
            id=_uid("run"),
            idempotency_key=idem_key,
            symbol=scope.symbol,
            exchange=scope.exchange,
            research_role=scope.research_role,
            horizon=scope.horizon,
            research_date=scope.research_date,
            data_cutoff=scope.data_cutoff,
            framework_ref=scope.framework_ref,
            state=RunState.CREATED.value,
            lock_version=0,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        self.session.flush()
        return row, True

    def get(self, run_id: str) -> ResearchRunRow:
        row = self.session.get(ResearchRunRow, run_id)
        if row is None:
            raise LookupError(f"run not found: {run_id}")
        return row

    def advance(self, run_id: str, target: RunState) -> None:
        row = self.get(run_id)
        row.state = transition(RunState(row.state), target).value
        row.lock_version += 1
        row.updated_at = datetime.now(UTC)
        self.session.flush()

    def touch(self, run_id: str) -> None:
        """Bump lock_version without a state transition (human edits in place)."""
        row = self.get(run_id)
        row.lock_version += 1
        row.updated_at = datetime.now(UTC)
        self.session.flush()

    def scope_of(self, run_id: str) -> ScopeSnapshot:
        r = self.get(run_id)
        return ScopeSnapshot(
            symbol=r.symbol,
            exchange=r.exchange,
            research_role=r.research_role,
            horizon=r.horizon,
            research_date=r.research_date,
            data_cutoff=r.data_cutoff,
            framework_ref=r.framework_ref,
        )

    def add_evidence(self, run_id: str, items: list[EvidenceItem]) -> int:
        self.get(run_id)
        existing = {
            e.evidence_id
            for e in self.session.scalars(
                select(EvidenceItemRow).where(EvidenceItemRow.run_id == run_id)
            )
        }
        for it in items:
            if it.id in existing:
                raise ValueError(f"duplicate evidence id: {it.id}")
            self.session.add(
                EvidenceItemRow(
                    run_id=run_id,
                    evidence_id=it.id,
                    source_name=it.source_name,
                    source_class=it.source_class,
                    url=it.url,
                    published_date=it.published_date,
                    data_period_end=it.data_period_end,
                    accessed_at=it.accessed_at,
                    grade=it.grade,
                    content_hash=it.content_hash,
                    excerpt=it.excerpt,
                )
            )
        self.session.flush()
        return len(items)

    def add_proposals(
        self, run_id: str, proposals: list[FactorProposal], origin: str = "agent"
    ) -> None:
        self.get(run_id)
        existing = {
            p.factor
            for p in self.session.scalars(
                select(FactorProposalRow).where(FactorProposalRow.run_id == run_id)
            )
        }
        for p in proposals:
            if p.factor in existing:
                raise ValueError(f"duplicate proposal for factor {p.factor}")
            self.session.add(
                FactorProposalRow(
                    run_id=run_id,
                    factor=p.factor,
                    proposed_score=p.proposed_score,
                    rationale=p.rationale,
                    evidence_ids=p.evidence_ids,
                    counter_evidence_ids=p.counter_evidence_ids,
                    confidence=p.confidence,
                    missing_data=p.missing_data,
                    as_of_date=p.as_of_date,
                    origin=origin,
                )
            )
        self.session.flush()

    def replace_proposal_score(
        self, run_id: str, factor: str, score: float, rationale: str
    ) -> None:
        row = self.session.scalar(
            select(FactorProposalRow).where(
                FactorProposalRow.run_id == run_id, FactorProposalRow.factor == factor
            )
        )
        if row is None:
            raise LookupError(f"no proposal for factor {factor}")
        row.proposed_score = score
        row.rationale = rationale
        row.origin = "human"
        self.session.flush()

    def evidence_of(self, run_id: str) -> list[EvidenceItem]:
        rows = self.session.scalars(
            select(EvidenceItemRow).where(EvidenceItemRow.run_id == run_id)
        )
        return [
            EvidenceItem(
                id=r.evidence_id,
                source_name=r.source_name,
                source_class=r.source_class,
                url=r.url,
                published_date=r.published_date,
                data_period_end=r.data_period_end,
                accessed_at=r.accessed_at,
                grade=r.grade,
                content_hash=r.content_hash,
                excerpt=r.excerpt,
            )
            for r in rows
        ]

    def proposals_of(self, run_id: str) -> list[FactorProposal]:
        rows = self.session.scalars(
            select(FactorProposalRow).where(FactorProposalRow.run_id == run_id)
        )
        return [
            FactorProposal(
                factor=r.factor,
                proposed_score=r.proposed_score,
                rationale=r.rationale,
                evidence_ids=r.evidence_ids,
                counter_evidence_ids=r.counter_evidence_ids,
                confidence=r.confidence,
                missing_data=r.missing_data,
                as_of_date=r.as_of_date,
            )
            for r in rows
        ]

    def save_draft_snapshot(self, run_id: str, snapshot: ScoreSnapshot) -> None:
        self.session.add(
            ScoreSnapshotRow(
                id=_uid("snap"),
                run_id=run_id,
                snapshot_json=snapshot.model_dump(mode="json"),
                content_hash=snapshot.content_hash,
                kind="draft",
                created_at=datetime.now(UTC),
            )
        )
        self.session.flush()

    def latest_snapshot(self, run_id: str) -> ScoreSnapshotRow | None:
        return self.session.scalar(
            select(ScoreSnapshotRow)
            .where(ScoreSnapshotRow.run_id == run_id)
            .order_by(ScoreSnapshotRow.created_at.desc())
            .limit(1)
        )

    def record_decision(
        self, run_id, action, factor, agent_score, final_score, reason, actor
    ) -> None:
        self.session.add(
            HumanDecisionRow(
                id=_uid("dec"),
                run_id=run_id,
                action=action,
                factor=factor,
                agent_score=agent_score,
                final_score=final_score,
                reason=reason,
                actor=actor,
                created_at=datetime.now(UTC),
            )
        )
        self.session.flush()

    def find_version_by_idem(self, idem_key: str) -> ResearchVersionRow | None:
        return self.session.scalar(
            select(ResearchVersionRow).where(
                ResearchVersionRow.idempotency_key == idem_key
            )
        )

    def create_version(self, run_id: str, idem_key: str, expected_lock: int):
        existing = self.find_version_by_idem(idem_key)
        if existing is not None:
            return existing, False
        row = self.get(run_id)
        if row.lock_version != expected_lock:
            raise ConcurrencyError(expected_lock, row.lock_version)
        snap = self.latest_snapshot(run_id)
        if snap is None:
            raise LookupError("no draft snapshot to approve")
        count = len(
            self.session.scalars(
                select(ResearchVersionRow).where(ResearchVersionRow.run_id == run_id)
            ).all()
        )
        version = ResearchVersionRow(
            id=_uid("ver"),
            run_id=run_id,
            version_no=count + 1,
            snapshot_json=snap.snapshot_json,
            content_hash=snap.content_hash,
            idempotency_key=idem_key,
            created_at=datetime.now(UTC),
        )
        self.session.add(version)
        self.advance(run_id, RunState.APPROVED)
        return version, True
