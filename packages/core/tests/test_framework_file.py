from pathlib import Path

import yaml


def test_framework_yaml_parses():
    path = Path(__file__).parents[3] / "frameworks" / "common-stock.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["id"] == "common-stock"
    assert data["version"] == "1.0.0"
    assert len(data["factors"]) == 11
    assert set(data["lenses"]) == {"core", "offensive", "tactical"}
