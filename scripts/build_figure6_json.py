"""Build figure6 JSON from global evaluation CSVs and merge into results.json.

Sources
-------
HealthGen:
    evaluations_healthgen.csv — 4 rows (one per data×task).
    Cols: data_name, task_name, trts_rpd_mean/std, tstr_rpd_mean/std, disc_mean/std.

TimeAutoDiff (baseline + enhanced):
    evaluations_fixed.csv — 40 rows with weight hyper-parameters.
    Baseline  = row per (data_name, task_name) where ALL FOUR weight cols == 0.
    Enhanced  = row per (data_name, task_name) with MINIMUM trts_rpd_mean
                (ties broken by minimum tstr_rpd_mean).

TimeDiff:
    timediff_evaluations.csv — 4 rows.

Output schema in results.json
------------------------------
{
  "figure6": {
    "delta_tstr": {
      "<task>": {
        "healthgen":             {"mean": ..., "std": ...},
        "timeautodiff":          {"mean": ..., "std": ...},
        "enhanced_timeautodiff": {"mean": ..., "std": ...},
        "timediff":              {"mean": ..., "std": ...}
      }, ...
    },
    "delta_trts": { ... }
  }
}

Task-key normalisation (CSV data_name + task_name → site key):
    eicu  + mortality24 → eicu_mortality24
    eicu  + los_24      → eicu_los24
    mimic + mortality24 → mimic_mortality24
    mimic + los_24      → mimic_los24
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


# ── Default source file paths ──────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent.parent  # …/icu-autodiff

HEALTHGEN_CSV_DEFAULT = (
    _REPO / "4_timediff/icu-autodiff/0a_ecml_conditional_healthgen_generation"
            "/scripts_evaluating/evaluations_healthgen.csv"
)
AUTODIFF_CSV_DEFAULT = (
    _REPO / "4_timediff/icu-autodiff/0_ecml_conditional_autodiff_generation"
            "/scripts_evaluating/evaluations_fixed.csv"
)
TIMEDIFF_CSV_DEFAULT = (
    _REPO / "4_timediff/icu-autodiff/1b_ecml_unconditional_timediff_generation"
            "/training_and_evaluating/timediff_evaluations.csv"
)


def _task_key(data_name: str, task_name: str) -> str:
    """Normalise (data_name, task_name) → site task key."""
    t = task_name.replace("_", "")  # los_24 → los24
    return f"{data_name}_{t}"


def _load_healthgen(path: Path) -> Dict[str, Dict[str, Any]]:
    """Returns {task_key: {delta_tstr: {mean, std}, delta_trts: {mean, std}}}."""
    df = pd.read_csv(path)
    out: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        key = _task_key(row["data_name"], row["task_name"])
        out[key] = {
            "delta_tstr": {"mean": float(row["tstr_rpd_mean"]), "std": float(row["tstr_rpd_std"])},
            "delta_trts": {"mean": float(row["trts_rpd_mean"]), "std": float(row["trts_rpd_std"])},
        }
    return out


def _load_autodiff(path: Path) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Returns {task_key: {baseline: {...}, enhanced: {...}}}."""
    df = pd.read_csv(path)
    weight_cols = ["auto_mmd_weight", "auto_consistency_weight",
                   "diff_mmd_weight", "diff_consistency_weight"]

    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for (data_name, task_name), grp in df.groupby(["data_name", "task_name"]):
        key = _task_key(data_name, task_name)

        # Baseline: all four weights == 0
        baseline_mask = (grp[weight_cols] == 0).all(axis=1)
        baseline_rows = grp[baseline_mask]
        if baseline_rows.empty:
            raise ValueError(
                f"No all-zero-weight row found for ({data_name}, {task_name}) "
                f"in {path}."
            )
        if len(baseline_rows) > 1:
            # pick the one with the lowest trts_rpd_mean among ties
            baseline_rows = baseline_rows.nsmallest(1, "trts_rpd_mean")
        b = baseline_rows.iloc[0]

        # Enhanced: minimum trts_rpd_mean (ties → lowest tstr_rpd_mean)
        enhanced_rows = grp.nsmallest(1, ["trts_rpd_mean", "tstr_rpd_mean"])
        e = enhanced_rows.iloc[0]

        print(
            f"[build_figure6] {key}: enhanced λ = "
            f"(auto_mmd={e['auto_mmd_weight']}, auto_cons={e['auto_consistency_weight']}, "
            f"diff_mmd={e['diff_mmd_weight']}, diff_cons={e['diff_consistency_weight']})"
        )

        out[key] = {
            "baseline": {
                "delta_tstr": {"mean": float(b["tstr_rpd_mean"]), "std": float(b["tstr_rpd_std"])},
                "delta_trts": {"mean": float(b["trts_rpd_mean"]), "std": float(b["trts_rpd_std"])},
            },
            "enhanced": {
                "delta_tstr": {"mean": float(e["tstr_rpd_mean"]), "std": float(e["tstr_rpd_std"])},
                "delta_trts": {"mean": float(e["trts_rpd_mean"]), "std": float(e["trts_rpd_std"])},
            },
        }
    return out


