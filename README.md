<p align="center">
  <img src="assets/choicesignal-banner.png" alt="Choice Signal: How do product attributes drive choice?" width="100%">
</p>

<p align="center">
  <a href="https://github.com/UlrikErlingsen/conjoint-analysis/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/UlrikErlingsen/conjoint-analysis/actions/workflows/tests.yml/badge.svg"></a>
  <a href="https://github.com/UlrikErlingsen/signal-hub"><img alt="Signal · Research" src="https://img.shields.io/badge/Signal-Research-a06f1f?labelColor=2e2b25"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2e2b25?logo=python&logoColor=f9f4ed">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-app-a06f1f?logo=streamlit&logoColor=f9f4ed">
  <a href="LICENSE"><img alt="License: AGPL-3.0-or-later" src="https://img.shields.io/badge/License-AGPL--3.0--or--later-645c50"></a>
</p>

<p align="center"><strong>Open conjoint analysis for marketers — feature values, attribute importance, and preference shares from simple ratings data.</strong></p>

**Choice Signal** turns ratings of product profiles into the value of every feature level. Upload a table where each row is one respondent rating one product profile; the app estimates part-worth utilities per respondent, shows which attributes drive preference, lets you simulate how candidate products would split preference, and exports every estimate with an audit trail. No account or statistics software is required: plain-language pages, fictional demo studies, design health checks before estimation, and portable exports make it usable by marketers.

> How do product attributes drive choice—and would people buy this one concept?

Everything runs locally with open-source Python packages. There is no account, telemetry, external AI call, remote database, or built-in data storage.

## Read this first

> **Treat these results as decision support, not predicted market shares.** Ratings describe stated preferences for hypothetical profiles. Real choices also depend on awareness, availability, budgets, habits, and competitors outside the study. Choice Signal shows fit quality, design warnings, and respondent disagreement so weak evidence looks weak.

- **Honest by design:** confounded designs are rejected, thin levels are flagged, respondents who rated too few profiles fall back to a pooled model with a visible warning, and R² is reported per respondent.
- Preference shares are shares among the exact products you define, not market-share forecasts. If the three choice rules disagree strongly, say so in your recommendation.
- The highest stated-preference design search ranks stated preference only; costs, margins, feasibility, and brand fit stay outside it.
- Stated purchase intent overstates real buying. The concept test's trial estimate applies discount weights that are assumptions to calibrate per category, and it always carries the unadjusted top-two-box ceiling.

## Scope

**Version 1.3 supports two pre-launch questions in one app:** full conjoint for *which features to build*, plus a single-concept purchase-intent test for *would people buy this one idea*.

- ratings-based (full-profile) conjoint from `.csv`, `.xlsx`, `.xls`, `.xlsm`, and `.json` files in long format;
- 2–12 levels per attribute and up to 10 attributes;
- per-respondent estimation, so differences between people survive into the results and power the simulator, with a respondent-fixed-effects pooled model as reference and fallback;
- design health checks before estimation;
- preference-share simulation, awareness × availability adjustment, a cannibalization view, and an exhaustive stated-preference design search;
- a per-respondent part-worth export shaped for preference segmentation;
- a five-point purchase-intent concept test with Wilson intervals, rejection reasons, an optional segment comparison, and a trial-intention export.

