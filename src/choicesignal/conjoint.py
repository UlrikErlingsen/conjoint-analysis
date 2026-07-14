"""Ratings-based conjoint estimation with effects coding, plus preference simulators."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .errors import DataProblem

MAX_LEVELS_PER_ATTRIBUTE = 12
MAX_ATTRIBUTES = 10
MAX_ROWS = 500_000
MAX_SEARCH_CELLS = 20_000_000


@dataclass
class ConjointDesign:
    """Validated column roles and the level structure of the study."""

    respondent_column: str
    rating_column: str
    attribute_columns: tuple[str, ...]
    levels: dict[str, list[str]]

    @property
    def parameter_count(self) -> int:
        return 1 + sum(len(levels) - 1 for levels in self.levels.values())


@dataclass
class ConjointResult:
    """Estimated part-worths, importances, and fit diagnostics."""

    partworths: pd.DataFrame
    importance: pd.DataFrame
    individual: pd.DataFrame
    fit: pd.DataFrame
    pooled_partworths: pd.DataFrame
    pooled_r_squared: float
    mean_rating: float
    method: str
    warnings: list[str] = field(default_factory=list)


def build_design(
    frame: pd.DataFrame,
    respondent_column: str,
    rating_column: str,
    attribute_columns: list[str],
) -> ConjointDesign:
    """Validate the study columns and freeze the attribute-level structure."""
    if len(frame) > MAX_ROWS:
        raise DataProblem(f"This release supports up to {MAX_ROWS:,} rating rows.")
    for column in [respondent_column, rating_column, *attribute_columns]:
        if column not in frame.columns:
            raise DataProblem(f"The column “{column}” is not in the file.")
    if len({respondent_column, rating_column, *attribute_columns}) != 2 + len(attribute_columns):
        raise DataProblem("Respondent, rating, and attribute columns must all be different columns.")
    if not attribute_columns:
        raise DataProblem("Choose at least one attribute column.")
    if len(attribute_columns) > MAX_ATTRIBUTES:
        raise DataProblem(f"This release supports up to {MAX_ATTRIBUTES} attributes.")

    ratings = pd.to_numeric(frame[rating_column], errors="coerce")
    if ratings.notna().sum() < 10:
        raise DataProblem(f"The rating column “{rating_column}” needs at least 10 numeric values.")
    if ratings.nunique() < 3:
        raise DataProblem(
            f"The rating column “{rating_column}” has almost no variation, so preferences cannot be estimated."
        )

    levels: dict[str, list[str]] = {}
    for column in attribute_columns:
        observed = frame[column].astype(str).str.strip()
        unique = sorted(observed.dropna().unique().tolist())
        unique = [level for level in unique if level not in ("", "nan")]
        if len(unique) < 2:
            raise DataProblem(f"The attribute “{column}” needs at least 2 different levels.")
        if len(unique) > MAX_LEVELS_PER_ATTRIBUTE:
            raise DataProblem(
                f"The attribute “{column}” has {len(unique)} levels; this release supports up to "
                f"{MAX_LEVELS_PER_ATTRIBUTE}. Numeric measurements should be grouped into a few levels first."
            )
        levels[column] = unique
    return ConjointDesign(
        respondent_column=respondent_column,
        rating_column=rating_column,
        attribute_columns=tuple(attribute_columns),
        levels=levels,
    )


def _effects_matrix(frame: pd.DataFrame, design: ConjointDesign) -> tuple[np.ndarray, list[tuple[str, str]]]:
    """Effects-coded design matrix (+1 own level, -1 reference level, 0 otherwise)."""
    columns: list[np.ndarray] = [np.ones(len(frame))]
    names: list[tuple[str, str]] = [("_intercept", "_intercept")]
    for attribute in design.attribute_columns:
        observed = frame[attribute].astype(str).str.strip().to_numpy()
        levels = design.levels[attribute]
        reference = levels[-1]
        for level in levels[:-1]:
            encoded = np.where(observed == level, 1.0, np.where(observed == reference, -1.0, 0.0))
            columns.append(encoded)
            names.append((attribute, level))
    return np.column_stack(columns), names


def _partworths_from_coefficients(
    coefficients: np.ndarray, names: list[tuple[str, str]], design: ConjointDesign
) -> pd.DataFrame:
    rows = []
    for attribute in design.attribute_columns:
        indices = [i for i, (a, _) in enumerate(names) if a == attribute]
        betas = coefficients[indices]
        for (a, level), beta in zip([names[i] for i in indices], betas):
            rows.append({"attribute": a, "level": level, "partworth": float(beta)})
        rows.append({"attribute": attribute, "level": design.levels[attribute][-1], "partworth": float(-betas.sum())})
    return pd.DataFrame(rows)


def design_report(frame: pd.DataFrame, design: ConjointDesign) -> tuple[pd.DataFrame, list[str]]:
    """Level exposure counts and honest design warnings before estimation."""
    warnings: list[str] = []
    rows = []
    for attribute in design.attribute_columns:
        observed = frame[attribute].astype(str).str.strip()
        counts = observed.value_counts()
        for level in design.levels[attribute]:
            rows.append({"attribute": attribute, "level": level, "times_shown": int(counts.get(level, 0))})
    report = pd.DataFrame(rows)
    smallest = report["times_shown"].min()
    if smallest < 5:
        warnings.append(
            "Some attribute levels appear fewer than 5 times, so their part-worth estimates will be unstable."
        )
    imbalance = report.groupby("attribute")["times_shown"].agg(lambda s: s.max() / max(s.min(), 1))
    if (imbalance > 3).any():
        unbalanced = ", ".join(imbalance[imbalance > 3].index)
        warnings.append(
            f"Levels are shown very unevenly for: {unbalanced}. Unbalanced designs make estimates less reliable."
        )

    matrix, _ = _effects_matrix(frame, design)
    if np.linalg.matrix_rank(matrix) < design.parameter_count:
        raise DataProblem(
            "Two or more attributes are perfectly confounded in this data (they always change together), "
            "so their effects cannot be separated. Revise the design or drop one of the confounded attributes."
        )

    duplicated = frame.duplicated(subset=[design.respondent_column, *design.attribute_columns]).sum()
    if duplicated:
        warnings.append(
            f"{duplicated:,} rows repeat the same profile for the same respondent; repeated ratings are averaged "
            "implicitly by the model."
        )
    profiles_per_respondent = frame.groupby(design.respondent_column).size()
    if (profiles_per_respondent < design.parameter_count).any():
        share = float((profiles_per_respondent < design.parameter_count).mean())
        warnings.append(
            f"{share:.0%} of respondents rated fewer profiles than the model needs "
            f"({design.parameter_count}), so their individual preferences cannot be estimated."
        )
    return report, warnings


def estimate_conjoint(frame: pd.DataFrame, design: ConjointDesign, minimum_individual_share: float = 0.3) -> ConjointResult:
    """Estimate part-worth utilities per respondent, with a pooled fallback."""
    working = frame[[design.respondent_column, design.rating_column, *design.attribute_columns]].copy()
    working[design.rating_column] = pd.to_numeric(working[design.rating_column], errors="coerce")
    dropped = int(working[design.rating_column].isna().sum())
    working = working.dropna(subset=[design.rating_column])
    warnings: list[str] = []
    if dropped:
        warnings.append(f"{dropped:,} rows without a numeric rating were excluded.")
    if len(working) < design.parameter_count + 2:
        raise DataProblem("There are not enough rated profiles to estimate this design.")

    pooled_matrix, names = _effects_matrix(working, design)
    ratings = working[design.rating_column].to_numpy(dtype=float)
    pooled_coefficients, *_ = np.linalg.lstsq(pooled_matrix, ratings, rcond=None)
    pooled_predictions = pooled_matrix @ pooled_coefficients
    total_variance = float(((ratings - ratings.mean()) ** 2).sum())
    pooled_r_squared = 1 - float(((ratings - pooled_predictions) ** 2).sum()) / total_variance if total_variance > 0 else float("nan")
    pooled_partworths = _partworths_from_coefficients(pooled_coefficients[1:], names[1:], design)

    individual_rows: list[pd.DataFrame] = []
    fit_rows: list[dict[str, object]] = []
    for respondent, group in working.groupby(design.respondent_column, sort=False):
        matrix, _ = _effects_matrix(group, design)
        estimable = len(group) >= design.parameter_count and np.linalg.matrix_rank(matrix) == design.parameter_count
        r_squared = np.nan
        intercept = np.nan
        if estimable:
            coefficients, *_ = np.linalg.lstsq(matrix, group[design.rating_column].to_numpy(dtype=float), rcond=None)
            intercept = float(coefficients[0])
            person = _partworths_from_coefficients(coefficients[1:], names[1:], design)
            person.insert(0, "respondent", respondent)
            individual_rows.append(person)
            observed = group[design.rating_column].to_numpy(dtype=float)
            predictions = matrix @ coefficients
            person_variance = float(((observed - observed.mean()) ** 2).sum())
            if person_variance > 0:
                r_squared = 1 - float(((observed - predictions) ** 2).sum()) / person_variance
        fit_rows.append(
            {
                "respondent": respondent,
                "profiles_rated": len(group),
                "estimable": bool(estimable),
                "r_squared": float(r_squared) if np.isfinite(r_squared) else np.nan,
                "intercept": intercept,
            }
        )
    fit = pd.DataFrame(fit_rows)

    individual = pd.concat(individual_rows, ignore_index=True) if individual_rows else pd.DataFrame(
        columns=["respondent", "attribute", "level", "partworth"]
    )
    estimable_share = float(fit["estimable"].mean()) if len(fit) else 0.0

    if individual_rows and estimable_share >= minimum_individual_share:
        method = "individual"
        aggregated = (
            individual.groupby(["attribute", "level"], sort=False)["partworth"]
            .agg(partworth="mean", spread_std="std")
            .reset_index()
        )
        aggregated["respondents"] = int(fit["estimable"].sum())
        importance = _importance_from_individual(individual)
        if estimable_share < 1:
            warnings.append(
                f"Individual preferences could be estimated for {estimable_share:.0%} of respondents; "
                "the others are excluded from the averages below but remain in the pooled model."
            )
    else:
        method = "pooled"
        aggregated = pooled_partworths.copy()
        aggregated["spread_std"] = np.nan
        aggregated["respondents"] = len(fit)
        importance = _importance_from_partworths(pooled_partworths)
        warnings.append(
            "Too few respondents rated enough profiles for individual estimation, so results come from one pooled "
            "model. Differences between respondents are invisible in this mode and the simulator is unavailable."
        )

    return ConjointResult(
        partworths=aggregated,
        importance=importance,
        individual=individual,
        fit=fit,
        pooled_partworths=pooled_partworths,
        pooled_r_squared=pooled_r_squared,
        mean_rating=float(ratings.mean()),
        method=method,
        warnings=warnings,
    )


def _importance_from_partworths(partworths: pd.DataFrame) -> pd.DataFrame:
    ranges = partworths.groupby("attribute", sort=False)["partworth"].agg(lambda s: s.max() - s.min())
    total = float(ranges.sum())
    importance = (100 * ranges / total if total > 0 else ranges * np.nan).reset_index()
    importance.columns = ["attribute", "importance_%"]
    importance["spread_std"] = np.nan
    return importance.sort_values("importance_%", ascending=False).reset_index(drop=True)


def _importance_from_individual(individual: pd.DataFrame) -> pd.DataFrame:
    per_person = []
    for respondent, person in individual.groupby("respondent", sort=False):
        ranges = person.groupby("attribute", sort=False)["partworth"].agg(lambda s: s.max() - s.min())
        total = float(ranges.sum())
        if total > 0:
            per_person.append(100 * ranges / total)
    stacked = pd.concat(per_person, axis=1)
    importance = pd.DataFrame(
        {"attribute": stacked.index, "importance_%": stacked.mean(axis=1).values, "spread_std": stacked.std(axis=1).values}
    )
    return importance.sort_values("importance_%", ascending=False).reset_index(drop=True)


def _utility_components(result: ConjointResult, design: ConjointDesign):
    """Per-respondent intercepts and one (respondents × levels) matrix per attribute."""
    if result.individual.empty:
        raise DataProblem("This needs individual estimates; the analysis only produced a pooled model.")
    respondents = result.individual["respondent"].unique()
    intercepts = (
        result.fit.set_index("respondent")["intercept"].reindex(respondents).fillna(result.mean_rating).to_numpy()
    )
    lookup = result.individual.set_index(["respondent", "attribute", "level"])["partworth"]
    matrices: dict[str, np.ndarray] = {}
    for attribute in design.attribute_columns:
        matrices[attribute] = np.column_stack(
            [
                lookup.loc[[(respondent, attribute, level) for respondent in respondents]].to_numpy()
                for level in design.levels[attribute]
            ]
        )
    return respondents, intercepts, matrices


def _product_utilities(
    products: dict[str, dict[str, str]],
    design: ConjointDesign,
    intercepts: np.ndarray,
    matrices: dict[str, np.ndarray],
) -> np.ndarray:
    utilities = np.repeat(intercepts[:, None], len(products), axis=1)
    for product_index, (product_name, profile) in enumerate(products.items()):
        for attribute in design.attribute_columns:
            if profile.get(attribute) not in design.levels[attribute]:
                raise DataProblem(f"“{product_name}” needs a valid level for “{attribute}”.")
            level_index = design.levels[attribute].index(profile[attribute])
            utilities[:, product_index] += matrices[attribute][:, level_index]
    return utilities


def simulate_shares(
    result: ConjointResult, products: dict[str, dict[str, str]], design: ConjointDesign
) -> pd.DataFrame:
    """Preference shares for user-defined products under three classic choice rules.

    First choice: each respondent 'chooses' their highest-utility product (ties
    split equally). Share of preference: utility-proportional split (negative
    utilities count as zero appeal). Logit: a Bradley–Terry–Luce rule on the
    rating-scale utilities — its softness depends on the rating scale, so read
    it as a sensitivity check.
    """
    if len(products) < 2:
        raise DataProblem("Define at least two products to compare.")
    respondents, intercepts, matrices = _utility_components(result, design)
    utilities = _product_utilities(products, design, intercepts, matrices)

    best = utilities.max(axis=1, keepdims=True)
    winners = np.isclose(utilities, best)
    first_choice = 100 * (winners / winners.sum(axis=1, keepdims=True)).mean(axis=0)

    positive = np.clip(utilities, 0, None)
    row_totals = positive.sum(axis=1, keepdims=True)
    equal_split = np.full_like(positive, 1 / positive.shape[1])
    proportional = np.where(row_totals > 0, positive / np.where(row_totals == 0, 1, row_totals), equal_split)
    share_of_preference = 100 * proportional.mean(axis=0)

    exponentials = np.exp(utilities - best)
    logit = 100 * (exponentials / exponentials.sum(axis=1, keepdims=True)).mean(axis=0)

    return pd.DataFrame(
        {
            "product": list(products.keys()),
            "first_choice_share_%": np.round(first_choice, 1),
            "share_of_preference_%": np.round(share_of_preference, 1),
            "logit_share_%": np.round(logit, 1),
            "mean_predicted_rating": np.round(utilities.mean(axis=0), 2),
        }
    )


def adjust_shares(shares: pd.DataFrame, factors: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """Weight preference shares by awareness × availability and renormalize.

    ``factors`` maps product name to (awareness, availability) in percent.
    A customer cannot prefer a product they never see: this classic adjustment
    multiplies each share by both factors before renormalizing to 100%.
    """
    adjusted = shares.copy()
    weights = np.array(
        [
            (factors.get(product, (100.0, 100.0))[0] / 100) * (factors.get(product, (100.0, 100.0))[1] / 100)
            for product in adjusted["product"]
        ]
    )
    if (weights < 0).any() or (weights > 1).any():
        raise DataProblem("Awareness and availability must be between 0 and 100 percent.")
    for column in ("first_choice_share_%", "share_of_preference_%", "logit_share_%"):
        raw = adjusted[column].to_numpy(dtype=float) * weights
        total = raw.sum()
        adjusted[column] = np.round(100 * raw / total, 1) if total > 0 else np.nan
    adjusted["awareness_%"] = [factors.get(product, (100.0, 100.0))[0] for product in adjusted["product"]]
    adjusted["availability_%"] = [factors.get(product, (100.0, 100.0))[1] for product in adjusted["product"]]
    return adjusted.drop(columns=["mean_predicted_rating"], errors="ignore")


def cannibalization_report(
    result: ConjointResult,
    products: dict[str, dict[str, str]],
    new_product: str,
    design: ConjointDesign,
    rule: str = "first_choice_share_%",
) -> pd.DataFrame:
    """Where a new product's share comes from: incumbent shares with vs without it."""
    if new_product not in products:
        raise DataProblem("Choose which of the defined products is the new entrant.")
    incumbents = {name: profile for name, profile in products.items() if name != new_product}
    if len(incumbents) < 2:
        raise DataProblem("Cannibalization needs at least two incumbent products besides the new entrant.")
    before = simulate_shares(result, incumbents, design).set_index("product")[rule]
    after_frame = simulate_shares(result, products, design).set_index("product")[rule]
    rows = []
    for name in incumbents:
        rows.append(
            {
                "product": name,
                "share_before_%": float(before[name]),
                "share_after_%": float(after_frame[name]),
                "change_points": round(float(after_frame[name] - before[name]), 1),
                "relative_change_%": round(100 * (after_frame[name] - before[name]) / before[name], 1)
                if before[name] > 0
                else np.nan,
            }
        )
    rows.append(
        {
            "product": f"{new_product} (new)",
            "share_before_%": 0.0,
            "share_after_%": float(after_frame[new_product]),
            "change_points": round(float(after_frame[new_product]), 1),
            "relative_change_%": np.nan,
        }
    )
    return pd.DataFrame(rows)


