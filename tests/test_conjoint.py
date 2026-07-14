from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from choicesignal.conjoint import (
    ConjointDesign,
    adjust_shares,
    build_design,
    cannibalization_report,
    design_report,
    estimate_conjoint,
    ideal_products,
    optimal_products,
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


STRONG_COFFEE = {
    "brand": "Arabica Hills", "price_per_month": "$14", "beans": "Single origin", "delivery": "Weekly",
}
WEAK_COFFEE = {
    "brand": "Casa Verde", "price_per_month": "$24", "beans": "House blend", "delivery": "Monthly",
}


def test_simulator_prefers_the_dominant_product_under_all_three_rules():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    result = estimate_conjoint(frame, design)
    shares = simulate_shares(result, {"Premium cheap": STRONG_COFFEE, "Weak expensive": WEAK_COFFEE}, design)
    for column in ("first_choice_share_%", "share_of_preference_%", "logit_share_%"):
        assert np.isclose(shares[column].sum(), 100, atol=0.2)
        assert shares.set_index("product")[column]["Premium cheap"] > shares.set_index("product")[column]["Weak expensive"]
    dominant = shares.set_index("product").loc["Premium cheap"]
    assert dominant["first_choice_share_%"] > 85
    assert dominant["mean_predicted_rating"] > shares.set_index("product").loc["Weak expensive"]["mean_predicted_rating"]


def test_simulator_requires_individual_estimates_and_valid_levels():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    result = estimate_conjoint(frame, design)
    with pytest.raises(DataProblem, match="at least two products"):
        simulate_shares(result, {"Only one": {}}, design)
    with pytest.raises(DataProblem, match="valid level"):
        simulate_shares(
            result,
            {"A": {**STRONG_COFFEE, "brand": "Nope"}, "B": WEAK_COFFEE},
            design,
        )
    pooled_only = estimate_conjoint(frame.groupby("respondent_id").head(3).reset_index(drop=True), design)
    with pytest.raises(DataProblem, match="individual estimates"):
        simulate_shares(pooled_only, {"A": STRONG_COFFEE, "B": WEAK_COFFEE}, design)


def test_optimal_search_finds_the_true_best_design():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    result = estimate_conjoint(frame, design)
    best_without_competitors = optimal_products(result, design, competitors=None, top_n=3)
    top = best_without_competitors.iloc[0]
    for attribute, level_values in TRUE_COFFEE.items():
        assert top[attribute] == max(level_values, key=level_values.get)
    against = optimal_products(result, design, competitors={"Weak": WEAK_COFFEE, "Strong": STRONG_COFFEE}, top_n=3)
    assert "first_choice_share_vs_competitors_%" in against.columns
    assert against.iloc[0]["first_choice_share_vs_competitors_%"] >= against.iloc[-1]["first_choice_share_vs_competitors_%"]


def test_ideal_products_match_true_preferences():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    result = estimate_conjoint(frame, design)
    favorites = ideal_products(result, design, top_n=3)
    top = favorites.iloc[0]
    for attribute, level_values in TRUE_COFFEE.items():
        assert top[attribute] == max(level_values, key=level_values.get)
    assert favorites["share_%"].iloc[0] > 10


def test_adjust_shares_weights_and_renormalizes():
    shares = pd.DataFrame(
        {
            "product": ["A", "B"],
            "first_choice_share_%": [50.0, 50.0],
            "share_of_preference_%": [50.0, 50.0],
            "logit_share_%": [50.0, 50.0],
            "mean_predicted_rating": [5.0, 5.0],
        }
    )
    adjusted = adjust_shares(shares, {"A": (100.0, 100.0), "B": (50.0, 50.0)})
    row = adjusted.set_index("product")
    assert np.isclose(row.loc["A", "first_choice_share_%"], 80.0, atol=0.1)
    assert np.isclose(row.loc["B", "first_choice_share_%"], 20.0, atol=0.1)
    with pytest.raises(DataProblem, match="between 0 and 100"):
        adjust_shares(shares, {"A": (150.0, 100.0)})


def test_cannibalization_report_shows_where_share_comes_from():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    result = estimate_conjoint(frame, design)
    middling = {"brand": "Nordic Roast", "price_per_month": "$19", "beans": "Single origin", "delivery": "Weekly"}
    products = {"Flagship": STRONG_COFFEE, "Budget line": WEAK_COFFEE, "New mid-tier": middling}
    report = cannibalization_report(result, products, "New mid-tier", design)
    assert set(report["product"]) == {"Flagship", "Budget line", "New mid-tier (new)"}
    incumbents = report[report["product"] != "New mid-tier (new)"]
    assert (incumbents["change_points"] <= 0).all()
    new_row = report[report["product"] == "New mid-tier (new)"].iloc[0]
    assert new_row["share_after_%"] > 0
    with pytest.raises(DataProblem, match="new entrant"):
        cannibalization_report(result, products, "Not defined", design)


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


def test_share_of_preference_is_invariant_to_rating_scale_shift():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    shifted = frame.copy()
    shifted["rating"] = shifted["rating"] + 100
    products = {"Premium cheap": STRONG_COFFEE, "Weak expensive": WEAK_COFFEE}
    original = simulate_shares(estimate_conjoint(frame, design), products, design)
    moved = simulate_shares(estimate_conjoint(shifted, design), products, design)
    for column in ("first_choice_share_%", "share_of_preference_%", "logit_share_%"):
        assert np.allclose(original[column], moved[column], atol=0.2), column


def test_pooled_fixed_effects_ignore_rating_style_differences():
    rng = np.random.default_rng(31)
    # Two rater styles (base 3 vs base 8) with IDENTICAL preferences, and
    # unbalanced profile subsets so a single-intercept pooled model would leak
    # style into the attribute effects.
    rows = []
    for index in range(60):
        respondent = f"R{index:03d}"
        base = 3.0 if index % 2 == 0 else 8.0
        # generous raters mostly see brand A, strict raters mostly see brand B
        levels = ["A", "A", "B"] if base > 5 else ["B", "B", "A"]
        for level in levels:
            rating = base + (0.5 if level == "A" else -0.5) + rng.normal(0, 0.1)
            rows.append({"respondent_id": respondent, "brand": level, "rating": rating})
    frame = pd.DataFrame(rows)
    design = build_design(frame, "respondent_id", "rating", ["brand"])
    result = estimate_conjoint(frame, design)
    partworth_a = float(
        result.pooled_partworths.set_index("level").loc["A", "partworth"]
    )
    # True effect is +0.5 for A; a naive pooled intercept would report ~-2 here
    # because generous raters saw A more often.
    assert np.isclose(partworth_a, 0.5, atol=0.1)


def test_saturated_individual_models_are_not_estimable():
    frame = _coffee_frame()
    design = _coffee_design(frame)
    exactly_p = frame.groupby("respondent_id").head(design.parameter_count).reset_index(drop=True)
    result = estimate_conjoint(exactly_p, design)
    assert not result.fit["estimable"].any()
    assert result.method == "pooled"


def test_rows_with_missing_attribute_levels_are_excluded_with_warning():
    frame = _coffee_frame().copy()
    frame.loc[frame.index[:25], "brand"] = np.nan
    design = _coffee_design(_coffee_frame())
    result = estimate_conjoint(frame, design)
    assert any("missing or unrecognized attribute levels" in warning for warning in result.warnings)
    assert result.method == "individual"
