"""Single-concept purchase-intent testing: top-box analysis with honest trial assumptions."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

import numpy as np
import pandas as pd

from .errors import DataProblem

# The classic five-point purchase-intent scale, best to worst.
INTENT_LEVELS: list[tuple[int, str]] = [
    (5, "Definitely would buy"),
    (4, "Probably would buy"),
    (3, "Might or might not buy"),
    (2, "Probably would not buy"),
    (1, "Definitely would not buy"),
]
INTENT_LABELS: dict[int, str] = dict(INTENT_LEVELS)

# Illustrative starting weights for turning stated intent into an expected trial
# rate. Stated intentions overstate purchase, and the right discount is
# category-specific: calibrate against past launches rather than trusting any
# fixed rule (Jamieson & Bass 1989; Morwitz, Steckel & Gupta 2007).
DEFAULT_TRIAL_WEIGHTS: dict[int, float] = {5: 0.80, 4: 0.30, 3: 0.10, 2: 0.0, 1: 0.0}

SMALL_SEGMENT = 30
_REASON_SEPARATORS = re.compile(r"[;|]")
_Z_95 = 1.959963984540054  # standard-normal 97.5% quantile

EXPORT_SCHEMA = "signal.trial-intention.v1"


@dataclass(frozen=True)
class ConceptData:
    """One validated respondent-level concept test."""

    frame: pd.DataFrame  # columns: respondent, intent_code, intent_label, reason?, segment?
    warnings: list[str]

    @property
    def n(self) -> int:
        return len(self.frame)


def parse_intent_value(value: object, reversed_numeric: bool = False) -> int | None:
    """Map one response to an intent code 1–5 (5 = definitely would buy), or None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        number = float(value)
        if number.is_integer() and 1 <= number <= 5:
            code = int(number)
            return 6 - code if reversed_numeric else code
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "2", "3", "4", "5"}:
        code = int(text)
        return 6 - code if reversed_numeric else code
    negated = "not" in text or "n't" in text or "unlikely" in text
    if "might" in text or "maybe" in text or "unsure" in text or "undecided" in text or "neutral" in text:
        return 3
    if "definitely" in text or "certainly" in text or "surely" in text:
        return 1 if negated else 5
    if "probably" in text or "likely" in text:
        return 2 if negated else 4
    return None


def prepare_concept(
    frame: pd.DataFrame,
    respondent_column: str,
    intent_column: str,
    reason_column: str | None = None,
    segment_column: str | None = None,
    reversed_numeric: bool = False,
) -> ConceptData:
    """Validate and normalize a one-row-per-respondent concept-test table."""
    chosen = [respondent_column, intent_column, reason_column, segment_column]
    named = [column for column in chosen if column]
    if len(set(named)) != len(named):
        raise DataProblem("Each role needs its own column — the same column was selected twice.")
    for column in named:
        if column not in frame.columns:
            raise DataProblem(f"The column ‘{column}’ was not found in this table.")

    warnings: list[str] = []
    work = pd.DataFrame({"respondent": frame[respondent_column].astype(str).str.strip()})
    work["intent_code"] = [
        parse_intent_value(value, reversed_numeric) for value in frame[intent_column].tolist()
    ]
    if reason_column:
        work["reason"] = frame[reason_column].astype(str).str.strip()
    if segment_column:
        segment = frame[segment_column].astype(str).str.strip()
        work["segment"] = segment.where(segment.ne("") & segment.str.lower().ne("nan"), "(not recorded)")

    blank_ids = int((work["respondent"].eq("") | work["respondent"].str.lower().eq("nan")).sum())
    if blank_ids:
        warnings.append(f"{blank_ids} row(s) without a respondent ID were excluded.")
        work = work[~(work["respondent"].eq("") | work["respondent"].str.lower().eq("nan"))]

    unparsed = work["intent_code"].isna()
    if unparsed.any():
        examples = (
            frame.loc[work.index[unparsed], intent_column].astype(str).str.strip().replace("", "(empty)")
        )
        shown = ", ".join(f"‘{value}’" for value in pd.unique(examples)[:3])
        warnings.append(
            f"{int(unparsed.sum())} response(s) were not recognized as one of the five intent answers "
            f"and were excluded (for example {shown}). Accepted forms: the five standard labels, or the "
            "numbers 1–5 with 5 = definitely would buy."
        )
        work = work[~unparsed]
    if work.empty:
        raise DataProblem(
            "No responses could be read as purchase intent. Use the five standard labels "
            "(‘Definitely would buy’ … ‘Definitely would not buy’) or the numbers 1–5 "
            "with 5 = definitely would buy."
        )

    duplicates = int(work["respondent"].duplicated().sum())
    if duplicates:
        warnings.append(
            f"{duplicates} duplicate respondent ID(s) found; only each respondent's first answer was kept. "
            "A single-concept test expects one row per respondent."
        )
        work = work.drop_duplicates(subset="respondent", keep="first")

    work = work.reset_index(drop=True)
    work["intent_code"] = work["intent_code"].astype(int)
    work["intent_label"] = work["intent_code"].map(INTENT_LABELS)
    return ConceptData(frame=work, warnings=warnings)


