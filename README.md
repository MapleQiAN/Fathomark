<p align="center">
  <img src="docs/assets/fathomark-mark.svg" width="132" alt="Fathomark 渊衡 mark" />
</p>

<h1 align="center">Fathomark · 渊衡</h1>

<p align="center"><a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <strong>璇玑观象，研几审势。</strong><br />
  Auditable multi-agent equity research with deterministic scoring and human approval.
</p>

<p align="center">
  <a href="TODO.md"><img src="https://img.shields.io/badge/status-M1%E2%80%93M5%20core%20implemented-102A43?style=for-the-badge&labelColor=0B172A" alt="Status: M1 to M5 core implemented" /></a>
  <a href="https://github.com/MapleQiAN/Fathomark/actions/workflows/ci.yml"><img src="https://github.com/MapleQiAN/Fathomark/actions/workflows/ci.yml/badge.svg" alt="CI status" /></a>
  <img src="https://img.shields.io/badge/Python-%E2%89%A53.12-C9973E?style=flat-square" alt="Python 3.12 or newer" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-2F6F73?style=flat-square" alt="Apache 2.0 license" /></a>
</p>

<p align="center">
  Fathomark turns one stock research question into a traceable chain of evidence,<br />
  specialist judgments, red-team objections, deterministic scores and an approved version.
</p>

> [!IMPORTANT]
> Fathomark is pre-1.0. The repository implements the M1–M5 core and validates it with offline fixtures and CI. The default Docker demo replays a recorded ADBE case and makes no live market-data or model calls. An internet-facing deployment still needs authentication, secret management, provider licensing and rate-limit review, monitoring and operator-owned release checks. No signed release tag exists yet.

## Use Fathomark: local demo

Fathomark is a headless API with an optional CLI; it does not include a research dashboard. For the quickest complete run, install Docker with Compose, then start the API from a checkout. The default stack uses SQLite in a named volume and needs no PostgreSQL service, provider account or LLM key. The commands below also need `curl`.

```bash
git clone https://github.com/MapleQiAN/Fathomark.git
cd Fathomark
docker compose up --build
```

