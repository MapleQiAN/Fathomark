# Fathomark 渊衡多 Agent 选股评分系统设计

- 日期：2026-09-18
- 状态：已确认，等待实施计划
- 项目类型：独立开源项目
- 首版市场：美股
- 首版资产：普通上市经营公司
- 产品形态：Headless API 优先，可选 CLI 与 Web 审核台

## 1. 背景与目标

现有 PersonalInvestment 同时存在旧的 7 因子 70 分数据库评分表，以及当前研报使用的 11 因子、100 分、多 Lens、证据置信度、Veto 和版本化体系。新项目不迁移旧模型作为正式评分口径，而是将当前研究方法抽取成独立、可验证、可扩展的开源系统。

Fathomark（渊衡）的首要目标是：输入一只普通美股上市经营公司，在锁定研究角色、数据截止日和框架版本后，由多个专业 Agent 分工采集与评议证据，再由确定性引擎计算评分，经过人工复核后发布不可变的正式评级版本。

系统不以“多个 Agent 聊天后投票”为核心。Agent 只负责需要语义判断的工作；加权计算、评级映射、Veto 优先级、版本状态和正式发布权限必须由确定性代码控制。

## 2. 产品边界

### 2.1 v1 包含

- 单标的深度评分，不做股票池批量排名；
- 普通上市经营公司，不含专项资产适配器；
- 美股官方内置数据链路；
- 核心、进攻与战术 Lens；
- 11 因子评分、证据置信度、Veto、NR 和评级光谱；
- Agent 建议分、反方审计与人工裁决；
- 不可变批准版本与完整历史；
- 完整 Headless REST API；
- Python SDK 和 CLI；
- 可选 Vue 3 审核台；
- JSON、HTML、Markdown 与 PDF 报告；
- SQLite 单机模式与 PostgreSQL 服务模式；
- OpenAI、Anthropic 和 OpenAI-compatible LLM Provider；
- SEC EDGAR/XBRL、公司 IR 页面和可插拔行情 Provider。

### 2.2 v1 不包含

- ETF、基金、ETP；
- 银行保险、周期资源与 REIT 专用适配器；
- A 股、港股官方全自动数据源；
- 批量股票排名与自动选股；
- 回测、收益预测与组合优化；
- 自动交易、持仓写入或交易指令；
- 多租户 SaaS、计费与社区插件市场；
- 多人实时协作。

### 2.3 治理边界

- 未经人工批准的结果只能标记为 `draft`；
- 外部新闻与事件只能作为待复核证据，不能自动修改正式评级；
- 分数评价标的与预设角色的适配性，不预测未来收益；
- 组合相关性、行业暴露和个人风险偏好不进入通用评分内核；
- 新系统不得直接修改下游系统的持仓或交易数据。

## 3. 总体架构

采用“证据流水线”架构：

```text
API / CLI / Optional Web
          |
          v
     Orchestrator
          |
          +--------> Specialist Agents
          |                  |
          |                  v
          |             Providers
          |                  |
          v                  v
    Typed evidence and factor proposals
          |
          v
 Deterministic scoring core
          |
          v
 Versioned storage and human approval
          |
          v
 JSON / HTML / Markdown / PDF
```

核心依赖规则：

- `core` 不依赖 LLM SDK、数据库、Web 框架或网络；
- Agent 不能直接写数据库，只能返回经过 Schema 约束的数据；
- Provider 不能绕过宿主校验和版本治理；
- API、CLI 和 Web 通过同一应用服务层访问业务能力；
- Web 是可选客户端，不拥有任何后端无法完成的独占功能。

## 4. 仓库结构

```text
fathomark/
├── packages/
│   ├── core/          # Pydantic 模型、框架规则、计算、Veto、评级映射
│   ├── agents/        # Agent 契约、专业 Agent 与编排状态机
│   ├── providers/     # LLM、财报、行情、IR、新闻适配器
│   ├── storage/       # SQLAlchemy、Alembic、仓储与版本治理
│   ├── reporting/     # ReportModel 与多格式渲染
│   └── sdk/           # Python SDK
├── apps/
│   ├── api/           # FastAPI Headless 服务
│   ├── cli/           # Typer CLI
│   ├── worker/        # 异步任务执行器
│   └── web/           # 可选 Vue 3 审核台
├── frameworks/        # 版本化 YAML 评分框架
├── examples/          # 可公开再分发的最小 fixture
├── tests/
└── docker-compose.yml
```

