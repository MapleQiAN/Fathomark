# Fathomark M1: Deterministic Scoring Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `packages/core` — a pure-Python deterministic scoring engine plus the versioned `common-stock@1.0.0` YAML framework — such that fixed JSON input produces a fully reproducible `ScoreSnapshot` (lens totals, ratings, veto, NR, tactical state) offline.

**Architecture:** Pydantic v2 models for all schemas. YAML framework file is the single source of truth for factors, anchors, lens weights, rating bands, veto rules and valuation rules; core code loads and validates it. Scoring pipeline: validate `FactorProposal`s against evidence index and data cutoff → compute weighted lens totals → apply veto (→ `X`) and NR rules → map total to rating spectrum and tactical state. Reverse DCF (two models) with bisection solver and 3×3 sensitivity matrix is exposed as deterministic functions. No LLM SDK, database, web framework, or network imports anywhere under `packages/core`.

**Tech Stack:** Python 3.12, Pydantic v2, PyYAML, uv (dependency manager), pytest, hypothesis.

**Spec:** `docs/design/2026-09-18-fathomark-design.md` (architecture, §5–§9, §14); source framework extracted from `PersonalInvestment/research/standard/选股评分框架.md` (v3.3) and `选股评分框架-v3.md`.

## Global Constraints

- Python `>=3.12` (design §4).
- `core` must not import LLM SDKs, database, web frameworks, or network (design §3, M1 exit criteria).
- Factor scores: 0–10, step 0.5; lens total = `Σ(score × weight) × 10`, range 0–100 (framework §一).
- Rating spectrum (framework v3.3 §4.7): S ≥90; A+ 85–<90; A 80–<85; B+ 75–<80; B 70–<75; B- 65–<70; C 60–<65; D <60; X = any score when veto triggered; NR = no valid total.
- Veto rules (framework §5.1): `financial_health < 3` → X all lenses; `governance < 3` → X all lenses; `policy_risk < 3` → X for core and offensive lenses only (tactical lens not vetoed, flagged); evidence confidence `insufficient` → NR.
- Tactical states (framework §4.3 note): T1 = tactical total ≥80; T2 = 65–79; T3 = <65.
- Reverse DCF: solve `g_implied` by bisection on `[-0.20, 1.00]`; no root in interval → model invalid, never extrapolate. Sensitivity: WACC ±1pp, g_T ±0.5pp, 3×3; width = max−min of valid `g_implied`; ≤10pp robust; >10≤20pp fragile (still score DCF base case, downgrade confidence); >20pp / any unsolvable valid scenario / <6 valid scenarios / deviation spans both `<-10%` and `≥10%` → model invalid, switch to backup valuation path.
- Deviation = `(g_implied − g_expected) / max(|g_expected|, 0.05)`. Anchor bands are left-closed right-open: `≥0.30`→0; `[0.10,0.30)`→4; `[-0.10,0.10)`→7; `[-0.20,-0.10)`→linear 7.5→9.5 rounded to nearest 0.5 (at −0.10 → 7.5, at −0.20 → 9.5); `<-0.20`→10.
- Backup PEG anchors: `>3`→0; `[2,3]`→4; `[1,2)`→7; `<1`→10.
- Personal portfolio, position sizing, and trade-action rules are excluded (TODO M1; design §2.3). Confidence multiplier is recorded on the snapshot but no position math.
- Package name: `fathomark-core` (module `fathomark_core`). Framework file: `frameworks/common-stock.yaml`, id `common-stock`, version `1.0.0`.
- Commits: conventional commits, one per task.

### Decisions locked for this plan (not in source docs)

- Dependency manager: **uv** with `pyproject.toml` at repo root (resolves TODO §0 "选择 Python 依赖管理与构建工具").
- Data freshness rules are required by design §8 but the source framework has no explicit numbers. They are added to the YAML as **configurable data** with defaults: `market_data: 7` days, `filings: 130` days, `consensus: 90` days, `news: 30` days. These are new defaults, not extracted rules — flagged for user review at first checkpoint.
- `policy_risk` veto on the tactical lens produces a `veto_flag` on the tactical result (per framework: tactical may only proceed as tiny event-driven position), but the tactical rating is still computed.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `packages/core/pyproject.toml`
- Create: `packages/core/src/fathomark_core/__init__.py`
- Create: `tests/__init__.py`, `packages/core/tests/__init__.py`

**Interfaces:**
- Produces: installable package `fathomark-core`, module `fathomark_core`, pytest discovering `packages/core/tests`.

- [ ] **Step 1: Initialize uv workspace and write pyproject files**

Root `pyproject.toml`:

```toml
[project]
name = "fathomark"
version = "0.1.0"
description = "Fathomark 渊衡 — evidence-driven multi-agent equity scoring"
requires-python = ">=3.12"
dependencies = []

[tool.uv.workspace]
members = ["packages/*"]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "hypothesis>=6.112",
    "ruff>=0.6",
]

[tool.pytest.ini_options]
testpaths = ["packages", "tests"]

[tool.ruff]
target-version = "py312"
```

`packages/core/pyproject.toml`:

```toml
[project]
name = "fathomark-core"
version = "0.1.0"
description = "Deterministic scoring core for Fathomark"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.9",
    "pyyaml>=6.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fathomark_core"]
```

`packages/core/src/fathomark_core/__init__.py`:

```python
"""Fathomark deterministic scoring core."""
```

- [ ] **Step 2: Install and verify**

Run: `cd /Users/serendylin/Documents/Fathomark && uv sync && uv run pytest -q`
Expected: no tests collected, exit code 5 (no tests) — install itself must succeed.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml packages/core uv.lock
git commit -m "chore: scaffold uv workspace and fathomark-core package"
```

---

### Task 2: `common-stock@1.0.0` framework YAML

**Files:**
- Create: `frameworks/common-stock.yaml`
- Test: `packages/core/tests/test_framework_file.py`

**Interfaces:**
- Produces: YAML at `frameworks/common-stock.yaml` with keys consumed by Task 3's loader: `id`, `version`, `scale{min,max,step}`, `factors[]`, `lenses{}`, `ratings[]`, `tactical_states[]`, `veto_rules[]`, `confidence_levels{}`, `freshness{}`, `valuation{}`.

- [ ] **Step 1: Write failing test (file exists and parses)**

```python
# packages/core/tests/test_framework_file.py
from pathlib import Path

import yaml


def test_framework_yaml_parses():
    path = Path(__file__).parents[3] / "frameworks" / "common-stock.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["id"] == "common-stock"
    assert data["version"] == "1.0.0"
    assert len(data["factors"]) == 11
    assert set(data["lenses"]) == {"core", "offensive", "tactical"}
```

Run: `uv run pytest packages/core/tests/test_framework_file.py -v`
Expected: FAIL (file not found).

- [ ] **Step 2: Write `frameworks/common-stock.yaml`**

```yaml
# common-stock@1.0.0 — extracted from PersonalInvestment 选股评分框架 v3.3 (baseline
# 普通经营公司 lens tables). Portfolio/position/trade rules intentionally excluded.
id: common-stock
version: "1.0.0"
asset_type: common_operating_company

scale:
  min: 0.0
  max: 10.0
  step: 0.5

factors:
  - id: business_moat
    name: 商业模式/护城河
    category: fundamentals
    anchors: {0: 无壁垒充分竞争单位经济性恶化, 4: 弱壁垒仅局部品牌渠道优势, 7: 至少具备网络效应/转换成本/成本优势之一且可数据验证, 10: 多重壁垒叠加竞争优势持续强化}
  - id: financial_health
    name: 财务健康度
    category: fundamentals
    anchors: {0: 现金跑道<12个月或利息覆盖<1.5倍或经营现金流为负且高度依赖外部融资, 4: 净负债/EBITDA约3-6倍或利息覆盖2-4倍现金跑道12-24个月, 7: 杠杆合理利息覆盖4-8倍未来24个月债务可覆盖经营现金流为正, 10: 净现金或负债极低利息覆盖>8倍自由现金流稳定为正}
  - id: governance
    name: 治理质量
    category: fundamentals
    anchors: {0: 实控人/管理层重大诚信问题或审计非标或关联交易严重, 4: 治理一般激励与披露质量普通, 7: 治理规范披露及时管理层稳定持股或合理长期激励, 10: 管理层与股东利益高度绑定资本配置记录优秀}
  - id: policy_risk
    name: 政策监管风险
    category: fundamentals
    anchors: {0: 行业强监管收紧商业模式可能被直接破坏, 4: 政策不确定性较高关键规则未落地, 7: 政策中性或边际改善公司具备合规缓冲, 10: 政策明确利好已落地公司为直接受益者}
  - id: growth_sustainability
    name: 成长可持续性
    category: growth_valuation
    anchors: {0: 收入/利润负增长或依赖单一客户/补贴/一次性提价, 4: 增速低于行业平均驱动力单一, 7: 增速达到或超行业平均至少2个可验证驱动力, 10: 增速持续超预期驱动力多元领先指标与单位经济性同步改善}
  - id: valuation
    name: 估值水平
    category: growth_valuation
    anchors: {0: 主/备用估值锚点落入0分档, 4: 落入4分档, 7: 落入7分档, 10: 落入10分档}
  - id: earnings_quality
    name: 盈利质量
    category: growth_valuation
    anchors: {0: ROE/ROIC<5%或利润主要来自一次性项目或负FCF源于经营恶化, 4: ROE/ROIC约5-10%现金转化率低且波动大, 7: ROE/ROIC约10-15%且FCF转化率>70%或ROIIC高于WACC, 10: ROE/ROIC>15%且FCF转化率>90%或ROIIC显著高于WACC且持续改善}
  - id: trend_momentum
    name: 趋势/动量
    category: market
    anchors: {0: 跌破关键均线相对强度持续走弱, 4: 震荡无方向相对强度中性, 7: 站上关键均线相对强度改善量价基本配合, 10: 多周期趋势共振向上突破有效量价同步确认}
  - id: liquidity
    name: 交易流动性
    category: market
    anchors: {0: 经常停牌/熔断买卖价差>1%盘口深度差, 4: 典型价差约0.3%-1%深度有限, 7: 典型价差约0.1%-0.3%常态交易顺畅, 10: 典型价差<0.1%成交活跃压力期仍有连续性}
  - id: volatility_downside
    name: 波动率/下行风险
    category: market
    anchors: {0: 近1年最大回撤>50%下行波动显著高于基准, 4: 最大回撤30%-50%尾部风险较高, 7: 最大回撤15%-30%波动与同类相当, 10: 最大回撤<15%下行波动低于基准}
  - id: catalyst_window
    name: 催化剂时间窗
    category: market
    anchors: {0: 无明确催化剂依赖远期叙事, 4: 催化剂存在但时点不确定预计>12个月, 7: 催化剂明确预计3-12个月内验证, 10: 催化剂已进入<3个月验证窗口且可观察指标清晰}

