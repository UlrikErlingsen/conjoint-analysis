<p align="center">
  <img src="assets/choicesignal-banner.svg" alt="ChoiceSignal — Know what customers actually value" width="100%">
</p>

<p align="center">
  <a href="https://github.com/UlrikErlingsen/conjoint-analysis/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/UlrikErlingsen/conjoint-analysis/actions/workflows/tests.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-173C3A?logo=python&logoColor=white">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-app-D95B40?logo=streamlit&logoColor=white">
  <a href="LICENSE"><img alt="License: AGPL-3.0-or-later" src="https://img.shields.io/badge/License-AGPL--3.0--or--later-36534E"></a>
</p>

<p align="center"><strong>Open conjoint analysis for marketers — feature values, attribute importance, and preference shares from simple ratings data.</strong></p>

**ChoiceSignal** turns ratings of product profiles into the value of every feature level. Upload a table where each row is one respondent rating one product profile; the app estimates part-worth utilities per respondent, shows which attributes drive preference, lets you simulate how candidate products would split preference, and exports every estimate with an audit trail. No account or statistics software is required.

## Read this first

> **Treat these results as decision support, not predicted market shares.** Ratings describe stated preferences for hypothetical profiles. Real choices also depend on awareness, availability, budgets, habits, and competitors outside the study. ChoiceSignal shows fit quality, design warnings, and respondent disagreement so weak evidence looks weak.

## Why ChoiceSignal

- **Made for marketers:** plain-language pages, fictional demo studies, design health checks before estimation, and portable exports.
- **Two pre-launch questions in one app:** full conjoint for *which features to build*, plus a single-concept purchase-intent test (top-box / top-two-box with honest trial assumptions) for *would people buy this one idea*.
- **Per-respondent estimation:** each respondent gets their own part-worth utilities, so differences between people survive into the results and power the simulator.
- **Honest by design:** confounded designs are rejected, thin levels are flagged, respondents who rated too few profiles fall back to a pooled model with a visible warning, and R² is reported per respondent.
- **Local-first:** no account, telemetry, external AI calls, or built-in data storage.
- **Explainable and reproducible:** effects-coded OLS you can verify by hand, with formulas and citations in the docs and a manifest in every export.

## Get the app

You need Python 3.10 or newer. Download this project from GitHub and unzip it, or clone it:

```bash
git clone https://github.com/UlrikErlingsen/conjoint-analysis.git
cd conjoint-analysis
```

**Mac:** double-click `run_app.command`. The browser opens automatically after the local server is ready.

**Windows:** double-click `run_app.bat`.

The first start creates a private `.venv` folder and installs the required packages, which can take a few minutes. Later starts reuse it without requiring a network connection.

Or use a terminal:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

With Docker:

```bash
docker build -t choicesignal .
docker run --rm -p 8501:8501 choicesignal
```

Then open `http://localhost:8501`.

## No install? Give this file to an AI

Don't want to install anything? [AI_ANALYST.md](AI_ANALYST.md) is a single copy-paste file that turns a capable AI assistant (Claude, ChatGPT, Gemini, …) into this analysis. Copy the file into a chat, add your data, and the AI follows the same published methods and honesty rules as the app. The app is still the more private option: local mode keeps your data on your computer, while a cloud AI sees whatever you paste.

## Try it in two minutes

1. Start the app and click **Demo · coffee subscriptions** in the sidebar (the **car buyers** demo hides two taste segments to discover, and **Demo · concept test** shows the single-concept purchase-intent workflow on page 4).
2. On **1 · Data & design**, confirm the suggested respondent, rating, and attribute columns, then check and save the design.
3. On **2 · Utilities & importance**, estimate the part-worth utilities and read which attributes drive preference.
4. On **3 · Simulate & export**, define two candidate subscriptions and compare their preference shares, then download the Excel pack.

All demos are fictional. `examples/ratings_template.csv` shows the expected data shape.

## Which data works?

ChoiceSignal reads `.csv`, `.xlsx`, `.xls`, `.xlsm`, and `.json` up to 200 MB locally. The study must be in long format:

