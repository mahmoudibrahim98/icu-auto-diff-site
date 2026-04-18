"""Aggregate per-subgroup AUROC CSVs → data/subgroups.json.

Subgroup encoding (confirmed via data exploration):
    subgroup = "{sex}_{ethnicity}_{age}"
    sex      ∈ {0=male, 1=female}
    ethnicity∈ {0=white, 1=black, 2=asian, 3=other}
    age      ∈ {0=<30, 1=31-50, 2=51-70, 3=>70}

Method encoding — source `evaluated_on` → internal site name:

    Source evaluated_on                 Internal          Source dir
    ─────────────────────────────────── ──────────────── ──────────
    oracle                              oracle (ref)      A or B
    test                                test              A or B
    synthetic_timeautodiff_baseline     timeautodiff      A
    synthetic_timeautodiff_enhanced     enhanced_ta       A
    synthetic_timeautodiff              timeautodiff      B (fallback)
    synthetic_timediff                  timediff          B
    random_all_subgroups                (ignored)         B

Strategy:
1. For each subgroup triple, compute oracle AUROC mean (ground truth).
2. For each method row, compute absolute |oracle_mean - method_mean|
   across the repetitions → "error".
3. Bootstrap a 95% CI on the method-AUROC distribution → transform to
   error CI via |oracle_mean - method_ci_lo|, |oracle_mean - method_ci_hi|.
4. Cells with no rows for a method emit {"status": "not_exported"}.
5. Cells with oracle rows but where all AUROC are NaN emit a
   degenerate-class marker {"status": "single_class"}.

Fails loud on unknown `evaluated_on` strings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# Canonical mapping: evaluated_on → internal method name (or sentinel).
# Anything NOT in this dict causes a KeyError (fail loud).
EVALUATED_ON_TO_METHOD: Dict[str, str] = {
    "oracle":                         "oracle",
    "test":                           "test",
    "synthetic_timeautodiff_baseline": "timeautodiff",     # Dir A preferred
    "synthetic_timeautodiff_enhanced": "enhanced_timeautodiff",  # Dir A only
    "synthetic_timeautodiff":          "timeautodiff",     # Dir B fallback
    "synthetic_timediff":              "timediff",         # Dir B only
    "random_all_subgroups":            "__ignore__",       # Dir B noise row
}

SEX: Dict[int, str] = {0: "male", 1: "female"}
ETH: Dict[int, str] = {0: "white", 1: "black", 2: "asian", 3: "other"}
AGE: Dict[int, str] = {0: "age_<30", 1: "age_31-50", 2: "age_51-70", 3: "age_>70"}

ALL_METHODS = ("test", "timeautodiff", "timediff",
               "enhanced_timeautodiff", "healthgen")

EMPTY_CELL_TEMPLATE = {
    "n_real": 0,
    "auroc_groundtruth": None,
    "auroc_groundtruth_ci": None,
    "methods": {m: {"status": "not_exported"} for m in ALL_METHODS},
}

# CSV filename stem → (data_task key used in output JSON, csv filename suffix in dirs)
TASK_MAP: Dict[str, str] = {
    "eicu_mortality24":  "eicu_mortality24",
    "eicu_los24":        "eicu_los_24",
    "mimic_mortality24": "mimic_mortality24",
    "mimic_los24":       "mimic_los_24",
}


def decode_subgroup(s: str) -> Tuple[str, str, str]:
    parts = s.split("_")
    sex = SEX[int(parts[0])]
    eth = ETH[int(parts[1])]
    age = AGE[int(parts[2])]
    return sex, eth, age


def _bootstrap_ci(values: np.ndarray, n: int = 2000, alpha: float = 0.05
                  ) -> Tuple[float, float]:
    if values.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(42)  # deterministic
    means = np.array([
        rng.choice(values, size=values.size, replace=True).mean()
        for _ in range(n)
    ])
    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return lo, hi


def _make_empty_tree(data_task: str) -> Dict[str, Any]:
    """Pre-populate the full 4×2×4 tree with not_exported cells."""
    tree: Dict[str, Any] = {data_task: {}}
    for age in AGE.values():
        tree[data_task][age] = {}
        for sex in SEX.values():
            tree[data_task][age][sex] = {}
            for eth in ETH.values():
                tree[data_task][age][sex][eth] = dict(
                    EMPTY_CELL_TEMPLATE,
                    methods={m: {"status": "not_exported"} for m in ALL_METHODS},
                )
    return tree


def _load_and_validate(csv_path: Path) -> pd.DataFrame:
    """Load CSV and fail loud on unknown evaluated_on values."""
    df = pd.read_csv(csv_path)
    unknown = set(df["evaluated_on"].unique()) - set(EVALUATED_ON_TO_METHOD.keys())
    if unknown:
        raise KeyError(
            f"Unknown evaluated_on values in {csv_path}: {sorted(unknown)}. "
            f"Expected one of: {sorted(EVALUATED_ON_TO_METHOD.keys())}."
        )
    return df


def build_subgroups(
    csv_path: Optional[Path],
    data_task: str,
    csv_path_b: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the subgroup tree for one data×task combo.

    csv_path   — Dir A CSV (has synthetic_timeautodiff_baseline/enhanced)
    csv_path_b — Dir B CSV (has synthetic_timediff, synthetic_timeautodiff fallback)
    """
    tree = _make_empty_tree(data_task)

    frames = []
    # Track which source a row came from so we can prefer Dir A for timeautodiff
    if csv_path is not None and csv_path.exists():
        df_a = _load_and_validate(csv_path)
        df_a = df_a[df_a["evaluated_on"] != "__ignore__"].copy()
        df_a["_src"] = "A"
        frames.append(df_a)
    if csv_path_b is not None and csv_path_b.exists():
        df_b = _load_and_validate(csv_path_b)
        df_b = df_b[df_b["evaluated_on"] != "__ignore__"].copy()
        # Drop random_all_subgroups rows
        df_b = df_b[df_b["evaluated_on"] != "random_all_subgroups"].copy()
        df_b["_src"] = "B"
        frames.append(df_b)

    if not frames:
        return tree  # All cells stay "not_exported".

    df = pd.concat(frames, ignore_index=True)

    # Group by subgroup triple.
    for sg, sub in df.groupby("subgroup"):
        sex, eth, age = decode_subgroup(str(sg))
        cell = tree[data_task][age][sex][eth]

        oracle = sub[sub["evaluated_on"] == "oracle"]["auroc"].dropna().to_numpy()
        if oracle.size == 0:
            cell["methods"] = {m: {"status": "single_class"} for m in ALL_METHODS}
            continue

        oracle_mean = float(oracle.mean())
        oracle_ci = _bootstrap_ci(oracle)
        cell["auroc_groundtruth"] = round(oracle_mean, 4)
        cell["auroc_groundtruth_ci"] = [round(v, 4) for v in oracle_ci]
        cell["n_real"] = int(sub[sub["evaluated_on"] == "test"]
                                ["auroc"].dropna().size)

        # Collect per-method rows with precedence rules:
        # - timeautodiff: prefer synthetic_timeautodiff_baseline (Dir A);
        #                 if absent, fall back to synthetic_timeautodiff (Dir B).
        # - enhanced_timeautodiff: synthetic_timeautodiff_enhanced (Dir A only).
        # - timediff: synthetic_timediff (Dir B only).
        # - test: prefer Dir A.

        method_rows: Dict[str, np.ndarray] = {}

        # Collect by eval label, then apply precedence.
        rows_by_label: Dict[str, np.ndarray] = {}
        for lbl in sub["evaluated_on"].unique():
            if lbl == "oracle":
                continue
            internal = EVALUATED_ON_TO_METHOD.get(lbl)
            if internal is None or internal == "__ignore__":
                continue
            rows_by_label[lbl] = sub[sub["evaluated_on"] == lbl]["auroc"].dropna().to_numpy()

        # timeautodiff: prefer baseline (Dir A), else fallback (Dir B)
        if "synthetic_timeautodiff_baseline" in rows_by_label:
            method_rows["timeautodiff"] = rows_by_label["synthetic_timeautodiff_baseline"]
        elif "synthetic_timeautodiff" in rows_by_label:
            method_rows["timeautodiff"] = rows_by_label["synthetic_timeautodiff"]

        if "synthetic_timeautodiff_enhanced" in rows_by_label:
            method_rows["enhanced_timeautodiff"] = rows_by_label["synthetic_timeautodiff_enhanced"]

        if "synthetic_timediff" in rows_by_label:
            method_rows["timediff"] = rows_by_label["synthetic_timediff"]

        if "test" in rows_by_label:
            method_rows["test"] = rows_by_label["test"]

        for method, rows in method_rows.items():
            if rows.size == 0:
                continue
            error = abs(oracle_mean - float(rows.mean()))
            lo, hi = _bootstrap_ci(rows)
            cell["methods"][method] = {
                "error": round(error, 4),
                "ci": [round(abs(oracle_mean - hi), 4),
                       round(abs(oracle_mean - lo), 4)],
            }
    return tree