def optimal_products(
    result: ConjointResult,
    design: ConjointDesign,
    competitors: dict[str, dict[str, str]] | None = None,
    top_n: int = 5,
) -> pd.DataFrame:
    """Search every possible attribute combination for the best product design.

    With competitors, candidates are ranked by first-choice share against that
    set; without, by mean predicted rating. The search is exhaustive over the
    full factorial of tested levels.
    """
    respondents, intercepts, matrices = _utility_components(result, design)
    level_counts = [len(design.levels[attribute]) for attribute in design.attribute_columns]
    total_candidates = int(np.prod(level_counts))
    if total_candidates * len(respondents) > MAX_SEARCH_CELLS:
        raise DataProblem(
            f"The full search would evaluate {total_candidates:,} designs × {len(respondents):,} respondents, "
            "which is beyond this release's limit. Reduce the number of attributes or levels."
        )

    utilities = intercepts[:, None]
    for attribute in design.attribute_columns:
        utilities = (utilities[:, :, None] + matrices[attribute][:, None, :]).reshape(len(respondents), -1)

    if competitors:
        competitor_utilities = _product_utilities(competitors, design, intercepts, matrices)
        competitor_best = competitor_utilities.max(axis=1, keepdims=True)
        wins = (utilities > competitor_best).mean(axis=0)
        ties = 0.5 * np.isclose(utilities, competitor_best).mean(axis=0)
        scores = 100 * (wins + ties)
        score_column = "first_choice_share_vs_competitors_%"
    else:
        scores = utilities.mean(axis=0)
        score_column = "mean_predicted_rating"

    order = np.argsort(scores)[::-1][: max(1, top_n)]
    combos = list(itertools.product(*[design.levels[attribute] for attribute in design.attribute_columns]))
    rows = []
    for rank, index in enumerate(order, start=1):
        row: dict[str, object] = {"rank": rank}
        row.update(dict(zip(design.attribute_columns, combos[index])))
        row[score_column] = round(float(scores[index]), 1 if competitors else 2)
        row["mean_predicted_rating"] = round(float(utilities[:, index].mean()), 2)
        rows.append(row)
    return pd.DataFrame(rows)


def ideal_products(result: ConjointResult, design: ConjointDesign, top_n: int = 3) -> pd.DataFrame:
    """The most common per-respondent favorite combination of levels."""
    respondents, _, matrices = _utility_components(result, design)
    picks = []
    for attribute in design.attribute_columns:
        best_indices = matrices[attribute].argmax(axis=1)
        picks.append([design.levels[attribute][index] for index in best_indices])
    combos = pd.Series(list(zip(*picks)))
    counts = combos.value_counts().head(max(1, top_n))
    rows = []
    for combo, count in counts.items():
        row = dict(zip(design.attribute_columns, combo))
        row["respondents"] = int(count)
        row["share_%"] = round(100 * count / len(respondents), 1)
        rows.append(row)
    return pd.DataFrame(rows)