lenses:
  core:
    business_moat: 0.22
    financial_health: 0.22
    governance: 0.12
    policy_risk: 0.08
    growth_sustainability: 0.05
    valuation: 0.11
    earnings_quality: 0.11
    trend_momentum: 0.01
    liquidity: 0.02
    volatility_downside: 0.06
    catalyst_window: 0.0
  offensive:
    business_moat: 0.15
    financial_health: 0.08
    governance: 0.08
    policy_risk: 0.06
    growth_sustainability: 0.24
    valuation: 0.17
    earnings_quality: 0.08
    trend_momentum: 0.05
    liquidity: 0.03
    volatility_downside: 0.02
    catalyst_window: 0.04
  tactical:
    business_moat: 0.03
    financial_health: 0.08
    governance: 0.02
    policy_risk: 0.0
    growth_sustainability: 0.0
    valuation: 0.10
    earnings_quality: 0.06
    trend_momentum: 0.20
    liquidity: 0.16
    volatility_downside: 0.13
    catalyst_window: 0.22

# Rating spectrum, framework v3.3 §4.7. Left-closed right-open on total (0-100).
ratings:
  - {grade: S,  min: 90, max_exclusive: 101}
  - {grade: A+, min: 85, max_exclusive: 90}
  - {grade: A,  min: 80, max_exclusive: 85}
  - {grade: B+, min: 75, max_exclusive: 80}
  - {grade: B,  min: 70, max_exclusive: 75}
  - {grade: B-, min: 65, max_exclusive: 70}
  - {grade: C,  min: 60, max_exclusive: 65}
  - {grade: D,  min: 0,  max_exclusive: 60}

# Tactical execution states from tactical lens total (§4.3).
tactical_states:
  - {state: T1, min: 80, max_exclusive: 101}
  - {state: T2, min: 65, max_exclusive: 80}
  - {state: T3, min: 0,  max_exclusive: 65}

veto_rules:
  - factor: financial_health
    below: 3.0
    applies_to: [core, offensive, tactical]
  - factor: governance
    below: 3.0
    applies_to: [core, offensive, tactical]
  - factor: policy_risk
    below: 3.0
    applies_to: [core, offensive]   # tactical: flag only, not vetoed

confidence_levels:      # §4.5; multiplier recorded, no position math in v1 core
  high:         {multiplier: 1.0}
  medium:       {multiplier: 0.75}
  low:          {multiplier: 0.5}
  insufficient: {multiplier: 0.0, forces_nr: true}

# Defaults new in Fathomark (design §8 requires freshness rules; source framework
# has none). Days relative to the run's research_date.
freshness:
  market_data: {max_age_days: 7}
  filings:     {max_age_days: 130}
  consensus:   {max_age_days: 90}
  news:        {max_age_days: 30}

valuation:
  root_interval: [-0.20, 1.00]     # g_implied bisection interval
  solver_tolerance: 1.0e-6
  horizon_years: 5
  sensitivity:
    wacc_offsets: [-0.01, 0.0, 0.01]
    terminal_growth_offsets: [-0.005, 0.0, 0.005]
    min_valid_scenarios: 6
    robust_max_width: 0.10         # pp width <= 10 -> robust
    fragile_max_width: 0.20        # >20pp or other failures -> invalid
  deviation:
    denominator_floor: 0.05
    anchors:
      - {min: 0.30,  max_exclusive: null, score: 0.0}
      - {min: 0.10,  max_exclusive: 0.30, score: 4.0}
      - {min: -0.10, max_exclusive: 0.10, score: 7.0}
      - {min: -0.20, max_exclusive: -0.10, score_low: 7.5, score_high: 9.5}  # linear interp
      - {min: null,  max_exclusive: -0.20, score: 10.0}
  backup_peg_anchors:
    - {min: 3.0, max_exclusive: null, score: 0.0}   # peg > 3
    - {min: 2.0, max_exclusive: 3.0, score: 4.0}    # peg in [2,3]
    - {min: 1.0, max_exclusive: 2.0, score: 7.0}
    - {min: null, max_exclusive: 1.0, score: 10.0}  # peg < 1
```

- [ ] **Step 3: Run test, verify pass**

Run: `uv run pytest packages/core/tests/test_framework_file.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frameworks/common-stock.yaml packages/core/tests/test_framework_file.py
git commit -m "feat(core): add common-stock@1.0.0 framework YAML"
```

---

### Task 3: Framework schema, loader, and validation

**Files:**
- Create: `packages/core/src/fathomark_core/framework.py`
- Test: `packages/core/tests/test_framework.py`

**Interfaces:**
- Consumes: `frameworks/common-stock.yaml` (Task 2).
- Produces:
  - `Framework(BaseModel)` with `.factors: dict[str, Factor]`, `.lenses: dict[str, dict[str, float]]`, `.ratings: list[RatingBand]`, `.tactical_states: list[TacticalBand]`, `.veto_rules: list[VetoRule]`, `.valuation: ValuationConfig`
  - `load_framework(path: Path) -> Framework` — parses and validates; raises `FrameworkValidationError(ValueError)` on any invalid config.
  - `FrameworkValidationError(ValueError)`

- [ ] **Step 1: Write failing tests**

```python
# packages/core/tests/test_framework.py
from pathlib import Path

import pytest

from fathomark_core.framework import (
    FrameworkValidationError,
    load_framework,
)

FRAMEWORK_PATH = Path(__file__).parents[3] / "frameworks" / "common-stock.yaml"


def test_load_bundled_framework():
    fw = load_framework(FRAMEWORK_PATH)
    assert fw.id == "common-stock"
    assert fw.version == "1.0.0"
    assert len(fw.factors) == 11
    assert fw.scale.step == 0.5
    assert fw.lenses["core"]["financial_health"] == 0.22


def test_lens_weights_must_sum_to_one(tmp_path):
    bad = FRAMEWORK_PATH.read_text(encoding="utf-8").replace("business_moat: 0.22", "business_moat: 0.23", 1)
    p = tmp_path / "bad.yaml"
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(FrameworkValidationError, match="sum"):
        load_framework(p)


def test_lens_must_reference_known_factors(tmp_path):
    text = FRAMEWORK_PATH.read_text(encoding="utf-8").replace("business_moat:", "unknown_factor:", 1)
    p = tmp_path / "bad.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(FrameworkValidationError):
        load_framework(p)


def test_rating_bands_must_cover_0_to_100(tmp_path):
    text = FRAMEWORK_PATH.read_text(encoding="utf-8").replace(
        "{grade: D,  min: 0,  max_exclusive: 60}", "{grade: D,  min: 0,  max_exclusive: 55}", 1
    )
    p = tmp_path / "bad.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(FrameworkValidationError, match="rating"):
        load_framework(p)


def test_veto_rule_factor_must_exist(tmp_path):
    text = FRAMEWORK_PATH.read_text(encoding="utf-8").replace(
        "  - factor: financial_health\n    below: 3.0", "  - factor: nope\n    below: 3.0", 1
    )
    p = tmp_path / "bad.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(FrameworkValidationError):
        load_framework(p)
