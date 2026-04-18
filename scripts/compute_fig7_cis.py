"""Compute Figure 7 stddevs (across-run variance) for all 4 data×task combos.

For each of the 4 tasks and each method, the pipeline was run 25 times
(5 synth_data_index × 5 model seeds).  For each run (synth_data_index, model)
we compute:

    run_error = mean over subgroups of |oracle_mean(sg) - method_auroc(run, sg)|

The point estimate is the mean of the 25 run_errors; the stddev is their
sample std (ddof=1).  This matches the paper's Fig 7 error-bar methodology
(across-run variance, NOT bootstrap CI across subgroups).

Results are stored in results.json under:
  - figure7_points[task][method] = float   (mean across 25 runs, for reference)
  - figure7_stds[task][method]   = float   (stddev across 25 runs, paper-consistent)
  - figure7_cis[task][method]    = [lo, hi] (kept for backward compat; now symmetric)

NOTE: The existing figure7[task][method] values are the paper-text numbers from
Section 5.3 and are left unchanged.  The JS renderer uses figure7[task] for bar
height (citation integrity) and figure7_stds for whisker half-width.

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


def _oracle_mean_by_subgroup(df: pd.DataFrame) -> pd.Series:
    """Return mean oracle AUROC per subgroup, pooled across all runs."""
    return (
        df[df["evaluated_on"] == "oracle"]
        .groupby("subgroup")["auroc"].mean()
    )


def compute_task_stds(
    path_a: Optional[Path],
    path_b: Optional[Path],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Return (points, stds) for one task.

    points: {method: mean_error_across_runs}
    stds:   {method: stddev_across_runs}

    Each "run" is identified by (synth_data_index, model).  For each run we
    compute the mean-absolute-deviation across subgroups; then aggregate those
    run-level scalars into a mean and stddev.
    """
    df_a = _load_df(path_a)
    df_b = _load_df(path_b)

    if df_a is None and df_b is None:
        return {}, {}

    # Merge, dropping ignored rows
    frames = []
    if df_a is not None:
        df_a = df_a[df_a["evaluated_on"] != "random_all_subgroups"].copy()
        df_a["_src"] = "A"
        frames.append(df_a)
    if df_b is not None:
        df_b = df_b[df_b["evaluated_on"] != "random_all_subgroups"].copy()
        df_b["_src"] = "B"
        frames.append(df_b)

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["auroc"])

    # Oracle mean per subgroup (all sources, all runs pooled)
    oracle_by_sg = _oracle_mean_by_subgroup(df)

    points: Dict[str, float] = {}
    stds: Dict[str, float] = {}

    for method in ALL_METHODS:
        # Select rows for this method using the correct evaluated_on labels.
        if method == "timeautodiff":
            # Prefer baseline (Dir A) rows; fall back to Dir B
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

        if rows_df.empty:
            continue

        # Compute one run-level error scalar per (synth_data_index, model).
        run_errors: List[float] = []
        for (_sidx, _midx), run_rows in rows_df.groupby(
            ["synth_data_index", "model"]
        ):
            # Mean oracle AUROC per subgroup for this run's subgroups.
            sgs = oracle_by_sg.index.intersection(run_rows["subgroup"].unique())
            if len(sgs) == 0:
                continue
            # Per-subgroup method AUROC for this run (single mean; usually one
            # row per subgroup, but average across any duplicates).
            method_by_sg = run_rows.groupby("subgroup")["auroc"].mean()
            run_error = float(
                (oracle_by_sg.loc[sgs] - method_by_sg.loc[sgs]).abs().mean()
            )
            run_errors.append(run_error)

        if len(run_errors) == 0:
            continue

        arr = np.array(run_errors)
        points[method] = round(float(arr.mean()), 4)
        ddof = 1 if len(arr) > 1 else 0
        stds[method] = round(float(arr.std(ddof=ddof)), 4)

    return points, stds


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
    results.setdefault("figure7_stds", {})
    # Keep figure7_cis for backward compat (now written as symmetric ± std)
    results.setdefault("figure7_cis", {})

    # Print header for sanity-check table
    print(f"\n{'Task':<22} {'Method':<24} {'Std':>8}  {'Point':>8}")
    print("-" * 66)

    for task_key, csv_suffix in TASK_CSV.items():
        path_a = (dir_a / f"all_results_{csv_suffix}.csv") if dir_a else None
        path_b = (dir_b / f"all_results_{csv_suffix}.csv") if dir_b else None

        points, stds = compute_task_stds(path_a, path_b)
        if not points:
            print(f"  {task_key}: no data found, skipping.")
            continue

        results["figure7_points"][task_key] = points
        results["figure7_stds"][task_key] = stds

        # Backward-compat: write symmetric CI as [point-std, point+std]
        cis: Dict[str, List[float]] = {}
        for m, pt in points.items():
            s = stds.get(m, 0.0)
            cis[m] = [round(pt - s, 4), round(pt + s, 4)]
        results["figure7_cis"][task_key] = cis

        for m in sorted(stds.keys()):
            print(f"  {task_key:<20} {m:<24} {stds[m]:>8.4f}  {points[m]:>8.4f}")

    print("-" * 66)

    args.results.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(f"\nWrote figure7_points + figure7_stds + figure7_cis into {args.results}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
