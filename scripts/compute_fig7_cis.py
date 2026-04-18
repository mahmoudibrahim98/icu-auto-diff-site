"""Compute Figure 7 CIs and point estimates across all 4 data×task combos.

For each of the 4 tasks and each method, we compute:
  - Per-subgroup error: ε(sg) = |AUROC_oracle(sg) - AUROC_method(sg)|
    (where each is the mean across repetitions for that subgroup).
  - Point estimate: mean of the 32 subgroup errors.
  - 95% bootstrap CI on that mean.

Results are stored in results.json under:
  - figure7_points[task][method] = float   (computed from CSVs)
  - figure7_cis[task][method]    = [lo, hi]

NOTE: The existing figure7[task][method] values are the paper-text numbers from
Section 5.3 and are left unchanged. The JS renderer uses figure7_points when
present (they come from the same data as the paper's computation), and falls
back to figure7 (paper text) if absent.

Source files
------------
Dir A (Enhanced TimeAutoDiff experiments):
    all_results_<task>.csv — has oracle, test, synthetic_timeautodiff_baseline,
                              synthetic_timeautodiff_enhanced.
Dir B (TimeDiff comparison):
    all_results_<task>.csv — has oracle, test, synthetic_timediff,
                              synthetic_timeautodiff (fallback).

Method routing (same canonical table as build_subgroups_json.py):
    synthetic_timeautodiff_baseline → timeautodiff    (prefer over B)
    synthetic_timeautodiff_enhanced → enhanced_timeautodiff
    synthetic_timediff              → timediff
    test                            → test
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ── Default source dirs ────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent.parent

DIR_A_DEFAULT = (
    _REPO / "4_timediff/icu-autodiff/0_ecml_conditional_autodiff_generation"
            "/scripts_evaluating_intersectional/results"
)
DIR_B_DEFAULT = (
    _REPO / "4_timediff/icu-autodiff/0c_ecml_conditional_timediff_generation"
            "/scripts_evaluating_intersectional/results"
)

# CSV filename suffix per task key
TASK_CSV: Dict[str, str] = {
    "eicu_mortality24":  "eicu_mortality24",
    "eicu_los24":        "eicu_los_24",
    "mimic_mortality24": "mimic_mortality24",
    "mimic_los24":       "mimic_los_24",
}

# Canonical evaluated_on → internal method (or __ignore__)
EVAL_TO_METHOD = {
    "oracle":                         "oracle",
    "test":                           "test",
    "synthetic_timeautodiff_baseline": "timeautodiff",
    "synthetic_timeautodiff_enhanced": "enhanced_timeautodiff",
    "synthetic_timeautodiff":          "timeautodiff",   # Dir B fallback
    "synthetic_timediff":              "timediff",
    "random_all_subgroups":            "__ignore__",
}

ALL_METHODS = ("test", "timeautodiff", "enhanced_timeautodiff", "timediff")


def _bootstrap_ci(values: np.ndarray, n: int = 2000,
                  alpha: float = 0.05) -> Tuple[float, float]:
    rng = np.random.default_rng(42)
    means = np.array([
        rng.choice(values, size=values.size, replace=True).mean()
        for _ in range(n)
    ])
    return (float(np.percentile(means, 100 * alpha / 2)),
            float(np.percentile(means, 100 * (1 - alpha / 2))))


def _load_df(path: Optional[Path]) -> Optional[pd.DataFrame]:
    if path is None or not path.exists():
        return None
    df = pd.read_csv(path)
    unknown = set(df["evaluated_on"].unique()) - set(EVAL_TO_METHOD.keys())
    if unknown:
        raise KeyError(
            f"Unknown evaluated_on values in {path}: {sorted(unknown)}. "
            f"Expected: {sorted(EVAL_TO_METHOD.keys())}."
        )
    return df


def compute_task_cis(
    path_a: Optional[Path],
    path_b: Optional[Path],
) -> Tuple[Dict[str, float], Dict[str, Tuple[float, float]]]:
    """Return (points, cis) for one task.

    points: {method: mean_error}
    cis:    {method: (lo, hi)}
    """
    df_a = _load_df(path_a)
    df_b = _load_df(path_b)

    if df_a is None and df_b is None:
        return {}, {}

    # Merge, dropping ignored rows
    frames = []
    if df_a is not None:
        df_a = df_a[df_a["evaluated_on"] != "__ignore__"].copy()
        df_a = df_a[df_a["evaluated_on"] != "random_all_subgroups"].copy()
        df_a["_src"] = "A"
        frames.append(df_a)
    if df_b is not None:
        df_b = df_b[df_b["evaluated_on"] != "__ignore__"].copy()
        df_b = df_b[df_b["evaluated_on"] != "random_all_subgroups"].copy()
        df_b["_src"] = "B"
        frames.append(df_b)

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["auroc"])

    # Oracle mean per subgroup (all sources together)
    oracle_by_sg = (
        df[df["evaluated_on"] == "oracle"]
        .groupby("subgroup")["auroc"].mean()
    )

    points: Dict[str, float] = {}
    cis: Dict[str, Tuple[float, float]] = {}

    for method in ALL_METHODS:
        # Choose the correct evaluated_on label for this method.
        # For timeautodiff: prefer baseline (Dir A) rows.
        if method == "timeautodiff":
            # Try baseline first
            rows_df = df[df["evaluated_on"] == "synthetic_timeautodiff_baseline"]
            if rows_df.empty:
                rows_df = df[df["evaluated_on"] == "synthetic_timeautodiff"]
        elif method == "enhanced_timeautodiff":
            rows_df = df[df["evaluated_on"] == "synthetic_timeautodiff_enhanced"]
        elif method == "timediff":
            rows_df = df[df["evaluated_on"] == "synthetic_timediff"]
        elif method == "test":
            rows_df = df[df["evaluated_on"] == "test"]
        else:
            continue

        method_means = rows_df.groupby("subgroup")["auroc"].mean()
        sgs = oracle_by_sg.index.intersection(method_means.index)
        if len(sgs) == 0:
            continue

        errors = (oracle_by_sg.loc[sgs] - method_means.loc[sgs]).abs().to_numpy()
        lo, hi = _bootstrap_ci(errors)
        points[method] = round(float(errors.mean()), 4)
        cis[method] = (round(lo, 4), round(hi, 4))

    return points, cis


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv-dir-autodiff", type=Path, default=DIR_A_DEFAULT,
        help="Dir A: Enhanced TimeAutoDiff experiments",
    )
    ap.add_argument(
        "--csv-dir-timediff", type=Path, default=DIR_B_DEFAULT,
        help="Dir B: TimeDiff comparison experiments",
    )
    ap.add_argument("--results", required=True, type=Path,
                    help="Path to data/results.json; patched in place.")
    args = ap.parse_args(argv)

    dir_a = args.csv_dir_autodiff if args.csv_dir_autodiff.exists() else None
    dir_b = args.csv_dir_timediff if args.csv_dir_timediff.exists() else None

    results = json.loads(args.results.read_text())
    results.setdefault("figure7_points", {})
    results.setdefault("figure7_cis", {})

    for task_key, csv_suffix in TASK_CSV.items():
        path_a = (dir_a / f"all_results_{csv_suffix}.csv") if dir_a else None
        path_b = (dir_b / f"all_results_{csv_suffix}.csv") if dir_b else None

        points, cis = compute_task_cis(path_a, path_b)
        if not points:
            print(f"  {task_key}: no data found, skipping.")
            continue

        results["figure7_points"][task_key] = points
        results["figure7_cis"][task_key] = {m: list(v) for m, v in cis.items()}
        print(f"  {task_key}: methods={sorted(points.keys())}, "
              f"points={points}")

    args.results.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(f"wrote figure7_points + figure7_cis into {args.results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
