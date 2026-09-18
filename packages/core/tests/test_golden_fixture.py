import json
from pathlib import Path

from fathomark_core import evaluate, load_framework
from fathomark_core.schemas import EvidenceItem, FactorProposal, ScopeSnapshot

ROOT = Path(__file__).parents[3]
FIXTURE_DIR = ROOT / "examples" / "fixtures" / "adbe_2026-09-03"
FIXTURE = FIXTURE_DIR / "input.json"
EXPECTED = FIXTURE_DIR / "expected_snapshot.json"


def _evaluate_fixture():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return evaluate(
        framework=load_framework(ROOT / "frameworks" / "common-stock.yaml"),
        scope=ScopeSnapshot.model_validate(data["scope"]),
        evidence=[EvidenceItem.model_validate(e) for e in data["evidence"]],
        proposals=[FactorProposal.model_validate(p) for p in data["proposals"]],
    )


def test_adbe_fixture_reproduces_offline():
    snap = _evaluate_fixture()
    core = snap.lens_results["core"]
    assert core.total == 85.75
    assert core.rating == "A+"
    assert not core.vetoed
    assert snap.overall_confidence == "high"


def test_adbe_fixture_matches_expected_snapshot():
    snap = _evaluate_fixture()
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert snap.model_dump(mode="json") == expected
