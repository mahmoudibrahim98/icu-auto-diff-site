"""Tests for build_subgroups_json.py."""
from pathlib import Path
import json

import pytest

from scripts.build_subgroups_json import (
    build_subgroups,
    decode_subgroup,
    EVALUATED_ON_TO_METHOD,
)


FIXTURE = Path(__file__).parent / "fixtures" / "subgroups_mini.csv"


def test_decode_subgroup_to_triple():
    assert decode_subgroup("0_0_0") == ("male", "white", "age_<30")
    assert decode_subgroup("1_3_3") == ("female", "other", "age_>70")


def test_build_subgroups_schema(tmp_path):
    out = build_subgroups(
        csv_path=FIXTURE,
        data_task="eicu_mortality24",
    )
    # Shape: { data_task: { age: { sex: { ethnicity: {...} } } } }
    root = out["eicu_mortality24"]
    cell = root["age_<30"]["male"]["white"]
    assert "n_real" in cell
    assert "auroc_groundtruth" in cell
    assert "auroc_groundtruth_ci" in cell
    assert "methods" in cell
    assert "test" in cell["methods"]
    assert "timeautodiff" in cell["methods"]
    # enhanced_timeautodiff should also be present from the fixture
    assert "enhanced_timeautodiff" in cell["methods"]
    # Each present method has error + CI.
    assert set(cell["methods"]["timeautodiff"].keys()) == {"error", "ci"}


def test_error_is_abs_deviation_from_groundtruth_mean():
    out = build_subgroups(csv_path=FIXTURE, data_task="eicu_mortality24")
    cell = out["eicu_mortality24"]["age_<30"]["male"]["white"]
    # oracle mean = (0.810+0.814+0.812+0.816+0.808)/5 = 0.812
    # synthetic_timeautodiff_baseline mean = (0.760+0.762+0.761+0.759+0.763)/5 = 0.761
    # error = |0.812 - 0.761| = 0.051
    assert cell["methods"]["timeautodiff"]["error"] == pytest.approx(0.051, abs=1e-3)


def test_fail_loud_on_unknown_evaluated_on(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "subgroup,evaluated_on,evaluation_size,subgroup_size,test_oracle_random_state,"
        "synth_data_index,model,auroc,auprc,sens,spec,bacc_sens,f1_sens,tp,tn,fp,fn,"
        "sens_opt,spec_opt,bacc_opt,f1_opt,tp_opt,tn_opt,fp_opt,fn_opt\n"
        "0_0_0,oracle,500,100,42,0,0,0.8,0.5,0.8,0.7,0.75,0.4,80,70,30,20,0.75,0.75,0.75,0.45,75,75,25,25\n"
        "0_0_0,synthetic_mystery_method,500,100,42,0,9,0.5,0.3,0.5,0.5,0.5,0.3,50,50,50,50,0.5,0.5,0.5,0.3,50,50,50,50\n"
    )
    with pytest.raises(KeyError, match="synthetic_mystery_method"):
        build_subgroups(csv_path=bad, data_task="eicu_mortality24")


def test_missing_methods_marked_not_exported():
    # eicu_los24 has no CSV → all cells mark all methods "not_exported".
    out = build_subgroups(
        csv_path=None,
        data_task="eicu_los24",
    )
    cell = out["eicu_los24"]["age_<30"]["male"]["white"]
    assert cell["methods"]["timeautodiff"] == {"status": "not_exported"}


def test_timediff_from_dir_b_fixture(tmp_path):
    """Dir B CSV with synthetic_timediff rows should populate timediff method."""
    csv_b = tmp_path / "all_results_eicu_mortality24.csv"
    header = (
        "subgroup,evaluated_on,evaluation_size,subgroup_size,test_oracle_random_state,"
        "synth_data_index,model,auroc,auprc,sens,spec,bacc_sens,f1_sens,tp,tn,fp,fn,"
        "sens_opt,spec_opt,bacc_opt,f1_opt,tp_opt,tn_opt,fp_opt,fn_opt\n"
    )
    def row(sg, eon, model, idx, auroc):
        return f"{sg},{eon},500,100,42,{idx},{model},{auroc},0.5,0.8,0.7,0.75,0.4,80,70,30,20,0.75,0.75,0.75,0.45,75,75,25,25\n"

    lines = header
    for i in range(5):
        lines += row("0_0_0", "oracle", 0, i, 0.80)
        lines += row("0_0_0", "test", 0, i, 0.75)
        lines += row("0_0_0", "synthetic_timediff", 2, i, 0.78)
        lines += row("0_0_0", "random_all_subgroups", 3, i, 0.70)  # should be ignored
    csv_b.write_text(lines)

    out = build_subgroups(csv_path=None, data_task="eicu_mortality24", csv_path_b=csv_b)
    cell = out["eicu_mortality24"]["age_<30"]["male"]["white"]
    assert "error" in cell["methods"]["timediff"]
    assert cell["methods"]["healthgen"] == {"status": "not_exported"}
