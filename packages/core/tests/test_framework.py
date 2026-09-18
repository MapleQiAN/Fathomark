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


def test_rating_bands_must_reach_100_at_top(tmp_path):
    # Bands contiguous from 0 but the top band ends at 95 (< 100) — must be rejected.
    text = FRAMEWORK_PATH.read_text(encoding="utf-8").replace(
        "{grade: S,  min: 90, max_exclusive: 101}", "{grade: S,  min: 90, max_exclusive: 95}", 1
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