```

Run: `uv run pytest packages/core/tests/test_framework.py -v`
Expected: FAIL (module not found).

- [ ] **Step 2: Implement `framework.py`**

```python
"""Versioned scoring framework loading and validation."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class FrameworkValidationError(ValueError):
    """Raised when a framework file fails validation."""


class Scale(BaseModel):
    min: float
    max: float
    step: float


class Factor(BaseModel):
    id: str
    name: str
    category: str
    anchors: dict[int, str]


class RatingBand(BaseModel):
    grade: str
    min: float
    max_exclusive: float


class TacticalBand(BaseModel):
    state: str
    min: float
    max_exclusive: float


class VetoRule(BaseModel):
    factor: str
    below: float
    applies_to: list[str]


class DeviationAnchor(BaseModel):
    min: float | None
    max_exclusive: float | None
    score: float | None = None
    score_low: float | None = None
    score_high: float | None = None


class SensitivityConfig(BaseModel):
    wacc_offsets: list[float]
    terminal_growth_offsets: list[float]
    min_valid_scenarios: int
    robust_max_width: float
    fragile_max_width: float


class ValuationConfig(BaseModel):
    root_interval: tuple[float, float]
    solver_tolerance: float
    horizon_years: int
    sensitivity: SensitivityConfig
    deviation: dict
    backup_peg_anchors: list[dict]


class Framework(BaseModel):
    model_config = {"frozen": True}

    id: str
    version: str
    asset_type: str
    scale: Scale
    lenses: dict[str, dict[str, float]]
    ratings: list[RatingBand]
    tactical_states: list[TacticalBand]
    veto_rules: list[VetoRule]
    confidence_levels: dict[str, dict]
    freshness: dict[str, dict]
    valuation: ValuationConfig
    raw_factors: list[Factor] = Field(alias="factors")

    @property
    def factors(self) -> dict[str, Factor]:
        return {f.id: f for f in self.raw_factors}

    @property
    def framework_ref(self) -> str:
        return f"{self.id}@{self.version}"

    @model_validator(mode="after")
    def _validate(self) -> "Framework":
        errors: list[str] = []
        known = set(self.factors)
        if len(self.raw_factors) != len(known):
            errors.append("duplicate factor ids")
        for lens_name, weights in self.lenses.items():
            unknown = set(weights) - known
            if unknown:
                errors.append(f"lens {lens_name} references unknown factors: {sorted(unknown)}")
            total = sum(weights.values())
            if abs(total - 1.0) > 1e-9:
                errors.append(f"lens {lens_name} weights sum to {total}, must sum to 1.0")
            if set(weights) != known:
                errors.append(f"lens {lens_name} must weight every factor")
        for band_set, label in ((self.ratings, "rating"), (self.tactical_states, "tactical")):
            covered = sorted((b.min, b.max_exclusive) for b in band_set)
            if covered[0][0] != 0 or any(covered[i][1] != covered[i + 1][0] for i in range(len(covered) - 1)):
                errors.append(f"{label} bands must be contiguous from 0 with no gaps")
        for rule in self.veto_rules:
            if rule.factor not in known:
                errors.append(f"veto rule references unknown factor {rule.factor}")
            unknown_lenses = set(rule.applies_to) - set(self.lenses)
            if unknown_lenses:
                errors.append(f"veto rule references unknown lenses: {sorted(unknown_lenses)}")
        if errors:
            raise FrameworkValidationError("; ".join(errors))
        return self


def load_framework(path: Path) -> Framework:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Framework.model_validate(data)
    except FrameworkValidationError:
        raise
    except Exception as exc:  # yaml errors, pydantic errors
        raise FrameworkValidationError(f"invalid framework {path}: {exc}") from exc
```

Note: `Framework` is frozen so it can be safely shared; `raw_factors` uses alias `factors` and the `factors` property exposes the id-keyed dict. (If pydantic rejects a property colliding with an alias, rename the property to `factor_map` and update tests accordingly.)

- [ ] **Step 3: Run tests, verify pass**

Run: `uv run pytest packages/core/tests/test_framework.py -v`
Expected: 5 PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/fathomark_core/framework.py packages/core/tests/test_framework.py
git commit -m "feat(core): framework loader with schema and config validation"
```

---

### Task 4: Domain schemas (ScopeSnapshot, EvidenceItem, MetricObservation, FactorProposal)

**Files:**
- Create: `packages/core/src/fathomark_core/schemas.py`
- Test: `packages/core/tests/test_schemas.py`

**Interfaces:**
- Consumes: `Framework` (Task 3).
- Produces:
  - `ScopeSnapshot(symbol, exchange, research_role: Literal["core","offensive","tactical"], horizon, research_date: date, data_cutoff: date, framework_ref: str)`
  - `EvidenceItem(id, source_name, source_class: Literal["market_data","filings","consensus","news","ir","other"], url: str | None, published_date: date, data_period_end: date | None, accessed_at: datetime, grade: Literal["A","B","C"], content_hash: str, excerpt: str | None)`
  - `MetricObservation(metric, value: float, unit, currency: str | None, basis, formula: str | None, data_date: date, evidence_id: str)`
  - `FactorProposal(factor, proposed_score: float, rationale, evidence_ids: list[str], counter_evidence_ids: list[str], confidence: Literal["high","medium","low","insufficient"], missing_data: list[str], as_of_date: date)`
  - `ProposalError(ValueError)`; `validate_proposal(p: FactorProposal, *, framework: Framework, evidence_ids: set[str], data_cutoff: date) -> None` — raises on unknown factor, unknown evidence id, evidence date beyond cutoff, illegal score, or missing rationale.

- [ ] **Step 1: Write failing tests**

```python
# packages/core/tests/test_schemas.py
from datetime import date, datetime
from pathlib import Path

import pytest

from fathomark_core.framework import load_framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ProposalError,
    ScopeSnapshot,
    validate_proposal,
)

FRAMEWORK = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml")
CUTOFF = date(2026, 9, 18)


def _evidence(ev_id: str = "ev_001", published: date = date(2026, 9, 1)) -> EvidenceItem:
    return EvidenceItem(
        id=ev_id,
        source_name="SEC 10-Q",
        source_class="filings",
        url="https://www.sec.gov/example",
        published_date=published,
        data_period_end=None,
        accessed_at=datetime(2026, 9, 18, 12, 0, 0),
        grade="A",
        content_hash="sha256:abc",
        excerpt=None,
    )


def _proposal(**kw) -> FactorProposal:
    base = dict(
        factor="financial_health",
        proposed_score=7.5,
        rationale="现金流覆盖未来两年债务，但利息覆盖率正在下降",
        evidence_ids=["ev_001"],
        counter_evidence_ids=[],
        confidence="medium",
        missing_data=[],
        as_of_date=date(2026, 9, 18),
    )
    return FactorProposal(**(base | kw))


def test_scope_snapshot_and_evidence_round_trip():
    scope = ScopeSnapshot(
        symbol="ADBE", exchange="NASDAQ", research_role="core", horizon="5-10y",
        research_date=date(2026, 9, 18), data_cutoff=date(2026, 9, 18),
        framework_ref="common-stock@1.0.0",
    )
    assert scope.framework_ref == "common-stock@1.0.0"
    ev = _evidence()
    assert EvidenceItem.model_validate_json(ev.model_dump_json()) == ev


def test_valid_proposal_passes():
    validate_proposal(_proposal(), framework=FRAMEWORK, evidence_ids={"ev_001"}, data_cutoff=CUTOFF)


def test_score_must_be_on_half_step():
    with pytest.raises(ProposalError, match="step"):
        validate_proposal(_proposal(proposed_score=7.3), framework=FRAMEWORK,
                          evidence_ids={"ev_001"}, data_cutoff=CUTOFF)


def test_unknown_evidence_rejected():
    with pytest.raises(ProposalError, match="ev_999"):
        validate_proposal(_proposal(evidence_ids=["ev_999"]), framework=FRAMEWORK,
                          evidence_ids={"ev_001"}, data_cutoff=CUTOFF)


def test_unknown_factor_rejected():
    with pytest.raises(ProposalError):
        validate_proposal(_proposal(factor="vibes"), framework=FRAMEWORK,
                          evidence_ids={"ev_001"}, data_cutoff=CUTOFF)


def test_proposal_after_cutoff_rejected():
    with pytest.raises(ProposalError, match="cutoff"):
        validate_proposal(_proposal(as_of_date=date(2026, 9, 19)), framework=FRAMEWORK,
                          evidence_ids={"ev_001"}, data_cutoff=CUTOFF)


def test_empty_rationale_rejected():
    with pytest.raises(ProposalError):
        validate_proposal(_proposal(rationale="  "), framework=FRAMEWORK,
                          evidence_ids={"ev_001"}, data_cutoff=CUTOFF)


def test_evidence_after_cutoff_rejected():
    with pytest.raises(ProposalError, match="cutoff"):
        validate_proposal(_proposal(), framework=FRAMEWORK,
                          evidence_ids={"ev_001"}, data_cutoff=date(2026, 8, 31))
```

Note: the last test passes an evidence set whose item was published after the cutoff — the validator receives `evidence_dates: dict[str, date]` rather than bare ids so it can check this. Adjust signature: `validate_proposal(p, *, framework, evidence: dict[str, date], data_cutoff)`. Update the earlier tests to pass `evidence={"ev_001": date(2026, 9, 1)}`.

- [ ] **Step 2: Implement `schemas.py`**

```python
"""Core domain schemas for research runs (M1 subset)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from fathomark_core.framework import Framework


class ProposalError(ValueError):
    """Raised when a FactorProposal violates the scoring contract."""


