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
    true_partworths: dict[str, dict[str, float]],
    heterogeneity: float,
    noise: float,
    base_rating: float,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    attributes = list(true_partworths)
    full_factorial = [[]]
    for attribute in attributes:
        full_factorial = [profile + [level] for profile in full_factorial for level in true_partworths[attribute]]
    full_factorial = np.array(full_factorial, dtype=object)

    rows = []
    for respondent_index in range(respondents):
        respondent = f"R{respondent_index + 1:04d}"
        personal = {
            attribute: {
                level: value + rng.normal(0, heterogeneity)
                for level, value in true_partworths[attribute].items()
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
        respondents=200,
        profiles_per_respondent=14,
        true_partworths={
            "brand": {"Arabica Hills": 0.5, "Nordic Roast": 0.2, "Casa Verde": -0.7},
            "price_per_month": {"$14": 1.5, "$19": 0.1, "$24": -1.6},
            "beans": {"Single origin": 0.4, "House blend": -0.4},
            "delivery": {"Weekly": 0.6, "Every two weeks": 0.3, "Monthly": -0.9},
        },
        heterogeneity=0.5,
        noise=0.9,
        base_rating=5.6,
    )


def streaming_demo() -> pd.DataFrame:
    return _make_ratings(
        seed=11,
        respondents=150,
        profiles_per_respondent=12,
        true_partworths={
            "monthly_price": {"$8": 1.2, "$12": 0.0, "$16": -1.2},
            "video_quality": {"4K": 0.8, "HD": -0.8},
            "ads": {"No ads": 1.0, "Some ads": -1.0},
            "simultaneous_screens": {"1 screen": -0.6, "2 screens": 0.1, "4 screens": 0.5},
        },
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
    streaming_demo().to_csv(EXAMPLES / "demo_streaming_ratings.csv", index=False)
    template().to_csv(EXAMPLES / "ratings_template.csv", index=False)
    print("Wrote example files to", EXAMPLES)