def wilson_interval(successes: int, n: int, z: float = _Z_95) -> tuple[float, float]:
    """Wilson (1927) score interval for a binomial proportion, as fractions of 1."""
    if n <= 0:
        raise DataProblem("A confidence interval needs at least one respondent.")
    if not 0 <= successes <= n:
        raise DataProblem("The number of successes must lie between 0 and the sample size.")
    p = successes / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    margin = (z / denominator) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return max(0.0, center - margin), min(1.0, center + margin)


def intent_table(data: ConceptData) -> pd.DataFrame:
    """Respondent counts and shares per intent box, best box first, with Wilson 95% intervals."""
    n = data.n
    rows = []
    for code, label in INTENT_LEVELS:
        count = int((data.frame["intent_code"] == code).sum())
        low, high = wilson_interval(count, n)
        rows.append(
            {
                "intent_code": code,
                "intent": label,
                "respondents": count,
                "share_%": 100 * count / n,
                "wilson95_low_%": 100 * low,
                "wilson95_high_%": 100 * high,
            }
        )
    return pd.DataFrame(rows)


def box_summary(data: ConceptData) -> dict:
    """Top-box and top-two-box shares (in percent) with Wilson 95% intervals."""
    n = data.n
    summary: dict[str, object] = {"respondents": n}
    for name, codes in (("top_box", {5}), ("top_two_box", {5, 4}), ("bottom_two_box", {1, 2})):
        count = int(data.frame["intent_code"].isin(codes).sum())
        low, high = wilson_interval(count, n)
        summary[name] = {
            "respondents": count,
            "share_%": round(100 * count / n, 2),
            "wilson95_%": [round(100 * low, 2), round(100 * high, 2)],
        }
    return summary


def trial_estimate(data: ConceptData, weights: dict[int, float] | None = None) -> dict:
    """A weighted stated-trial estimate plus its unadjusted top-two-box ceiling."""
    used = dict(DEFAULT_TRIAL_WEIGHTS)
    used.update(weights or {})
    if set(used) != {1, 2, 3, 4, 5} or any(not 0 <= value <= 1 for value in used.values()):
        raise DataProblem("Trial weights need one value between 0 and 1 for each of the five intent boxes.")
    n = data.n
    shares = data.frame["intent_code"].value_counts()
    weighted = sum(used[code] * int(shares.get(code, 0)) / n for code in used)
    top_two = int(data.frame["intent_code"].isin({5, 4}).sum()) / n
    return {
        "weights": {INTENT_LABELS[code]: used[code] for code, _ in INTENT_LEVELS},
        "weighted_trial_%": round(100 * weighted, 2),
        "ceiling_top_two_box_%": round(100 * top_two, 2),
        "note": (
            "Stated intent overstates real trial. The weights are assumptions, not measurements: "
            "calibrate them to past launches in this category before using the estimate "
            "(Jamieson & Bass 1989; Morwitz, Steckel & Gupta 2007)."
        ),
    }


