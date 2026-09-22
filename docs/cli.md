# Fathomark CLI

The CLI is an optional thin client over the headless API. It does not score,
approve, or store local research state by itself; the API remains the source of
truth.

## Install and health check

From a checkout:

```bash
uv sync
uv run fathomark health
```

For another API address, set `FATHOMARK_API_URL` or pass `--base-url` before
the command:

```bash
FATHOMARK_API_URL=https://research.example.com uv run fathomark health
uv run fathomark --base-url http://localhost:8000 health
```

## Recorded demo flow

The Compose demo enables the offline ADBE fixture. Create a run, then copy its
ID from the JSON response:

```bash
uv run fathomark run create \
  --symbol ADBE --exchange NASDAQ --research-role core \
  --horizon 5-10y --research-date 2026-09-03 \
  --data-cutoff 2026-09-03 --framework-ref common-stock@1.0.0 \
  --idempotency-key cli-create-1

uv run fathomark run execute <run-id>
uv run fathomark run show <run-id>
uv run fathomark run approve <run-id> --idempotency-key cli-approve-1
uv run fathomark run result <run-id>
```

`approve` reads the current optimistic-lock version when `--lock-version` is
omitted. For an explicit concurrency boundary, pass the value returned by
`run show`.

## Plugin authentication and contract templates

The auth command checks whether an environment variable is present and never
prints its value:

```bash
uv run fathomark plugin auth \
  --provider my-market-data --env-var MY_MARKET_DATA_API_KEY
```

Generate a starting contract for a data provider, LLM provider, or report
theme:

```bash
uv run fathomark plugin contract-template --kind data > my_provider.py
```

The host still validates schemas, dates, licenses and evidence references.
These commands do not turn an unreviewed plugin into an approved data source.