推荐技术栈：Python 3.12、FastAPI、Pydantic、SQLAlchemy、Alembic、Typer、PostgreSQL、SQLite、Vue 3、TypeScript 和 Playwright。

首版使用项目自有的显式状态机，不将 LangGraph、CrewAI 或 AutoGen 设为核心依赖。未来可以增加可选编排适配器，但不得改变核心任务与数据契约。

## 5. Agent 分工

### 5.1 Scope Agent

在评分前冻结股票代码、交易所、研究角色、持有期、研究日期、数据截止日和评分框架版本。任务开始后不得为了获得更高分而更换 Lens。

### 5.2 Business Agent

分析商业模式、护城河、竞争格局、客户与产品集中度，主要覆盖商业模式/护城河和部分成长可持续性。

### 5.3 Financial Agent

读取财报和监管申报，计算现金流、杠杆、利息覆盖、ROIC、FCF 转化等指标，主要覆盖财务健康度与盈利质量。

### 5.4 Growth Agent

分析增长来源、订单、用户、产能与单位经济性，区分可持续增长、周期反弹和一次性增长。

### 5.5 Valuation Agent

选择框架允许的估值路径并解释输入选择。反向 DCF、敏感性分析和备用估值的数值计算由确定性工具执行，Agent 不心算最终估值结果。

### 5.6 Governance & Risk Agent

分析管理层诚信、审计、关联交易、资本配置、监管与政策风险，并提出 Veto 候选。

### 5.7 Market Agent

解释趋势、流动性、波动、回撤和催化剂窗口。行情指标由程序计算，Agent 只解释异常和事件背景。

### 5.8 Red-Team Agent

只审计已有结果，不重新写完整报告。检查无来源结论、日期或币种冲突、重复计分、估值方法择优、反例缺失、Veto 遗漏、数据缺口与历史评分变化依据。

### 5.9 冲突规则

系统不采用 Agent 投票或平均分。若专业 Agent 与 Red-Team Agent 对因子分存在分歧，草稿保留双方建议与证据，由人工裁决。未解决的关键冲突进入 `needs_review`；证据严重不足进入 `NR`。

## 6. 数据流

```text
创建研究任务
→ Scope Agent 冻结任务契约
→ 专业 Agent 并行采证
→ Evidence Normalizer 去重并统一日期、单位和币种
→ 专业 Agent 提交因子评分建议
→ Red-Team Agent 提交异议
→ 确定性引擎计算 Lens、Veto、NR 和评级
→ 生成 draft
→ 人工接受、修改或退回
→ 发布 approved 不可变版本
→ 渲染多格式制品
```

Agent 的因子建议必须符合结构化契约：

```json
{
  "factor": "financial_health",
  "proposed_score": 7.5,
  "rationale": "现金流覆盖未来两年债务，但利息覆盖率正在下降",
  "evidence_ids": ["ev_019", "ev_024"],
  "counter_evidence_ids": ["ev_031"],
  "confidence": "medium",
  "missing_data": [],
  "as_of_date": "2026-09-18"
}
```

不存在的 `evidence_id`、超出数据截止日的证据、非法分值和未声明缺口的必填字段会被拒绝。

## 7. 核心数据模型

```text
ResearchRun
├── ScopeSnapshot
├── ProviderRuns[]
├── EvidenceItems[]
├── MetricObservations[]
├── FactorProposals[]
├── ReviewIssues[]
├── ScoreSnapshot
├── HumanDecisions[]
└── Artifacts[]
```

- `ResearchRun`：一次完整研究运行及状态；
- `ScopeSnapshot`：评分前冻结的任务契约；
- `ProviderRun`：模型或数据 Provider 的版本、输入哈希、耗时、成本与结果；
- `EvidenceItem`：来源、URL、发布日期、数据期、访问时间、证据等级、内容哈希与许可范围内的摘录；
- `MetricObservation`：标准化数值、单位、币种、口径、公式与数据日期；
- `FactorProposal`：建议分、理由、正反证据、置信度和数据缺口；
- `ReviewIssue`：冲突、过期、重复计分、Veto 候选与阻断状态；
- `ScoreSnapshot`：确定性引擎计算出的完整结果；
- `HumanDecision`：人工接受、修改、退回与批准记录；
- `Artifact`：JSON、HTML、Markdown 和 PDF 制品及哈希。

