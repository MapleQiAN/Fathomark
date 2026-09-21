import hashlib

import pytest
from fathomark_reporting.charts import (
    render_factor_chart,
    render_score_change,
    render_valuation_sensitivity,
)
from test_renderers import _report


def test_factor_chart_is_deterministic_and_escapes_labels():
    base = _report()
    changed = base.model_copy(
        update={
            "factors": (base.factors[0].model_copy(update={"factor": "<factor>"}),),
            "model_hash": "",
        }
    )
    digest = (
        "sha256:"
        + hashlib.sha256(
            changed._canonical_payload(changed).encode("utf-8")
        ).hexdigest()
    )
    report = changed.model_copy(update={"model_hash": digest})

    first = render_factor_chart(report)
    assert first == render_factor_chart(report)
    assert first.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "&lt;factor&gt;" in first
    assert "aria-label" in first


def test_valuation_sensitivity_matrix_rejects_ragged_values_and_renders_cells():
    rendered = render_valuation_sensitivity(
        rows=["Bear", "Base"],
        columns=["8%", "10%"],
        values=[[12.0, 10.0], [18.0, 15.0]],
    )
    assert "Bear" in rendered and "10%" in rendered
    assert rendered.count("<rect") == 5  # background plus four matrix cells

    with pytest.raises(ValueError, match="column count"):
        render_valuation_sensitivity(
            rows=["Bear"], columns=["8%", "10%"], values=[[1.0]]
        )


def test_score_change_handles_new_missing_and_changed_factors():
    rendered = render_score_change(
        {"business_moat": 8.0, "old_factor": 6.0},
        {"business_moat": 9.0, "new_factor": 7.0},
    )
    assert "business_moat" in rendered
    assert "old_factor" in rendered and "new_factor" in rendered
    assert "+1.0" in rendered
