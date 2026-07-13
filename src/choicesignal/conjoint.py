"""Ratings-based conjoint estimation with effects coding, plus a preference-share simulator."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .errors import DataProblem

MAX_LEVELS_PER_ATTRIBUTE = 12
MAX_ATTRIBUTES = 10
MAX_ROWS = 500_000


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
        if estimable:
            coefficients, *_ = np.linalg.lstsq(matrix, group[design.rating_column].to_numpy(dtype=float), rcond=None)
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


def simulate_shares(
    individual: pd.DataFrame, products: dict[str, dict[str, str]], design: ConjointDesign
) -> pd.DataFrame:
    """Preference shares for user-defined products from individual part-worths.

    First-choice: each respondent 'chooses' their highest-utility product (ties
    split equally). Share-of-preference: a Bradley–Terry–Luce (logit) rule on
    the rating-scale utilities, reported as a sensitivity check.
    """
    if individual.empty:
        raise DataProblem("The simulator needs individual estimates; this analysis only produced a pooled model.")
    if len(products) < 2:
        raise DataProblem("Define at least two products to compare.")
    for product_name, profile in products.items():
        for attribute in design.attribute_columns:
            if profile.get(attribute) not in design.levels[attribute]:
                raise DataProblem(f"“{product_name}” needs a valid level for “{attribute}”.")

    lookup = individual.set_index(["respondent", "attribute", "level"])["partworth"]
    respondents = individual["respondent"].unique()
    utilities = np.zeros((len(respondents), len(products)))
    for product_index, profile in enumerate(products.values()):
        for attribute, level in profile.items():
            utilities[:, product_index] += lookup.loc[
                [(respondent, attribute, level) for respondent in respondents]
            ].to_numpy()

    best = utilities.max(axis=1, keepdims=True)
    winners = np.isclose(utilities, best)
    first_choice = 100 * (winners / winners.sum(axis=1, keepdims=True)).mean(axis=0)

    exponentials = np.exp(utilities - best)
    logit = 100 * (exponentials / exponentials.sum(axis=1, keepdims=True)).mean(axis=0)

    return pd.DataFrame(
        {
            "product": list(products.keys()),
            "first_choice_share_%": np.round(first_choice, 1),
            "share_of_preference_%": np.round(logit, 1),
            "mean_utility": np.round(utilities.mean(axis=0), 2),
        }
    )
