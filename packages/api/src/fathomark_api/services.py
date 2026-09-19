"""Service layer: orchestrates repository + deterministic core."""

import time
from pathlib import Path

from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ProposalError
from fathomark_storage.repository import ConcurrencyError, RunRepository
from fathomark_storage.state_machine import TERMINAL_STATES, RunState

from fathomark_api.webhooks import WebhookDispatcher, WebhookEvent, notify


class StateConflict(RuntimeError):
    pass


class RunService:
    def __init__(
        self,
        repo: RunRepository,
        framework_dir: Path,
        dispatcher: WebhookDispatcher | None = None,
    ):
        self.repo = repo
        self.framework_dir = framework_dir
        self.dispatcher = dispatcher
        self._pending_events: list[WebhookEvent] = []

    def pending_events(self) -> list[WebhookEvent]:
        """Return queued webhook events and clear the queue."""
        events, self._pending_events = self._pending_events, []
        return events

    def dispatch_pending(self) -> None:
        """Dispatch queued events; call only after a successful commit.

        Events queued by a mutation that later rolls back are never
        dispatched (the queue dies with the per-request service).
        """
        for event in self.pending_events():
            notify(self.dispatcher, event)

    def _require_state(self, run_id: str, *states: RunState):
        row = self.repo.get(run_id)
        if RunState(row.state) not in states:
            raise StateConflict(f"run {run_id} in state {row.state}")
        return row

    def _framework(self):
        return load_framework(self.framework_dir / "common-stock.yaml")

    def _evaluate(self, run_id: str):
        return evaluate(
            framework=self._framework(),
            scope=self.repo.scope_of(run_id),
            evidence=self.repo.evidence_of(run_id),
            proposals=self.repo.proposals_of(run_id),
        )

    def ingest_evidence(self, run_id: str, items: list[EvidenceItem]) -> None:
        self._require_state(run_id, RunState.CREATED)
        self.repo.add_evidence(run_id, items)
        self.repo.advance(run_id, RunState.COLLECTING)

    def ingest_proposals(self, run_id: str, proposals: list[FactorProposal]) -> None:
        self._require_state(run_id, RunState.COLLECTING)
        self.repo.add_proposals(run_id, proposals)
        self.repo.advance(run_id, RunState.ANALYZING)

    def compute(self, run_id: str):
        self._require_state(run_id, RunState.ANALYZING)
        snapshot = self._evaluate(run_id)
        self.repo.save_draft_snapshot(run_id, snapshot)
        self.repo.advance(run_id, RunState.DRAFT)
        return snapshot

    def review(self, run_id: str, req) -> None:
        row = self._require_state(run_id, RunState.DRAFT)
        if row.lock_version != req.expected_lock_version:
            raise ConcurrencyError(req.expected_lock_version, row.lock_version)
        if req.action == "modify":
            if req.factor is None or req.final_score is None:
                raise ProposalError("modify requires factor and final_score")
            current = {p.factor: p for p in self.repo.proposals_of(run_id)}[req.factor]
            self.repo.record_decision(
                run_id,
                "modify",
                req.factor,
                current.proposed_score,
                req.final_score,
                req.reason,
                req.actor,
            )
            self.repo.replace_proposal_score(
                run_id, req.factor, req.final_score, req.reason
            )
            self.repo.save_draft_snapshot(run_id, self._evaluate(run_id))
            self.repo.touch(run_id)
        elif req.action == "accept":
            self.repo.record_decision(
                run_id, "accept", req.factor, None, None, req.reason, req.actor
            )
            self.repo.touch(run_id)
        elif req.action == "return":
            self.repo.record_decision(
                run_id, "return", None, None, None, req.reason, req.actor
            )
            self.repo.advance(run_id, RunState.NEEDS_REVIEW)
            self._pending_events.append(
                WebhookEvent(
                    event="needs_review",
                    run_id=run_id,
                    occurred_at=int(time.time()),
                    payload={"reason": req.reason, "actor": req.actor},
                )
            )

    def approve(self, run_id: str, expected_lock: int, idem_key: str, actor: str):
        replay = self.repo.find_version_by_idem(idem_key)
        if replay is not None:
            if replay.run_id != run_id:
                raise StateConflict(
                    f"idempotency key {idem_key} already used by run {replay.run_id}"
                )
            return replay, False
        self._require_state(run_id, RunState.DRAFT)
        version, _ = self.repo.create_version(run_id, idem_key, expected_lock)
        self.repo.record_decision(
            run_id, "approve", None, None, None, f"approved by {actor}", actor
        )
        self._pending_events.append(
            WebhookEvent(
                event="approved",
                run_id=run_id,
                occurred_at=int(time.time()),
                payload={"version_id": version.id, "actor": actor},
            )
        )
        return version, True

    def cancel(self, run_id: str) -> None:
        row = self.repo.get(run_id)
        if RunState(row.state) in TERMINAL_STATES:
            raise StateConflict(f"run {run_id} already terminal ({row.state})")
        self.repo.advance(run_id, RunState.CANCELLED)

    def retry(self, run_id: str, idem_key: str) -> None:
        """Retry a failed run, idempotent per run + key.

        On success the key is persisted on the run row. A later request with
        the same key against the now-``collecting`` run is a replay and returns
        without change; any other state or a mismatched key conflicts.
        """
        row = self.repo.get(run_id)
        state = RunState(row.state)
        if state == RunState.FAILED:
            self.repo.advance(run_id, RunState.COLLECTING)
            row.retry_idem_key = idem_key
            self.repo.session.flush()
        elif state == RunState.COLLECTING and row.retry_idem_key == idem_key:
            return
        else:
            raise StateConflict(f"run {run_id} in state {row.state}")

    def resolve_review(self, run_id: str, reason: str, actor: str) -> None:
        self._require_state(run_id, RunState.NEEDS_REVIEW)
        if self.repo.latest_snapshot(run_id) is None:
            # needs_review from an agent failure has no draft to return to;
            # the run must be re-executed instead of advancing blind.
            raise StateConflict("run has no draft snapshot; re-execute instead")
        self.repo.record_decision(run_id, "resolve", None, None, None, reason, actor)
        self.repo.advance(run_id, RunState.DRAFT)