class ScopeSnapshot(BaseModel):
    model_config = {"frozen": True}

    symbol: str
    exchange: str
    research_role: Literal["core", "offensive", "tactical"]
    horizon: str
    research_date: date
    data_cutoff: date
    framework_ref: str


class EvidenceItem(BaseModel):
    model_config = {"frozen": True}

    id: str
    source_name: str
    source_class: Literal["market_data", "filings", "consensus", "news", "ir", "other"]
    url: str | None
    published_date: date
    data_period_end: date | None
    accessed_at: datetime
    grade: Literal["A", "B", "C"]
    content_hash: str
    excerpt: str | None = None


class MetricObservation(BaseModel):
    model_config = {"frozen": True}

    metric: str
    value: float
    unit: str
    currency: str | None = None
    basis: str
    formula: str | None = None
    data_date: date
    evidence_id: str


class FactorProposal(BaseModel):
    model_config = {"frozen": True}

    factor: str
    proposed_score: float
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low", "insufficient"]
    missing_data: list[str] = Field(default_factory=list)
    as_of_date: date


def validate_proposal(
    proposal: FactorProposal,
    *,
    framework: Framework,
    evidence: dict[str, date],
    data_cutoff: date,
) -> None:
    scale = framework.scale
    if proposal.factor not in framework.factors:
        raise ProposalError(f"unknown factor: {proposal.factor}")
    steps = round((proposal.proposed_score - scale.min) / scale.step)
    snapped = scale.min + steps * scale.step
    if abs(proposal.proposed_score - snapped) > 1e-9 or not (scale.min <= proposal.proposed_score <= scale.max):
        raise ProposalError(
            f"score {proposal.proposed_score} violates scale [{scale.min}, {scale.max}] step {scale.step}"
        )
    if not proposal.rationale.strip():
        raise ProposalError("rationale must not be empty")
    if proposal.as_of_date > data_cutoff:
        raise ProposalError(f"proposal as_of_date {proposal.as_of_date} beyond cutoff {data_cutoff}")
    for ev_id in proposal.evidence_ids + proposal.counter_evidence_ids:
        if ev_id not in evidence:
            raise ProposalError(f"unknown evidence id: {ev_id}")
        if evidence[ev_id] > data_cutoff:
            raise ProposalError(f"evidence {ev_id} published after cutoff {data_cutoff}")
```

- [ ] **Step 3: Run tests, verify pass**

Run: `uv run pytest packages/core/tests/test_schemas.py -v`
Expected: 8 PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/fathomark_core/schemas.py packages/core/tests/test_schemas.py
git commit -m "feat(core): domain schemas and factor proposal validation"
```

---

### Task 5: Lens scoring, rating spectrum, tactical state

**Files:**
- Create: `packages/core/src/fathomark_core/scoring.py`
- Test: `packages/core/tests/test_scoring.py`

**Interfaces:**
- Consumes: `Framework` (Task 3).
- Produces:
  - `LensResult(lens: str, total: float | None, rating: str, tactical_state: str | None, vetoed: bool, veto_reasons: list[str], flagged: bool)`
  - `weighted_total(framework: Framework, lens: str, scores: dict[str, float]) -> float` — `round(Σ score×weight × 10, 2)`
  - `rating_for_total(framework: Framework, total: float) -> str`
  - `tactical_state_for_total(framework: Framework, total: float) -> str`

- [ ] **Step 1: Write failing tests (incl. ADBE golden)**

```python
# packages/core/tests/test_scoring.py
from pathlib import Path

import pytest

from fathomark_core.framework import load_framework
from fathomark_core.scoring import rating_for_total, tactical_state_for_total, weighted_total

FRAMEWORK = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml")

# ADBE 长期核心仓研究 2026-09-03: core lens total 85.75 -> A+
ADBE_SCORES = {
    "business_moat": 9.0, "financial_health": 9.5, "governance": 7.5,
    "policy_risk": 6.5, "growth_sustainability": 7.5, "valuation": 10.0,
    "earnings_quality": 10.0, "trend_momentum": 7.0, "liquidity": 10.0,
    "volatility_downside": 4.0, "catalyst_window": 0.0,
}


def test_adbe_core_total_reproduces_report():
    assert weighted_total(FRAMEWORK, "core", ADBE_SCORES) == 85.75


def test_missing_factor_rejected():
    with pytest.raises(KeyError):
        weighted_total(FRAMEWORK, "core", {k: v for k, v in ADBE_SCORES.items() if k != "valuation"})


@pytest.mark.parametrize(
    "total,grade",
    [(100.0, "S"), (90.0, "S"), (89.99, "A+"), (85.0, "A+"), (84.5, "A"),
     (80.0, "A"), (79.5, "B+"), (75.0, "B+"), (74.5, "B"), (70.0, "B"),
     (69.5, "B-"), (65.0, "B-"), (64.5, "C"), (60.0, "C"), (59.5, "D"), (0.0, "D")],
)
def test_rating_spectrum_boundaries(total, grade):
    assert rating_for_total(FRAMEWORK, total) == grade


@pytest.mark.parametrize("total,state", [(80.0, "T1"), (79.5, "T2"), (65.0, "T2"), (64.5, "T3"), (0.0, "T3")])
def test_tactical_state_boundaries(total, state):
    assert tactical_state_for_total(FRAMEWORK, total) == state
```

Run: `uv run pytest packages/core/tests/test_scoring.py -v` → FAIL (module missing).

- [ ] **Step 2: Implement `scoring.py`**

```python
"""Deterministic lens scoring and rating mapping."""

from pydantic import BaseModel

from fathomark_core.framework import Framework


class LensResult(BaseModel):
    model_config = {"frozen": True}

    lens: str
    total: float | None          # None when vetoed/NR — never fabricate a number
    rating: str                  # spectrum grade, or "X" / "NR"
    tactical_state: str | None = None
    vetoed: bool = False
    veto_reasons: list[str] = []
    flagged: bool = False        # policy_risk veto on tactical lens


def weighted_total(framework: Framework, lens: str, scores: dict[str, float]) -> float:
    weights = framework.lenses[lens]
    missing = set(weights) - set(scores)
    if missing:
        raise KeyError(f"missing factor scores: {sorted(missing)}")
    return round(sum(scores[f] * w for f, w in weights.items()) * 10, 2)


def _band_for(bands, total: float, label: str) -> str:
    for band in bands:
        if band.min <= total < band.max_exclusive:
            return band.grade if label == "rating" else band.state
    raise ValueError(f"total {total} outside all {label} bands")


def rating_for_total(framework: Framework, total: float) -> str:
    return _band_for(framework.ratings, total, "rating")


def tactical_state_for_total(framework: Framework, total: float) -> str:
    return _band_for(framework.tactical_states, total, "tactical")
```

- [ ] **Step 3: Run tests, verify pass**

Run: `uv run pytest packages/core/tests/test_scoring.py -v`
Expected: all PASS (ADBE golden included).

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/fathomark_core/scoring.py packages/core/tests/test_scoring.py
git commit -m "feat(core): weighted lens totals, rating spectrum, tactical states"
```

---

### Task 6: Veto and NR engine

**Files:**
- Create: `packages/core/src/fathomark_core/veto.py`
- Test: `packages/core/tests/test_veto.py`

**Interfaces:**
- Consumes: `Framework` (Task 3), `LensResult`, `weighted_total`, `rating_for_total`, `tactical_state_for_total` (Task 5).
- Produces:
  - `evaluate_lens(framework: Framework, lens: str, scores: dict[str, float], confidence: str) -> LensResult` — applies NR (confidence `insufficient`), veto rules (→ rating `X`, total preserved for audit), policy_risk tactical flag, tactical state on the tactical lens.
  - `overall_confidence(proposals_confidence: list[str]) -> str` — minimum across factors (weakest link, framework §4.5 rule against dilution).

- [ ] **Step 1: Write failing tests**

```python
# packages/core/tests/test_veto.py
from pathlib import Path

from fathomark_core.framework import load_framework
from fathomark_core.veto import evaluate_lens, overall_confidence

FRAMEWORK = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml")

HIGH = {f.id: 9.0 for f in FRAMEWORK.raw_factors}


def test_high_scores_no_veto():
    r = evaluate_lens(FRAMEWORK, "core", HIGH, confidence="high")
    assert r.rating == "S" and r.total == 90.0 and not r.vetoed


def test_financial_health_veto_beats_high_total():
    scores = HIGH | {"financial_health": 2.5}
    r = evaluate_lens(FRAMEWORK, "core", scores, confidence="high")
    assert r.rating == "X" and r.vetoed
    assert any("financial_health" in reason for reason in r.veto_reasons)


def test_governance_veto_applies_to_tactical():
    r = evaluate_lens(FRAMEWORK, "tactical", HIGH | {"governance": 2.0}, confidence="high")
    assert r.vetoed and r.rating == "X"


def test_policy_risk_flags_but_does_not_veto_tactical():
    r = evaluate_lens(FRAMEWORK, "tactical", HIGH | {"policy_risk": 1.0}, confidence="high")
    assert not r.vetoed and r.flagged and r.rating == "S"


def test_policy_risk_vetoes_core_and_offensive():
    for lens in ("core", "offensive"):
        r = evaluate_lens(FRAMEWORK, lens, HIGH | {"policy_risk": 2.5}, confidence="high")
        assert r.vetoed and r.rating == "X"


