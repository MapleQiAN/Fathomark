<p align="center">
  <img src="docs/assets/fathomark-mark.svg" width="132" alt="Fathomark 渊衡 mark" />
</p>

<h1 align="center">Fathomark · 渊衡</h1>

<p align="center"><a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <strong>深研有据，权衡有度。</strong><br />
  Evidence-first multi-agent equity research for people who want to see the reasoning.
</p>

<p align="center">
  <a href="docs/design/2026-09-18-fathomark-design.md"><img src="https://img.shields.io/badge/status-design%20ready-102A43?style=for-the-badge&labelColor=0B172A" alt="Status: design ready" /></a>
  <img src="https://img.shields.io/badge/agents-specialists%20%2B%20red%20team-C9973E?style=for-the-badge&labelColor=0B172A" alt="Specialist agents and red team" />
  <img src="https://img.shields.io/badge/output-HTML%20%7C%20MD%20%7C%20PDF-2F6F73?style=for-the-badge&labelColor=0B172A" alt="HTML, Markdown and PDF reports" />
</p>

<p align="center">
  Fathomark turns a stock research question into a traceable chain of evidence,<br />
  specialist judgments, deterministic scoring, red-team review and a human-approved report.
</p>

<br />

> [!IMPORTANT]
> M1–M5 core slices are implemented: M4 provides one validated report model, deterministic JSON/Markdown/HTML/PDF export boundaries, artifact manifests and offline accessibility/responsive contracts; M5 provides a zero-config Docker/SQLite demo, an opt-in recorded ADBE path from creation through approval, the optional `fathomark` CLI and plugin contract scaffolding. The deterministic scoring core in `packages/core` implements the `common-stock@1.0.0` framework; `packages/storage` + `packages/api` add the run state machine, headless API, Python SDK, OpenAPI contract and HMAC webhooks — see [TODO.md](TODO.md) for live-provider, target-browser and review-console boundaries.

## The idea in one sentence

**Let language models investigate the evidence, let deterministic code calculate the score, and let a human decide when a result becomes official.**

That boundary is the heart of 渊衡. Agents can read, compare, explain and challenge. They cannot silently change weights, fill missing data with a story, or publish an unreviewed rating.

## What makes it different

<table>
  <tr>
    <td width="33%" valign="top"><strong>01 · Evidence ledger</strong><br /><sub>Every factor conclusion points to dated sources, excerpts, provenance and a confidence level.</sub></td>
    <td width="33%" valign="top"><strong>02 · Deterministic core</strong><br /><sub>The same structured inputs always produce the same score, Veto result, grade and version hash.</sub></td>
    <td width="33%" valign="top"><strong>03 · Human gate</strong><br /><sub>Draft findings stay drafts until a reviewer approves an immutable release.</sub></td>
  </tr>
</table>

## How a score earns its grade

<p align="center">
  <img src="docs/assets/scoring-snapshot.svg" alt="Illustrative offline ADBE fixture snapshot: core lens 85.75 out of 100, A plus, high confidence, eleven evidence-backed factors, a clear Veto check and an approval API decision record. Recorded fixture: adbe_2026-09-03." width="100%" />
</p>

> [!NOTE]
> This is the checked, offline [`adbe_2026-09-03`](examples/fixtures/adbe_2026-09-03) reproducibility fixture — not a current rating, forecast, recommendation or trade instruction.

1. **Set the frame.** Each run fixes one ordinary listed operating company, a cutoff date and the versioned [`common-stock@1.0.0`](frameworks/common-stock.yaml) framework.
2. **Ground every factor.** Dated, source-linked evidence and counter-evidence support one 0–10 proposal for each of 11 factors. A gap is declared; prose does not smooth it away.
3. **Calculate, then constrain.** `core`, `offensive` and `tactical` lenses reweight the same structured proposals for different research questions. Deterministic code turns the selected lens into a 100-point total and grade; a triggered Veto yields `X`, while insufficient confidence yields `NR` instead of a total.
4. **Review before release — implemented API gate.** M2 implements the `draft` → `needs_review` → `approved` transitions and records the reviewer decision. M3 now runs the scope agent and six specialist agents offline, covering all 11 factors through deterministic cassette replay. M4 renders the approved `ReportModel` into one manifest-bound report bundle; the recorded fixture is still a checked offline example, not a current rating or investment instruction.

### The 11 factors and their weights

