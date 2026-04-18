"""Tests for extract_paper_numbers.py.

The extractor reads camera-ready.pdf and produces a dict of the paper's
numeric values (Fig 7 per-Data×Task errors, Table 2 percentages,
Fig 6 / Table 1 global gaps). Tests assert the known ground-truth values
from Section 5.2 / 5.3 of the paper.
"""
from pathlib import Path
import json

import pytest

from scripts.extract_paper_numbers import extract_results


FIXTURE = Path(__file__).parent / "fixtures" / "camera-ready.pdf"


def test_figure7_subgroup_mean_errors():
    r = extract_results(FIXTURE)
    # Paper Section 5.3: "on eICU LOS24 the mean error drops from
    # 0.044 (Test) to 0.039 (TimeAutoDiff), 0.033 (TimeDiff),
    # and 0.028 (Enhanced TimeAutoDiff)"
    assert r["figure7"]["eicu_los24"] == {
        "test": 0.044,
        "timeautodiff": 0.039,
        "timediff": 0.033,
        "enhanced_timeautodiff": 0.028,
    }
    assert r["figure7"]["eicu_mortality24"] == {
        "test": 0.075,
        "timeautodiff": 0.061,
        "timediff": 0.056,
        "enhanced_timeautodiff": 0.050,
    }
    assert r["figure7"]["mimic_mortality24"] == {
        "test": 0.142,
        "timeautodiff": 0.081,
        "timediff": 0.088,
        "enhanced_timeautodiff": 0.081,
    }
    assert r["figure7"]["mimic_los24"] == {
        "test": 0.067,
        "timeautodiff": 0.043,
        "timediff": 0.049,
        "enhanced_timeautodiff": 0.042,
    }


def test_table2_percentages():
    r = extract_results(FIXTURE)
    assert r["table2"]["eicu_mortality24"] == {"ta": 48, "td": 60, "ta_plus": 76}
    assert r["table2"]["eicu_los24"] == {"ta": 44, "td": 52, "ta_plus": 72}
    assert r["table2"]["mimic_mortality24"] == {"ta": 68, "td": 68, "ta_plus": 84}
    assert r["table2"]["mimic_los24"] == {"ta": 72, "td": 56, "ta_plus": 76}


def test_table1_example_rows():
    r = extract_results(FIXTURE)
    assert r["table1"]["eicu_los24_timeautodiff"] == {
        "delta_tstr": 0.010, "delta_tstr_err": 0.002,
        "delta_trts": 0.026, "delta_trts_err": 0.002,
    }
    assert r["table1"]["eicu_mortality24_timediff"] == {
        "delta_tstr": 0.003, "delta_tstr_err": 0.002,
        "delta_trts": 0.019, "delta_trts_err": 0.003,
    }


def test_emits_deterministic_json(tmp_path):
    from scripts.extract_paper_numbers import main
    out = tmp_path / "results.json"
    main(["--pdf", str(FIXTURE), "--out", str(out)])
    assert out.exists()
    loaded = json.loads(out.read_text())
    assert set(loaded.keys()) >= {"figure7", "figure6_health_gen_ranges",
                                  "table1", "table2", "meta"}
    assert loaded["meta"]["source_pdf"].endswith("camera-ready.pdf")
