from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd


def compute_pair(ai_values: pd.Series, human_values: pd.Series) -> dict:
    sub = pd.DataFrame({"ai": ai_values, "human": human_values}).dropna()
    sub = sub[sub["human"].astype(str).str.strip() != ""]
    n = len(sub)
    if n == 0:
        return {"n_reviewed": 0, "agreement_rate": None, "cohen_kappa": None, "status": "insufficient"}

    ai = sub["ai"].astype(str).str.strip()
    human = sub["human"].astype(str).str.strip()
    observed = float((ai == human).mean())
    categories = sorted(set(ai) | set(human))
    ai_counts, human_counts = Counter(ai), Counter(human)
    expected = sum((ai_counts[c] / n) * (human_counts[c] / n) for c in categories)
    kappa = None if abs(1 - expected) < 1e-12 else (observed - expected) / (1 - expected)
    return {
        "n_reviewed": n,
        "agreement_rate": round(observed, 3),
        "cohen_kappa": None if kappa is None else round(float(kappa), 3),
        "status": "uncomputable" if kappa is None else "computed",
    }


def discover_pairs(columns: Iterable[str]) -> list[tuple[str, str, str]]:
    column_set = set(columns)
    pairs = []
    for column in sorted(column_set):
        if not column.startswith("ai_"):
            continue
        variable = column[3:]
        human = f"human_{variable}"
        if human in column_set:
            pairs.append((variable, column, human))
    return pairs


def compute_reliability(df: pd.DataFrame, pairs: list[tuple[str, str, str]] | None = None) -> pd.DataFrame:
    selected_pairs = pairs if pairs is not None else discover_pairs(df.columns)
    rows = []
    for variable, ai_column, human_column in selected_pairs:
        if ai_column not in df.columns or human_column not in df.columns:
            raise ValueError(f"Missing reliability columns for {variable}: {ai_column}, {human_column}")
        rows.append({"variable": variable, **compute_pair(df[ai_column], df[human_column])})
    return pd.DataFrame(rows, columns=["variable", "n_reviewed", "agreement_rate", "cohen_kappa", "status"])


def parse_pair(value: str) -> tuple[str, str, str]:
    parts = value.split(":")
    if len(parts) != 3 or not all(parts):
        raise argparse.ArgumentTypeError("Pair must be variable:ai_column:human_column")
    return parts[0], parts[1], parts[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute agreement and Cohen's kappa from a review CSV.")
    parser.add_argument("--input", required=True, help="CSV containing ai_* and human_* columns.")
    parser.add_argument("--pair", action="append", type=parse_pair, help="Optional variable:ai_column:human_column mapping.")
    parser.add_argument("--output", default=None, help="Optional output CSV. Without it, results are printed only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input, encoding="utf-8-sig")
    result = compute_reliability(df, args.pair)
    print(result.to_string(index=False))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