**It does not:** estimate interactions between attributes, run choice-based conjoint (CBC) or hierarchical Bayes estimation, convert part-worths to willingness-to-pay, interpolate between tested levels, or forecast market shares or sales. Where a sibling app covers it, use **[Tag Signal](https://github.com/UlrikErlingsen/pricing-analysis)** for the pricing decision itself, **[Segment Signal](https://github.com/UlrikErlingsen/customer-segmentation)** to find preference-based segments in the per-respondent export, and **[Gate Signal](https://github.com/UlrikErlingsen/launch-decision-gate)** to carry the trial estimate into a volume plan and investment decision.

## Try the demo in three minutes

1. Start the app: the fictional **coffee subscriptions** demo study is already loaded, so there is nothing to upload. The sidebar demo buttons switch studies or restore the coffee demo (the **car buyers** demo hides two taste segments to discover, and **Demo · concept test** shows the single-concept purchase-intent workflow on page 4); uploading your own file replaces the demo.
2. On **1 · Data & design**, confirm the suggested respondent, rating, and attribute columns, then check and save the design.
3. On **2 · Utilities & importance**, estimate the part-worth utilities and read which attributes drive preference.
4. On **3 · Simulate & export**, define two candidate subscriptions and compare their preference shares, then download the Excel pack.

All demos are fictional: every record is synthetic and represents no real respondent, organisation, or empirical finding. `examples/ratings_template.csv` shows the expected data shape.

## Data contract

Choice Signal reads `.csv`, `.xlsx`, `.xls`, `.xlsm`, and `.json` up to 200 MB locally (JSON up to 50 MB). The study must be in long format:

| respondent_id | brand   | price | warranty | rating |
| ------------- | ------- | ----- | -------- | ------ |
| R0001         | Brand A | $10   | 1 year   | 7      |
| R0001         | Brand B | $15   | 2 years  | 4      |
| R0002         | Brand A | $15   | 2 years  | 8      |

One row per rated profile: a respondent ID, one column per attribute (2–12 levels each, up to 10 attributes), and a numeric rating where higher means better. Respondents should each rate several profiles — more than the model has parameters for individual estimation. Rows with missing or unrecognized attribute levels are excluded with a visible count.

The **single-concept test** (page 4) instead expects one row per respondent: an ID, a five-point purchase-intent answer, and optional rejection-reason and segment columns — see `examples/concept_template.csv`. Unrecognized answers and duplicate respondents are excluded with visible counts.

See the [data guide](docs/data_guide.md).

## Analysis contract

Before anything is estimated, you declare which columns hold the respondent ID, the rating (higher = better), and the attributes that were varied. The design is then health-checked: level exposure, imbalance, and perfectly confounded attributes (rejected rather than silently mis-estimated). The declared attributes and levels, the respondent and rating counts, and a fingerprint of the data travel into the conjoint exports.

For the concept test you declare the respondent and purchase-intent columns, optional reason and segment columns, whether a numeric scale is reversed, and the trial discount weights. The illustrative default weights (0.80 / 0.30 / 0.10) are labelled as assumptions to calibrate to past launches in your category.

## Methods

Choice Signal implements classic **ratings-based (full-profile) conjoint analysis**: attribute levels are effects-coded and a separate ordinary-least-squares regression is fitted per respondent, with a respondent-fixed-effects pooled model as reference and fallback. The effects-coded OLS can be verified by hand. The app reports:

- part-worth utilities per feature level (zero-centered within each attribute), with the spread across respondents;
- attribute importance as each attribute's share of the total preference range, averaged over respondents;
- per-respondent fit (R²) and estimability;
- design health: level exposure, imbalance, and perfectly confounded attributes (rejected);
- preference-share simulation under three classic choice rules (first choice, share of preference, logit);
- awareness × availability share adjustment and a cannibalization view for product-line decisions;
- an exhaustive stated-preference design search across every combination of tested levels (deliberately not called 'optimal': costs and feasibility stay outside);
- a per-respondent part-worth export shaped for preference segmentation (it opens directly in Segment Signal);
- a single-concept purchase-intent test: five-point scale, top-box and top-two-box shares with Wilson 95% intervals, rejection reasons, an optional segment comparison, and a trial-intention export with user-editable, clearly-labeled discount weights (stated intent overstates real buying).

When fewer than 30% of respondents are estimable, the app reports the pooled results only and says so; the simulator then stays off. Interactions between attributes, choice-based conjoint (CBC), hierarchical Bayes estimation, and willingness-to-pay conversion are deliberately outside this release; the docs explain why. See [methods and references](docs/methods.md).

## Exports

The Excel pack and the JSON audit trail include:

- an analysis manifest with the source filename, a SHA-256 fingerprint of the respondent and attribute columns, the software and library versions, and the estimation method;
- the declared attributes and levels, respondent and rating counts, pooled R², and the simulated products;
- part-worth utilities, attribute importance, individual part-worths, respondent fit, and pooled part-worths;
- simulated shares, awareness/availability-adjusted shares, and the top stated-preference designs, when you have run them;
- the caution that these are stated-preference estimates, not market-share forecasts.

A part-worths CSV and a per-respondent part-worth CSV (one row per respondent, ready for segmentation) are also available. The concept test exports its intent table as CSV and a trial-intention JSON (`signal.trial-intention.v1`) that carries the boxes, intervals, weights, ceiling, and caveats. Excel and CSV exports neutralise formula-like cells and column headers against spreadsheet-formula interpretation.

## Run locally

You need Python 3.10 or newer. Download this project from GitHub and unzip it, or clone it:

```bash
git clone https://github.com/UlrikErlingsen/conjoint-analysis.git
cd conjoint-analysis
```

**macOS:** double-click `run_app.command`; the browser opens automatically after the local server is ready. **Windows:** double-click `run_app.bat`.

The first start creates a private `.venv` folder and installs the required packages, which can take a few minutes. Later starts reuse it without requiring a network connection. Or use a terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Choice Signal prefers local port 8501 and falls back to another free port on macOS. The macOS launcher accepts `CHOICESIGNAL_PORT`, `CHOICESIGNAL_MAX_UPLOAD_MB` and `CHOICESIGNAL_NO_BROWSER`; set `CHOICESIGNAL_DEBUG=1` to reveal technical details for unexpected errors.

### Docker

```bash
docker build -t choicesignal .
docker run --rm -p 8501:8501 choicesignal
```

Then open http://localhost:8501. The container runs as a non-root user and includes a health check.

## Privacy

Local mode keeps the file in the running process on your computer. Hosted mode sends it to the chosen host, so the operator is responsible for access control, logs, retention, and legal compliance. Read [PRIVACY.md](PRIVACY.md) before using personal data. Use pseudonymous respondent IDs; the analysis never needs names or contact details.

## No install? Give this file to an AI

Don't want to install anything? [AI_ANALYST.md](AI_ANALYST.md) is a single copy-paste file that turns a capable AI assistant (Claude, ChatGPT, Gemini, …) into this analysis. Copy the file into a chat, add your data, and the AI follows the same published methods and honesty rules as the app. The app is still the more private option: local mode keeps your data on your computer, while a cloud AI sees whatever you paste.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check .
python -m build
```

The analysis core (`choicesignal`) installs without Streamlit or Plotly; the app needs the `ui` extra (`python -m pip install -e ".[ui]"`), and `requirements.txt` lists everything for the launchers and Docker. [Signal Hub](https://github.com/UlrikErlingsen/signal-hub) embeds the app through `choicesignal.ui.render()`.

The suite checks the conjoint estimation and design checks, the share rules and design search, the concept test, file loading and export safety, every Streamlit page and demo flow, the shared Signal shell, and the Signal Hub contract (no Streamlit or Plotly import outside `ui/`, `render()` without a page config, namespaced keys).

## Where this fits in Signal

Choice Signal is part of a family of open, local-first marketing-analytics apps that share one design language but do different statistical jobs. It answers a third question: not who your customers are or what they are worth, but **what they want**.

- **[Worth Signal](https://github.com/UlrikErlingsen/customer-value-analytics)** — customer value: RFM targeting, CLV, retention, and marketing ROI.
- **[Segment Signal](https://github.com/UlrikErlingsen/customer-segmentation)** — multi-variable B2C customer segmentation with stability checks.
- **[Adopt Signal](https://github.com/UlrikErlingsen/adoption-forecasting)** — new-product adoption forecasting with the Bass diffusion model: published analogies, scenario stress-tests, and fitting to real history.
- **[Position Signal](https://github.com/UlrikErlingsen/brand-positioning)** — perceptual mapping for brand positioning: where brands sit relative to competitors, from brand-attribute ratings.
- **[Alloc Signal](https://github.com/UlrikErlingsen/marketing-mix-allocation)** — marketing response and budget allocation: saturating response curves, constrained optimization, and a panel-evidence workspace.
- **[Driver Signal](https://github.com/UlrikErlingsen/survey-driver-analysis)** — survey driver analysis: scale reliability, robust standardized drivers, and correlated-predictor importance for satisfaction and NPS.
- **[Gate Signal](https://github.com/UlrikErlingsen/launch-decision-gate)** — the decision gate for the next bounded investment: criteria, evidence, scenario NPV, and risk triage. Its volume bridge imports this app's trial-intention export (`signal.trial-intention.v1`) directly.
- **[Experiment Signal](https://github.com/UlrikErlingsen/experiment-analysis)** — randomized experiment analysis: design audit, covariate-adjusted HC3 intervals, Holm multiplicity control, and a practical-effect decision bound declared before the result.
- **[Measure Signal](https://github.com/UlrikErlingsen/measurement-validation)** — measurement diagnostics: factorability, parallel analysis, common-factor EFA, alpha and omega, and a frozen scoring recipe for holdout confirmation.
- **[Text Signal](https://github.com/UlrikErlingsen/open-text-analysis)** — open-text evidence: corpus audit, lexical contrast, perturbation-stable NMF patterns, and a human codebook hand-off.
- **[Tag Signal](https://github.com/UlrikErlingsen/pricing-analysis)** — the pricing decision itself: candidate vs reference price from experiment, history, or willingness-to-pay evidence. Choice Signal's price attribute measures *preference sensitivity across tested levels*; when the question becomes “what should this product cost?”, use Tag Signal rather than over-reading part-worths—willingness-to-pay conversion stays deliberately out of this app.
- **[Recommend Signal](https://github.com/UlrikErlingsen/recommender-evaluation)** — temporal offline policy comparison when the decision is which products or content to recommend, not which product profile people state they prefer.
- **[Trace Signal](https://github.com/UlrikErlingsen/journey-path-analysis)** — descriptive customer-journey evidence from event logs: transitions, path support, drop-off, and Markov removal sensitivity, with no causal channel credit.
- **[Track Signal](https://github.com/UlrikErlingsen/brand-tracking)** — brand-tracking wave comparison: separate measures with intervals, multiple-comparison control, and declared practical thresholds.

<!-- signal-suite:start (generated from signal-hub/apps.yaml by scripts/sync_readme_suite.py) -->
| Family | App | Asks |
|---|---|---|
| Brand | [Track Signal](https://github.com/UlrikErlingsen/brand-tracking) | Is the brand moving, or is the tracker just noisy? |
| Brand | [Position Signal](https://github.com/UlrikErlingsen/brand-positioning) | Where do brands sit relative to competitors? |
| Market | [Prospect Signal](https://github.com/UlrikErlingsen/b2b-prospecting) | Which Norwegian companies fit your ideal customer, and which first? |
| Market | [Listen Signal](https://github.com/UlrikErlingsen/media-listening) | Who is talking about the brand in Norwegian media, and in what tone? |
| Market | [Influence Signal](https://github.com/UlrikErlingsen/influencer-campaigns) | Which creators delivered, and was every post labelled properly? |
| Market | [Season Signal](https://github.com/UlrikErlingsen/marketing-calendar) | What does the Norwegian marketing year look like, worked backwards? |
| Market | [Adopt Signal](https://github.com/UlrikErlingsen/adoption-forecasting) | When will a new product be adopted? |
| Customer | [Worth Signal](https://github.com/UlrikErlingsen/customer-value-analytics) | What are customers and relationships worth? |
| Customer | [Segment Signal](https://github.com/UlrikErlingsen/customer-segmentation) | Do customers form stable, useful groups? |
| Customer | [Trace Signal](https://github.com/UlrikErlingsen/journey-path-analysis) | How do logged customer journeys actually unfold? |
| Customer | [Recommend Signal](https://github.com/UlrikErlingsen/recommender-evaluation) | Which recommendation policy should be tested live? |
| Research | **Choice Signal** (this app) | How do product attributes drive choice? |
| Research | [Driver Signal](https://github.com/UlrikErlingsen/survey-driver-analysis) | Which measured experiences move with satisfaction? |
| Research | [Measure Signal](https://github.com/UlrikErlingsen/measurement-validation) | Does a multi-item score have a defensible structure? |
| Research | [Text Signal](https://github.com/UlrikErlingsen/open-text-analysis) | What recurring patterns appear in open-ended responses? |
| Research | [Tag Signal](https://github.com/UlrikErlingsen/pricing-analysis) | What price range is supported, and how does profit move? |
| Decide | [Experiment Signal](https://github.com/UlrikErlingsen/experiment-analysis) | Did the treatment cause a practically meaningful change? |
| Decide | [Gate Signal](https://github.com/UlrikErlingsen/launch-decision-gate) | Does a concept deserve the next investment? |
| Decide | [Alloc Signal](https://github.com/UlrikErlingsen/marketing-mix-allocation) | Where should the next marketing budget go? |

All 19 apps run side by side in [Signal Hub](https://github.com/UlrikErlingsen/signal-hub), each opening with fictional demo data. Every repo carries the [`signal-suite`](https://github.com/topics/signal-suite) topic, and the suite is listed at [ulrikerlingsen.com](https://ulrikerlingsen.com). Freddo CRM is a separate product.
<!-- signal-suite:end -->

## References

- Green, P. E., & Rao, V. R. (1971). Conjoint measurement for quantifying judgmental data. *Journal of Marketing Research*, 8(3), 355–363.
- Green, P. E., & Srinivasan, V. (1978). Conjoint analysis in consumer research: Issues and outlook. *Journal of Consumer Research*, 5(2), 103–123.
- Green, P. E., & Srinivasan, V. (1990). Conjoint analysis in marketing: New developments with implications for research and practice. *Journal of Marketing*, 54(4), 3–19.
- Green, P. E., & Krieger, A. M. (1985). Models and heuristics for product line selection. *Marketing Science*, 4(1), 1–19.
- Green, P. E., & Krieger, A. M. (1988). Choice rules and sensitivity analysis in conjoint simulators. *Journal of the Academy of Marketing Science*, 16(1), 114–127.
- Jamieson, L. F., & Bass, F. M. (1989). Adjusting stated intention measures to predict trial purchase of new products. *Journal of Marketing Research*, 26(3), 336–345.
- Kalwani, M. U., & Silk, A. J. (1982). On the reliability and predictive validity of purchase intention measures. *Marketing Science*, 1(3), 243–286.
- Lilien, G. L., Rangaswamy, A., & De Bruyn, A. (2017). *Principles of Marketing Engineering and Analytics* (3rd ed.). DecisionPro.
- Morwitz, V. G., Steckel, J. H., & Gupta, A. (2007). When do purchase intentions predict sales? *International Journal of Forecasting*, 23(3), 347–364.
- Orme, B. K. (2020). *Getting Started with Conjoint Analysis* (4th ed.). Research Publishers.
- Rao, V. R. (2014). *Applied Conjoint Analysis*. Springer.
- Urban, G. L., & Hauser, J. R. (1993). *Design and Marketing of New Products* (2nd ed.). Prentice Hall.
- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209–212.

Formulas, warnings, and implementation notes are in [docs/methods.md](docs/methods.md).

## Originality and license

The product name is **Choice Signal**; the repository keeps the clear `conjoint-analysis` name. This app was built with AI assistance and reviewed against the published conjoint-analysis literature cited in [docs/methods.md](docs/methods.md). All example respondents are synthetic; no licensed third-party materials are included.

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

The software and documentation are free under AGPL-3.0-or-later. Commercial use is allowed, while distribution and modified network services carry source-sharing obligations described in the full [LICENSE](LICENSE). The license covers this project's expression, not ownership of published statistical methods. This summary is not legal advice; the license text controls.

---

<p>
  <img src="assets/choicesignal-mark-64.png" width="20" height="20" alt="" align="absmiddle">
  <strong>Choice Signal</strong> is part of <a href="https://github.com/UlrikErlingsen/signal-hub"><strong>Signal</strong></a>, open marketing-evidence tools by <a href="https://ulrikerlingsen.com">Ulrik Erlingsen</a>.
</p>
