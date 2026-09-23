# Fathomark（渊衡）系统功能编排与架构文档

> 版本：pre-1.0（M1–M5 已落地）
> 日期：2026-09-22
> 主要参考：`docs/design/2026-09-18-fathomark-design.md`、`README.zh-CN.md`

## 1. 系统定位

Fathomark 是**可审计的多智能体股票研究系统**。核心原则：

- LLM 智能体负责**取证与判断**（收集证据、给出 0–10 因子评分提案）；
- 确定性代码负责**计算**（评分、Veto、反向 DCF）；
- **人工审批闸门**之后才发布不可变的报告版本；
- 全流程留痕：每步输入/输出哈希、工件 SHA-256 清单、内容哈希，可回放、可审计。

## 2. 技术栈

| 层 | 选型 |
|---|---|
| 语言 | Python ≥ 3.12（纯 Python，无 JS） |
| 构建 | uv workspace 单仓（`packages/*`），hatchling，`uv.lock` 锁定 |
| Schema | Pydantic 2.9 |
| API | FastAPI + uvicorn |
| 存储 | SQLAlchemy 2.0 + Alembic；默认 SQLite，可选 PostgreSQL |
| 评分框架 | PyYAML（`frameworks/common-stock.yaml`） |
| HTTP | 数据/LLM Provider 用 stdlib urllib（刻意零依赖）；SDK 用 httpx |
| 报告 | 程序化生成 HTML（无模板引擎）；PDF 经 Playwright/Chromium（可选 extra）；SVG 图表零依赖 |
| 测试 | pytest + hypothesis；release 契约测试 |
| 部署 | Docker + docker-compose（可选 postgres overlay） |

## 3. 包结构与分层

```
packages/
├── core       fathomark_core      确定性评分核心（framework / schemas / scoring / snapshot / valuation / veto）
├── providers  fathomark_providers 数据源与 LLM 契约/适配器（evidence / market / llm / remote_llm / fake）
├── agents     fathomark_agents    多智能体层 + 编排器（orchestrator / specialists / red_team / repair / budget）
├── storage    fathomark_storage   持久化（models / repository / state_machine / alembic 迁移）
├── api        fathomark_api       FastAPI 无头服务（routes / services / webhooks / demo 工厂）
├── sdk        fathomark_sdk       httpx 薄客户端，覆盖全部 /v1 端点
├── reporting  fathomark_reporting 报告模型与渲染（model / renderers / charts / manifest / pdf_checks）
└── cli        fathomark_cli       argparse CLI + 插件契约模板
```

依赖方向单向：`core ← providers/agents ← storage ← api ← sdk/cli`；reporting 只依赖 core 的快照模型。core 仅依赖 pydantic + pyyaml，保持纯净。

## 4. 数据流总览

```
┌─────────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────────┐   ┌───────────┐   ┌──────────┐
│ 数据源       │ → │ 归一化        │ → │ 智能体判断    │ → │ 确定性计算    │ → │ 人工闸门   │ → │ 工件输出  │
│ EDGAR/XBRL  │   │ 截止/新鲜度   │   │ 6 专员+红队   │   │ evaluate()   │   │ 审批+版本  │   │ JSON/MD  │
│ 公司 IR     │   │ 去重/单位校验 │   │ FactorProposal│   │ 三透镜评分   │   │ 乐观锁    │   │ HTML/PDF │
│ Stooq OHLCV │   │ 弃项必记录    │   │ ReviewIssue   │   │ Veto/DCF     │   │           │   │ SVG/清单 │
└─────────────┘   └──────────────┘   └─────────────┘   └──────────────┘   └───────────┘   └──────────┘
```

