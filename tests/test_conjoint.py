from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from choicesignal.conjoint import (
    ConjointDesign,
    build_design,
    design_report,
    estimate_conjoint,
    simulate_shares,
)
from choicesignal.errors import DataProblem
from choicesignal.io import load_data


ROOT = Path(__file__).parents[1]

TRUE_COFFEE = {
    "brand": {"Arabica Hills": 0.5, "Nordic Roast": 0.2, "Casa Verde": -0.7},
    "price_per_month": {"$14": 1.5, "$19": 0.1, "$24": -1.6},
    "beans": {"Single origin": 0.4, "House blend": -0.4},
    "delivery": {"Weekly": 0.6, "Every two weeks": 0.3, "Monthly": -0.9},
}


def _coffee_frame() -> pd.DataFrame:
    return load_data(ROOT / "examples" / "demo_coffee_ratings.csv").tables["ratings"]


def _coffee_design(frame: pd.DataFrame) -> ConjointDesign:
    return build_design(frame, "respondent_id", "rating", ["brand", "price_per_month", "beans", "delivery"])


def test_recovers_known_partworths_from_demo_data():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    result = estimate_conjoint(frame, design)
    assert result.method == "individual"
    truth, estimated = [], []
    for attribute, level_values in TRUE_COFFEE.items():
        centered = {level: value - np.mean(list(level_values.values())) for level, value in level_values.items()}
        for level, value in centered.items():
            truth.append(value)
            row = result.partworths[
                (result.partworths["attribute"] == attribute) & (result.partworths["level"] == level)
            ]
            estimated.append(float(row["partworth"].iloc[0]))
    assert np.corrcoef(truth, estimated)[0, 1] > 0.97
    assert result.importance.iloc[0]["attribute"] == "price_per_month"
    assert result.pooled_r_squared > 0.4


def test_partworths_are_zero_centered_per_attribute():
    frame = _coffee_frame()
    result = estimate_conjoint(frame, _coffee_design(frame))
    sums = result.partworths.groupby("attribute")["partworth"].sum()
    assert np.allclose(sums, 0, atol=1e-8)
    importances = result.importance["importance_%"]
    assert np.isclose(importances.sum(), 100, atol=0.01)


def test_pooled_fallback_when_respondents_rate_too_few_profiles():
    frame = _coffee_frame().groupby("respondent_id").head(3).reset_index(drop=True)
    result = estimate_conjoint(frame, _coffee_design(frame))
    assert result.method == "pooled"
    assert any("pooled" in warning for warning in result.warnings)
    assert result.individual.empty


def test_confounded_attributes_are_rejected():
    frame = _coffee_frame()
    frame["shadow"] = frame["brand"]
    design = build_design(frame, "respondent_id", "rating", ["brand", "shadow"])
    with pytest.raises(DataProblem, match="confounded"):
        design_report(frame, design)


def test_design_validation_errors_are_friendly():
    frame = _coffee_frame()
    with pytest.raises(DataProblem, match="not in the file"):
        build_design(frame, "respondent_id", "rating", ["missing_column"])
    with pytest.raises(DataProblem, match="at least 2 different levels"):
        constant = frame.assign(constant="same")
        build_design(constant, "respondent_id", "rating", ["constant"])
    with pytest.raises(DataProblem, match="must all be different"):
        build_design(frame, "respondent_id", "rating", ["rating"])


def test_simulator_prefers_the_dominant_product():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    result = estimate_conjoint(frame, design)
    products = {
        "Premium cheap": {
            "brand": "Arabica Hills", "price_per_month": "$14", "beans": "Single origin", "delivery": "Weekly",
        },
        "Weak expensive": {
            "brand": "Casa Verde", "price_per_month": "$24", "beans": "House blend", "delivery": "Monthly",
        },
    }
    shares = simulate_shares(result.individual, products, design)
    assert np.isclose(shares["first_choice_share_%"].sum(), 100, atol=0.1)
    assert np.isclose(shares["share_of_preference_%"].sum(), 100, atol=0.1)
    dominant = shares[shares["product"] == "Premium cheap"].iloc[0]
    assert dominant["first_choice_share_%"] > 85
    assert dominant["share_of_preference_%"] > 60


def test_simulator_requires_individual_estimates_and_valid_levels():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    result = estimate_conjoint(frame, design)
    with pytest.raises(DataProblem, match="at least two products"):
        simulate_shares(result.individual, {"Only one": {}}, design)
    with pytest.raises(DataProblem, match="valid level"):
        simulate_shares(
            result.individual,
            {"A": {"brand": "Nope", "price_per_month": "$14", "beans": "Single origin", "delivery": "Weekly"},
             "B": {"brand": "Casa Verde", "price_per_month": "$24", "beans": "House blend", "delivery": "Monthly"}},
            design,
        )
    empty = result.individual.iloc[0:0]
    with pytest.raises(DataProblem, match="individual estimates"):
        simulate_shares(empty, {"A": {}, "B": {}}, design)


def test_design_report_flags_rare_levels():
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(
        {
            "respondent_id": np.repeat([f"R{i}" for i in range(30)], 8),
            "color": rng.choice(["red", "blue"], size=240),
            "size": ["small"] * 238 + ["large"] * 2,
            "rating": rng.integers(1, 11, size=240),
        }
    )
    design = build_design(frame, "respondent_id", "rating", ["color", "size"])
    report, warnings = design_report(frame, design)
    assert set(report.columns) == {"attribute", "level", "times_shown"}
    assert any("fewer than 5" in warning for warning in warnings)