| respondent_id | brand   | price | warranty | rating |
| ------------- | ------- | ----- | -------- | ------ |
| R0001         | Brand A | $10   | 1 year   | 7      |
| R0001         | Brand B | $15   | 2 years  | 4      |
| R0002         | Brand A | $15   | 2 years  | 8      |

One row per rated profile: a respondent ID, one column per attribute (2–12 levels each, up to 10 attributes), and a numeric rating where higher means better. Respondents should each rate several profiles — more than the model has parameters for individual estimation. See [the data guide](docs/data_guide.md).

The **single-concept test** (page 4) instead expects one row per respondent: an ID, a five-point purchase-intent answer, and optional rejection-reason and segment columns — see `examples/concept_template.csv` and the data guide.

## Methods and accuracy

ChoiceSignal implements classic **ratings-based (full-profile) conjoint analysis**: attribute levels are effects-coded and a separate ordinary-least-squares regression is fitted per respondent, with a pooled model as reference and fallback. The app reports:

- part-worth utilities per feature level (zero-centered within each attribute), with the spread across respondents;
- attribute importance as each attribute's share of the total preference range, averaged over respondents;
- per-respondent fit (R²) and estimability;
- design health: level exposure, imbalance, and perfectly confounded attributes (rejected);
- preference-share simulation under three classic choice rules (first choice, share of preference, logit);
- awareness × availability share adjustment and a cannibalization view for product-line decisions;
- an exhaustive stated-preference design search across every combination of tested levels (deliberately not called 'optimal': costs and feasibility stay outside);
- a per-respondent part-worth export shaped for preference segmentation (it opens directly in SegmentSignal);
- a single-concept purchase-intent test: five-point scale, top-box and top-two-box shares with Wilson 95% intervals, rejection reasons, an optional segment comparison, and a trial-intention export with user-editable, clearly-labeled discount weights (stated intent overstates real buying).

Interactions between attributes, choice-based conjoint (CBC), hierarchical Bayes estimation, and willingness-to-pay conversion are deliberately outside this first release; the docs explain why. See [methods and references](docs/methods.md).

Run the automated tests with:

```bash
python -m pytest
```

## Related tools

ChoiceSignal is part of a small family of open, local-first marketing-analytics apps that share one design language but do different statistical jobs:

- **[WorthSignal](https://github.com/UlrikErlingsen/customer-value-analytics)** — customer value: RFM targeting, CLV, retention, and marketing ROI.
- **[SegmentSignal](https://github.com/UlrikErlingsen/customer-segmentation)** — multi-variable B2C customer segmentation with stability checks.
- **[AdoptSignal](https://github.com/UlrikErlingsen/adoption-forecasting)** — new-product adoption forecasting with the Bass diffusion model: published analogies, scenario stress-tests, and fitting to real history.
- **[PositionSignal](https://github.com/UlrikErlingsen/brand-positioning)** — perceptual mapping for brand positioning: where brands sit relative to competitors, from brand-attribute ratings.
- **[AllocSignal](https://github.com/UlrikErlingsen/marketing-mix-allocation)** — marketing response and budget allocation: saturating response curves, constrained optimization, and a panel-evidence workspace.
- **[DriverSignal](https://github.com/UlrikErlingsen/survey-driver-analysis)** — survey driver analysis: scale reliability, robust standardized drivers, and correlated-predictor importance for satisfaction and NPS.

ChoiceSignal answers a third question: not who your customers are or what they are worth, but **what they want**.

## Privacy and responsible use

Local mode keeps the file in the running process on your computer. Hosted mode sends it to the chosen host, so the operator is responsible for access control, logs, retention, and legal compliance. Read [PRIVACY.md](PRIVACY.md) before using personal data. Use pseudonymous respondent IDs; the analysis never needs names or contact details.

## About this project

The product name is **ChoiceSignal**; the repository keeps the clear `conjoint-analysis` name. This app was built with AI assistance and reviewed against the published conjoint-analysis literature cited in [docs/methods.md](docs/methods.md). All example respondents are synthetic; no licensed third-party materials are included.

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## License

AGPL-3.0-or-later. Commercial use is allowed, while distribution and modified network services carry source-sharing obligations described in the full [LICENSE](LICENSE). This summary is not legal advice; the license text controls.