1. **数据源**（providers）：`SecEdgarEvidenceProvider`（SEC EDGAR/XBRL）、`CompanyIREvidenceProvider`（运营方维护的 IR 文档清单，HTTPS 白名单）、`StooqMarketDataProvider`（OHLCV）、`FixtureEvidenceProvider`（录制夹具）。统一契约 `EvidenceProvider.fetch(scope) -> ProviderResult`。
2. **归一化**（宿主侧负责，见 `DATA_PROVIDERS.md`）：`EvidenceNormalizer` 执行数据截止、框架 YAML 新鲜度规则、去重、规范 ID；`MetricNormalizer` 校验单位/币种。**丢弃/过期项全部记录，绝不静默编造**。
3. **智能体判断**：6 个专员 + 财务智能体产出带依据与证据引用的 `FactorProposal`（0.5 步进）；`RedTeamAgent` 只做证据审计，产出类型化 `ReviewIssue`。LLM 输出经 `complete_with_repairs` 结构化修复与 `_BudgetedLLM` 预算（调用数/token/时长）约束。
4. **确定性计算**：`fathomark_core.evaluate(framework, scope, evidence, proposals)` → `ScoreSnapshot`：三透镜（core/offensive/tactical）评分、置信度、Veto（X）、NR 处理、评级、反向 DCF 敏感性、内容哈希。
5. **人工闸门**：API review/approve 端点 + 乐观锁；批准后生成不可变 `ResearchVersionRow`。
6. **输出**：`ReportModel` 渲染为 JSON / GFM Markdown / 自包含主题 HTML / Playwright PDF，附 SVG 图表与 SHA-256 工件清单。

## 5. 功能编排（Orchestrator）

编排核心：`packages/agents/src/fathomark_agents/orchestrator.py`。

### 5.1 执行模型

- **DAG-ready 步执行器**：步骤以 `StepSpec(depends_on=...)` 声明依赖，`_topo_levels` 按拓扑层级执行；当前图为线性，但同层步骤未来可并发。
- 每步记录**输入/输出哈希**，**先提交本步状态边界再进下一步**，支持**步级断点续跑（resume）**。
- 全部 LLM 调用经 `_BudgetedLLM`（预算超限即失败，可审计）。

### 5.2 默认流水线（`build_default_steps`）

```
scope ──→ collect ──→ financial ─┐
(冻结    (全源取证    business ──┤
 Scope    归一化      growth ────┼──→ red_team ──→ review_gate ──→ compute
 Snapshot) 持久化     valuation ─┤   (红队审计)    (阻断问题→      (evaluate()
                      governance ┤                  needs_review)   → draft)
                      market ────┘
```

| 步骤 | 职责 | 失败/分支 |
|---|---|---|
| `scope` | ScopeAgent 确定性冻结 `ScopeSnapshot`（标的、截止日、框架版本） | — |
| `collect` | 全部证据源 fetch → 归一化 → 持久化证据与指标观测 | 空结果 → `ReviewRequiredError` |
| 6 专员步 | `financial/business/growth/valuation/governance_risk/market`，均依赖 `collect` | LLM 修复超限 → 步失败 |
| `red_team` | RedTeamAgent 证据审计，产出 `ReviewIssue` | 状态 → `auditing` |
| `review_gate` | 存在阻断问题 → `needs_review` | 人工处理后可 resume |
| `compute` | `evaluate()` → 草稿快照 + 内容哈希 | 状态 → `draft` |

### 5.3 运行状态机

`packages/storage/src/fathomark_storage/state_machine.py`：

```
created → scoped → collecting → analyzing → auditing → ┬→ needs_review → (人工) → …
                                                       └→ draft → approved
                                任意失败 → failed；可 cancel → cancelled
```

`TRANSITIONS` 表 + `_bfs_path` 辅助，编排器按合法迁移推进；并发写用乐观锁（`ConcurrencyError`）。

## 6. 评分框架契约

`frameworks/common-stock.yaml`（`common-stock@1.0.0`）是评分唯一事实源：

- 11 个因子及锚点定义（0–10，0.5 步进）；
- 3 套透镜权重：`core` / `offensive` / `tactical`；
- Veto 阈值（触发即 X）、NR（证据不足）规则；
- 新鲜度窗口（归一化与 evaluate 双侧消费）；
- 评级边界。

