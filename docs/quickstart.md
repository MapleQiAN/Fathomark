# Fathomark five-minute local start

The default demo uses SQLite inside a named Docker volume. No PostgreSQL
service or LLM key is required just to start the API.

```bash
docker compose up --build
```

In another terminal, verify the process:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Create a research run with an idempotency key:

```bash
curl -X POST http://localhost:8000/v1/research-runs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: quickstart-create-1' \
  -d '{
    "symbol": "ADBE",
    "exchange": "NASDAQ",
    "research_role": "core",
    "horizon": "5-10y",
    "research_date": "2026-09-03",
    "data_cutoff": "2026-09-03",
    "framework_ref": "common-stock@1.0.0"
  }'
```

The Compose service enables the recorded, offline ADBE fixture so the same
container can complete the full create → execute → approve path.  Copy the
run ID from the create response, then execute it:

```bash
RUN_ID='<run-id from the create response>'
curl -X POST "http://localhost:8000/v1/research-runs/${RUN_ID}/execute"
```

Read the optimistic-lock version and approve the immutable result:

```bash
LOCK_VERSION=$(curl -s "http://localhost:8000/v1/research-runs/${RUN_ID}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["lock_version"])')
curl -X POST "http://localhost:8000/v1/research-runs/${RUN_ID}/approve" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: quickstart-approve-1' \
  -d "{\"expected_lock_version\": ${LOCK_VERSION}}"
curl "http://localhost:8000/v1/research-runs/${RUN_ID}/result"
```

This fixture mode is deterministic and does not call an external provider.  To
run a deployment without the fixture, remove `FATHOMARK_DEMO_FIXTURE_DIR` from
Compose; `/execute` then remains disabled until a provider/orchestrator is
configured explicitly.

The named `fathomark-data` volume keeps `/data/fathomark.sqlite3` after the
container is recreated. Stop the API with `Ctrl-C`; `docker compose down`
stops containers while preserving the named volume.

For a custom database URL, set it explicitly before starting the service:

```bash
DATABASE_URL='sqlite:////absolute/path/fathomark.sqlite3' docker compose up --build
```

For an optional PostgreSQL service deployment, use the override file. It
includes `psycopg[binary]` in the image's `postgres` extra and waits for the
database health check before starting the API:

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

The override's default password is for local development only. Set
`POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` through a secret-aware
environment before using it outside a local machine. The PostgreSQL service
does not enable the recorded fixture; configure a real provider/orchestrator
explicitly for `/execute`.

The image exposes the headless API and health endpoint. Provider keys and live
collection remain explicit deployment configuration rather than hidden startup
side effects.