def build_full(
    csv_dir_autodiff: Optional[Path],
    csv_dir_timediff: Optional[Path],
) -> Dict[str, Any]:
    """Build all four Data×Task combos into one tree."""
    merged: Dict[str, Any] = {}
    for task_key, csv_suffix in TASK_MAP.items():
        path_a = (csv_dir_autodiff / f"all_results_{csv_suffix}.csv"
                  ) if csv_dir_autodiff else None
        path_b = (csv_dir_timediff / f"all_results_{csv_suffix}.csv"
                  ) if csv_dir_timediff else None
        tree = build_subgroups(
            csv_path=path_a if path_a and path_a.exists() else None,
            data_task=task_key,
            csv_path_b=path_b if path_b and path_b.exists() else None,
        )
        merged.update(tree)
    return merged


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    # New canonical args
    ap.add_argument(
        "--csv-dir-autodiff", required=False, type=Path,
        default=Path(__file__).resolve().parent.parent.parent /
                "4_timediff/icu-autodiff/0_ecml_conditional_autodiff_generation"
                "/scripts_evaluating_intersectional/results",
        help="Dir A: Enhanced TimeAutoDiff experiments",
    )
    ap.add_argument(
        "--csv-dir-timediff", required=False, type=Path,
        default=Path(__file__).resolve().parent.parent.parent /
                "4_timediff/icu-autodiff/0c_ecml_conditional_timediff_generation"
                "/scripts_evaluating_intersectional/results",
        help="Dir B: TimeDiff comparison experiments",
    )
    # Back-compat alias
    ap.add_argument(
        "--csv-dir", required=False, type=Path,
        dest="csv_dir_autodiff_alias",
        help="Alias for --csv-dir-autodiff (back-compat).",
    )
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    # Back-compat: if old --csv-dir was passed, let it override autodiff dir
    autodiff_dir = args.csv_dir_autodiff
    if args.csv_dir_autodiff_alias is not None:
        autodiff_dir = args.csv_dir_autodiff_alias

    out = build_full(
        csv_dir_autodiff=autodiff_dir if autodiff_dir and autodiff_dir.exists() else None,
        csv_dir_timediff=args.csv_dir_timediff if args.csv_dir_timediff and args.csv_dir_timediff.exists() else None,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