def test_insufficient_confidence_forces_nr():
    r = evaluate_lens(FRAMEWORK, "core", HIGH, confidence="insufficient")
    assert r.rating == "NR" and r.total is None


def test_tactical_state_only_on_tactical_lens():
    r = evaluate_lens(FRAMEWORK, "tactical", HIGH, confidence="high")
    assert r.tactical_state == "T1"
    r2 = evaluate_lens(FRAMEWORK, "core", HIGH, confidence="high")
    assert r2.tactical_state is None


def test_overall_confidence_is_weakest_link():
    assert overall_confidence(["high", "medium", "high"]) == "medium"
    assert overall_confidence(["low", "insufficient", "high"]) == "insufficient"
    assert overall_confidence(["high"]) == "high"
```

Run → FAIL.

- [ ] **Step 2: Implement `veto.py`**

```python
"""Veto, NR, and confidence aggregation rules."""

from fathomark_core.framework import Framework
from fathomark_core.scoring import (
    LensResult,
    rating_for_total,
    tactical_state_for_total,
    weighted_total,
)

_CONFIDENCE_ORDER = ["insufficient", "low", "medium", "high"]


def overall_confidence(proposals_confidence: list[str]) -> str:
    if not proposals_confidence:
        return "insufficient"
    return min(proposals_confidence, key=_CONFIDENCE_ORDER.index)


def evaluate_lens(
    framework: Framework,
    lens: str,
    scores: dict[str, float],
    confidence: str,
) -> LensResult:
    conf = framework.confidence_levels.get(confidence)
    if conf is None:
        raise ValueError(f"unknown confidence level: {confidence}")
    if conf.get("forces_nr"):
        return LensResult(lens=lens, total=None, rating="NR")

    total = weighted_total(framework, lens, scores)
    veto_reasons = [
        f"{rule.factor} {scores[rule.factor]} below {rule.below}"
        for rule in framework.veto_rules
        if lens in rule.applies_to and scores[rule.factor] < rule.below
    ]
    flagged = any(
        lens not in rule.applies_to and scores[rule.factor] < rule.below
        for rule in framework.veto_rules
    )
    vetoed = bool(veto_reasons)
    return LensResult(
        lens=lens,
        total=total,
        rating="X" if vetoed else rating_for_total(framework, total),
        tactical_state=tactical_state_for_total(framework, total) if lens == "tactical" and not vetoed else None,
        vetoed=vetoed,
        veto_reasons=veto_reasons,
        flagged=flagged and not vetoed,
    )
```

- [ ] **Step 3: Run tests, verify pass**

Run: `uv run pytest packages/core/tests/test_veto.py -v` → 8 PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/fathomark_core/veto.py packages/core/tests/test_veto.py
git commit -m "feat(core): veto, NR, and weakest-link confidence rules"
```

---

### Task 7: ScoreSnapshot and `evaluate()` pipeline + property tests

**Files:**
- Create: `packages/core/src/fathomark_core/snapshot.py`
- Modify: `packages/core/src/fathomark_core/__init__.py`
- Test: `packages/core/tests/test_snapshot.py`, `packages/core/tests/test_properties.py`

**Interfaces:**
- Consumes: everything from Tasks 3–6.
- Produces:
  - `ScoreSnapshot(scope: ScopeSnapshot, lens_results: dict[str, LensResult], factor_scores: dict[str, float], overall_confidence: str, content_hash: str)` — `content_hash` = sha256 of canonical JSON of (scope, factor_scores) so identical inputs always yield identical hashes.
  - `evaluate(*, framework: Framework, scope: ScopeSnapshot, evidence: list[EvidenceItem], proposals: list[FactorProposal]) -> ScoreSnapshot` — validates every proposal (Task 4), requires exactly one proposal per factor, computes all three lens results.
  - Re-exports in `__init__.py`: `load_framework`, `evaluate`, `ScoreSnapshot`, `ScopeSnapshot`, `EvidenceItem`, `MetricObservation`, `FactorProposal`.

- [ ] **Step 1: Write failing tests**

```python
# packages/core/tests/test_snapshot.py
from datetime import date, datetime
from pathlib import Path

import pytest

from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot

FRAMEWORK = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml")
DAY = date(2026, 9, 18)

SCOPE = ScopeSnapshot(
    symbol="ADBE", exchange="NASDAQ", research_role="core", horizon="5-10y",
    research_date=DAY, data_cutoff=DAY, framework_ref="common-stock@1.0.0",
)

ADBE = {
    "business_moat": 9.0, "financial_health": 9.5, "governance": 7.5,
    "policy_risk": 6.5, "growth_sustainability": 7.5, "valuation": 10.0,
    "earnings_quality": 10.0, "trend_momentum": 7.0, "liquidity": 10.0,
    "volatility_downside": 4.0, "catalyst_window": 0.0,
}


def _evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"ev_{i:03d}", source_name="fixture", source_class="filings",
            url=None, published_date=date(2026, 9, 1), data_period_end=None,
            accessed_at=datetime(2026, 9, 18), grade="A", content_hash=f"sha256:{i}",
        )
        for i in range(1, 12)
    ]


def _proposals(scores=None) -> list[FactorProposal]:
    scores = scores or ADBE
    return [
        FactorProposal(
            factor=factor, proposed_score=score, rationale=f"依据 {factor}",
            evidence_ids=[f"ev_{i:03d}"], counter_evidence_ids=[],
            confidence="high", missing_data=[], as_of_date=DAY,
        )
        for i, (factor, score) in enumerate(scores.items(), start=1)
    ]


def test_evaluate_adbe_reproduces_report():
    snap = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals())
    assert snap.lens_results["core"].total == 85.75
    assert snap.lens_results["core"].rating == "A+"
    assert snap.overall_confidence == "high"
    assert snap.lens_results["tactical"].tactical_state is not None


def test_duplicate_factor_proposal_rejected():
    dup = _proposals() + [_proposals()[0]]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=dup)


def test_missing_factor_proposal_rejected():
    with pytest.raises(ValueError, match="missing"):
        evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals()[:-1])


def test_identical_inputs_identical_hash():
    a = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals())
    b = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals())
    assert a.content_hash == b.content_hash
    assert a == b


def test_different_inputs_different_hash():
    a = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals())
    changed = ADBE | {"valuation": 9.5}
    b = evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=_evidence(), proposals=_proposals(changed))
    assert a.content_hash != b.content_hash
```

```python
# packages/core/tests/test_properties.py
from datetime import date, datetime
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot

FRAMEWORK = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml")
DAY = date(2026, 9, 18)
SCOPE = ScopeSnapshot(
    symbol="T", exchange="NYSE", research_role="core", horizon="1y",
    research_date=DAY, data_cutoff=DAY, framework_ref="common-stock@1.0.0",
)

score_dicts = st.fixed_dictionaries(
    {f.id: st.floats(min_value=0, max_value=10).map(lambda x: round(x * 2) / 2)
     for f in FRAMEWORK.raw_factors}
)


def _run(scores):
    evidence = [
        EvidenceItem(
            id=f"ev_{i:03d}", source_name="fixture", source_class="filings",
            url=None, published_date=DAY, data_period_end=None,
            accessed_at=datetime(2026, 9, 18), grade="A", content_hash=str(i),
        )
        for i in range(1, 12)
    ]
    proposals = [
        FactorProposal(
            factor=f, proposed_score=s, rationale="r", evidence_ids=[f"ev_{i:03d}"],
            counter_evidence_ids=[], confidence="high", missing_data=[], as_of_date=DAY,
        )
        for i, (f, s) in enumerate(scores.items(), start=1)
    ]
    return evaluate(framework=FRAMEWORK, scope=SCOPE, evidence=evidence, proposals=proposals)


@given(scores=score_dicts)
@settings(max_examples=200, deadline=None)
def test_determinism(scores):
    assert _run(scores) == _run(scores)


@given(scores=score_dicts)
@settings(max_examples=200, deadline=None)
def test_totals_in_range_and_rating_consistent(scores):
    snap = _run(scores)
    for result in snap.lens_results.values():
        if result.total is not None:
            assert 0.0 <= result.total <= 100.0
        assert result.rating in {"S", "A+", "A", "B+", "B", "B-", "C", "D", "X", "NR"}
```

Run: `uv run pytest packages/core/tests/test_snapshot.py packages/core/tests/test_properties.py -v` → FAIL.

- [ ] **Step 2: Implement `snapshot.py`**