Keep that terminal open. In another terminal, check the service (the interactive API reference is at [localhost:8000/docs](http://localhost:8000/docs)):

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

**1. Create a research run.** This exact ADBE scope matches the recorded demo fixture. Copy the `id` from the JSON response into `RUN_ID` for the following commands. Use a new `Idempotency-Key` when creating a separate run; repeating the same key returns the existing run.

```bash
curl -sS -X POST http://localhost:8000/v1/research-runs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: readme-adbe-create-1' \
  -d '{"symbol":"ADBE","exchange":"NASDAQ","research_role":"core","horizon":"5-10y","research_date":"2026-09-03","data_cutoff":"2026-09-03","framework_ref":"common-stock@1.0.0"}'
RUN_ID='<id from the response>'
```

**2. Execute and inspect the draft.** `/execute` replays the fixture's evidence and model responses, then computes the score. A successful response has `state: "draft"`; `/result` contains the unapproved `snapshot` with factor scores, lens results, confidence and a content hash. Review the recorded [input and source material](examples/fixtures/adbe_2026-09-03) before approving; the snapshot itself does not contain the full evidence ledger.

```bash
curl -sS -X POST "http://localhost:8000/v1/research-runs/${RUN_ID}/execute"
curl -sS "http://localhost:8000/v1/research-runs/${RUN_ID}/result"
```

**3. Approve the reviewed result.** First read `lock_version` from the run response and substitute that number below. Approval records the actor and creates an immutable version. If the version has changed, fetch the run again before deciding whether to retry.

```bash
curl -sS "http://localhost:8000/v1/research-runs/${RUN_ID}"
LOCK_VERSION='<lock_version from the response>'
curl -sS -X POST "http://localhost:8000/v1/research-runs/${RUN_ID}/approve" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: readme-adbe-approve-1' \
  -H 'Actor: your-name' \
  -d "{\"expected_lock_version\":${LOCK_VERSION}}"
curl -sS "http://localhost:8000/v1/research-runs/${RUN_ID}/result"
```

The final `/result` response has `state: "approved"`, the score `snapshot`, and a `version` record. The demo does not automatically generate or upload a PDF/HTML report; `/v1/research-runs/{run_id}/artifacts` lists only artifacts stored for that run. For other API operations, use the [five-minute guide](docs/quickstart.md), [API and SDK guide](docs/api-and-sdk.md), or [CLI guide](docs/cli.md). Stop with `Ctrl-C` and `docker compose down`; the named SQLite volume survives container removal.

The demo fixture is reproducible historical research infrastructure, not a current rating, forecast, recommendation or trade instruction. The default `/execute` path is configured for this recorded case; researching another company requires an explicitly configured provider and orchestrator. See [data providers](DATA_PROVIDERS.md) and [model providers](MODEL_PROVIDERS.md).

## Why Fathomark

**Let language models investigate the evidence, let deterministic code calculate the score, and let a human decide when a result becomes official.**

<table>
  <tr>
    <td width="33%" valign="top"><strong>01 · Evidence ledger</strong><br /><sub>Each factor conclusion points to dated sources, excerpts, provenance, counter-evidence and confidence.</sub></td>
    <td width="33%" valign="top"><strong>02 · Deterministic core</strong><br /><sub>The same validated inputs produce the same score, Veto result, grade and content hash.</sub></td>
    <td width="33%" valign="top"><strong>03 · Human gate</strong><br /><sub>Red-team issues remain visible, and only explicit approval creates an immutable version.</sub></td>
  </tr>
</table>

Agents can read, compare, explain and challenge. They cannot change framework weights, invent values for missing evidence, bypass a blocking review issue or publish an unapproved rating.

## What works today

| Area | Implemented in this repository |
| --- | --- |
| Deterministic scoring | Versioned `common-stock@1.0.0` framework, 11 factors, three lenses, confidence, `NR`, Vetoes, grades, reverse DCF and sensitivity calculations |
| Storage and API | SQLite by default, optional PostgreSQL, Alembic migrations, run state machine, idempotency, optimistic locks, immutable versions, artifact storage, OpenAPI, SDK and HMAC webhooks |
| Providers and agents | SEC EDGAR/XBRL, allowlisted company IR and replaceable market-data contracts; OpenAI, Anthropic and OpenAI-compatible LLM adapters; Scope, six specialist and Red-Team agents |
| Orchestration | Recorded step inputs/outputs, cutoff and freshness filtering, structured-output repair, LLM budgets, explicit failure/review states and step-level resume |
| Reports | One validated `ReportModel` rendered to JSON, GFM Markdown, self-contained themed HTML and Playwright PDF, with SVG charts, content hashes and artifact manifests |
| Local demo and release tooling | One-command Docker/SQLite startup, recorded ADBE golden path, optional CLI, plugin contract templates, locked CI, dependency audit and CycloneDX SBOM |

The live adapters are replaceable deployment components. Repository tests use recorded responses and mocked transports, so they establish contract behavior without claiming live-provider availability.

## From question to approved artifact

<p align="center">
  <img src="docs/assets/research-workflow.png" alt="Fathomark workflow from research contract through evidence collection, specialist analysis, Red-Team review, deterministic scoring, human approval and JSON, Markdown, HTML and PDF artifacts." width="100%" />
</p>

Provider failures, stale evidence, missing references and unresolved objections become stored state. Each orchestrator step commits its boundary before the next step runs, which makes interrupted executions auditable and resumable.

## How a score earns its grade

<p align="center">
  <img src="docs/assets/scoring-snapshot.svg" alt="Offline ADBE fixture snapshot: core lens 85.75 out of 100, A plus, high confidence, eleven evidence-backed factors, a clear Veto check and an approval API record." width="100%" />
</p>

> [!NOTE]
> The checked [`adbe_2026-09-03`](examples/fixtures/adbe_2026-09-03) fixture is an offline reproducibility case. Its 85.75 / A+ snapshot is historical test data.

1. **Fix the research contract.** Each run identifies one ordinary listed operating company, a research date, a data cutoff and the versioned [`common-stock@1.0.0`](frameworks/common-stock.yaml) framework.
2. **Ground all 11 factors.** Dated evidence and counter-evidence support one 0–10 proposal per factor. Missing or stale evidence stays visible.
3. **Run the audit.** The Red-Team agent records typed issues. A blocking issue routes the run to `needs_review` before scoring.
4. **Calculate deterministically.** `core`, `offensive` and `tactical` lenses reweight the same proposals. A Veto returns `X`; insufficient confidence returns `NR`.
5. **Approve explicitly.** Review decisions record actor, reason and optimistic-lock version. Approval creates an immutable research version.

### The 11 factors and their weights

<p align="center">
  <img src="docs/assets/scoring-weights.svg" alt="Weight map for the common-stock framework. Core allocates 64 percent to fundamentals, 27 percent to growth and valuation, and 9 percent to market factors. Offensive allocates 37, 49, and 14 percent. Tactical allocates 13, 16, and 71 percent." width="100%" />
</p>

Every lens uses the same evidence standard and the same 0–10 factor proposals.

| Factor | Category | `core` | `offensive` | `tactical` |
| --- | --- | ---: | ---: | ---: |
| Business moat | Fundamentals | 22% | 15% | 3% |
| Financial health | Fundamentals | 22% | 8% | 8% |
| Governance | Fundamentals | 12% | 8% | 2% |
| Policy risk | Fundamentals | 8% | 6% | 0% |
| Growth sustainability | Growth / valuation | 5% | 24% | 0% |
| Valuation | Growth / valuation | 11% | 17% | 10% |
| Earnings quality | Growth / valuation | 11% | 8% | 6% |
| Trend / momentum | Market | 1% | 5% | 20% |
| Liquidity | Market | 2% | 3% | 16% |
| Volatility / downside | Market | 6% | 2% | 13% |
| Catalyst window | Market | 0% | 4% | 22% |
| **Total** |  | **100%** | **100%** | **100%** |

`core` emphasizes business quality and financial resilience. `offensive` assigns almost half its weight to growth and valuation. `tactical` concentrates on timing, liquidity, downside and catalysts. A Veto takes precedence over the weighted total, and insufficient confidence cannot be converted into a numeric result.

The [framework YAML](frameworks/common-stock.yaml) is the source of truth for anchors, weights, Veto thresholds, freshness rules and grade boundaries. Any weight change requires a new framework version.

## Reports stay tied to the same facts

<p align="center">
  <img src="docs/assets/report-ribbon.svg" alt="Fathomark report sections: thesis, score, risks and evidence" width="100%" />
</p>

| Reader question | Report content |
| --- | --- |
| What is the view? | Scope, grade, lens scores and confidence |
| What supports it? | Factor rationale, evidence and counter-evidence |
| What could invalidate it? | Vetoes, missing data and Red-Team issues |
| Can it be audited later? | Source dates, framework reference, snapshot hash, model hash and approval record |

All renderers consume the same integrity-checked `ReportModel`. The reporting package creates JSON, Markdown, HTML and PDF bytes plus a manifest; the API stores and serves those artifacts with their content and manifest hashes. The pinned Docker font and target Chromium checks cover pagination, blank pages, expected text and horizontal overflow.

## API-first integration

The REST API is available under `/v1`; the checked contract lives at [`docs/api/openapi-v1.json`](docs/api/openapi-v1.json). Creating a run is idempotent:

```http
POST /v1/research-runs HTTP/1.1
Content-Type: application/json
Idempotency-Key: readme-create-1

{
  "symbol": "ADBE",
  "exchange": "NASDAQ",
  "research_role": "core",
  "horizon": "5-10y",
  "research_date": "2026-09-03",
  "data_cutoff": "2026-09-03",
  "framework_ref": "common-stock@1.0.0"
}
```

The API returns `201 Created` for the first request and `200 OK` when the same idempotency key is replayed. It exposes create, inspect, execute, ingest, compute, review, resolve, approve, cancel, retry, result and artifact endpoints. The [Python SDK](docs/api-and-sdk.md) and [CLI](docs/cli.md) remain thin clients; scoring and approval rules stay on the server.

## Scope and boundaries

| Area | v1 boundary |
| --- | --- |
| Research unit | One ordinary US-listed operating company per run |
| Product surface | Headless REST API, Python SDK and optional CLI; no bundled review UI |
| Execution | Synchronous `/execute` in the demo with resumable step records; no standalone queue or worker service |
| Storage | Embedded SQLite for local use; optional PostgreSQL for service deployments |
| Providers | Live adapters require deployment-owned credentials, terms review, rate limits and availability checks |
| Security | The local API has no built-in production authentication; follow [SECURITY.md](SECURITY.md) before network exposure |
| Release | CI, SBOM and release checks exist; maintainer approval and a signed tag are still required |

ETFs, banks and insurers, cyclical resources, REITs, batch ranking, portfolio optimization, automated trading, multi-tenant SaaS and official A/H-share connectors are outside v1.

## Repository map

```text
Fathomark/
├── packages/
│   ├── core/          # schemas, framework loading, scoring, Veto and valuation
│   ├── providers/     # evidence, market-data and LLM provider contracts/adapters
│   ├── agents/        # scope, specialist, Red-Team and resumable orchestration
│   ├── storage/       # SQLAlchemy repositories, state machine and Alembic migrations
│   ├── api/           # FastAPI service and recorded-demo wiring
│   ├── sdk/           # thin Python API client
│   ├── reporting/     # ReportModel, charts, renderers, PDF checks and manifests
│   └── cli/           # optional API client and plugin contract templates
├── frameworks/        # versioned scoring definitions
├── examples/fixtures/ # recorded offline research cases
├── docs/              # contracts, guides, design and release evidence
├── scripts/           # cassette, OpenAPI and PDF verification helpers
└── tests/             # repository-level release contracts
```

## Documentation

- [Five-minute local demo](docs/quickstart.md)
- [API and Python SDK](docs/api-and-sdk.md) · [OpenAPI v1](docs/api/openapi-v1.json)
- [CLI](docs/cli.md) · [Plugin development](docs/plugin-development.md)
- [Data providers](DATA_PROVIDERS.md) · [Model providers](MODEL_PROVIDERS.md)
- [Reporting](docs/reporting-development.md) · [Scoring framework development](docs/framework-development.md)
- [System design](docs/design/2026-09-18-fathomark-design.md) · [Roadmap](TODO.md) · [Release checklist](docs/release-checklist.md)

## Development

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required for local development.

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution workflow. The project is pre-1.0, so contract changes should include the matching tests and documentation.

## Principles

1. Agents collect evidence, make explicit judgments and surface counterexamples; deterministic code owns arithmetic and state transitions.
2. Identical validated inputs produce identical scores, Veto results, grades and hashes.
3. Missing evidence produces `NR` or review state; prose cannot manufacture a number.
4. Every factor conclusion remains traceable to dated, source-linked evidence.
5. Approved versions are immutable.
6. Fathomark supports research decisions; it does not predict returns or issue trading instructions.

See [LICENSE](LICENSE), [NOTICE](NOTICE), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [DISCLAIMER.md](DISCLAIMER.md), [SECURITY.md](SECURITY.md), [DATA_PROVIDERS.md](DATA_PROVIDERS.md) and [MODEL_PROVIDERS.md](MODEL_PROVIDERS.md) for project policies.

<p align="center">
  <sub>Fathomark · 渊衡</sub><br />
  <em>Deep research, measured judgment.</em>
</p>
