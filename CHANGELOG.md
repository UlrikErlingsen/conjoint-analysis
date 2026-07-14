# Changelog

All notable changes to ChoiceSignal are documented here.

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