```python
"""ScoreSnapshot assembly and the deterministic evaluate() pipeline."""

import hashlib
import json

from pydantic import BaseModel

from fathomark_core.framework import Framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    ScopeSnapshot,
    validate_proposal,
)
from fathomark_core.scoring import LensResult
from fathomark_core.veto import evaluate_lens, overall_confidence


class ScoreSnapshot(BaseModel):
    model_config = {"frozen": True}

    scope: ScopeSnapshot
    lens_results: dict[str, LensResult]
    factor_scores: dict[str, float]
    overall_confidence: str
    content_hash: str


def _content_hash(scope: ScopeSnapshot, factor_scores: dict[str, float]) -> str:
    canonical = json.dumps(
        {"scope": json.loads(scope.model_dump_json()), "factor_scores": factor_scores},
        sort_keys=True,
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate(
    *,
    framework: Framework,
    scope: ScopeSnapshot,
    evidence: list[EvidenceItem],
    proposals: list[FactorProposal],
) -> ScoreSnapshot:
    if scope.framework_ref != framework.framework_ref:
        raise ValueError(f"scope framework {scope.framework_ref} != loaded {framework.framework_ref}")
    evidence_index = {ev.id: ev.published_date for ev in evidence}
    seen: set[str] = set()
    for p in proposals:
        if p.factor in seen:
            raise ValueError(f"duplicate proposal for factor {p.factor}")
        seen.add(p.factor)
        validate_proposal(p, framework=framework, evidence=evidence_index, data_cutoff=scope.data_cutoff)
    missing = set(framework.factors) - seen
    if missing:
        raise ValueError(f"missing proposals for factors: {sorted(missing)}")

    scores = {p.factor: p.proposed_score for p in proposals}
    confidence = overall_confidence([p.confidence for p in proposals])
    lens_results = {
        lens: evaluate_lens(framework, lens, scores, confidence)
        for lens in framework.lenses
    }
    return ScoreSnapshot(
        scope=scope,
        lens_results=lens_results,
        factor_scores=scores,
        overall_confidence=confidence,
        content_hash=_content_hash(scope, scores),
    )
```

Update `__init__.py`:

```python
"""Fathomark deterministic scoring core."""

from fathomark_core.framework import Framework, FrameworkValidationError, load_framework
from fathomark_core.schemas import (
    EvidenceItem,
    FactorProposal,
    MetricObservation,
    ScopeSnapshot,
)
from fathomark_core.snapshot import ScoreSnapshot, evaluate

__all__ = [
    "EvidenceItem",
    "FactorProposal",
    "Framework",
    "FrameworkValidationError",
    "MetricObservation",
    "ScopeSnapshot",
    "ScoreSnapshot",
    "evaluate",
    "load_framework",
]
```

- [ ] **Step 3: Run tests, verify pass**

Run: `uv run pytest packages/core/tests -v`
Expected: all PASS including 2 hypothesis property tests.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/fathomark_core/snapshot.py packages/core/src/fathomark_core/__init__.py packages/core/tests/test_snapshot.py packages/core/tests/test_properties.py
git commit -m "feat(core): evaluate() pipeline, ScoreSnapshot, property tests"
```

---

### Task 8: Reverse DCF solver + sensitivity classification

**Files:**
- Create: `packages/core/src/fathomark_core/valuation.py`
- Test: `packages/core/tests/test_valuation.py`

**Interfaces:**
- Consumes: `ValuationConfig` (Task 3).
- Produces:
  - `two_stage_ev(fcff0: float, g: float, wacc: float, terminal_growth: float, years: int) -> float`
  - `solve_implied_growth(ev_market: float, fcff0: float, wacc: float, terminal_growth: float, cfg: ValuationConfig) -> float | None` — bisection on `cfg.root_interval`; `None` if no sign change.
  - `SensitivityResult(base_g: float | None, min_g: float | None, max_g: float | None, width: float | None, valid_scenarios: int, classification: Literal["robust","fragile","invalid"])`
  - `run_sensitivity(ev_market, fcff0, wacc, terminal_growth, cfg) -> SensitivityResult`

- [ ] **Step 1: Write failing tests**

Anchor: ADBE §12.2 — EV ≈ $1115亿, FCFF0 ≈ $102.8亿, WACC ≈ 9.6%, g_T = 3% → implied g ≈ −5%.

```python
# packages/core/tests/test_valuation.py
from pathlib import Path

import pytest

from fathomark_core.framework import load_framework
from fathomark_core.valuation import (
    run_sensitivity,
    solve_implied_growth,
    two_stage_ev,
)

CFG = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml").valuation


def test_two_stage_ev_terminal_value():
    # g=0: EV = sum of discounted FCFF + discounted perpetuity
    ev = two_stage_ev(100.0, 0.0, 0.10, 0.03, 5)
    expected = sum(100.0 / 1.1**t for t in range(1, 6)) + (100.0 * 1.03 / 0.07) / 1.1**5
    assert ev == pytest.approx(expected)


def test_adbe_implied_growth_approx_minus_5pct():
    g = solve_implied_growth(ev_market=111.5e9, fcff0=10.28e9, wacc=0.096, terminal_growth=0.03, cfg=CFG)
    assert g == pytest.approx(-0.05, abs=0.01)


def test_solver_returns_none_when_no_root():
    # EV far above anything reachable in [-20%, 100%] growth
    assert solve_implied_growth(ev_market=1e15, fcff0=1.0, wacc=0.10, terminal_growth=0.03, cfg=CFG) is None


def test_sensitivity_adbe_is_classified():
    r = run_sensitivity(ev_market=111.5e9, fcff0=10.28e9, wacc=0.096, terminal_growth=0.03, cfg=CFG)
    assert r.valid_scenarios == 9
    assert r.classification in {"robust", "fragile"}
    assert r.min_g <= r.base_g <= r.max_g
    assert r.width == pytest.approx(r.max_g - r.min_g)


def test_sensitivity_invalid_when_too_few_valid_scenarios():
    # wacc - 1pp == g_T + 0.5pp violates wacc > g_T in some cells only with crafted numbers
    r = run_sensitivity(ev_market=100.0, fcff0=10.0, wacc=0.04, terminal_growth=0.03, cfg=CFG)
    assert r.classification == "invalid"
    assert r.valid_scenarios < CFG.sensitivity.min_valid_scenarios
```

Run → FAIL.

- [ ] **Step 2: Implement `valuation.py`**

```python
"""Deterministic reverse DCF and sensitivity analysis (framework §B valuation rules)."""

from typing import Literal

from pydantic import BaseModel

from fathomark_core.framework import ValuationConfig


class SensitivityResult(BaseModel):
    model_config = {"frozen": True}

    base_g: float | None
    min_g: float | None
    max_g: float | None
    width: float | None
    valid_scenarios: int
    classification: Literal["robust", "fragile", "invalid"]


def two_stage_ev(fcff0: float, g: float, wacc: float, terminal_growth: float, years: int) -> float:
    pv = sum(fcff0 * (1 + g) ** t / (1 + wacc) ** t for t in range(1, years + 1))
    terminal = fcff0 * (1 + g) ** years * (1 + terminal_growth) / (wacc - terminal_growth)
    return pv + terminal / (1 + wacc) ** years


def solve_implied_growth(
    ev_market: float,
    fcff0: float,
    wacc: float,
    terminal_growth: float,
    cfg: ValuationConfig,
) -> float | None:
    if wacc <= terminal_growth or fcff0 <= 0:
        return None
    lo, hi = cfg.root_interval
    f_lo = two_stage_ev(fcff0, lo, wacc, terminal_growth, cfg.horizon_years) - ev_market
    f_hi = two_stage_ev(fcff0, hi, wacc, terminal_growth, cfg.horizon_years) - ev_market
    if f_lo > 0 or f_hi < 0:
        return None  # no root in interval — never extrapolate
    for _ in range(200):
        mid = (lo + hi) / 2
        if two_stage_ev(fcff0, mid, wacc, terminal_growth, cfg.horizon_years) < ev_market:
            lo = mid
        else:
            hi = mid
        if hi - lo < cfg.solver_tolerance:
            break
    return (lo + hi) / 2


def run_sensitivity(
    ev_market: float,
    fcff0: float,
    wacc: float,
    terminal_growth: float,
    cfg: ValuationConfig,
) -> SensitivityResult:
    sens = cfg.sensitivity
    base_g = solve_implied_growth(ev_market, fcff0, wacc, terminal_growth, cfg)
    solutions: list[float] = []
    unsolvable_valid = False
    for dw in sens.wacc_offsets:
        for dg in sens.terminal_growth_offsets:
            w, gt = wacc + dw, terminal_growth + dg
            if w <= gt:
                continue  # not economically valid, excluded from the matrix
            g = solve_implied_growth(ev_market, fcff0, w, gt, cfg)
            if g is None:
                unsolvable_valid = True
            else:
                solutions.append(g)

    valid = len(solutions)
    if valid == 0:
        return SensitivityResult(
            base_g=base_g, min_g=None, max_g=None, width=None,
            valid_scenarios=0, classification="invalid",
        )
    lo, hi = min(solutions), max(solutions)
    width = hi - lo
    if (
        unsolvable_valid
        or valid < sens.min_valid_scenarios
        or width > sens.fragile_max_width
    ):
        classification = "invalid"
    elif width <= sens.robust_max_width:
        classification = "robust"
    else:
        classification = "fragile"
    return SensitivityResult(
        base_g=base_g, min_g=lo, max_g=hi, width=width,
        valid_scenarios=valid, classification=classification,
    )
```

Note: the "deviation spans both `<-10%` and `≥10%`" invalid condition requires `g_expected`, so it is enforced in Task 9's `score_valuation`, not here.

- [ ] **Step 3: Run tests, verify pass**

Run: `uv run pytest packages/core/tests/test_valuation.py -v` → 5 PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/fathomark_core/valuation.py packages/core/tests/test_valuation.py
git commit -m "feat(core): reverse DCF solver with sensitivity classification"
```