正式版本必须同时满足：状态为 `approved`、框架版本固定、输入证据集合与计算结果均有内容哈希。

批准后的版本不可原地修改。新研究版本通过 `supersedes_id` 指向上一版。框架升级也不会自动重算或覆盖历史结果。

## 8. 评分框架

首版框架标识为 `common-stock@1.0.0`，来源于现有 11 因子普通经营公司评分方法。框架以 YAML 定义并由核心代码校验：

```yaml
id: common-stock
version: 1.0.0
factors:
  - id: financial_health
    weight: 0.15
    scale:
      min: 0
      max: 10
      step: 0.5
ratings:
  A:
    min: 80
    max_exclusive: 85
veto_rules:
  - factor: financial_health
    below: 3
```

框架必须表达：

- 11 个因子及量化锚点；
- 核心、进攻与战术 Lens 权重；
- 0.5 分步长与舍入规则；
- Veto 与 NR 条件；
- 评级区间；
- 因子最低证据要求；
- 数据新鲜度规则；
- 允许的估值路径与失败切换条件。

组合暴露、个人风险偏好、具体交易批次和自动买卖动作不进入通用框架。

## 9. 状态机

```text
created
→ scoped
→ collecting
→ analyzing
→ auditing
→ needs_review
→ draft
→ approved
```

异常与终止状态为 `failed`、`cancelled` 和 `superseded`。

- 只有 `draft` 可以批准；
- `needs_review` 必须先解决阻断问题；
- `approved` 不可回退或修改，只能被新版本替代；
- 更换角色、框架或数据截止日必须创建新运行；
- Worker 崩溃后从最后一个成功步骤继续，不重跑无关步骤。

## 10. Headless API

Headless REST API 是唯一完整产品接口：

```text
POST   /v1/research-runs
GET    /v1/research-runs/{id}
GET    /v1/research-runs/{id}/evidence
GET    /v1/research-runs/{id}/factor-proposals
GET    /v1/research-runs/{id}/review-issues
GET    /v1/research-runs/{id}/result
POST   /v1/research-runs/{id}/review-decisions
POST   /v1/research-runs/{id}/approve
POST   /v1/research-runs/{id}/retry
POST   /v1/research-runs/{id}/cancel
GET    /v1/research-runs/{id}/artifacts
GET    /v1/artifacts/{id}/download
GET    /v1/frameworks
```

创建任务必须显式提供标的、交易所、角色、持有期、框架版本和数据截止日。创建、重试、批准与制品生成使用幂等键。人工审核使用乐观锁，阻止旧页面覆盖重新生成后的结果。

API 自动生成版本化 OpenAPI 文档，并提供 Python SDK。后续可由 OpenAPI 生成 TypeScript SDK。

Webhook 使用 HMAC 签名、时间戳与重放保护，通知 `needs_review`、`approved` 和 `failed`。调用方无需解析 Markdown，可通过结果接口获得完整机器数据。

## 11. CLI 与可选 Web 审核台

CLI 与 API 使用同一 SDK：

```text
fathomark run AAPL --exchange NASDAQ --role core
fathomark status <run-id>
fathomark evidence <run-id>
fathomark review <run-id>
fathomark approve <run-id>
fathomark export <run-id> --format html,md,pdf
fathomark frameworks validate frameworks/common-stock.yaml
```

Web 首版仅包含研究任务列表、新建研究、因子审核工作台和报告预览。Web 不保存业务状态，删除 Web 应用后系统仍完整可用。

人工修改建议分必须保存 Agent 建议分、人工最终分、修改理由、操作者与时间。

## 12. 报告系统

结构化数据库是事实源，Markdown 不是数据库真相。所有格式由同一个经过验证的 `ReportModel` 生成：

```text
Approved ScoreSnapshot
        |
        v
ReportModel
├── JSON Renderer
├── Markdown Renderer
├── HTML Renderer
└── PDF Renderer from print HTML
```