<p align="center">
  <img src="docs/assets/scoring-weights.svg" alt="Weight map for the common-stock framework. Core allocates 64 percent to fundamentals, 27 percent to growth and valuation, and 9 percent to market factors. Offensive allocates 37, 49, and 14 percent. Tactical allocates 13, 16, and 71 percent." width="100%" />
</p>

The map shows the shape; this table carries every number. Each lens reweights the same evidence-backed 0–10 proposals, rather than creating a separate evidence standard.

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

`core` prioritizes business quality and financial resilience. `offensive` puts almost half its weight on growth and valuation. `tactical` concentrates on timing, liquidity, downside and catalysts. A high score elsewhere cannot offset a Veto or turn insufficient confidence into a number.

The [full framework](frameworks/common-stock.yaml) remains the source of truth for factor anchors, lens weights, Veto thresholds and the complete rating spectrum. Changing a weight requires a framework version change, not a README edit.

## From question to report

```mermaid
flowchart LR
    Q[Research question] --> C[Research contract]
    C --> E[Evidence collection]
    E --> L[Specialist lenses]
    L --> S[Deterministic scoring]
    S --> R[Red-team review]
    R --> H{Human approval}
    H -->|revise| E
    H -->|approve| P[Immutable report package]
    P --> J[JSON]
    P --> M[Markdown]
    P --> HT[HTML]
    P --> PDF[Print-ready PDF]
```

The system is intentionally a pipeline with explicit handoffs. A failed provider, weak source or unresolved contradiction becomes visible state, rather than disappearing into a final paragraph.

## Architecture at a glance

```mermaid
flowchart TB
    subgraph Interface[Interfaces]
      API[Headless REST API]
      CLI[Optional CLI]
      WEB[Optional review console]
    end

    subgraph Orchestration[Orchestration]
      RUN[Research run state machine]
      BUS[Event and audit log]
      GATE[Review and approval gate]
    end

    subgraph Intelligence[Agent layer]
      FACTS[Fact collector]
      BUSINESS[Business quality]
      FIN[Financial quality]
      VAL[Valuation]
      RISK[Risk and governance]
      TEAM[Red team]
    end

    subgraph Core[Deterministic core]
      SCHEMA[Versioned schemas]
      SCORE[Weighted score engine]
      VETO[Veto and NR rules]
      GRADE[Grade mapping]
      ART[Artifact renderer]
    end

    API --> RUN
    CLI --> API
    WEB --> API
    RUN --> BUS
    RUN --> FACTS
    RUN --> BUSINESS
    RUN --> FIN
    RUN --> VAL
    RUN --> RISK
    FACTS --> SCHEMA
    BUSINESS --> SCHEMA
    FIN --> SCHEMA
    VAL --> SCHEMA
    RISK --> SCHEMA
    TEAM --> GATE
    SCHEMA --> SCORE --> VETO --> GRADE --> GATE --> ART
```

## What v1 covers

| Area | v1 decision |
| --- | --- |
| Research unit | One ordinary US-listed operating company per run |
| Product surface | Headless REST API first; CLI and Vue review console are optional clients |
| Scoring | 11-factor, 100-point framework with confidence, Veto, `NR` and versioning |
| Evidence | SEC EDGAR/XBRL, company investor relations and replaceable market-data providers |
| Models | OpenAI, Anthropic and OpenAI-compatible adapters |
| Storage | SQLite for local work; PostgreSQL for a service deployment |
| Reports | JSON, polished HTML, well-formed Markdown and print-generated PDF |
| Approval | Human approval is required before an official rating is published |

Out of scope for v1: ETFs, banks and insurers, cyclical resources, REITs, batch ranking, portfolio optimization, automated trading, multi-tenant SaaS and official A/H-share data connectors.

## A report should answer four questions

<p align="center">
  <img src="docs/assets/report-ribbon.svg" alt="Fathomark report sections: thesis, score, risks and evidence" width="100%" />
</p>

| Reader need | Fathomark report section |
| --- | --- |
| What is the current view? | Thesis, grade, score and confidence |
| Why did it get that view? | Factor cards with evidence and counter-evidence |
| What could invalidate it? | Vetoes, open questions, risks and red-team objections |
| Can I audit the result later? | Sources, dates, framework version, input hash and approval record |

The HTML report is the visual master. Markdown remains portable, JSON remains machine-readable, and PDF is generated from the same print layout so the four formats do not drift apart.

## Designed as a backend other systems can call

The core workflow is API-first. A future client can create a run, poll its state, inspect evidence, request review, approve a version and fetch report artifacts without knowing how the web console is built.