---

### Task 9: Margin-convergence model, deviation scoring, backup PEG

**Files:**
- Modify: `packages/core/src/fathomark_core/valuation.py`
- Test: `packages/core/tests/test_valuation_scoring.py`

**Interfaces:**
- Consumes: Task 8 functions.
- Produces:
  - `margin_convergence_ev(revenue0, margin0, margin_t, g, wacc, terminal_growth, years) -> float`
  - `solve_implied_growth_margin_model(ev_market, revenue0, margin0, margin_t, wacc, terminal_growth, cfg) -> float | None`
  - `deviation(g_implied: float, g_expected: float, denominator_floor: float) -> float`
  - `score_deviation(d: float, cfg: ValuationConfig) -> float` — anchor table incl. linear interp band rounded to nearest 0.5.
  - `score_backup_peg(peg: float, cfg: ValuationConfig) -> float`
  - `ValuationScore(score: float | None, method: Literal["reverse_dcf","reverse_dcf_margin","backup_peg"], implied_growth: float | None, sensitivity: SensitivityResult | None, switched_to_backup: bool, switch_reason: str | None)`
  - `score_valuation(*, cfg, ev_market, fcff0, wacc, terminal_growth, g_expected, backup_peg=None, revenue0=None, margin0=None, margin_t=None) -> ValuationScore` — runs reverse DCF (or margin model when `fcff0 <= 0` and margin inputs given), enforces cross-side deviation invalid rule, switches to backup PEG on invalid; raises `ValueError` if backup needed but `backup_peg` missing.

- [ ] **Step 1: Write failing tests**

```python
# packages/core/tests/test_valuation_scoring.py
from pathlib import Path

import pytest

from fathomark_core.framework import load_framework
from fathomark_core.valuation import (
    deviation,
    score_backup_peg,
    score_deviation,
    score_valuation,
    solve_implied_growth_margin_model,
)

CFG = load_framework(Path(__file__).parents[3] / "frameworks" / "common-stock.yaml").valuation


@pytest.mark.parametrize(
    "d,expected",
    [(0.35, 0.0), (0.30, 0.0), (0.29, 4.0), (0.10, 4.0), (0.09, 7.0),
     (-0.10, 7.5), (-0.15, 8.5), (-0.20, 9.5), (-0.21, 10.0)],
)
def test_deviation_anchor_bands(d, expected):
    assert score_deviation(d, CFG) == expected


def test_deviation_denominator_floor():
    # g_expected near zero must not blow up
    assert deviation(0.01, 0.001, 0.05) == pytest.approx((0.01 - 0.001) / 0.05)


@pytest.mark.parametrize("peg,expected", [(3.5, 0.0), (3.0, 4.0), (2.5, 4.0), (2.0, 4.0), (1.5, 7.0), (1.0, 7.0), (0.9, 10.0)])
def test_backup_peg_bands(peg, expected):
    assert score_backup_peg(peg, CFG) == expected


def test_adbe_scores_10():
    v = score_valuation(
        cfg=CFG, ev_market=111.5e9, fcff0=10.28e9, wacc=0.096,
        terminal_growth=0.03, g_expected=0.08,
    )
    assert v.method == "reverse_dcf"
    assert not v.switched_to_backup
    assert v.implied_growth == pytest.approx(-0.05, abs=0.01)
    assert v.score == 10.0  # deviation ≈ ( -0.05 - 0.08 ) / 0.08 ≈ -1.6 < -0.20


def test_no_root_switches_to_backup():
    v = score_valuation(
        cfg=CFG, ev_market=1e15, fcff0=1.0, wacc=0.10,
        terminal_growth=0.03, g_expected=0.10, backup_peg=1.5,
    )
    assert v.switched_to_backup and v.method == "backup_peg" and v.score == 7.0


def test_no_backup_peg_when_required_raises():
    with pytest.raises(ValueError, match="backup"):
        score_valuation(cfg=CFG, ev_market=1e15, fcff0=1.0, wacc=0.10,
                        terminal_growth=0.03, g_expected=0.10)


def test_margin_model_solves_positive_growth():
    # company with negative current margin converging to 25%
    g = solve_implied_growth_margin_model(
        ev_market=50e9, revenue0=5e9, margin0=-0.10, margin_t=0.25,
        wacc=0.11, terminal_growth=0.03, cfg=CFG,
    )
    assert g is not None and -0.20 <= g <= 1.00


def test_cross_side_deviation_forces_invalid_and_backup():
    # craft: valid base but sensitivity implies deviation on both sides of ±10%
    v = score_valuation(
        cfg=CFG, ev_market=111.5e9, fcff0=10.28e9, wacc=0.096,
        terminal_growth=0.03, g_expected=0.0,  # floor 0.05 makes deviation huge
        backup_peg=2.5,
    )
    assert v.switched_to_backup and v.score == 4.0
```

Run → FAIL.

- [ ] **Step 2: Extend `valuation.py`**

Append to `packages/core/src/fathomark_core/valuation.py`:

```python
def margin_convergence_ev(
    revenue0: float, margin0: float, margin_t: float,
    g: float, wacc: float, terminal_growth: float, years: int,
) -> float:
    pv = 0.0
    for t in range(1, years + 1):
        revenue_t = revenue0 * (1 + g) ** t
        margin = margin0 + (margin_t - margin0) * t / years
        pv += revenue_t * margin / (1 + wacc) ** t
    revenue_n = revenue0 * (1 + g) ** years
    terminal = revenue_n * margin_t * (1 + terminal_growth) / (wacc - terminal_growth)
    return pv + terminal / (1 + wacc) ** years


def solve_implied_growth_margin_model(
    ev_market: float, revenue0: float, margin0: float, margin_t: float,
    wacc: float, terminal_growth: float, cfg: ValuationConfig,
) -> float | None:
    if wacc <= terminal_growth or revenue0 <= 0:
        return None
    lo, hi = cfg.root_interval
    f = lambda g: margin_convergence_ev(revenue0, margin0, margin_t, g, wacc, terminal_growth, cfg.horizon_years)
    if f(lo) > ev_market or f(hi) < ev_market:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < ev_market:
            lo = mid
        else:
            hi = mid
        if hi - lo < cfg.solver_tolerance:
            break
    return (lo + hi) / 2


def deviation(g_implied: float, g_expected: float, denominator_floor: float) -> float:
    return (g_implied - g_expected) / max(abs(g_expected), denominator_floor)


def _round_half(x: float) -> float:
    return round(x * 2) / 2


def score_deviation(d: float, cfg: ValuationConfig) -> float:
    for anchor in cfg.deviation["anchors"]:
        lo = anchor["min"] if anchor["min"] is not None else float("-inf")
        hi = anchor["max_exclusive"] if anchor["max_exclusive"] is not None else float("inf")
        if lo <= d < hi:
            if anchor.get("score") is not None:
                return anchor["score"]
            # linear interpolation band: score_low at hi edge, score_high at lo edge
            frac = (hi - d) / (hi - lo)
            return _round_half(anchor["score_low"] + frac * (anchor["score_high"] - anchor["score_low"]))
    raise ValueError(f"deviation {d} outside anchor table")


def score_backup_peg(peg: float, cfg: ValuationConfig) -> float:
    if peg <= 0:
        raise ValueError("PEG must be positive; use industry adapter methods otherwise")
    for anchor in cfg.backup_peg_anchors:
        lo = anchor["min"] if anchor["min"] is not None else float("-inf")
        hi = anchor["max_exclusive"] if anchor["max_exclusive"] is not None else float("inf")
        if lo <= peg < hi:
            return anchor["score"]
    raise ValueError(f"peg {peg} outside anchor table")


class ValuationScore(BaseModel):
    model_config = {"frozen": True}

    score: float | None
    method: Literal["reverse_dcf", "reverse_dcf_margin", "backup_peg"]
    implied_growth: float | None
    sensitivity: SensitivityResult | None
    switched_to_backup: bool
    switch_reason: str | None


def _backup(peg: float | None, cfg: ValuationConfig, reason: str) -> "ValuationScore":
    if peg is None:
        raise ValueError(f"backup valuation path required ({reason}) but no backup_peg provided")
    return ValuationScore(
        score=score_backup_peg(peg, cfg), method="backup_peg",
        implied_growth=None, sensitivity=None, switched_to_backup=True, switch_reason=reason,
    )


def score_valuation(
    *,
    cfg: ValuationConfig,
    ev_market: float,
    fcff0: float,
    wacc: float,
    terminal_growth: float,
    g_expected: float,
    backup_peg: float | None = None,
    revenue0: float | None = None,
    margin0: float | None = None,
    margin_t: float | None = None,
) -> ValuationScore:
    use_margin_model = fcff0 <= 0
    if use_margin_model:
        if revenue0 is None or margin0 is None or margin_t is None:
            raise ValueError("margin model requires revenue0, margin0, margin_t")
        base_g = solve_implied_growth_margin_model(
            ev_market, revenue0, margin0, margin_t, wacc, terminal_growth, cfg
        )
        sensitivity = None  # margin-model sensitivity uses same grid; omitted in M1, noted in docs
        method: Literal["reverse_dcf", "reverse_dcf_margin", "backup_peg"] = "reverse_dcf_margin"
    else:
        sensitivity = run_sensitivity(ev_market, fcff0, wacc, terminal_growth, cfg)
        base_g = sensitivity.base_g
        method = "reverse_dcf"
        if sensitivity.classification == "invalid":
            return _backup(backup_peg, cfg, "sensitivity classification invalid")

    if base_g is None:
        return _backup(backup_peg, cfg, "no root in solver interval")

    floor = cfg.deviation["denominator_floor"]
    deviations = [deviation(g, g_expected, floor) for g in ([base_g] if sensitivity is None else
                  [sensitivity.min_g, sensitivity.max_g])]
    if any(d >= 0.10 for d in deviations) and any(d < -0.10 for d in deviations):
        return _backup(backup_peg, cfg, "sensitivity deviation spans undervalued and overvalued")

    return ValuationScore(
        score=score_deviation(deviation(base_g, g_expected, floor), cfg),
        method=method, implied_growth=base_g, sensitivity=sensitivity,
        switched_to_backup=False, switch_reason=None,
    )
```