### 12.1 HTML

- 专业封面、评级、总分、置信度与数据截止日；
- 因子图、估值敏感性矩阵和评分变化；
- 区分事实、计算结果和 Agent 判断；
- 因子可展开查看来源、反方意见和人工修改；
- 来源编号可回到证据；
- 浅色、深色和打印主题；
- 单文件离线 HTML；
- 草稿水印与正式批准标识不可混淆。

### 12.2 Markdown

- 从 `ReportModel` 独立渲染，不从 HTML 反向转换；
- 使用标准 GFM 标题、表格、引用与链接；
- 不依赖自定义 HTML 才能理解核心结论；
- 图表附文字版关键结论；
- YAML metadata 供其他系统解析；
- 通过 Markdown lint 与黄金快照测试。

### 12.3 PDF

- 由 HTML 专用打印主题通过 Playwright/Chromium 生成；
- A4、封面、目录、页眉页脚与页码；
- Docker 镜像固定 Noto/思源字体版本；
- 图表使用 SVG；
- 表格跨页重复表头；
- 自动检测空白页、横向溢出、字体缺失和内容裁断。

每次导出保存 `research_version`、`report_model_hash`、模板版本和各制品哈希，保证多格式的数字、评级、证据和版本一致。

## 13. Provider 与插件

插件分为 `LLMProvider`、`DataProvider` 和 `ReportTheme`。每个插件通过 Python entry point 注册，并声明名称、版本、支持市场、数据类型、Schema、授权限制、缓存限制、超时、重试、速率限制、原始响应存储策略与健康检查。

插件不能直接写核心数据库。宿主必须对插件返回的数据执行 Schema、日期、许可和证据引用校验。

官方 v1 数据链路优先支持美股：SEC EDGAR/XBRL、公司 IR 页面和可替换行情 Provider。其他市场可以通过手工证据上传或第三方 Provider 接入，但不承诺开箱即用的自动采集。

## 14. 失败处理与恢复

- 每个步骤保存输入哈希、Agent/Provider 版本、时间、结构化输出、校验结果和重试次数；
- Agent 输出不符合 Schema 时最多执行两次结构修复，仍失败则进入 `needs_review`；
- Provider 不可用时只重跑受影响步骤；
- 必需证据缺失时输出 `NR` 或阻断草稿；
- 冲突来源同时保留并标记 `conflicted`；
- 超过数据截止日的资料不进入当次评分；
- 财报、行情和一致预期分别记录新鲜度；
- 每次运行设置调用次数、Token、金额和最长执行时间预算；
- 重试使用同一幂等键；
- 付费数据默认不完整落库，只保存许可范围内的数据、元数据、哈希和必要摘录。

## 15. 安全设计

- 外部网页、PDF、新闻和财报全部视为不可信数据；
- 文档中的指令不能改变系统任务、评分框架或工具权限；
- Agent 只能调用注册工具，不能执行任意 Shell、SQL 或 Python；
- URL 抓取只允许 HTTPS，阻止私网、重定向到内网、异常 MIME 与超大文件；
- 密钥只从环境变量或 Secret Manager 读取；
- 日志脱敏 Authorization、Cookie、数据库 URL 和 Provider 错误；
- 非本机服务必须配置 API Key；
- 人工批准权限与只读权限分离；
- 自定义框架只作为数据解析，不允许可执行表达式；
- Webhook 使用签名与重放保护。

## 16. 测试策略

### 16.1 评分内核

- 权重、边界、评级区间、Veto、NR 和舍入单元测试；
- 属性测试保证相同输入得到相同输出；
- 框架兼容性与非法配置拒绝测试。

### 16.2 Agent 契约

- 固定证据 fixture 与假 Provider；
- 输出 Schema、证据引用、日期和缺口声明检查；
- 禁止不存在的证据引用；
- 事实、计算结果和判断分离检查。

### 16.3 编排与恢复

- Provider 超时、限流和损坏 JSON；
- Worker 崩溃后的断点恢复；
- 重复提交、重复批准与并发审核；
- 取消、重试和版本替代；
- SQLite 与 PostgreSQL 双数据库。

### 16.4 报告

