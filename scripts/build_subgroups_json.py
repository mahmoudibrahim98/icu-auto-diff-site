"""Aggregate per-subgroup AUROC CSV → data/subgroups.json.

Subgroup encoding (confirmed via data exploration):
    subgroup = "{sex}_{ethnicity}_{age}"
    sex      ∈ {0=male, 1=female}
    ethnicity∈ {0=white, 1=black, 2=asian, 3=other}
    age      ∈ {0=<30, 1=31-50, 2=51-70, 3=>70}

Method encoding (confirmed from TimeDiff/notebooks/3a_*_mortality.ipynb):
    evaluated_on                     → bar label
    "oracle"                         → ground-truth pool (reference)
    "test"                           → small-real subset (ε_naive)
    "synthetic_timeautodiff"         → TimeAutoDiff (ε_synth)
    "synthetic_timediff"             → TimeDiff
    "synthetic_enhanced_timeautodiff"→ Enhanced TimeAutoDiff  (if exported)
    "synthetic_healthgen"            → HealthGen (if exported)

Strategy:
1. For each subgroup triple, compute oracle AUROC mean (ground truth).
2. For each method row, compute absolute |oracle_mean - method_mean|
   across the 5 synth_data_index repetitions → "error".
3. Bootstrap a 95% CI on the method-AUROC distribution → transform to
   error CI via |oracle_mean - method_ci_lo|, |oracle_mean - method_ci_hi|.
4. Cells with no rows for a method emit {"status": "not_exported"}.
5. Cells with oracle rows but where all AUROC are NaN emit a
   degenerate-class marker {"status": "single_class"}.

Fails loud if any `model` integer ID is seen that isn't in METHOD_MAP.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# Method ID → internal name.  Update if the source notebook changes.
# Verified against TimeDiff/notebooks/3a_[COMPLETE]intersectional_evaluation_eicu_mortality.ipynb.
METHOD_MAP: Dict[int, str] = {
    0: "real_model",           # trained on real, used for oracle/test evals
    1: "timeautodiff",
    2: "timediff",
    3: "enhanced_timeautodiff",
    4: "healthgen",
}

EVALUATED_ON_TO_METHOD: Dict[str, str] = {
    "oracle": "oracle",
    "test": "test",
    "synthetic_timeautodiff": "timeautodiff",
    "synthetic_timediff": "timediff",
    "synthetic_enhanced_timeautodiff": "enhanced_timeautodiff",
    "synthetic_healthgen": "healthgen",
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


def build_subgroups(csv_path: Optional[Path], data_task: str) -> Dict[str, Any]:
    tree = _make_empty_tree(data_task)

    if csv_path is None:
        return tree  # All cells stay "not_exported".

    df = pd.read_csv(csv_path)

    # Fail loud on unknown model IDs.
    unknown = set(df["model"].unique()) - set(METHOD_MAP.keys())
    if unknown:
        raise KeyError(
            f"Unknown model IDs in {csv_path}: {sorted(unknown)}. "
            f"Expected {sorted(METHOD_MAP.keys())}."
        )

    # Group by subgroup triple.
    for sg, sub in df.groupby("subgroup"):
        sex, eth, age = decode_subgroup(sg)
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

        for eval_label, method in EVALUATED_ON_TO_METHOD.items():
            if method == "oracle":
                continue
            rows = sub[sub["evaluated_on"] == eval_label]["auroc"].dropna().to_numpy()
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


def build_full(csv_dir: Optional[Path]) -> Dict[str, Any]:
    """Build all four Data×Task combos into one tree.

    Only `eicu_mortality24` has a CSV shipped today; the other three
    Data×Task combos render as all-not_exported stubs until the
    aggregate_missing_tasks pipeline runs.
    """
    csv_map: Dict[str, Optional[Path]] = {
        "eicu_mortality24": (csv_dir / "all_results_timediff_and_timeautodiff_"
                             "eicu_with_cond_mortality.csv") if csv_dir else None,
        "eicu_los24": None,
        "mimic_mortality24": None,
        "mimic_los24": None,
    }
    merged: Dict[str, Any] = {}
    for task, path in csv_map.items():
        tree = build_subgroups(csv_path=path if path and path.exists() else None,
                               data_task=task)
        merged.update(tree)
    return merged


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", required=False, type=Path,
                    default=Path("../4_timediff/TimeDiff/intersectional_analysis_results"))
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    out = build_full(args.csv_dir if args.csv_dir.exists() else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
