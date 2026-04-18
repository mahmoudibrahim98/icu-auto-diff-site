"""Tests for build_figure6_json.py."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from scripts.build_figure6_json import build_figure6, _task_key


# ── Fixture helpers ────────────────────────────────────────────────────────

def _make_healthgen_csv(path: Path) -> Path:
    path.write_text(
        "data_name,task_name,disc_mean,disc_std,trts_rpd_mean,trts_rpd_std,"
        "trts_real_mean,trts_real_std,trts_synth_mean,trts_synth_std,"
        "trts_kl_mean,trts_kl_std,tstr_rpd_mean,tstr_rpd_std,"
        "tstr_real_mean,tstr_real_std,tstr_synth_mean,tstr_synth_std,"
        "pred_mean,pred_std\n"
        "eicu,mortality24,0.05,0.01,0.13,0.02,0.8,0.01,0.85,0.01,0.01,0.001,"
        "0.085,0.006,0.82,0.01,0.83,0.01,0.09,0.005\n"
        "eicu,los_24,0.04,0.01,0.14,0.02,0.81,0.01,0.82,0.01,0.01,0.001,"
        "0.070,0.005,0.81,0.01,0.82,0.01,0.08,0.005\n"
        "mimic,mortality24,0.06,0.01,0.16,0.02,0.79,0.01,0.80,0.01,0.01,0.001,"
        "0.090,0.007,0.80,0.01,0.81,0.01,0.10,0.005\n"
        "mimic,los_24,0.03,0.01,0.12,0.02,0.82,0.01,0.83,0.01,0.01,0.001,"
        "0.065,0.004,0.83,0.01,0.84,0.01,0.07,0.005\n"
    )
    return path


def _make_autodiff_csv(path: Path) -> Path:
    """Two rows per task: one all-zero (baseline), one with weights (enhanced)."""
    rows = []
    header = (
        "data_name,task_name,standardize,data_timestamp,model,"
        "auto_mmd_weight,auto_consistency_weight,diff_mmd_weight,diff_consistency_weight,"
        "VAE_training,diff_training,disc_mean,disc_std,"
        "trts_rpd_mean,trts_rpd_std,trts_real_mean,trts_real_std,"
        "trts_synth_mean,trts_synth_std,trts_kl_mean,trts_kl_std,"
        "tstr_rpd_mean,tstr_rpd_std,tstr_real_mean,tstr_real_std,"
        "tstr_synth_mean,tstr_synth_std,pred_mean,pred_std\n"
    )
    tasks = [
        ("eicu", "mortality24"),
        ("eicu", "los_24"),
        ("mimic", "mortality24"),
        ("mimic", "los_24"),
    ]
    for dn, tn in tasks:
        # baseline: all weights zero
        rows.append(
            f"{dn},{tn},False,20250101,modelA,"
            "0.0,0.0,0.0,0.0,"
            "100,100,0.05,0.005,"
            "0.030,0.003,0.80,0.01,0.81,0.01,0.005,0.001,"
            "0.010,0.002,0.82,0.01,0.83,0.01,0.09,0.005"
        )
        # enhanced: non-zero weights, lower trts_rpd_mean
        rows.append(
            f"{dn},{tn},False,20250101,modelB,"
            "0.1,0.1,0.0,0.0,"
            "100,100,0.04,0.004,"
            "0.005,0.001,0.81,0.01,0.82,0.01,0.004,0.001,"
            "0.008,0.002,0.83,0.01,0.84,0.01,0.08,0.004"
        )
    path.write_text(header + "\n".join(rows) + "\n")
    return path


def _make_timediff_csv(path: Path) -> Path:
    path.write_text(
        "data_name,task_name,disc_mean,disc_std,trts_rpd_mean,trts_rpd_std,"
        "trts_real_mean,trts_real_std,trts_synth_mean,trts_synth_std,"
        "trts_kl_mean,trts_kl_std,tstr_rpd_mean,tstr_rpd_std,"
        "tstr_real_mean,tstr_real_std,tstr_synth_mean,tstr_synth_std,"
        "pred_mean,pred_std\n"
        "mimic,los_24,0.06,0.012,0.003,0.001,0.80,0.01,0.81,0.01,0.01,0.001,"
        "0.005,0.003,0.82,0.01,0.83,0.01,0.09,0.005\n"
        "mimic,mortality24,0.05,0.010,0.023,0.005,0.79,0.01,0.80,0.01,0.01,0.001,"
        "0.009,0.006,0.81,0.01,0.82,0.01,0.10,0.005\n"
        "eicu,mortality24,0.003,0.003,0.019,0.003,0.81,0.01,0.82,0.01,0.01,0.001,"
        "0.003,0.002,0.83,0.01,0.84,0.01,0.08,0.004\n"
        "eicu,los_24,0.006,0.003,0.006,0.003,0.82,0.01,0.83,0.01,0.01,0.001,"
        "0.005,0.002,0.84,0.01,0.85,0.01,0.07,0.003\n"
    )
    return path


EXPECTED_TASKS = {"eicu_mortality24", "eicu_los24", "mimic_mortality24", "mimic_los24"}
EXPECTED_METHODS = {"healthgen", "timeautodiff", "enhanced_timeautodiff", "timediff"}


# ── Tests ──────────────────────────────────────────────────────────────────

def test_task_key_normalisation():
    assert _task_key("eicu", "mortality24") == "eicu_mortality24"
    assert _task_key("eicu", "los_24") == "eicu_los24"
    assert _task_key("mimic", "los_24") == "mimic_los24"


def test_build_figure6_synthetic_fixture(tmp_path):
    hg = _make_healthgen_csv(tmp_path / "healthgen.csv")
    ad = _make_autodiff_csv(tmp_path / "autodiff.csv")
    td = _make_timediff_csv(tmp_path / "timediff.csv")

    f6 = build_figure6(healthgen_csv=hg, autodiff_csv=ad, timediff_csv=td)

    assert "delta_tstr" in f6
    assert "delta_trts" in f6

    for panel in ("delta_tstr", "delta_trts"):
        # All 4 task keys must be present
        assert set(f6[panel].keys()) == EXPECTED_TASKS, (
            f"Missing tasks in {panel}: {EXPECTED_TASKS - set(f6[panel].keys())}"
        )
        for task in EXPECTED_TASKS:
            task_data = f6[panel][task]
            # All 4 methods present
            assert set(task_data.keys()) == EXPECTED_METHODS, (
                f"Missing methods in {panel}.{task}: "
                f"{EXPECTED_METHODS - set(task_data.keys())}"
            )
            for method in EXPECTED_METHODS:
                entry = task_data[method]
                assert "mean" in entry and "std" in entry
                assert math.isfinite(entry["mean"]), f"{panel}.{task}.{method}.mean not finite"
                assert entry["std"] >= 0, f"{panel}.{task}.{method}.std < 0"


def test_enhanced_has_lower_trts_than_baseline(tmp_path):
    """Enhanced TA must have lower trts_rpd_mean than baseline."""
    hg = _make_healthgen_csv(tmp_path / "healthgen.csv")
    ad = _make_autodiff_csv(tmp_path / "autodiff.csv")
    td = _make_timediff_csv(tmp_path / "timediff.csv")

    f6 = build_figure6(healthgen_csv=hg, autodiff_csv=ad, timediff_csv=td)

    for task in EXPECTED_TASKS:
        baseline_trts = f6["delta_trts"][task]["timeautodiff"]["mean"]
        enhanced_trts = f6["delta_trts"][task]["enhanced_timeautodiff"]["mean"]
        assert enhanced_trts <= baseline_trts, (
            f"{task}: enhanced trts {enhanced_trts} > baseline {baseline_trts}"
        )


@pytest.mark.integration
def test_build_figure6_real_data():
    """Integration test — reads real on-disk CSVs. Marked as integration."""
    import importlib
    import scripts.build_figure6_json as m

    if not m.HEALTHGEN_CSV_DEFAULT.exists():
        pytest.skip("Real HealthGen CSV not found")

    f6 = build_figure6(
        healthgen_csv=m.HEALTHGEN_CSV_DEFAULT,
        autodiff_csv=m.AUTODIFF_CSV_DEFAULT,
        timediff_csv=m.TIMEDIFF_CSV_DEFAULT,
    )

    assert "delta_tstr" in f6
    assert "delta_trts" in f6
    for panel in ("delta_tstr", "delta_trts"):
        assert set(f6[panel].keys()) == EXPECTED_TASKS
        for task in EXPECTED_TASKS:
            for method in EXPECTED_METHODS:
                entry = f6[panel][task][method]
                assert math.isfinite(entry["mean"])
                assert entry["std"] >= 0
