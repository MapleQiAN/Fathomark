# M3 切片 2：剩余专业评分 Agent 设计

**日期:** 2026-09-20
**状态:** 已批准
**前置:** M3 切片 1（Provider 协议、Scope/Financial Agent、Orchestrator、step_runs、execute 端点）已完成
**规格来源:** `docs/design/2026-09-18-fathomark-design.md` §5.2/§5.4–§5.7；`TODO.md` §3

## 目标

实现 5 个剩余专业评分 Agent（Business、Growth、Valuation、Governance & Risk、Market），覆盖 FixtureReplayAgent 当前回放的全部 9 个因子，删除 fixture 回放路径。ADBE 离线 e2e 继续产出与 `expected_snapshot.json` 完全一致的 draft（content_hash 不变）。

Red-Team Agent（design §5.8）不在本切片——它是审计者而非评分者，需审计输入/输出结构与 `needs_review` 挂接设计，留待后续切片。Veto 候选同理（FactorProposal 无 veto 字段）。

## 非目标

- Red-Team Agent、Veto 机制
- 新证据来源（继续使用 ADBE fixture 的 2 条证据；EDGAR/IR/行情 Provider 另属 TODO §3）
- 并行执行（DAG 层级结构就位，仍顺序执行）
- 异步 worker

## 架构

### SpecialistAgent 基类

新模块 `packages/agents/src/fathomark_agents/specialist_agent.py`：

```python
class SpecialistAgent:
    name: str
    version: str
    factors: tuple[str, ...]
    instructions: str  # 类常量，per-agent 指令头

    def __init__(self, llm: LLMProvider, max_repairs: int = 2): ...
    def run(self, *, scope, framework, evidence) -> list[FactorProposal]: ...
```

- `build_prompt(scope, evidence, instructions)` 从 `financial_agent.py` 迁入本模块，canonical JSON 格式逐字节不变（指令头除外）
- `run()` 逻辑 = 现 FinancialAgent：一次 LLM 调用返回 `{"proposals": [...]}`，`complete_with_repairs`（≤2 次修复），逐条 `FactorProposal.model_validate` + 因子归属检查（不得提议 `self.factors` 之外因子）+ `validate_proposal`（未知证据 id、超截止日、框架校验）

### 6 个子类

| 类 | name | factors |
|---|---|---|
| FinancialAgent（重构为子类） | financial-agent | financial_health, earnings_quality |
| BusinessAgent | business-agent | business_moat |
| GrowthAgent | growth-agent | growth_sustainability |
| ValuationAgent | valuation-agent | valuation |
| GovernanceRiskAgent | governance-risk-agent | governance, policy_risk |
| MarketAgent | market-agent | trend_momentum, liquidity, volatility_downside, catalyst_window |

因子归属依据 design §5.2–§5.7。`growth_sustainability` 归 Growth Agent（design §5.2 的"部分成长可持续性"由 Growth 汇总提议，Business 只拥有 business_moat，归属互斥）。

每个子类 = 指令常量 + 因子元组，无重复逻辑。`financial_agent.py` 保留 `FINANCIAL_FACTORS` 与 `FinancialAgent` 导出（兼容现有测试/导入）。

## Cassette 与夹具

- 每 Agent 一份 golden 响应文件：`examples/fixtures/adbe_2026-09-03/responses/<agent>.json`（6 份，含 financial；proposals 逐字取自 `input.json` 黄金值）。现有 `financial_response.json` 迁入 `responses/financial.json`
- `llm_cassette.json` 由**提交入库的确定性脚本** `scripts/build_cassette.py` 生成：从夹具加载 scope/evidence，对 6 个 Agent 各算 `build_prompt` → `prompt_key` → 写入 `{key: response_text}`。无网络、无 LLM，纯确定性。cassette 漂移 = 重跑脚本
- `expected_snapshot.json` 不变：6 个 Agent 的 proposals 合计 = 原 golden 11 因子，draft 计算结果与 content_hash 不变，e2e 继续断言相等
- 删除：`fixture_agent.py`、`stub_proposals.json`、`test_fixture_agent.py`

## Orchestrator 改动

- 步骤图：`scope → collect → {financial, business, growth, valuation, governance_risk, market} → compute`。6 个 Agent 步骤同一 DAG 层级（Kahn 分层已就位，顺序执行）
- `Orchestrator.__init__` 删除 `stub_path` 参数；6 个 Agent 内部构造，共享 `_BudgetedLLM`
- proposals 持久化 `origin="agent"`（repository 默认值，与 financial 现状一致；snapshot 不含 origin，黄金快照不受影响）
- resume/失败语义不变：AgentError → `needs_review`（仅失败步骤重跑）；ProviderError/空证据 → `failed`；input_hash 匹配的成功步骤跳过

## 错误处理

沿用切片 1 语义，无新增：

- LLM 输出非法 JSON / 缺因子 / 外族因子 / 引用未知或超期证据 → 修复重试（≤2），耗尽 → AgentError → run `needs_review`，不写任何 proposal
- ProviderError（cassette miss、预算超限）→ run `failed`，error 落库
- 预算：`max_llm_calls=32` 默认不变（6 Agent 各 1 调用，余量充足）

## 测试

- `test_specialist_agent.py`：6 Agent × cassette 回放参数化测试（因子集、分数、证据引用断言）；Market Agent（4 因子）做修复/拒绝代表（外族因子、超期证据、坏 JSON 修复）
- `test_orchestrator.py` 更新：步骤集 = 9 步；resume 测试断言失败 Agent 单独重跑、其余 attempt 不变、无重复 evidence/proposals；预算测试保留
- `test_fixture_agent.py` 删除
- `packages/api/tests/test_execute_adbe.py`：factory 去掉 `stub_path`，断言不变（draft + content_hash）
- 全量 `pytest`、`ruff check`、`ruff format --check` 绿

## 文档

- `TODO.md` §3：勾选 Business/Growth/Valuation/Governance & Risk/Market Agent；删除 FixtureReplayAgent 注释行
- `README.md` / `README.zh-CN.md`：状态行更新为"全部 11 因子由真实 Agent 覆盖（ADBE 离线回放）"
