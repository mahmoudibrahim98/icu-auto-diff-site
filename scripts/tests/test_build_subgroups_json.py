"""Tests for build_subgroups_json.py."""
from pathlib import Path
import json

import pytest

from scripts.build_subgroups_json import (
    build_subgroups,
    METHOD_MAP,
    decode_subgroup,
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
    assert "timediff" in cell["methods"]
    # Each present method has error + CI.
    assert set(cell["methods"]["timeautodiff"].keys()) == {"error", "ci"}


def test_error_is_abs_deviation_from_groundtruth_mean():
    out = build_subgroups(csv_path=FIXTURE, data_task="eicu_mortality24")
    cell = out["eicu_mortality24"]["age_<30"]["male"]["white"]
    # oracle mean ≈ (0.810+0.814+0.812+0.816+0.808)/5 = 0.812
    # timeautodiff mean ≈ 0.761 → error ≈ |0.812 - 0.761| = 0.051
    assert cell["methods"]["timeautodiff"]["error"] == pytest.approx(0.051, abs=1e-3)


def test_fail_loud_on_unknown_method_id(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "subgroup,evaluated_on,model,synth_data_index,auroc\n"
        "0_0_0,oracle,0,0,0.8\n"
        "0_0_0,synthetic_mystery_method,9,0,0.5\n"
    )
    with pytest.raises(KeyError, match="9"):
        build_subgroups(csv_path=bad, data_task="eicu_mortality24")


def test_missing_methods_marked_not_exported():
    # eicu_los24 has no CSV → all cells mark all methods "not_exported".
    out = build_subgroups(
        csv_path=None,
        data_task="eicu_los24",
    )
    cell = out["eicu_los24"]["age_<30"]["male"]["white"]
    assert cell["methods"]["timeautodiff"] == {"status": "not_exported"}