Check the interp-band test: d=-0.15 → band [−0.20, −0.10); frac = (−0.10 − (−0.15)) / 0.10 = 0.5 → 7.5 + 0.5×2.0 = 8.5 ✓. d=−0.10 → frac=0 → 7.5 ✓ (matches spec "接近-10%取7.5分"). d=−0.20 → frac=1 → 9.5 ✓.

`test_cross_side_deviation_forces_invalid_and_backup`: g_expected=0.0 → floor 0.05. base_g ≈ −0.05 → d = −1.0. min/max span: WACC+g_T grid shifts g by several points each way; with floor 0.05, max_g (lowest wacc −1pp, lowest g_T) is well above base — for ADBE numbers max_g ≈ +0.10ish → d ≥ +0.10 possible while min d < −0.10. If the crafted test fails on numbers, adjust inputs until both sides are spanned (e.g., g_expected = −0.04 → base d = (−0.05+0.04)/0.05 = −0.2; need max_g such that d ≥ 0.10 → max_g ≥ −0.035). Keep bisection monotone note: EV strictly increasing in g given positive FCFF, so bisection is valid.

- [ ] **Step 3: Run tests, verify pass**

Run: `uv run pytest packages/core/tests/test_valuation_scoring.py -v` → all PASS (adjust crafted inputs if a scenario doesn't span both sides).

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/fathomark_core/valuation.py packages/core/tests/test_valuation_scoring.py
git commit -m "feat(core): margin-convergence model, deviation anchors, backup PEG"
```

---

### Task 10: Offline golden fixture + M1 exit check

**Files:**
- Create: `examples/fixtures/adbe_2026-09-03/input.json`
- Create: `examples/fixtures/adbe_2026-09-03/expected_snapshot.json`
- Test: `packages/core/tests/test_golden_fixture.py`
- Modify: `README.md` (M1 status note)

**Interfaces:**
- Consumes: public `evaluate()` API (Task 7).
- Produces: end-to-end proof that fixed JSON input reproduces the ADBE report numbers offline.

- [ ] **Step 1: Write fixture input JSON**

`examples/fixtures/adbe_2026-09-03/input.json`:

```json
{
  "scope": {
    "symbol": "ADBE",
    "exchange": "NASDAQ",
    "research_role": "core",
    "horizon": "5-10y",
    "research_date": "2026-09-03",
    "data_cutoff": "2026-09-03",
    "framework_ref": "common-stock@1.0.0"
  },
  "evidence": [
    {"id": "ev_001", "source_name": "Adobe Q2 FY2026 Results", "source_class": "filings",
     "url": "https://www.sec.gov/Archives/edgar/data/796343/000079634326000109/adbeex991q226.htm",
     "published_date": "2026-06-11", "data_period_end": "2026-05-29",
     "accessed_at": "2026-09-03T12:00:00", "grade": "A", "content_hash": "sha256:fixture1", "excerpt": null},
    {"id": "ev_002", "source_name": "Adobe FY2026 Q2 Form 10-Q", "source_class": "filings",
     "url": "https://www.sec.gov/Archives/edgar/data/796343/000079634326000112/adbe-20260529.htm",
     "published_date": "2026-06-15", "data_period_end": "2026-05-29",
     "accessed_at": "2026-09-03T12:00:00", "grade": "A", "content_hash": "sha256:fixture2", "excerpt": null}
  ],
  "proposals": [
    {"factor": "business_moat", "proposed_score": 9.0, "rationale": "专业创作/PDF/企业工作流转换成本极强", "evidence_ids": ["ev_001"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "financial_health", "proposed_score": 9.5, "rationale": "轻资本百亿美元OCF债务可覆盖", "evidence_ids": ["ev_002"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "governance", "proposed_score": 7.5, "rationale": "治理成熟但CEO交接扣分", "evidence_ids": ["ev_001"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "policy_risk", "proposed_score": 6.5, "rationale": "订阅和解与大型并购监管", "evidence_ids": ["ev_001"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "growth_sustainability", "proposed_score": 7.5, "rationale": "双位数增长但AI范式风险", "evidence_ids": ["ev_001"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "valuation", "proposed_score": 10.0, "rationale": "反向DCF隐含FCFF约-5%增长", "evidence_ids": ["ev_002"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "earnings_quality", "proposed_score": 10.0, "rationale": "高订阅高FCF转化极低资本开支", "evidence_ids": ["ev_002"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "trend_momentum", "proposed_score": 7.0, "rationale": "自6月低点恢复但低于52周高点", "evidence_ids": ["ev_001"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "liquidity", "proposed_score": 10.0, "rationale": "大型NASDAQ软件股流动性充分", "evidence_ids": ["ev_001"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "volatility_downside", "proposed_score": 4.0, "rationale": "一年内最大回撤约49%", "evidence_ids": ["ev_001"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"},
    {"factor": "catalyst_window", "proposed_score": 0.0, "rationale": "核心仓不依赖短期催化剂", "evidence_ids": ["ev_001"], "counter_evidence_ids": [], "confidence": "high", "missing_data": [], "as_of_date": "2026-09-03"}
  ]
}
```

- [ ] **Step 2: Write failing golden test**

```python
# packages/core/tests/test_golden_fixture.py
import json
from pathlib import Path

from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot

ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "examples" / "fixtures" / "adbe_2026-09-03" / "input.json"


def test_adbe_fixture_reproduces_offline():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = evaluate(
        framework=load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        scope=ScopeSnapshot.model_validate(data["scope"]),
        evidence=[EvidenceItem.model_validate(e) for e in data["evidence"]],
        proposals=[FactorProposal.model_validate(p) for p in data["proposals"]],
    )
    core = snap.lens_results["core"]
    assert core.total == 85.75
    assert core.rating == "A+"
    assert not core.vetoed
    assert snap.overall_confidence == "high"
```

Run → PASS (fixture only re-uses pipeline; if any failure, the pipeline has a bug — fix before proceeding).

- [ ] **Step 3: Generate expected snapshot JSON and assert against it**

Run once to generate:

```bash
uv run python -c "
import json
from pathlib import Path
from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot
root = Path('.')
data = json.loads((root/'examples/fixtures/adbe_2026-09-03/input.json').read_text())
snap = evaluate(
    framework=load_framework(root/'frameworks/common-stock.yaml'),
    scope=ScopeSnapshot.model_validate(data['scope']),
    evidence=[EvidenceItem.model_validate(e) for e in data['evidence']],
    proposals=[FactorProposal.model_validate(p) for p in data['proposals']],
)
(root/'examples/fixtures/adbe_2026-09-03/expected_snapshot.json').write_text(snap.model_dump_json(indent=2))
"
```

Then extend the golden test to compare `snap.model_dump()` against the stored JSON (review the generated file first — verify A+ / 85.75 / no veto by eye).

- [ ] **Step 4: Run full suite + verify M1 exit criteria**

Run: `uv run pytest -q && uv run ruff check packages`
Expected: all tests PASS, no lint errors. Verify manually:
- `grep -ri "openai\|anthropic\|sqlalchemy\|requests\|httpx" packages/core/src` → no matches (core has no LLM/DB/network deps).

- [ ] **Step 5: Update README status and commit**

Change README §当前状态 to note M1 core complete. Then:

```bash
git add examples packages/core/tests/test_golden_fixture.py README.md
git commit -m "test(core): ADBE golden fixture proves offline reproducibility"
```

---

## Self-Review Notes

- Spec coverage: §5–7 schemas → Tasks 4/7; §8 framework YAML → Tasks 2–3; §一 formula → Task 5; §4.7 spectrum + §4.3 tactical → Task 5; §5.1 veto + §4.5 confidence → Task 6; valuation §B (both models, sensitivity 3-tier, deviation anchors, backup PEG) → Tasks 8–9; M1 exit criteria (offline reproducible snapshot, weights/ratings tested, no LLM/DB/network in core) → Task 10. M1 items deferred to later milestones by design: storage/state machine (M2), agents (M3).
- Known gaps accepted for M1: margin-model sensitivity grid not implemented (Task 9 notes it); freshness config is loaded but staleness enforcement arrives with Evidence Normalizer in M3.
