# API and Python SDK

The versioned contract is [docs/api/openapi-v1.json](api/openapi-v1.json). The
API is a headless REST surface under `/v1`; the local Compose demo is described
in [quickstart.md](quickstart.md).

## Run lifecycle

1. `POST /research-runs` with an `Idempotency-Key` creates a run.
2. A configured orchestrator uses `POST /research-runs/{id}/execute`, or a
   caller can ingest evidence and proposals then call `/compute`.
3. Review with `/review-decisions` while the run is `draft`.
4. Read `lock_version`, then `POST /approve` with a new idempotency key and the
   expected lock version. Approval creates an immutable version.
5. `GET /research-runs/{id}/result` returns the draft snapshot or approved
   version.
6. Upload a rendered artifact with `POST /research-runs/{id}/artifacts`, using
   base64 content and the manifest hash from the reporting package. List
   artifacts with `GET /research-runs/{id}/artifacts` and download bytes from
   the returned `/v1/artifacts/{artifact_id}/download` URL. Draft artifacts are
   accepted only for draft runs; approved artifacts are accepted only after the
   run is approved.

Cancellation, retry, review resolution, webhook delivery and run lookup are
also exposed in the OpenAPI document. Mutations that can create a version or
retry a run require an idempotency key; optimistic-lock conflicts return 409.

## SDK

```python
from fathomark_sdk import FathomarkClient

with FathomarkClient("http://localhost:8000") as client:
    run = client.create_run(scope, idem_key="example-create-1")
    result = client.get_result(run["id"])
```

The SDK is intentionally thin: it preserves API response dictionaries and
raises `FathomarkAPIError` for non-2xx responses. Supply a configured
`httpx.Client` when custom transport, authentication, or timeout policy is
needed. The SDK does not calculate scores or silently retry mutations.