def _load_timediff(path: Path) -> Dict[str, Dict[str, Any]]:
    """Returns {task_key: {delta_tstr: {mean, std}, delta_trts: {mean, std}}}."""
    df = pd.read_csv(path)
    out: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        key = _task_key(row["data_name"], row["task_name"])
        out[key] = {
            "delta_tstr": {"mean": float(row["tstr_rpd_mean"]), "std": float(row["tstr_rpd_std"])},
            "delta_trts": {"mean": float(row["trts_rpd_mean"]), "std": float(row["trts_rpd_std"])},
        }
    return out


def build_figure6(
    healthgen_csv: Path,
    autodiff_csv: Path,
    timediff_csv: Path,
) -> Dict[str, Any]:
    """Build the figure6 object."""
    hg = _load_healthgen(healthgen_csv)
    ad = _load_autodiff(autodiff_csv)
    td = _load_timediff(timediff_csv)

    all_tasks = sorted(set(list(hg.keys()) + list(ad.keys()) + list(td.keys())))

    delta_tstr: Dict[str, Any] = {}
    delta_trts: Dict[str, Any] = {}

    for task in all_tasks:
        delta_tstr[task] = {}
        delta_trts[task] = {}

        if task in hg:
            delta_tstr[task]["healthgen"] = hg[task]["delta_tstr"]
            delta_trts[task]["healthgen"] = hg[task]["delta_trts"]

        if task in ad:
            delta_tstr[task]["timeautodiff"] = ad[task]["baseline"]["delta_tstr"]
            delta_trts[task]["timeautodiff"] = ad[task]["baseline"]["delta_trts"]
            delta_tstr[task]["enhanced_timeautodiff"] = ad[task]["enhanced"]["delta_tstr"]
            delta_trts[task]["enhanced_timeautodiff"] = ad[task]["enhanced"]["delta_trts"]

        if task in td:
            delta_tstr[task]["timediff"] = td[task]["delta_tstr"]
            delta_trts[task]["timediff"] = td[task]["delta_trts"]

    return {"delta_tstr": delta_tstr, "delta_trts": delta_trts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, type=Path,
                    help="Path to data/results.json; patched in place.")
    ap.add_argument("--healthgen-csv", type=Path, default=HEALTHGEN_CSV_DEFAULT)
    ap.add_argument("--autodiff-csv", type=Path, default=AUTODIFF_CSV_DEFAULT)
    ap.add_argument("--timediff-csv", type=Path, default=TIMEDIFF_CSV_DEFAULT)
    args = ap.parse_args(argv)

    figure6 = build_figure6(
        healthgen_csv=args.healthgen_csv,
        autodiff_csv=args.autodiff_csv,
        timediff_csv=args.timediff_csv,
    )

    results = json.loads(args.results.read_text())
    results["figure6"] = figure6
    args.results.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(f"wrote figure6 into {args.results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
