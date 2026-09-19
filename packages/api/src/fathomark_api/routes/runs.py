"""Research-run endpoints."""

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ProposalError,
    ScopeSnapshot,
)
from fathomark_storage.repository import ConcurrencyError, RunRepository

from fathomark_api.schemas import (
    ApproveRequest,
    CreateRunRequest,
    DecisionRequest,
    IngestEvidenceRequest,
    IngestProposalsRequest,
    ResolveReviewRequest,
    ResultResponse,
    RunResponse,
    VersionResponse,
)
from fathomark_api.services import RunService, StateConflict

router = APIRouter()


def _service(request: Request) -> RunService:
    repo = RunRepository(request.app.state.session_factory())
    return RunService(repo, request.app.state.framework_dir)


def _run_response(row) -> RunResponse:
    return RunResponse(
        id=row.id,
        state=row.state,
        lock_version=row.lock_version,
        symbol=row.symbol,
        exchange=row.exchange,
        research_role=row.research_role,
        horizon=row.horizon,
        research_date=row.research_date,
        data_cutoff=row.data_cutoff,
        framework_ref=row.framework_ref,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _version_response(row) -> VersionResponse:
    return VersionResponse(
        id=row.id,
        run_id=row.run_id,
        version_no=row.version_no,
        snapshot_json=row.snapshot_json,
        content_hash=row.content_hash,
        created_at=row.created_at,
    )


def _error(status: int, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=status)


def _handle(service: RunService, fn):
    """Run a mutation; map domain errors to HTTP; commit or rollback."""
    try:
        result = fn()
    except LookupError as exc:
        service.repo.session.rollback()
        return _error(404, exc)
    except (StateConflict, ConcurrencyError) as exc:
        service.repo.session.rollback()
        return _error(409, exc)
    except (ValueError, ProposalError) as exc:
        service.repo.session.rollback()
        return _error(422, exc)
    service.repo.session.commit()
    return result


@router.post("/research-runs", status_code=201)
def create_run(
    payload: CreateRunRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None),
):
    if not idempotency_key:
        return JSONResponse(
            {"detail": "Idempotency-Key header required"}, status_code=400
        )
    service = _service(request)
    row, created = service.repo.create_run(
        idem_key=idempotency_key, scope=ScopeSnapshot(**payload.model_dump())
    )
    service.repo.session.commit()
    response.status_code = 201 if created else 200
    return _run_response(row)


@router.get("/research-runs/{run_id}")
def get_run(run_id: str, request: Request):
    service = _service(request)
    try:
        return _run_response(service.repo.get(run_id))
    except LookupError as exc:
        return _error(404, exc)


@router.post("/research-runs/{run_id}/evidence")
def ingest_evidence(run_id: str, payload: IngestEvidenceRequest, request: Request):
    service = _service(request)
    try:
        items = [EvidenceItem.model_validate(e) for e in payload.evidence]
    except ValueError as exc:
        return _error(422, exc)

    def op():
        service.ingest_evidence(run_id, items)
        return _run_response(service.repo.get(run_id))

    return _handle(service, op)


@router.post("/research-runs/{run_id}/factor-proposals")
def ingest_proposals(run_id: str, payload: IngestProposalsRequest, request: Request):
    service = _service(request)
    try:
        proposals = [FactorProposal.model_validate(p) for p in payload.proposals]
    except ValueError as exc:
        return _error(422, exc)

    def op():
        service.ingest_proposals(run_id, proposals)
        return _run_response(service.repo.get(run_id))

    return _handle(service, op)


@router.post("/research-runs/{run_id}/compute")
def compute(run_id: str, request: Request):
    service = _service(request)
    return _handle(service, lambda: service.compute(run_id).model_dump(mode="json"))


@router.get("/research-runs/{run_id}/result")
def get_result(run_id: str, request: Request):
    service = _service(request)
    try:
        row = service.repo.get(run_id)
    except LookupError as exc:
        return _error(404, exc)
    snap = service.repo.latest_snapshot(run_id)
    version = None
    if row.state == "approved":
        from fathomark_storage.models import ResearchVersionRow
        from sqlalchemy import select

        version = service.repo.session.scalar(
            select(ResearchVersionRow)
            .where(ResearchVersionRow.run_id == run_id)
            .order_by(ResearchVersionRow.version_no.desc())
            .limit(1)
        )
    return ResultResponse(
        run_id=run_id,
        state=row.state,
        snapshot=snap.snapshot_json if snap else None,
        version=(
            _version_response(version).model_dump(mode="json") if version else None
        ),
    )


@router.post("/research-runs/{run_id}/review-decisions")
def review_decision(run_id: str, payload: DecisionRequest, request: Request):
    service = _service(request)

    def op():
        service.review(run_id, payload)
        return _run_response(service.repo.get(run_id))

    return _handle(service, op)


@router.post("/research-runs/{run_id}/approve", status_code=201)
def approve(
    run_id: str,
    payload: ApproveRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None),
    actor: str = Header(default="unknown"),
):
    if not idempotency_key:
        return JSONResponse(
            {"detail": "Idempotency-Key header required"}, status_code=400
        )
    service = _service(request)

    def op():
        version, created = service.approve(
            run_id, payload.expected_lock_version, idempotency_key, actor
        )
        response.status_code = 201 if created else 200
        return _version_response(version)

    return _handle(service, op)


@router.post("/research-runs/{run_id}/cancel")
def cancel(run_id: str, request: Request):
    service = _service(request)

    def op():
        service.cancel(run_id)
        return _run_response(service.repo.get(run_id))

    return _handle(service, op)


@router.post("/research-runs/{run_id}/retry")
def retry(
    run_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None),
):
    if not idempotency_key:
        return JSONResponse(
            {"detail": "Idempotency-Key header required"}, status_code=400
        )
    service = _service(request)

    def op():
        service.retry(run_id)
        return _run_response(service.repo.get(run_id))

    return _handle(service, op)


@router.post("/research-runs/{run_id}/resolve-review")
def resolve_review(run_id: str, payload: ResolveReviewRequest, request: Request):
    service = _service(request)

    def op():
        service.resolve_review(run_id, payload.reason, payload.actor)
        return _run_response(service.repo.get(run_id))

    return _handle(service, op)
