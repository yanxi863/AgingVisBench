from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]


def metric_map(config: dict) -> dict:
    result = {}
    for group in config["metric_groups"].values():
        for metric in group["metrics"]:
            result[metric["id"]] = metric
    return result


def test_published_reliability_matches_registry():
    config = yaml.safe_load((ROOT / "config/metrics.yml").read_text(encoding="utf-8"))
    metrics = metric_map(config)
    summary = pd.read_csv(ROOT / "reports/reliability_summary.csv")
    expected = {
        "development_oriented_agency": "high",
        "scene_type": "high",
        "modern_object": "medium",
        "traditional_cultural_marker": "high",
        "rural_scene": "high",
    }
    for variable, tier in expected.items():
        row = summary.loc[summary["variable"] == variable].iloc[0]
        assert row["reliability_tier"] == tier
        assert metrics[variable]["reliability_tier"] == tier
        assert "reliability_source" in metrics[variable]
    assert metrics["is_alone"]["reliability_tier"] == "insufficient"


def test_reports_are_labeled_as_snapshots():
    readme = (ROOT / "reports/README.md").read_text(encoding="utf-8")
    benchmark = (ROOT / "BENCHMARK_CARD.md").read_text(encoding="utf-8")
    assert "历史聚合研究快照" in readme
    assert "synthetic" in readme
    assert "Public release note" in benchmark
