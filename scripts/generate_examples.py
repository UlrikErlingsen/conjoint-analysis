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
    template().to_csv(EXAMPLES / "ratings_template.csv", index=False)
    print("Wrote example files to", EXAMPLES)
