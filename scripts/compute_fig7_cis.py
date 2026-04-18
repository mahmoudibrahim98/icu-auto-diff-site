"""Compute Figure 7 CIs (for eICU Mortality 24 only) from per-subgroup data.

The paper Fig 7 bar height = mean across 32 subgroups of
    ε_method(subgroup) = |AUROC_oracle - AUROC_method| (mean across 5 reps).
Its error bars = 95% bootstrap CI of that mean.

We only have per-subgroup data for eICU Mortality 24, so this script
writes CIs for that one task. Other tasks are left out of the JSON
(the site renderer skips whiskers when data is absent).

Usage:
    python3 scripts/compute_fig7_cis.py \\
        --csv ../4_timediff/TimeDiff/intersectional_analysis_results/all_results_timediff_and_timeautodiff_eicu_with_cond_mortality.csv \\
        --results data/results.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd


METHOD_MAP = {
    "test": "test",
    "synthetic_timeautodiff": "timeautodiff",
    "synthetic_timediff": "timediff",
}


def _bootstrap_ci(values: np.ndarray, n: int = 2000, alpha: float = 0.05) -> Tuple[float, float]:
    rng = np.random.default_rng(42)
    means = np.array([rng.choice(values, size=values.size, replace=True).mean() for _ in range(n)])
    return float(np.percentile(means, 100 * alpha / 2)), float(np.percentile(means, 100 * (1 - alpha / 2)))


def compute_cis(csv_path: Path) -> Dict[str, Tuple[float, float]]:
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["auroc"])  # single-class subgroups have NaN AUROC

    # oracle mean per subgroup
    oracle_by_sg = (df[df["evaluated_on"] == "oracle"]
                    .groupby("subgroup")["auroc"].mean())

    out: Dict[str, Tuple[float, float]] = {}
    for eval_label, method_name in METHOD_MAP.items():
        # per-subgroup: mean AUROC across reps for this method
        method_means = (df[df["evaluated_on"] == eval_label]
                        .groupby("subgroup")["auroc"].mean())
        # align by subgroup
        sgs = oracle_by_sg.index.intersection(method_means.index)
        if len(sgs) == 0:
            continue
        errors = (oracle_by_sg.loc[sgs] - method_means.loc[sgs]).abs().to_numpy()
        lo, hi = _bootstrap_ci(errors)
        out[method_name] = (round(lo, 4), round(hi, 4))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--results", required=True, type=Path,
                    help="path to data/results.json; edited in place")
    args = ap.parse_args(argv)

    cis = compute_cis(args.csv)

    results = json.loads(args.results.read_text())
    results.setdefault("figure7_cis", {})
    results["figure7_cis"]["eicu_mortality24"] = {m: list(v) for m, v in cis.items()}
    args.results.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(f"wrote figure7_cis.eicu_mortality24 with methods: {sorted(cis.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
