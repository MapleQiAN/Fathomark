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

The named `fathomark-data` volume keeps `/data/fathomark.sqlite3` after the
container is recreated. Stop the API with `Ctrl-C`; `docker compose down`
stops containers while preserving the named volume.

For a custom database URL, set it explicitly before starting the service:

```bash
DATABASE_URL='sqlite:////absolute/path/fathomark.sqlite3' docker compose up --build
```

The default image exposes the headless API and health endpoint. Provider keys,
live collection, and the complete fixture-to-approved golden path are explicit
follow-up configuration rather than hidden startup side effects.
