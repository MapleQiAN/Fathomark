"""Synchronous client for the Fathomark /v1 research-run API."""

from typing import Any, Self

import httpx

API_PREFIX = "/v1"


class FathomarkAPIError(Exception):
    """Raised when the API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class FathomarkClient:
    """Thin synchronous wrapper over the /v1 research-run endpoints.

    Pass a pre-configured ``httpx_client`` (e.g. with an ASGI transport for
    tests, or custom auth/timeouts) to control connection behavior; otherwise
    a default client bound to ``base_url`` is created.
    """

    def __init__(self, base_url: str, httpx_client: httpx.Client | None = None):
        self._base_url = base_url.rstrip("/")
        self._http = httpx_client or httpx.Client(base_url=self._base_url)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _url(self, path: str) -> str:
        return f"{self._base_url}{API_PREFIX}{path}"

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        resp = self._http.request(method, self._url(path), **kwargs)
        if resp.is_error:
            detail: Any
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise FathomarkAPIError(resp.status_code, str(detail))
        return resp.json()

    def create_run(self, payload: dict, idem_key: str) -> dict:
        """Create a research run (idempotent per ``idem_key``)."""
        return self._request(
            "POST", "/research-runs", json=payload, headers=_idem(idem_key)
        )

    def get_run(self, run_id: str) -> dict:
        return self._request("GET", f"/research-runs/{run_id}")

    def ingest_evidence(self, run_id: str, evidence: list[dict]) -> dict:
        return self._request(
            "POST", f"/research-runs/{run_id}/evidence", json={"evidence": evidence}
        )

    def ingest_proposals(self, run_id: str, proposals: list[dict]) -> dict:
        return self._request(
            "POST",
            f"/research-runs/{run_id}/factor-proposals",
            json={"proposals": proposals},
        )

    def compute(self, run_id: str) -> dict:
        """Run deterministic scoring; returns the draft snapshot."""
        return self._request("POST", f"/research-runs/{run_id}/compute")

    def get_result(self, run_id: str) -> dict:
        return self._request("GET", f"/research-runs/{run_id}/result")

    def review(self, run_id: str, decision: dict) -> dict:
        """Submit a review decision (accept / modify / return)."""
        return self._request(
            "POST", f"/research-runs/{run_id}/review-decisions", json=decision
        )

    def approve(
        self,
        run_id: str,
        expected_lock_version: int,
        idem_key: str,
        actor: str = "sdk",
    ) -> dict:
        """Approve a draft run, creating an immutable version."""
        return self._request(
            "POST",
            f"/research-runs/{run_id}/approve",
            json={"expected_lock_version": expected_lock_version},
            headers={**_idem(idem_key), "actor": actor},
        )

    def cancel(self, run_id: str) -> dict:
        return self._request("POST", f"/research-runs/{run_id}/cancel")

    def retry(self, run_id: str, idem_key: str) -> dict:
        return self._request(
            "POST", f"/research-runs/{run_id}/retry", headers=_idem(idem_key)
        )

    def resolve_review(self, run_id: str, reason: str, actor: str) -> dict:
        return self._request(
            "POST",
            f"/research-runs/{run_id}/resolve-review",
            json={"reason": reason, "actor": actor},
        )


def _idem(key: str) -> dict[str, str]:
    return {"Idempotency-Key": key}
