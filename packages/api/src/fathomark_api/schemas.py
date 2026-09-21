"""API request/response DTOs."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    symbol: str
    exchange: str
    research_role: Literal["core", "offensive", "tactical"]
    horizon: str
    research_date: date
    data_cutoff: date
    framework_ref: str


class RunResponse(BaseModel):
    id: str
    state: str
    lock_version: int
    symbol: str
    exchange: str
    research_role: str
    horizon: str
    research_date: date
    data_cutoff: date
    framework_ref: str
    created_at: datetime
    updated_at: datetime


class IngestEvidenceRequest(BaseModel):
    evidence: list[dict]  # validated into core EvidenceItem in service


class IngestProposalsRequest(BaseModel):
    proposals: list[dict]


class DecisionRequest(BaseModel):
    action: Literal["accept", "modify", "return"]
    factor: str | None = None
    final_score: float | None = None
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    expected_lock_version: int


class ApproveRequest(BaseModel):
    expected_lock_version: int


class ResolveReviewRequest(BaseModel):
    reason: str = Field(min_length=1)
    actor: str = Field(min_length=1)


class VersionResponse(BaseModel):
    id: str
    run_id: str
    version_no: int
    snapshot_json: dict
    content_hash: str
    created_at: datetime


class ResultResponse(BaseModel):
    run_id: str
    state: str
    snapshot: dict | None
    version: dict | None


class ArtifactUploadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    media_type: str = Field(min_length=1, max_length=160)
    content_base64: str = Field(min_length=1, max_length=16_000_000)
    manifest_hash: str = Field(min_length=8, max_length=80)
    status: Literal["draft", "approved"]


class ArtifactResponse(BaseModel):
    id: str
    run_id: str
    name: str
    media_type: str
    size_bytes: int
    content_hash: str
    manifest_hash: str
    status: Literal["draft", "approved"]
    created_at: datetime
    download_url: str
