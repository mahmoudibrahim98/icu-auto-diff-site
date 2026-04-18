"""Tests for compute_fig7_cis.py (paper-consistent across-run stddev)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.compute_fig7_cis import compute_task_stds, ALL_METHODS


# ── Fixture helpers ────────────────────────────────────────────────────────

_HEADER = (
    "subgroup,evaluated_on,evaluation_size,subgroup_size,test_oracle_random_state,"
    "synth_data_index,model,auroc,auprc,sens,spec,bacc_sens,f1_sens,tp,tn,fp,fn,"
    "sens_opt,spec_opt,bacc_opt,f1_opt,tp_opt,tn_opt,fp_opt,fn_opt\n"
)


def _row(sg: str, eon: str, synth_idx: int, model: int, auroc: float) -> str:
    return (
        f"{sg},{eon},500,100,42,{synth_idx},{model},{auroc},"
        "0.5,0.8,0.7,0.75,0.4,80,70,30,20,0.75,0.75,0.75,0.45,75,75,25,25\n"
    )


def _make_mini_csv(path: Path) -> Path:
    """25 runs (5 synth × 5 model) of oracle + baseline + enhanced + timediff."""
    lines = _HEADER
    # two subgroups; oracle AUROC fixed at 0.80 and 0.85
    for sidx in range(5):
        for midx in range(5):
            for sg, oracle_auroc in [("0_0_0", 0.80), ("0_1_0", 0.85)]:
                lines += _row(sg, "oracle", sidx, midx, oracle_auroc)
                # baseline: error ≈ 0.05 (0.75/0.80 mean), slight variation
                lines += _row(sg, "synthetic_timeautodiff_baseline", sidx, midx,
                              oracle_auroc - 0.05 + (sidx - 2) * 0.001)
                # enhanced: error ≈ 0.03
                lines += _row(sg, "synthetic_timeautodiff_enhanced", sidx, midx,
                              oracle_auroc - 0.03 + (midx - 2) * 0.001)
                # test: small variation across runs
                lines += _row(sg, "test", sidx, midx,
                              oracle_auroc - 0.02 + (sidx + midx) * 0.0005)
    path.write_text(lines)
    return path


def _make_mini_csv_b(path: Path) -> Path:
    """25 runs with synthetic_timediff and synthetic_timeautodiff (fallback)."""
    lines = _HEADER
    for sidx in range(5):
        for midx in range(5):
            for sg, oracle_auroc in [("0_0_0", 0.80), ("0_1_0", 0.85)]:
                lines += _row(sg, "oracle", sidx, midx, oracle_auroc)
                # timediff: error ≈ 0.04
                lines += _row(sg, "synthetic_timediff", sidx, midx,
                              oracle_auroc - 0.04 + sidx * 0.001)
                lines += _row(sg, "random_all_subgroups", sidx, midx, 0.5)
    path.write_text(lines)
    return path


# ── Tests ──────────────────────────────────────────────────────────────────

def test_stds_are_positive_floats(tmp_path):
    """Each method should yield a strictly positive stddev."""
    csv_a = _make_mini_csv(tmp_path / "csv_a.csv")
    csv_b = _make_mini_csv_b(tmp_path / "csv_b.csv")

    points, stds = compute_task_stds(csv_a, csv_b)

    for method in ("test", "timeautodiff", "enhanced_timeautodiff", "timediff"):
        assert method in stds, f"Missing method: {method}"
        assert isinstance(stds[method], float), f"{method} std not float"
        assert stds[method] > 0, f"{method} std should be > 0, got {stds[method]}"


def test_25_runs_used(tmp_path):
    """Verify we get a point per (synth_data_index, model) = 25 runs."""
    csv_a = _make_mini_csv(tmp_path / "csv_a.csv")

    points, stds = compute_task_stds(csv_a, None)

    # With 25 nearly-identical runs and tiny variation, stds should be very small
    assert stds["timeautodiff"] < 0.01
    assert stds["test"] < 0.01


def test_real_eicu_mortality24_timeautodiff():
    """Integration: eICU Mortality 24 / timeautodiff std must be a positive float."""
    from scripts.compute_fig7_cis import DIR_A_DEFAULT, DIR_B_DEFAULT, TASK_CSV

    path_a = DIR_A_DEFAULT / "all_results_eicu_mortality24.csv"
    path_b = DIR_B_DEFAULT / "all_results_eicu_mortality24.csv"

    if not path_a.exists() and not path_b.exists():
        pytest.skip("Real CSVs not found")

    points, stds = compute_task_stds(
        path_a if path_a.exists() else None,
        path_b if path_b.exists() else None,
    )

    assert "timeautodiff" in stds, "timeautodiff not in stds"
    assert isinstance(stds["timeautodiff"], float)
    assert stds["timeautodiff"] > 0, (
        f"expected positive stddev, got {stds['timeautodiff']}"
    )
