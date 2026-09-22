# Fathomark 渊衡后续待办

本清单用于记录设计确认后仍需完成的工作。它是项目级 backlog，不是逐文件实施计划；开始编码前仍需把当前里程碑拆成可执行计划。

## 0. 开工准备

- [ ] 完成 `Fathomark` / `渊衡` 的正式商标、包名与域名核验。
- [ ] 确认 Python 包名、Docker 镜像名和未来 GitHub 组织/仓库名。
- [x] 补齐 Apache 2.0 `LICENSE` 与 `NOTICE`。
- [x] 编写 `SECURITY.md`、`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md` 和 `DISCLAIMER.md`。
- [x] 选择 Python 依赖管理与构建工具，并记录最低支持版本。(uv workspace + hatchling，Python ≥3.12)
- [x] 建立 CI、格式化、静态检查、测试和依赖安全扫描。(CI + pip-audit；依赖来自锁文件)
- [x] 创建第一份可执行实施计划。(docs/design M1 计划已执行完毕)

## 1. M1：确定性评分内核 ✅ 已完成

- [x] 从 PersonalInvestment 提取普通经营公司的 11 因子定义。
- [x] 提取核心、进攻和战术 Lens 权重。
- [x] 将 Veto、NR、评级光谱、置信度与数据新鲜度写入版本化 YAML。(frameworks/common-stock.yaml)
- [x] 删除或隔离个人组合、具体仓位和交易动作规则。
- [x] 定义 `ScopeSnapshot`、`EvidenceItem`、`MetricObservation`、`FactorProposal`、`ScoreSnapshot` Schema。
- [x] 实现框架加载、Schema 校验和版本解析。
- [x] 实现 0.5 分步长、加权计算、舍入、Veto 和评级映射。
- [x] 实现反向 DCF 与敏感性分析的确定性计算接口。
- [x] 为所有边界、非法配置和 Veto 优先级补齐单元测试。
- [x] 增加属性测试，验证相同输入始终得到相同结果。

### M1 完成标准

- [x] 固定 JSON 输入能离线生成完整、可复现的评分快照。(examples/fixtures/adbe_2026-09-03 金样)
- [x] `common-stock@1.0.0` 权重和评级边界全部通过测试。
- [x] `core` 不依赖网络、数据库或任何 LLM SDK。

## 2. M2：存储、状态机与 Headless API

- [x] 设计 SQLAlchemy 模型和 Alembic 迁移。(packages/storage、alembic/versions/0001_baseline)
- [x] 同时支持 SQLite 与 PostgreSQL。(SQLite 默认；PG 经 PG_TEST_URL 可选测试，类型可移植)
- [x] 实现研究运行、证据、指标、建议分、异议、人工决定、版本和制品仓储。(runs/evidence/proposals/decisions/versions/snapshots/metric_observations；ProviderRun/ReviewIssue/Artifact 表延至 M3/M4)
- [x] 实现任务状态机和非法状态转换保护。(packages/storage/state_machine.py)
- [x] 实现步骤级输入哈希、幂等执行和断点恢复。(输入哈希与幂等已就绪；断点恢复依赖 M3 worker)
- [x] 实现研究任务创建、查询、取消、重试、审核、批准和结果 API。(packages/api，11 条路由)
- [x] 为创建、重试、批准和制品生成加入幂等键。
- [x] 为人工审核加入乐观锁。(lock_version)
- [x] 生成并版本化 OpenAPI 文档。(docs/api/openapi-v1.json + 漂移测试)
- [x] 实现 Python SDK。(packages/sdk，FathomarkClient)
- [x] 实现 HMAC Webhook 与重放保护。(packages/api webhooks)
- [x] 编写 API 契约和双数据库集成测试。(SQLite 跑 CI；PG 经 PG_TEST_URL 可选)

### M2 完成标准

- [x] 使用固定 fixture 可以从 API 创建任务、审核并批准不可变版本。(packages/api/tests/test_e2e_adbe.py)
- [x] Worker 中断后只恢复未完成步骤。(execute 重入 + step_runs 输入哈希实现步骤级恢复；异步 worker 调度进程仍由部署方接入)
  - [x] 异步 worker 需要步骤边界逐条提交。(begin/finish/fail 均在步骤边界提交；跨会话恢复契约测试覆盖)
- [x] 重复请求不会产生重复正式版本。(幂等键测试)

## 3. M3：美股 Provider 与专业 Agent

