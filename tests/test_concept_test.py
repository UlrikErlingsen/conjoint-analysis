"""Tests for the single-concept purchase-intent module.

Expected values are derived by hand inside this file from the published
formulas, so the tests are independent of the implementation.
"""

import json
import math

import pandas as pd
import pytest

from choicesignal.concept_test import (
    DEFAULT_TRIAL_WEIGHTS,
    EXPORT_SCHEMA,
    box_summary,
    intent_table,
    parse_intent_value,
    prepare_concept,
    rejection_summary,
    segment_table,
    trial_estimate,
    trial_intention_export,
    wilson_interval,
)
from choicesignal.errors import DataProblem


def _frame(intents, reasons=None, segments=None, ids=None):
    frame = pd.DataFrame({"rid": ids or [f"R{i}" for i in range(len(intents))], "intent": intents})
    if reasons is not None:
        frame["reason"] = reasons
    if segments is not None:
        frame["segment"] = segments
    return frame


def test_parse_recognizes_labels_numbers_and_reversals():
    assert parse_intent_value("Definitely would buy") == 5
    assert parse_intent_value("probably would buy") == 4
    assert parse_intent_value("Might or might not buy") == 3
    assert parse_intent_value("Probably would NOT buy") == 2
    assert parse_intent_value("definitely wouldn't buy") == 1
    assert parse_intent_value("Very likely") == 4
    assert parse_intent_value("unlikely") == 2
    assert parse_intent_value("maybe") == 3
    assert parse_intent_value(5) == 5
    assert parse_intent_value("2") == 2
    assert parse_intent_value(1, reversed_numeric=True) == 5
    assert parse_intent_value("5", reversed_numeric=True) == 1
    assert parse_intent_value("no idea what this is") is None
    assert parse_intent_value(7) is None
    assert parse_intent_value(2.5) is None
    assert parse_intent_value(None) is None
    assert parse_intent_value(float("nan")) is None
    assert parse_intent_value(True) is None


def test_prepare_excludes_unparseable_and_duplicates_with_warnings():
    frame = _frame(
        ["Definitely would buy", "banana", "3", "Probably would buy"],
        ids=["A", "B", "C", "C"],
    )
    data = prepare_concept(frame, "rid", "intent")
    assert data.n == 2  # banana excluded, duplicate C kept once
    assert sorted(data.frame["respondent"]) == ["A", "C"]
    assert any("not recognized" in warning for warning in data.warnings)
    assert any("duplicate" in warning.lower() for warning in data.warnings)


def test_prepare_rejects_fully_unreadable_intent():
    with pytest.raises(DataProblem):
        prepare_concept(_frame(["x", "y"]), "rid", "intent")


def test_prepare_rejects_reused_columns():
    with pytest.raises(DataProblem):
        prepare_concept(_frame(["5"]), "rid", "rid")


def test_wilson_interval_matches_hand_computation():
    # p = 0.5, n = 10, z = 1.96: center and margin computed from the published formula.
    z = 1.959963984540054
    n, p = 10, 0.5
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    margin = (z / denominator) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(center - margin)
    assert high == pytest.approx(center + margin)
    # Bounds stay inside [0, 1] even at the extremes.
    assert wilson_interval(0, 8)[0] == 0.0
    assert wilson_interval(8, 8)[1] == 1.0


def test_intent_table_and_box_summary_add_up():
    data = prepare_concept(_frame(["5", "5", "4", "3", "2", "1"]), "rid", "intent")
    table = intent_table(data)
    assert list(table["intent_code"]) == [5, 4, 3, 2, 1]
    assert table["respondents"].sum() == 6
    assert table["share_%"].sum() == pytest.approx(100.0)
    summary = box_summary(data)
    assert summary["top_box"]["share_%"] == pytest.approx(100 * 2 / 6, abs=0.01)
    assert summary["top_two_box"]["share_%"] == pytest.approx(100 * 3 / 6, abs=0.01)
    assert summary["bottom_two_box"]["respondents"] == 2


def test_trial_estimate_is_the_weighted_box_sum():
    data = prepare_concept(_frame(["5", "5", "4", "3", "2", "1"]), "rid", "intent")
    trial = trial_estimate(data, {5: 0.8, 4: 0.3, 3: 0.1})
    expected = 100 * (0.8 * 2 / 6 + 0.3 * 1 / 6 + 0.1 * 1 / 6)
    assert trial["weighted_trial_%"] == pytest.approx(expected, abs=0.01)
    assert trial["ceiling_top_two_box_%"] == pytest.approx(100 * 3 / 6, abs=0.01)
    assert trial["weighted_trial_%"] <= trial["ceiling_top_two_box_%"]
    with pytest.raises(DataProblem):
        trial_estimate(data, {5: 1.4})


def test_rejection_reasons_split_multi_mentions_and_skip_buyers():
    data = prepare_concept(
        _frame(
            ["5", "4", "3", "2", "1", "1"],
            reasons=["should be ignored", "", "Too expensive", "Too expensive; No need", "No need | Too expensive", ""],
        ),
        "rid",
        "intent",
        reason_column="reason",
    )
    table, meta = rejection_summary(data)
    assert meta["rejecters"] == 4  # codes 3, 2, 1, 1
    assert meta["rejecters_with_reason"] == 3
    counts = dict(zip(table["reason"], table["mentions"]))
    assert counts == {"Too expensive": 3, "No need": 2}
    assert table.iloc[0]["reason"] == "Too expensive"


def test_segment_table_flags_small_groups():
    intents = ["5"] * 30 + ["1"] * 30 + ["4"] * 3
    segments = ["Big A"] * 30 + ["Big B"] * 30 + ["Tiny"] * 3
    data = prepare_concept(_frame(intents, segments=segments), "rid", "intent", segment_column="segment")
    table, warnings = segment_table(data)
    assert len(table) == 3
    assert table.iloc[0]["segment"] == "Big A"  # sorted by top-two-box share
    assert table.iloc[0]["top_two_box_%"] == pytest.approx(100.0)
    assert any("Tiny" in warning for warning in warnings)
    assert not any("Big A" in warning for warning in warnings)


def test_export_is_json_serializable_and_complete():
    data = prepare_concept(
        _frame(["5", "4", "3", "2"], segments=["A", "A", "B", "B"]),
        "rid",
        "intent",
        segment_column="segment",
    )
    payload = trial_intention_export(data, "  Cold brew  ", None, "9.9.9", "demo.csv")
    round_trip = json.loads(json.dumps(payload, allow_nan=False))
    assert round_trip["schema"] == EXPORT_SCHEMA
    assert round_trip["concept"] == "Cold brew"
    assert round_trip["respondents"] == 4
    assert len(round_trip["boxes"]) == 5
    assert round_trip["trial_assumption"]["weights"]["Definitely would buy"] == DEFAULT_TRIAL_WEIGHTS[5]
    assert {segment["segment"] for segment in round_trip["segments"]} == {"A", "B"}
    assert "ATR" in round_trip["caution"] or "awareness" in round_trip["caution"]
