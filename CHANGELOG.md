# Changelog

All notable changes to ChoiceSignal are documented here.

## 1.1.0 - 2026-07-14

Statistical corrections following an external methods audit:

- The pooled reference model now uses respondent fixed effects (within transformation), so differences in rating style can no longer masquerade as attribute effects.
- Saturated individual models (exactly as many ratings as parameters) are no longer treated as estimable; a respondent needs strictly more ratings than parameters.
- Share of preference is now anchored at the study's lowest observed rating, making it invariant to shifting the rating scale (the naive utility-proportional rule depends on the scale's arbitrary origin).
- Rows with missing or unrecognized attribute levels are excluded with a visible count instead of being silently treated as an average level.
- Awareness/availability-adjusted shares are now included in the exports.
- The "optimal product" search is renamed to what it is: the highest stated-preference design search.
- Corrected the parameter-count example in the data guide.

## 1.0.0 - 2026-07-14

- First stable release. No functional changes since 0.2.0; the version now
  signals that the workflow, methods, exports, and file formats are stable.

## 0.2.0 - 2026-07-14

- Simulator now reports three classic choice rules: first choice, utility-proportional share of preference, and logit.
- Added awareness × availability share adjustment with per-product managerial estimates.
- Added a cannibalization view: incumbent shares with vs without a chosen new entrant.
- Added an exhaustive optimal-product search over all tested level combinations, ranked against the simulated competitive set or by predicted rating.
- Page 2 shows the most common per-respondent ideal combinations.
- New per-respondent part-worth export (wide CSV) ready for preference segmentation in SegmentSignal.
- New car-buyers demo (350 respondents, two hidden taste segments); coffee demo grown to 300 respondents.

## 0.1.0 - 2026-07-14

- First release.
- Ratings-based (full-profile) conjoint with effects coding and per-respondent OLS, plus a pooled fallback.
- Part-worth utilities, attribute importance, respondent-level fit, and heterogeneity spread.
- Design health checks: level exposure, imbalance, confounded attributes, and estimability warnings.
- Preference-share simulator with first-choice and share-of-preference rules.
- Excel, CSV, and JSON exports with a reproducibility manifest.
- Local-first Streamlit UI, fictional demo studies, methods documentation, and automated tests.