- [x] 实现 LLM Provider 通用协议。(packages/providers：LLMProvider/LLMRequest/LLMResponse/ProviderError)
- [x] 实现 OpenAI Provider。(标准库 HTTP 适配器；离线契约测试，真实密钥/网络由部署方提供)
- [x] 实现 Anthropic Provider。(标准库 HTTP 适配器；离线契约测试，真实密钥/网络由部署方提供)
- [x] 实现 OpenAI-compatible Provider。(可配置 endpoint；支持无密钥本地服务)
- [x] 实现 SEC EDGAR/XBRL Provider。（10-K/10-Q 证据采集；companyfacts 中收入、净利润、经营现金流的可追溯 USD 单期指标。）
- [x] 实现公司 IR 文档 Provider。(CompanyIREvidenceProvider：显式文档元数据 + HTTPS host allowlist + redirect guard)
- [x] 定义行情 Provider 协议并实现一个可替换的公开数据适配器。(MarketDataProvider + StooqMarketDataProvider；录制 transport 契约测试，实时可用性与授权仍由部署方确认)
- [x] 实现 Evidence Normalizer 基础范围：去重、冲突 ID 拒绝、截止日/新鲜度过滤，以及 SEC XBRL USD 指标标准化。
- [x] 补齐通用多币种和非 XBRL 口径的日期/单位/币种标准化。(显式货币/数量/百分比/比例别名；不在无 FX 证据时猜测汇率)
- [x] 实现 Scope Agent。(packages/agents ScopeAgent)
- [x] 实现 Business Agent。(BusinessAgent：business_moat，cassette 回放)
- [x] 实现 Financial Agent。(financial_health + earnings_quality，录制 cassette 回放)
  - 注：全部 11 个因子由真实 Agent 覆盖（离线 cassette 回放）；FixtureReplayAgent 已删除。cassette 由 `scripts/build_cassette.py` 确定性重建。
- [x] 实现 Growth Agent。(GrowthAgent：growth_sustainability)
- [x] 实现 Valuation Agent。(ValuationAgent：valuation)
- [x] 实现 Governance & Risk Agent。(GovernanceRiskAgent：governance + policy_risk；Veto 候选随 Red-Team 后续)
- [x] 实现 Market Agent。(MarketAgent：trend/liquidity/volatility/catalyst)
- [x] 实现 Red-Team Agent。(仅审计已有提议；阻断性异议持久化并将运行置于 `needs_review`)
- [x] 实现 Agent 输出结构修复与最多两次重试。(complete_with_repairs：1 次初始 + 至多 2 次修复)
- [x] 实现证据冲突、数据截止日和来源数据新鲜度过滤。(冲突 ID 拒绝、截止日过滤、按 source_class 的 freshness 窗口过滤；核心已有 NR/Veto 规则)
- [x] 将证据严重不足自动路由为 `NR` 或 `needs_review`。(无可用证据进入 `needs_review`；`insufficient` 置信度由确定性核心输出 `NR`)
- [x] 数据截止日校验（本切片范围）。(collect 步骤过滤超出截止日的证据；提议引用不存在或超出截止日的证据被拒绝)
- [x] 实现调用次数、Token、金额和运行时间预算。(LLMBudget + step-run 累计用量；真实价格由部署配置)
- [x] 建立录制响应和离线 Agent 契约测试。(Fake/Replay/RecordingLLMProvider + 录制契约测试)

### M3 完成标准

- [x] 对一个公开美股样例可以生成包含完整证据引用的草稿。(ADBE 录制 Provider/LLM cassette；实时 Provider 仍由部署方配置)
- [x] 任一必需 Provider 失败时，系统显式失败或进入 `needs_review`。(orchestrator 契约测试覆盖)
- [x] Agent 无法引用不存在或超出截止日的证据。(validate_proposal 契约测试覆盖)

## 4. M4：审核与多格式报告

- [x] 实现人工接受、修改、退回和批准记录。(HumanDecisionRow + review/approve API)
- [x] 修改建议分时强制填写理由。(DecisionRequest.reason 非空；modify 同时要求 factor/final_score)
- [x] 定义统一 `ReportModel`。(由同一模型驱动 JSON、Markdown 与 HTML)
- [x] 实现机器 JSON 报告。
- [x] 实现 GFM Markdown 渲染器和 YAML metadata。
- [x] 实现专业 HTML 模板、证据脚注和离线单文件导出。(基础自包含模板；图表、主题、PDF 与固定字体已补)
- [x] 实现因子图、估值敏感性矩阵和评分变化 SVG。(packages/reporting/charts.py)
- [x] 实现浅色、深色与打印主题。(render_html(theme=...) + SVG theme)
- [x] 实现 Playwright/Chromium PDF 导出。(render_pdf：print HTML + lazy Playwright；CI 注入 launcher，目标部署按 optional `pdf` 安装)
- [x] 在 Docker 镜像中固定中文字体版本。(Noto CJK `1:20220127+repack1-1`；目标镜像已执行实际字体渲染检查)
- [x] 实现制品 manifest 与内容哈希。(reporting 确定性 builder + artifacts 表/API 持久化与下载)
- [x] 增加 Markdown lint、黄金快照和格式交叉核对测试。(reporting 合约 lint + JSON/Markdown/HTML golden hashes)
- [x] 增加 HTML 可访问性、响应式和视觉契约测试。(离线结构/CSS/SVG 契约；真实浏览器视觉回归仍是部署级检查)
- [x] 增加 PDF 分页、空白页、字体和溢出测试。(verify_pdf.py：目标 Chromium + Noto CJK；pypdf 结构检查)
- [x] 决定是否在 v1 同期交付 Vue 审核台。(不交付；v1 保持 Headless API + CLI，避免把客户端 UI 变成后端 Demo 依赖)
- [ ] 若交付 Web，仅实现任务列表、新建任务、审核工作台和报告预览。(不适用；待 v1 之后单独立项)

