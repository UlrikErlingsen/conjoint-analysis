"""Regenerate the fictional example datasets. All records are synthetic."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _make_ratings(
    seed: int,
    respondents: int,
    profiles_per_respondent: int,
    segments: list[tuple[float, dict[str, dict[str, float]]]],
    heterogeneity: float,
    noise: float,
    base_rating: float,
) -> pd.DataFrame:
    """Ratings from one or more latent preference segments with known true part-worths."""
    rng = np.random.default_rng(seed)
    attributes = list(segments[0][1])
    full_factorial = [[]]
    for attribute in attributes:
        full_factorial = [profile + [level] for profile in full_factorial for level in segments[0][1][attribute]]
    full_factorial = np.array(full_factorial, dtype=object)

    weights = np.array([weight for weight, _ in segments], dtype=float)
    weights = weights / weights.sum()

    rows = []
    for respondent_index in range(respondents):
        respondent = f"R{respondent_index + 1:04d}"
        segment_partworths = segments[rng.choice(len(segments), p=weights)][1]
        personal = {
            attribute: {
                level: value + rng.normal(0, heterogeneity)
                for level, value in segment_partworths[attribute].items()
            }
            for attribute in attributes
        }
        chosen = rng.choice(len(full_factorial), size=profiles_per_respondent, replace=False)
        for profile in full_factorial[chosen]:
            utility = base_rating + sum(personal[a][level] for a, level in zip(attributes, profile))
            rating = int(np.clip(round(utility + rng.normal(0, noise)), 1, 10))
            rows.append({"respondent_id": respondent, **dict(zip(attributes, profile)), "rating": rating})
    return pd.DataFrame(rows)


def coffee_demo() -> pd.DataFrame:
    return _make_ratings(
        seed=7,
        respondents=300,
        profiles_per_respondent=14,
        segments=[
            (
                1.0,
                {
                    "brand": {"Arabica Hills": 0.5, "Nordic Roast": 0.2, "Casa Verde": -0.7},
                    "price_per_month": {"$14": 1.5, "$19": 0.1, "$24": -1.6},
                    "beans": {"Single origin": 0.4, "House blend": -0.4},
                    "delivery": {"Weekly": 0.6, "Every two weeks": 0.3, "Monthly": -0.9},
                },
            )
        ],
        heterogeneity=0.5,
        noise=0.9,
        base_rating=5.6,
    )


def cars_demo() -> pd.DataFrame:
    """Two latent segments: value seekers (60%) and eco enthusiasts (40%)."""
    return _make_ratings(
        seed=17,
        respondents=350,
        profiles_per_respondent=16,
        segments=[
            (
                0.6,
                {
                    "brand_origin": {"Domestic": 0.5, "European": -0.1, "Asian": -0.4},
                    "body_type": {"Sedan": 0.4, "SUV": 0.2, "Compact": -0.6},
                    "engine": {"Petrol": 0.5, "Hybrid": 0.2, "Electric": -0.7},
                    "price": {"$25,000": 1.8, "$35,000": -0.2, "$45,000": -1.6},
                },
            ),
            (
                0.4,
                {
                    "brand_origin": {"Domestic": -0.3, "European": 0.5, "Asian": -0.2},
                    "body_type": {"Sedan": -0.3, "SUV": 0.6, "Compact": -0.3},
                    "engine": {"Petrol": -1.6, "Hybrid": 0.5, "Electric": 1.1},
                    "price": {"$25,000": 0.6, "$35,000": 0.1, "$45,000": -0.7},
                },
            ),
        ],
        heterogeneity=0.5,
        noise=0.9,
        base_rating=5.5,
    )


def streaming_demo() -> pd.DataFrame:
    return _make_ratings(
        seed=11,
        respondents=150,
        profiles_per_respondent=12,
        segments=[
            (
                1.0,
                {
                    "monthly_price": {"$8": 1.2, "$12": 0.0, "$16": -1.2},
                    "video_quality": {"4K": 0.8, "HD": -0.8},
                    "ads": {"No ads": 1.0, "Some ads": -1.0},
                    "simultaneous_screens": {"1 screen": -0.6, "2 screens": 0.1, "4 screens": 0.5},
                },
            )
        ],
        heterogeneity=0.6,
        noise=1.0,
        base_rating=5.4,
    )


def concept_demo() -> pd.DataFrame:
    """Purchase-intent answers from 260 fictional respondents about one cold-brew subscription concept."""
    rng = np.random.default_rng(23)
    labels = [
        "Definitely would buy",
        "Probably would buy",
        "Might or might not buy",
        "Probably would not buy",
        "Definitely would not buy",
    ]
    # (segment, share of sample, probabilities for the five boxes best-to-worst)
    segments = [
        ("Coffee enthusiasts", 0.30, [0.26, 0.34, 0.22, 0.12, 0.06]),
        ("Busy professionals", 0.45, [0.12, 0.28, 0.30, 0.20, 0.10]),
        ("Occasional drinkers", 0.25, [0.04, 0.12, 0.26, 0.32, 0.26]),
    ]
    reasons = [
        "Too expensive for what it is",
        "Happy with my current coffee routine",
        "Worried it will not taste fresh",
        "Too much packaging waste",
        "Do not drink cold coffee",
    ]
    segment_names = [name for name, _, _ in segments]
    segment_weights = np.array([weight for _, weight, _ in segments])
    box_probabilities = {name: probabilities for name, _, probabilities in segments}
    rows = []
    for index in range(260):
        segment = segment_names[rng.choice(len(segments), p=segment_weights / segment_weights.sum())]
        intent = rng.choice(5, p=box_probabilities[segment])  # 0 = best box
        reason = ""
        if intent >= 2 and rng.random() < 0.8:  # below the top two boxes, most give a reason
            reason = reasons[rng.choice(len(reasons))]
            if rng.random() < 0.25:
                second = reasons[rng.choice(len(reasons))]
                if second != reason:
                    reason = f"{reason}; {second}"
        rows.append(
            {
                "respondent_id": f"C{index + 1:04d}",
                "segment": segment,
                "purchase_intent": labels[intent],
                "rejection_reason": reason,
            }
        )
    return pd.DataFrame(rows)


def concept_template() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "respondent_id": ["R0001", "R0002", "R0003"],
            "segment": ["Segment A", "Segment B", "Segment A"],
            "purchase_intent": ["Definitely would buy", "Might or might not buy", "Probably would not buy"],
            "rejection_reason": ["", "Too expensive", "Too expensive; No need for it"],
        }
    )


def template() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "respondent_id": ["R0001", "R0001", "R0002"],
            "brand": ["Brand A", "Brand B", "Brand A"],
            "price": ["$10", "$15", "$15"],
            "warranty": ["1 year", "2 years", "2 years"],
            "rating": [7, 4, 8],
        }
    )


if __name__ == "__main__":
    EXAMPLES.mkdir(exist_ok=True)
    coffee_demo().to_csv(EXAMPLES / "demo_coffee_ratings.csv", index=False)
    cars_demo().to_csv(EXAMPLES / "demo_car_ratings.csv", index=False)
    streaming_demo().to_csv(EXAMPLES / "demo_streaming_ratings.csv", index=False)
    concept_demo().to_csv(EXAMPLES / "demo_concept_test.csv", index=False)
    template().to_csv(EXAMPLES / "ratings_template.csv", index=False)
    concept_template().to_csv(EXAMPLES / "concept_template.csv", index=False)
    print("Wrote example files to", EXAMPLES)
