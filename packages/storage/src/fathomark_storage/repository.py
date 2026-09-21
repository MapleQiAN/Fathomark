"""All DB access for research runs. No web imports here."""

import hashlib
import uuid
from datetime import UTC, date, datetime

from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    MetricObservation,
    ReviewIssue,
    ScopeSnapshot,
)
from fathomark_core.snapshot import ScoreSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session

from fathomark_storage.models import (
    ArtifactRow,
    EvidenceItemRow,
    FactorProposalRow,
    HumanDecisionRow,
    MetricObservationRow,
    ResearchRunRow,
    ResearchVersionRow,
    ReviewIssueRow,
    ScoreSnapshotRow,
    StepRunRow,
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

    def add_metric_observations(
        self, run_id: str, observations: list[MetricObservation]
    ) -> int:
        self.get(run_id)
        evidence_ids = {
            evidence.evidence_id
            for evidence in self.session.scalars(
                select(EvidenceItemRow).where(EvidenceItemRow.run_id == run_id)
            )
        }
        for observation in observations:
            if observation.evidence_id not in evidence_ids:
                raise ValueError(f"unknown evidence id: {observation.evidence_id}")

        existing = {
            (
                observation.metric,
                observation.data_date,
                observation.evidence_id,
                observation.basis,
            )
            for observation in self.session.scalars(
                select(MetricObservationRow).where(
                    MetricObservationRow.run_id == run_id
                )
            )
        }
        batch: set[tuple[str, date, str, str]] = set()
        for observation in observations:
            key = (
                observation.metric,
                observation.data_date,
                observation.evidence_id,
                observation.basis,
            )
            if key in existing or key in batch:
                raise ValueError(f"duplicate metric observation: {key}")
            batch.add(key)

        for observation in observations:
            self.session.add(
                MetricObservationRow(
                    run_id=run_id,
                    metric=observation.metric,
                    value=observation.value,
                    unit=observation.unit,
                    currency=observation.currency,
                    basis=observation.basis,
                    formula=observation.formula,
                    data_date=observation.data_date,
                    evidence_id=observation.evidence_id,
                )
            )
        self.session.flush()
        return len(observations)

    def add_review_issues(self, run_id: str, issues: list[ReviewIssue]) -> int:
        self.get(run_id)
        evidence_ids = {
            evidence.evidence_id
            for evidence in self.session.scalars(
                select(EvidenceItemRow).where(EvidenceItemRow.run_id == run_id)
            )
        }
        for issue in issues:
            for evidence_id in issue.evidence_ids:
                if evidence_id not in evidence_ids:
                    raise ValueError(f"unknown evidence id: {evidence_id}")

        existing = {
            (issue.category, issue.factor, issue.rationale)
            for issue in self.session.scalars(
                select(ReviewIssueRow).where(ReviewIssueRow.run_id == run_id)
            )
        }
        batch: set[tuple[str, str | None, str]] = set()
        for issue in issues:
            key = (issue.category, issue.factor, issue.rationale)
            if key in existing or key in batch:
                raise ValueError(f"duplicate review issue: {key}")
            batch.add(key)

        for issue in issues:
            self.session.add(
                ReviewIssueRow(
                    run_id=run_id,
                    category=issue.category,
                    factor=issue.factor,
                    evidence_ids=issue.evidence_ids,
                    rationale=issue.rationale,
                    blocking=issue.blocking,
                    as_of_date=issue.as_of_date,
                )
            )
        self.session.flush()
        return len(issues)

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

    def metric_observations_of(self, run_id: str) -> list[MetricObservation]:
        rows = self.session.scalars(
            select(MetricObservationRow)
            .where(MetricObservationRow.run_id == run_id)
            .order_by(
                MetricObservationRow.data_date,
                MetricObservationRow.metric,
                MetricObservationRow.basis,
                MetricObservationRow.evidence_id,
            )
        )
        return [
            MetricObservation(
                metric=row.metric,
                value=row.value,
                unit=row.unit,
                currency=row.currency,
                basis=row.basis,
                formula=row.formula,
                data_date=row.data_date,
                evidence_id=row.evidence_id,
            )
            for row in rows
        ]

    def review_issues_of(self, run_id: str) -> list[ReviewIssue]:
        rows = self.session.scalars(
            select(ReviewIssueRow)
            .where(ReviewIssueRow.run_id == run_id)
            .order_by(ReviewIssueRow.pk)
        )
        return [
            ReviewIssue(
                category=row.category,
                factor=row.factor,
                evidence_ids=row.evidence_ids,
                rationale=row.rationale,
                blocking=row.blocking,
                as_of_date=row.as_of_date,
            )
            for row in rows
        ]

    def has_blocking_review_issues(self, run_id: str) -> bool:
        return (
            self.session.scalar(
                select(ReviewIssueRow.pk)
                .where(
                    ReviewIssueRow.run_id == run_id,
                    ReviewIssueRow.blocking.is_(True),
                )
                .limit(1)
            )
            is not None
        )

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

    def step_record(self, run_id: str, step: str) -> StepRunRow | None:
        return self.session.scalar(
            select(StepRunRow).where(
                StepRunRow.run_id == run_id, StepRunRow.step == step
            )
        )

    def begin_step(
        self, run_id, step, input_hash, provider_name=None, provider_version=None
    ) -> StepRunRow:
        self.get(run_id)
        rec = self.step_record(run_id, step)
        now = datetime.now(UTC)
        if rec is None:
            rec = StepRunRow(
                run_id=run_id,
                step=step,
                status="running",
                attempt=1,
                provider_name=provider_name,
                provider_version=provider_version,
                input_hash=input_hash,
                output_json=None,
                error=None,
                started_at=now,
                finished_at=None,
            )
            self.session.add(rec)
        else:
            rec.status = "running"
            rec.attempt += 1
            rec.provider_name = provider_name
            rec.provider_version = provider_version
            rec.input_hash = input_hash
            rec.output_json = None
            rec.error = None
            rec.started_at = now
            rec.finished_at = None
        self.session.flush()
        return rec

    def finish_step(self, run_id: str, step: str, output: dict) -> None:
        rec = self.step_record(run_id, step)
        assert rec is not None and rec.status == "running"
        rec.status = "succeeded"
        rec.output_json = output
        rec.finished_at = datetime.now(UTC)
        self.session.flush()

    def fail_step(self, run_id: str, step: str, error: str) -> None:
        rec = self.step_record(run_id, step)
        assert rec is not None and rec.status == "running"
        rec.status = "failed"
        rec.error = error
        rec.finished_at = datetime.now(UTC)
        self.session.flush()

    def steps_of(self, run_id: str) -> list[StepRunRow]:
        return list(
            self.session.scalars(select(StepRunRow).where(StepRunRow.run_id == run_id))
        )

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

    def find_artifact_by_idem(self, idem_key: str) -> ArtifactRow | None:
        return self.session.scalar(
            select(ArtifactRow).where(ArtifactRow.idempotency_key == idem_key)
        )

    def get_artifact(self, artifact_id: str) -> ArtifactRow:
        row = self.session.get(ArtifactRow, artifact_id)
        if row is None:
            raise LookupError(f"artifact not found: {artifact_id}")
        return row

    def artifacts_of(self, run_id: str) -> list[ArtifactRow]:
        self.get(run_id)
        return list(
            self.session.scalars(
                select(ArtifactRow)
                .where(ArtifactRow.run_id == run_id)
                .order_by(ArtifactRow.name, ArtifactRow.status)
            )
        )

    def create_artifact(
        self,
        run_id: str,
        *,
        idem_key: str,
        name: str,
        media_type: str,
        content: bytes,
        manifest_hash: str,
        status: str,
    ) -> tuple[ArtifactRow, bool]:
        existing = self.find_artifact_by_idem(idem_key)
        if existing is not None:
            if existing.run_id != run_id:
                raise ValueError(
                    f"idempotency key {idem_key} already used by run {existing.run_id}"
                )
            return existing, False
        self.get(run_id)
        _validate_artifact_name(name)
        if not media_type.strip() or len(media_type) > 160:
            raise ValueError(
                "artifact media_type must be non-empty and at most 160 characters"
            )
        if status not in {"draft", "approved"}:
            raise ValueError(f"unsupported artifact status: {status}")
        if not manifest_hash.startswith("sha256:"):
            raise ValueError("artifact manifest_hash must be sha256-prefixed")
        duplicate = self.session.scalar(
            select(ArtifactRow).where(
                ArtifactRow.run_id == run_id,
                ArtifactRow.name == name,
                ArtifactRow.status == status,
            )
        )
        if duplicate is not None:
            raise ValueError(f"duplicate artifact: {name} ({status})")
        row = ArtifactRow(
            id=_uid("art"),
            run_id=run_id,
            name=name,
            media_type=media_type,
            size_bytes=len(content),
            content_hash="sha256:" + hashlib.sha256(content).hexdigest(),
            manifest_hash=manifest_hash,
            status=status,
            content_bytes=content,
            idempotency_key=idem_key,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        self.session.flush()
        return row, True


def _validate_artifact_name(name: str) -> None:
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or '"' in name
        or any(ord(char) < 32 for char in name)
    ):
        raise ValueError(f"invalid artifact name: {name!r}")