### M4 完成标准

- [x] 同一批准版本的 JSON、HTML、Markdown 和 PDF 数字与证据一致。(统一 `render_report_bundle` + manifest/跨格式契约测试；目标 Chromium 已验证 PDF 文本与字体资源)
- [x] 草稿与正式报告在所有格式中都能明确区分。(JSON 状态、Markdown/HTML 标识、PDF 来自 print HTML)
- [x] PDF 无字体缺失、内容裁断和异常空白页。(浏览器双视口字体/溢出检查 + PDF 页文本/字体资源检查；已在固定 Noto CJK 的 Docker 目标镜像执行)

## 5. M5：自包含 Demo 与开源发布

- [x] 完成不依赖外置数据库的本地单镜像启动，默认使用 SQLite。(Docker/Compose + 应用数据目录；完整黄金路径仍需接入 worker/provider)
- [x] 用固定公开 fixture 或录制 Provider 响应展示完整黄金路径。(Compose opt-in ADBE cassette；创建→execute→approve 已有 API e2e)
- [x] 提供 PostgreSQL 作为可选的服务化部署示例。(docker-compose.postgres.yml；默认 Compose 仍使用 SQLite)
- [x] 编写五分钟快速开始。(docs/quickstart.md)
- [x] 编写 API、Python SDK 文档。(docs/api-and-sdk.md)
- [x] 编写 CLI 文档。(可选 `fathomark` API 客户端；见 `docs/cli.md`)
- [x] 编写 LLM Provider 和 Data Provider 开发指南。(MODEL_PROVIDERS.md、DATA_PROVIDERS.md)
- [x] 编写 ReportTheme 开发指南。(docs/reporting-development.md)
- [x] 编写评分框架开发和校验指南。(docs/framework-development.md)
- [x] 编写数据来源、许可、缓存与再分发政策。(DATA_PROVIDERS.md)
- [x] 编写提示注入、SSRF、密钥与恶意文档安全指南。(SECURITY.md)
- [x] 提供不依赖付费数据的最小公开 fixture。(examples/fixtures/adbe_2026-09-03：SEC 公开来源元数据 + 录制响应，CI 离线回放)
- [x] 提供插件认证命令与契约测试模板。(环境变量状态检查不打印密钥；见 `docs/plugin-development.md`)
- [x] 生成 SBOM 并加入依赖漏洞扫描。(CI 导出 CycloneDX 1.5 并上传构建产物)
- [x] 完成第一个公开版本的变更日志和发布检查。(CHANGELOG.md + docs/release-checklist.md；签名 tag/真实部署仍需维护者执行)
- [x] 发布打包前将 httpx 提升为 fathomark-api 运行时依赖（webhook 发送器需要）。
- [x] 验证 fathomark-storage wheel 内 alembic 目录在干净安装后可用（migrate_db 端到端）。(CI build job)

### M5 完成标准

- [x] 新用户可用一条 Docker 命令启动系统，无需预先配置外置数据库。(SQLite 默认 + health/Compose)
- [x] 新用户可按快速开始完成一次从创建研究到批准报告的自包含演示。(记录 ADBE fixture)
- [x] CI 不需要实时网络、真实 LLM 或秘密密钥。(Provider/LLM cassette + locked checks)
- [x] 贡献者可以按文档新增一个 Provider 或评分框架。(DATA_PROVIDERS.md / MODEL_PROVIDERS.md / framework-development.md)

## 6. v1 之后

- [ ] 提供面向外部研究系统的通用集成示例。
- [ ] 批量股票任务与同类 Lens 内排名。
- [ ] 银行/保险适配器。
- [ ] 周期/资源适配器。
- [ ] REIT 适配器。
- [ ] ETF 独立评分框架。
- [ ] A 股和港股官方 Provider。
- [ ] 评分变化监控与复核提醒。
- [ ] 历史版本与未来回报/回撤的研究性验证。
- [ ] 多用户权限与 OIDC。
- [ ] 独立任务队列与横向扩容。

## 7. 始终禁止

- [ ] 不允许 LLM 直接决定最终加权总分或评级映射。
- [ ] 不允许通过 Agent 投票平均消除证据冲突。
- [ ] 不允许在数据不足时用常识或叙事补数字。
- [ ] 不允许覆盖已批准版本。
- [ ] 不允许自动生成或执行交易指令。
- [ ] 不允许插件绕过宿主直接写核心数据库。
- [ ] 不允许把无授权的付费数据提交到开源仓库。