def rejection_summary(data: ConceptData) -> tuple[pd.DataFrame, dict]:
    """Reasons given by rejecters (everyone below the top two boxes), multi-mention aware."""
    if "reason" not in data.frame.columns:
        raise DataProblem("No rejection-reason column was selected.")
    rejecters = data.frame[data.frame["intent_code"] <= 3]
    mentions: dict[str, int] = {}
    with_reason = 0
    for raw in rejecters["reason"]:
        text = str(raw).strip()
        if not text or text.lower() == "nan":
            continue
        with_reason += 1
        for part in _REASON_SEPARATORS.split(text):
            reason = part.strip()
            if reason:
                mentions[reason] = mentions.get(reason, 0) + 1
    table = pd.DataFrame(
        {
            "reason": list(mentions),
            "mentions": list(mentions.values()),
        }
    ).sort_values(["mentions", "reason"], ascending=[False, True], ignore_index=True)
    if not table.empty:
        table["%_of_rejecters"] = (100 * table["mentions"] / len(rejecters)).round(1)
    meta = {
        "rejecters": int(len(rejecters)),
        "rejecters_with_reason": int(with_reason),
        "definition": "Rejecters are respondents below the top two boxes (codes 1–3).",
    }
    return table, meta


def segment_table(data: ConceptData) -> tuple[pd.DataFrame, list[str]]:
    """Per-segment top-box and top-two-box shares with Wilson 95% intervals."""
    if "segment" not in data.frame.columns:
        raise DataProblem("No segment column was selected.")
    warnings: list[str] = []
    rows = []
    for segment, group in data.frame.groupby("segment", sort=False):
        n = len(group)
        top = int((group["intent_code"] == 5).sum())
        top_two = int(group["intent_code"].isin({5, 4}).sum())
        top_low, top_high = wilson_interval(top, n)
        two_low, two_high = wilson_interval(top_two, n)
        rows.append(
            {
                "segment": segment,
                "respondents": n,
                "top_box_%": 100 * top / n,
                "top_two_box_%": 100 * top_two / n,
                "top_two_wilson95_low_%": 100 * two_low,
                "top_two_wilson95_high_%": 100 * two_high,
                "top_box_wilson95_low_%": 100 * top_low,
                "top_box_wilson95_high_%": 100 * top_high,
            }
        )
        if n < SMALL_SEGMENT:
            warnings.append(
                f"Segment ‘{segment}’ has only {n} respondent(s); its shares are very imprecise — "
                "lean on the intervals, not the point estimates."
            )
    table = pd.DataFrame(rows).sort_values("top_two_box_%", ascending=False, ignore_index=True)
    return table, warnings


def trial_intention_export(
    data: ConceptData,
    concept_name: str,
    weights: dict[int, float] | None,
    version: str,
    source: str | None = None,
) -> dict:
    """A portable summary designed as the trial input of an ATR volume model (for example in GateSignal)."""
    boxes = intent_table(data)
    payload = {
        "schema": EXPORT_SCHEMA,
        "generated_by": {
            "product": "ChoiceSignal",
            "version": version,
            "method": "single-concept five-point purchase-intent test",
        },
        "concept": concept_name.strip() or "Unnamed concept",
        "source": source,
        "respondents": data.n,
        "boxes": [
            {
                "code": int(row["intent_code"]),
                "label": row["intent"],
                "respondents": int(row["respondents"]),
                "share_pct": round(float(row["share_%"]), 2),
                "wilson95_pct": [
                    round(float(row["wilson95_low_%"]), 2),
                    round(float(row["wilson95_high_%"]), 2),
                ],
            }
            for row in boxes.to_dict("records")
        ],
        "summary": box_summary(data),
        "trial_assumption": trial_estimate(data, weights),
        "caution": (
            "Stated trial intention for one described concept. Use it as the trial input of an "
            "awareness × trial × availability × repeat (ATR) volume plan — it is not a sales forecast, "
            "and it says nothing about awareness, distribution, repeat, or purchase frequency."
        ),
    }
    if "segment" in data.frame.columns:
        segments, _ = segment_table(data)
        payload["segments"] = [
            {
                "segment": str(row["segment"]),
                "respondents": int(row["respondents"]),
                "top_box_pct": round(float(row["top_box_%"]), 2),
                "top_two_box_pct": round(float(row["top_two_box_%"]), 2),
                "top_two_wilson95_pct": [
                    round(float(row["top_two_wilson95_low_%"]), 2),
                    round(float(row["top_two_wilson95_high_%"]), 2),
                ],
            }
            for row in segments.to_dict("records")
        ]
    return payload
