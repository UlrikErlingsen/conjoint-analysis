"""Ratings-based conjoint estimation with effects coding, plus preference simulators."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .errors import DataProblem
from .limits import active, demo_limit

# Above this many levels an attribute is probably an ungrouped measurement; run locally the app warns, the
# public demo refuses (limits.py).
ADVISED_LEVELS_PER_ATTRIBUTE = 12
# The optimal-design search is exhaustive: designs × respondents grows combinatorially with attributes and levels.
# Utilities are scored in blocks of this many cells, and a search beyond EXHAUSTIVE_SEARCH_CELLS is refused
# because it would run for hours, not because of memory.
SEARCH_BLOCK_CELLS = 20_000_000
EXHAUSTIVE_SEARCH_CELLS = 5_000_000_000
# Respondents are estimated together in blocks of about this many design-matrix cells.
ESTIMATION_BLOCK_CELLS = 4_000_000


def _clean_levels(series: pd.Series) -> np.ndarray:
    """``series.astype(str).str.strip()`` as an array, stripping each distinct value once."""
    codes, uniques = pd.factorize(series.astype(str), sort=False)
    stripped = np.asarray(pd.Index(uniques).str.strip(), dtype=object)
    return stripped[codes]


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
    rating_floor: float = 0.0
    warnings: list[str] = field(default_factory=list)


def build_design(
    frame: pd.DataFrame,
    respondent_column: str,
    rating_column: str,
    attribute_columns: list[str],
) -> ConjointDesign:
    """Validate the study columns and freeze the attribute-level structure."""
    limits = active()
    if limits.rating_rows is not None and len(frame) > limits.rating_rows:
        raise DataProblem(demo_limit(f"The demo analyzes up to {limits.rating_rows:,} rating rows."))
    for column in [respondent_column, rating_column, *attribute_columns]:
        if column not in frame.columns:
            raise DataProblem(f"The column “{column}” is not in the file.")
    if len({respondent_column, rating_column, *attribute_columns}) != 2 + len(attribute_columns):
        raise DataProblem("Respondent, rating, and attribute columns must all be different columns.")
    if not attribute_columns:
        raise DataProblem("Choose at least one attribute column.")
    if limits.attributes is not None and len(attribute_columns) > limits.attributes:
        raise DataProblem(demo_limit(f"The demo supports up to {limits.attributes} attributes."))

    ratings = pd.to_numeric(frame[rating_column], errors="coerce")
    if ratings.notna().sum() < 10:
        raise DataProblem(f"The rating column “{rating_column}” needs at least 10 numeric values.")
    if ratings.nunique() < 3:
        raise DataProblem(
            f"The rating column “{rating_column}” has almost no variation, so preferences cannot be estimated."
        )

    levels: dict[str, list[str]] = {}
    for column in attribute_columns:
        unique = sorted(pd.unique(_clean_levels(frame[column])).tolist())
        unique = [level for level in unique if level not in ("", "nan")]
        if len(unique) < 2:
            raise DataProblem(f"The attribute “{column}” needs at least 2 different levels.")
        if limits.levels_per_attribute is not None and len(unique) > limits.levels_per_attribute:
            raise DataProblem(
                demo_limit(
                    f"The attribute “{column}” has {len(unique)} levels; the demo supports up to "
                    f"{limits.levels_per_attribute}. Numeric measurements should be grouped into a few levels first."
                )
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
        observed = _clean_levels(frame[attribute])
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
        counts = pd.Series(_clean_levels(frame[attribute])).value_counts()
        for level in design.levels[attribute]:
            rows.append({"attribute": attribute, "level": level, "times_shown": int(counts.get(level, 0))})
    report = pd.DataFrame(rows)
    many_levels = [
        attribute for attribute in design.attribute_columns if len(design.levels[attribute]) > ADVISED_LEVELS_PER_ATTRIBUTE
    ]
    if many_levels:
        warnings.append(
            f"These attributes have more than {ADVISED_LEVELS_PER_ATTRIBUTE} levels: {', '.join(many_levels)}. "
            "If they are measurements such as exact prices, group them into a few levels first; every level adds a "
            "parameter each respondent must rate enough profiles to estimate."
        )
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
    minimum_needed = design.parameter_count + 1
    if (profiles_per_respondent < minimum_needed).any():
        share = float((profiles_per_respondent < minimum_needed).mean())
        warnings.append(
            f"{share:.0%} of respondents rated fewer than {minimum_needed} profiles (the model's "
            f"{design.parameter_count} parameters plus one), so their individual preferences cannot be estimated."
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
    unknown_level = pd.Series(False, index=working.index)
    for attribute in design.attribute_columns:
        observed = pd.Series(_clean_levels(working[attribute]), index=working.index)
        unknown_level |= ~observed.isin(design.levels[attribute])
    excluded_levels = int(unknown_level.sum())
    if excluded_levels:
        working = working[~unknown_level]
        warnings.append(
            f"{excluded_levels:,} rows with missing or unrecognized attribute levels were excluded — "
            "treating them as an 'average' level would bias the part-worths."
        )
    if len(working) < design.parameter_count + 2:
        raise DataProblem("There are not enough rated profiles to estimate this design.")

    # Pooled reference model with respondent fixed effects (within transformation):
    # demeaning ratings and design columns per respondent means differences in
    # rating style (a generous vs strict scale use) cannot masquerade as
    # attribute effects when respondents saw different profile subsets.
    pooled_matrix, names = _effects_matrix(working, design)
    ratings = working[design.rating_column].to_numpy(dtype=float)
    respondents_index = working[design.respondent_column]
    attribute_frame = pd.DataFrame(pooled_matrix[:, 1:], index=working.index)
    attribute_within = (attribute_frame - attribute_frame.groupby(respondents_index).transform("mean")).to_numpy()
    rating_series = pd.Series(ratings, index=working.index)
    ratings_within = (rating_series - rating_series.groupby(respondents_index).transform("mean")).to_numpy()
    pooled_coefficients, *_ = np.linalg.lstsq(attribute_within, ratings_within, rcond=None)
    within_predictions = attribute_within @ pooled_coefficients
    within_variance = float((ratings_within**2).sum())
    pooled_r_squared = (
        1 - float(((ratings_within - within_predictions) ** 2).sum()) / within_variance
        if within_variance > 0
        else float("nan")
    )
    pooled_partworths = _partworths_from_coefficients(pooled_coefficients, names[1:], design)

    individual, fit = _individual_models(working, design, pooled_matrix, ratings, names)
    individual_rows = not individual.empty
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
        rating_floor=float(ratings.min()),
        warnings=warnings,
    )


def _individual_models(
    working: pd.DataFrame,
    design: ConjointDesign,
    matrix: np.ndarray,
    ratings: np.ndarray,
    names: list[tuple[str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One effects-coded regression per respondent, solved for many respondents at once.

    Respondents who rated the same number of profiles are stacked into one array (rank checks and fit statistics
    run on whole blocks); each respondent's coefficients come from the same least-squares call as before.
    Respondents keep their first-appearance order.
    """
    parameters = design.parameter_count
    codes, respondents = pd.factorize(working[design.respondent_column], sort=False)
    order = np.argsort(codes, kind="stable")
    counts = np.bincount(codes, minlength=len(respondents))
    starts = np.concatenate(([0], np.cumsum(counts)[:-1]))
    estimable = np.zeros(len(respondents), dtype=bool)
    r_squared = np.full(len(respondents), np.nan)
    intercept = np.full(len(respondents), np.nan)
    coefficients = np.full((len(respondents), parameters), np.nan)
    sorted_matrix = matrix[order]
    sorted_ratings = ratings[order]
    for size in np.unique(counts):
        members = np.flatnonzero(counts == size)
        # Strictly more ratings than parameters: a saturated model has zero residual degrees of freedom, fits
        # noise exactly (R² = 1), and yields unstable utilities.
        if size < parameters + 1:
            continue
        block = max(1, ESTIMATION_BLOCK_CELLS // (int(size) * parameters))
        for begin in range(0, len(members), block):
            chunk = members[begin : begin + block]
            rows = starts[chunk][:, None] + np.arange(size)[None, :]
            stacked = sorted_matrix[rows]  # respondents × profiles × parameters
            observed = sorted_ratings[rows]
            full_rank = np.linalg.matrix_rank(stacked) == parameters
            if not full_rank.any():
                continue
            chunk, stacked, observed = chunk[full_rank], stacked[full_rank], observed[full_rank]
            # The same LAPACK least-squares call as fitting one respondent at a time, so estimates are unchanged.
            solution = np.vstack(
                [np.linalg.lstsq(stacked[index], observed[index], rcond=None)[0] for index in range(len(chunk))]
            )
            predictions = np.vstack([stacked[index] @ solution[index] for index in range(len(chunk))])
            variance = ((observed - observed.mean(axis=1, keepdims=True)) ** 2).sum(axis=1)
            residual = ((observed - predictions) ** 2).sum(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                r_squared[chunk] = np.where(variance > 0, 1 - residual / variance, np.nan)
            estimable[chunk] = True
            coefficients[chunk] = solution
            intercept[chunk] = solution[:, 0]
    fit = pd.DataFrame(
        {
            "respondent": np.asarray(respondents),
            "profiles_rated": counts.astype(int),
            "estimable": estimable,
            "r_squared": np.where(np.isfinite(r_squared), r_squared, np.nan),
            "intercept": intercept,
        }
    )
    fitted = np.flatnonzero(estimable)
    if not len(fitted):
        return pd.DataFrame(columns=["respondent", "attribute", "level", "partworth"]), fit
    # Part-worths per respondent, attribute by attribute: the coded levels, then the reference level as minus
    # their sum, exactly as _partworths_from_coefficients lays them out.
    attribute_names = names[1:]
    blocks: list[np.ndarray] = []
    labels: list[tuple[str, str]] = []
    for attribute in design.attribute_columns:
        indices = [index for index, (name, _) in enumerate(attribute_names) if name == attribute]
        betas = coefficients[fitted][:, [index + 1 for index in indices]]
        blocks.append(betas)
        blocks.append(-betas.sum(axis=1, keepdims=True))
        labels.extend(attribute_names[index] for index in indices)
        labels.append((attribute, design.levels[attribute][-1]))
    values = np.hstack(blocks)
    level_count = len(labels)
    individual = pd.DataFrame(
        {
            "respondent": np.repeat(np.asarray(respondents)[fitted], level_count),
            "attribute": np.tile(np.asarray([label[0] for label in labels], dtype=object), len(fitted)),
            "level": np.tile(np.asarray([label[1] for label in labels], dtype=object), len(fitted)),
            "partworth": values.ravel().astype(float),
        }
    )
    return individual, fit


def _importance_from_partworths(partworths: pd.DataFrame) -> pd.DataFrame:
    ranges = partworths.groupby("attribute", sort=False)["partworth"].agg(lambda s: s.max() - s.min())
    total = float(ranges.sum())
    importance = (100 * ranges / total if total > 0 else ranges * np.nan).reset_index()
    importance.columns = ["attribute", "importance_%"]
    importance["spread_std"] = np.nan
    return importance.sort_values("importance_%", ascending=False).reset_index(drop=True)


def _importance_from_individual(individual: pd.DataFrame) -> pd.DataFrame:
    grouped = individual.groupby(["respondent", "attribute"], sort=False)["partworth"]
    ranges = (grouped.max() - grouped.min()).unstack("attribute")
    attributes = list(dict.fromkeys(individual["attribute"]))
    ranges = ranges[attributes]
    totals = ranges.sum(axis=1)
    shares = 100 * ranges[totals > 0].div(totals[totals > 0], axis=0)
    importance = pd.DataFrame(
        {"attribute": attributes, "importance_%": shares.mean(axis=0).values, "spread_std": shares.std(axis=0).values}
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
    level_count = sum(len(design.levels[attribute]) for attribute in design.attribute_columns)
    values = result.individual["partworth"].to_numpy(dtype=float)
    expected_labels = [(attribute, level) for attribute in design.attribute_columns for level in design.levels[attribute]]
    if (
        len(values) == level_count * len(respondents)
        and np.array_equal(result.individual["respondent"].to_numpy()[::level_count], respondents)
        and list(zip(result.individual["attribute"].iloc[:level_count], result.individual["level"].iloc[:level_count]))
        == expected_labels
    ):
        # The usual layout (one block of every level per respondent): reshape instead of millions of lookups.
        wide = values.reshape(len(respondents), level_count)
        matrices = {}
        start = 0
        for attribute in design.attribute_columns:
            width = len(design.levels[attribute])
            matrices[attribute] = wide[:, start : start + width]
            start += width
        return respondents, intercepts, matrices
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
    split equally). Share of preference: split in proportion to how far each
    product's predicted rating sits above the study's lowest observed rating —
    anchoring at the observed floor makes the rule invariant to shifting the
    whole rating scale (an arbitrary-origin problem the naive utility-
    proportional rule suffers from). Logit: a Bradley–Terry–Luce rule whose
    softness depends on the rating-scale units, so read it as a sensitivity
    check.
    """
    if len(products) < 2:
        raise DataProblem("Define at least two products to compare.")
    respondents, intercepts, matrices = _utility_components(result, design)
    utilities = _product_utilities(products, design, intercepts, matrices)

    best = utilities.max(axis=1, keepdims=True)
    winners = np.isclose(utilities, best)
    first_choice = 100 * (winners / winners.sum(axis=1, keepdims=True)).mean(axis=0)

    positive = np.clip(utilities - result.rating_floor, 0, None)
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
    """Search every attribute combination for the highest stated-preference design.

    With competitors, candidates are ranked by first-choice share against that
    set; without, by mean predicted rating. The search is exhaustive over the
    full factorial of tested levels — it optimizes stated preference only;
    costs, margins, and feasibility are outside the search.
    """
    respondents, intercepts, matrices = _utility_components(result, design)
    level_counts = [len(design.levels[attribute]) for attribute in design.attribute_columns]
    total_candidates = int(np.prod(level_counts))
    cells = total_candidates * len(respondents)
    demo_cap = active().search_cells
    if demo_cap is not None and cells > demo_cap:
        raise DataProblem(
            demo_limit(
                f"The full search would evaluate {total_candidates:,} designs × {len(respondents):,} respondents; "
                f"the demo stops at {demo_cap:,}. Reduce the number of attributes or levels."
            )
        )
    if cells > EXHAUSTIVE_SEARCH_CELLS:
        raise DataProblem(
            f"The full search would evaluate {total_candidates:,} designs × {len(respondents):,} respondents "
            f"({cells:,} utilities). An exhaustive search grows with every added level and would run for hours; "
            "fix some attributes at their likely level, or test fewer levels."
        )

    competitor_best = None
    if competitors:
        competitor_utilities = _product_utilities(competitors, design, intercepts, matrices)
        competitor_best = competitor_utilities.max(axis=1, keepdims=True)
    # Designs are numbered like itertools.product over the levels (the last attribute changes fastest) and scored
    # in blocks of designs, so memory stays bounded however large the search is.
    strides = np.cumprod([1, *level_counts[::-1]])[::-1][1:]
    block = max(1, SEARCH_BLOCK_CELLS // max(len(respondents), 1))
    scores = np.empty(total_candidates)
    mean_ratings = np.empty(total_candidates)
    for begin in range(0, total_candidates, block):
        candidates = np.arange(begin, min(begin + block, total_candidates))
        utilities = np.repeat(intercepts[:, None], len(candidates), axis=1)
        for attribute, count, stride in zip(design.attribute_columns, level_counts, strides):
            utilities = utilities + matrices[attribute][:, (candidates // stride) % count]
        if competitor_best is not None:
            wins = (utilities > competitor_best).mean(axis=0)
            ties = 0.5 * np.isclose(utilities, competitor_best).mean(axis=0)
            scores[candidates] = 100 * (wins + ties)
        mean_ratings[candidates] = utilities.mean(axis=0)
    if competitor_best is None:
        scores = mean_ratings
    score_column = "first_choice_share_vs_competitors_%" if competitors else "mean_predicted_rating"

    order = np.argsort(scores)[::-1][: max(1, top_n)]
    rows = []
    for rank, index in enumerate(order, start=1):
        combo = [
            design.levels[attribute][(int(index) // int(stride)) % count]
            for attribute, count, stride in zip(design.attribute_columns, level_counts, strides)
        ]
        row: dict[str, object] = {"rank": rank}
        row.update(dict(zip(design.attribute_columns, combo)))
        row[score_column] = round(float(scores[index]), 1 if competitors else 2)
        row["mean_predicted_rating"] = round(float(mean_ratings[index]), 2)
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
