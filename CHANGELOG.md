# Changelog

All notable changes to Choice Signal are documented here.

## 1.3.0 - 2026-10-02

Signal brand refresh and Signal Hub entry point. The estimation, simulation, concept test, data contract and exports are unchanged.

### Brand

- Display name written **Choice Signal** (with a space) in the app, README, docs, AI analyst file, launchers and metadata. Package, dist, file and environment-variable names stay `choicesignal` / `conjoint-analysis` / `CHOICESIGNAL_*`; the trial-intention JSON (`signal.trial-intention.v1`) is unchanged.
- The app uses the shared `signal_theme` module (Organic Signal design, Research family colour `#a06f1f`, Figtree): sidebar lockup, masthead, hero, step cards, notes, footer, the per-app Plotly template on every chart and the mark as favicon replace the pasted styles.
- New banner, social preview and marks in `assets/`; the old banner SVG is removed. `.streamlit/config.toml` uses the family colours. Its default upload limit is 50 MB; the launchers and the Docker image keep the documented 200 MB.
- README follows the Signal template; bug-report and feature-request issue templates added.

### Signal Hub contract

- `choicesignal.ui` exposes `APP_INFO` and `render()`, so Signal Hub can embed the app; `app.py` is now a thin standalone entry point.
- All session-state and widget keys are namespaced `choice:` (including the page selector).
- The fictional demo studies ship as package data, so the demo buttons also work when the app is installed from a wheel.
- `streamlit` and `plotly` moved to a `ui` extra (also in `test`); the analysis core installs without them. `requirements.txt` still lists everything.
- New tests: no Streamlit/Plotly import outside `choicesignal.ui`, the UI reads data only from inside the package, `render()` runs from a script without a page config, and every widget key is namespaced. Ruff runs in CI.

## 1.2.1 - 2026-07-16

### Security

- Excel and CSV exports now neutralize formula-like column headers (including the per-respondent part-worth export whose headers come from attribute and level names) and de-duplicate scrubbed sheet names.
- The Docker image keeps application code root-owned and read-only, and defusedxml hardens workbook XML parsing.

## 1.2.0 - 2026-07-15

New: single-concept purchase-intent testing (page 4 · Concept test):

- The classic five-point definitely/probably/might/probably-not/definitely-not scale, read from standard labels or the numbers 1–5 (reversed numeric convention supported); unrecognized answers and duplicate respondents are excluded with visible counts.
- Top-box and top-two-box shares with Wilson 95% score intervals.
- A weighted stated-trial estimate with user-editable discount weights (illustrative defaults 0.80/0.30/0.10, clearly labeled as assumptions to calibrate per category), always carrying the unadjusted top-two-box ceiling.
- Reasons for rejection among respondents below the top two boxes, multi-mention aware (`;` or `|` separators).
- Optional descriptive segment comparison with per-segment Wilson intervals and small-segment warnings — no significance theater.
- A trial-intention JSON export (`signal.trial-intention.v1`) designed as the trial input of an awareness × trial × availability × repeat volume plan, carrying every assumption with the number.
- New fictional demo (`examples/demo_concept_test.csv`, 260 respondents) and template (`examples/concept_template.csv`).

Full conjoint remains the multi-concept method, and willingness-to-pay conversions remain deliberately excluded.

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