- JSON、Markdown 和 HTML 黄金快照；
- 多格式分数、评级和来源数量交叉核对；
- HTML 可访问性和响应式检查；
- PDF 字体、分页、空白页与溢出检测；
- 草稿与正式标识检查。

### 16.5 离线端到端

CI 使用固定公开样例与录制 Provider 响应，不依赖实时网络或真实 LLM。实时测试单独运行并明确标记，不能代替确定性 CI。

插件认证命令只证明接口、格式与确定性要求满足，不代表数据准确或投资结论正确。

## 17. 部署

本地单后端使用一个镜像，可在同一进程运行 API 与轻量任务执行器：

```text
docker run \
  -e DATABASE_URL=sqlite:////data/fathomark.db \
  -e OPENAI_API_KEY=<secret> \
  -v ./data:/data \
  -p 8000:8000 \
  fathomark/server
```

正式部署使用相同镜像拆分 API 与 Worker，并连接 PostgreSQL：

```text
fathomark serve
fathomark worker
```

首版不要求 Redis。吞吐量需要横向扩展时，再引入独立任务队列；该变化不得影响 API 和核心数据契约。

## 18. PersonalInvestment 迁移与集成

两个项目只通过 API 集成，不共享数据库：

```text
PersonalInvestment
→ 创建 Fathomark 研究任务
→ 展示 needs_review
→ 用户提交审核与批准
→ 拉取 approved JSON 与报告制品
→ 更新自身研究版本索引
```

迁移规则：

- 现有 Markdown 研报保持不变；
- Fathomark 提供导入器解析当前 front matter 与因子表；
- 旧 70 分 `scores` 表进入只读兼容期，不转换成新的正式评级；
- 新评级按 `symbol + research_role + framework_version` 建立版本；
- PersonalInvestment 只消费 `approved`；
- PersonalInvestment 不能直接写 Fathomark 数据库；
- 新评级不能自动更新持仓、交易记录或交易动作。

## 19. 开源治理

- 代码与默认评分框架：Apache License 2.0；
- 示例报告：CC BY 4.0；
- 第三方数据不随仓库发布，只提供可公开再分发的最小 fixture；
- 项目明确声明不构成投资建议，不提供自动交易能力。

正式发布前必须包含：`LICENSE`、`NOTICE`、`SECURITY.md`、`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`DATA_PROVIDERS.md`、`MODEL_PROVIDERS.md` 和 `DISCLAIMER.md`。

## 20. 分阶段交付

1. M1：确定性评分内核与 `common-stock@1.0.0`；
2. M2：存储、状态机、Headless API、OpenAPI 与 Python SDK；
3. M3：美股数据 Provider 与专业 Agent；
4. M4：人工审核、ReportModel、多格式报告与可选 Web；
5. M5：PersonalInvestment API 适配与历史研报导入；
6. M6：安全、文档、许可证、示例与公开发布。

## 21. v1 验收标准

- 一条 Docker 命令可启动单后端；
- API 可以对一只普通美股发起深度评分；
- 每个因子都能追溯到结构化证据；
- Agent 失败会重试或进入 `needs_review`，不会伪造完整结果；
- 人工可以修改建议分、说明理由并批准不可变版本；
- JSON、HTML、Markdown 与 PDF 内容一致；
- 批准版本可在断网环境下复算出相同评分；
- API、CLI 和可选 Web 使用同一业务能力；
- PersonalInvestment 可以只通过 API 消费正式结果；
- CI 不使用真实密钥或实时网络；
- 项目文档覆盖快速开始、Provider 开发、评分框架开发、安全和数据许可。

## 22. 已确认的关键决策

- 项目完全独立，并面向开源发布；
- v1 先完成单股票深度评分，再考虑批量选股；
- v1 仅支持普通上市经营公司；
- v1 官方数据链路美股优先；
- 正式评级必须人工批准；
- Headless API 是产品本体；
- Web 只是可选客户端；
- Agent 冲突不通过平均投票解决；
- 结构化数据是事实源，报告只是渲染物；
- HTML 是视觉主版，Markdown 独立渲染，PDF 由打印 HTML 生成；
- 批准版本不可变；
- 代码采用 Apache 2.0 方向；
- 英文品牌为 Fathomark，中文品牌为“渊衡”，标语为“深研有据，权衡有度”。