```http
POST /v1/research-runs
Content-Type: application/json

{
  "symbol": "AAPL",
  "exchange": "NASDAQ",
  "research_role": "core",
  "as_of": "2026-09-18",
  "framework_version": "common-stock.v1"
}
```

```text
202 Accepted
Location: /v1/research-runs/run_01J...
```

The public API will expose stable contracts for `draft`, `needs_review`, `approved`, `failed` and `cancelled` states. A consumer can safely treat an approved result as a versioned research artifact rather than as a live trading instruction.

## Repository map

```text
fathomark/
├── packages/
│   ├── core/          # schemas, framework rules, scoring, Veto and grade mapping
│   ├── agents/        # specialist contracts and orchestration
│   ├── providers/     # filings, IR and market-data adapters
│   ├── reports/       # JSON, HTML, Markdown and PDF renderers
│   ├── cli/           # optional API CLI and plugin contract scaffolding
│   └── api/           # REST service and background worker entry points
├── frameworks/        # versioned scoring definitions
├── docs/              # design notes and integration guidance
├── examples/          # recorded provider responses and sample reports
└── tests/             # contract, deterministic-core and integration tests
```

## Read next

1. [System design](docs/design/2026-09-18-fathomark-design.md) — architecture, data contracts, scoring governance and report formats.
2. [Roadmap](TODO.md) — milestones, acceptance criteria and the remaining project work.
3. [CLI guide](docs/cli.md) and [plugin development](docs/plugin-development.md) — optional client and extension boundaries.

M2 is done: `packages/storage` and `packages/api` implement the run state machine, SQLite/PostgreSQL storage, the headless API (create, query, cancel, retry, review, approve, result), the Python SDK in `packages/sdk`, the versioned OpenAPI contract and HMAC webhooks. M3 adds provider protocols with fake/replay/recording test doubles, hosted-LLM adapters, SEC/IR/market data adapters, a scope agent, six specialist agents with a repair loop, cutoff/freshness-aware evidence normalization, auditable LLM budgets, automatic evidence-gap routing, and a step-recorded Red-Team audit that persists typed issues and blocks drafts when an issue is blocking. M4 adds deterministic report bundle/manifest contracts; M5 adds the local demo, CLI and release foundations. The asynchronous worker, operator verification of live-source availability/licensing, target-image browser checks and review console remain explicit boundaries — see [TODO.md](TODO.md).

## Get the repository

```bash
git clone git@github.com:MapleQiAN/Fathomark.git
cd Fathomark
```

## Principles

1. Agents collect evidence, make explicit judgments and surface counterexamples; deterministic code owns arithmetic and state transitions.
2. Identical structured inputs produce identical scores, Veto results and grades.
3. Missing evidence produces `NR`; prose cannot manufacture a number.
4. Every factor conclusion is traceable to dated, source-linked evidence.
5. An approved version is immutable; a change creates a new version.
6. Fathomark is research and decision support, not a return forecast or trading instruction.

## Project status

| Milestone | State |
| --- | --- |
| Brand, architecture and contracts | ✅ Defined |
| Deterministic scoring core | ✅ Implemented (M1) |
| Agent adapters and provider recordings | Protocols + scope and all six specialist agents ✅ (M3, offline replay) |
| API and worker | API ✅ Implemented (M2); orchestrator ✅ (M3 slice); background worker ◻ Planned |
| HTML / Markdown / PDF renderer | ✅ Implemented from one `ReportModel`; browser/font deployment checks remain |
| Self-contained demo and release packaging | ✅ Local Docker/SQLite + recorded golden path + CLI; maintainer release gates remain |

M1 scoring core 已实现：`packages/core` 承载 `common-stock@1.0.0` 框架的确定性评分、Veto 与评级映射。
离线可复现：`examples/fixtures/adbe_2026-09-03` 金样测试证明同一 JSON 输入永远得到同一快照（ADBE 核心 85.75 / A+）。

## Contributing

The project is pre-1.0 and the API surface is not stable yet. Feedback is most useful when it is concrete: point to a contract, state transition, evidence rule or report section and describe the failure mode it prevents.

See [LICENSE](LICENSE), [NOTICE](NOTICE), [CONTRIBUTING.md](CONTRIBUTING.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md),
[DISCLAIMER.md](DISCLAIMER.md), [DATA_PROVIDERS.md](DATA_PROVIDERS.md) and
[MODEL_PROVIDERS.md](MODEL_PROVIDERS.md) for the project policies.

<p align="center">
  <sub>Fathomark · 渊衡</sub><br />
  <em>Deep research, measured judgment.</em>
</p>
