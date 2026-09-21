from __future__ import annotations

import pandas as pd
from pathlib import Path

from processing.compute_reliability import compute_pair, compute_reliability, discover_pairs

ROOT = Path(__file__).resolve().parents[1]


def test_pair_computes_agreement_and_kappa():
    result = compute_pair(pd.Series(["a", "b", "a"]), pd.Series(["a", "a", "a"]))
    assert result["n_reviewed"] == 3
    assert result["agreement_rate"] == 0.667
    assert result["cohen_kappa"] == 0.0
    assert result["status"] == "computed"


def test_empty_and_one_class_are_explicit():
    empty = compute_pair(pd.Series([None]), pd.Series([None]))
    assert empty["status"] == "insufficient"
    one_class = compute_pair(pd.Series([1, 1]), pd.Series([1, 1]))
    assert one_class["cohen_kappa"] is None
    assert one_class["status"] == "uncomputable"


def test_discovery_and_fixture():
    df = pd.read_csv(ROOT / "examples/sample_reliability.csv")
    pairs = discover_pairs(df.columns)
    result = compute_reliability(df, pairs)
    assert set(result["variable"]) == {"scene_type", "rural_scene", "one_class"}