框架 YAML 同时被智能体（提示词与锚点对齐）和 `evaluate()`（权重/Veto/评级）消费，改框架=升版本。

## 7. API 与服务编排

- 入口：`fathomark_api.main:app`（ASGI），由 `app.py` 的 `create_app()` 工厂构建。
- 路由：`routes/runs.py` 全部 `/v1` 端点；契约固定于 `docs/api/openapi-v1.json`（`scripts/dump_openapi.py` 再生，release 契约测试守护）。
- `RunService`：编排 Repository + core evaluate，负责幂等、review/approve。
- `/execute` 同步驱动 `Orchestrator.execute(run_id)`。
- Webhook：`webhooks.py` HMAC 签名外发事件。
- 配置（环境变量）：`DATABASE_URL`、`FATHOMARK_DATA_DIR`、`FATHOMARK_FRAMEWORK_DIR`、`FATHOMARK_DEMO_FIXTURE_DIR`、webhook URL/secret。
- **演示注入**：`demo.py` 的 `env_orchestrator_factory` 在设置 `FATHOMARK_DEMO_FIXTURE_DIR` 时，把 `ReplayLLMProvider` + `FixtureEvidenceProvider` 注入 Orchestrator，实现离线回放（golden fixture 见 `examples/fixtures/adbe_2026-09-03/`）；生产环境不设置即走真实 Provider。

## 8. 报告子系统

`packages/reporting/src/fathomark_reporting/`：

| 模块 | 职责 |
|---|---|
| `model.py` | `ReportModel`（冻结 Pydantic）：`from_snapshot(...)` 组装唯一校验输入；携带 `model_hash`/`snapshot_hash`，渲染前 `verify_integrity()` 防篡改 |
| `renderers.py` | `render_json`（规范 JSON）、`render_markdown`（GFM）、`render_html`（自包含、全转义、auto/light/dark/print 主题）、`render_pdf`（懒加载 Playwright，launcher 可注入以便确定性测试）、`render_report_bundle`（一键全工件） |
| `charts.py` | 零依赖确定性 SVG：因子图、估值敏感性、评分变化 |
| `manifest.py` | `ArtifactManifest`：逐工件 SHA-256 + media type，绑定模型与快照哈希 |
| `pdf_checks.py` | pypdf 结构校验（分页/空白页/期望文本/溢出），供 `scripts/verify_pdf.py` release 检查 |

无 Jinja/模板文件——HTML 程序化生成并转义；第三方"模板"指 CLI 插件契约桩（数据 Provider / LLM Provider / 报告主题）。示例产物：`dist/aapl-report-2026-07-18`、`dist/aapl-premium-report-2026-07-18`。

## 9. 入口点汇总

| 类型 | 入口 |
|---|---|
| 服务 | `fathomark_api.main:app`（uvicorn；容器入口见 `Dockerfile`） |
| CLI | `fathomark = fathomark_cli.cli:main` |
| 库 | `fathomark_core.evaluate` / `load_framework`；`Orchestrator.execute`；`render_report_bundle` |
| 脚本 | `scripts/build_cassette.py`（录 LLM cassette）、`dump_openapi.py`、`verify_pdf.py` |

## 10. 可审计性与信任边界

- **步级留痕**：每步输入/输出哈希 + 状态边界提交 → 断点续跑不重放副作用。
- **快照哈希**：`ScoreSnapshot` 内容哈希贯穿审批与报告模型，任何篡改在渲染前被 `verify_integrity` 拦截。
- **工件清单**：SHA-256 + 哈希绑定，外部可独立校验。
- **回放能力**：LLM cassette（`RecordingLLMProvider`/`ReplayLLMProvider`）+ fixture 证据 → 离线 golden path 复现。
- **信任边界**：归一化由宿主拥有（Provider 不得自行决定取舍）；LLM 只做判断不做计算；发布必须过人。
