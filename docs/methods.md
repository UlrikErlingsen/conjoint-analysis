# Methods and validation

ChoiceSignal implements classic ratings-based (full-profile) conjoint analysis. This document describes the model, the diagnostics, and the boundaries.

## The model

### Effects coding

Each attribute \(a\) with levels \(1..L_a\) is effects-coded: for every non-reference level a column takes +1 when the profile shows that level, −1 when it shows the reference level (the last level alphabetically), and 0 otherwise. The reference level's part-worth is minus the sum of the attribute's other part-worths, so **part-worths sum to zero within each attribute** and describe value relative to that attribute's average. The model for a rating \(y\) of a profile is additive:

\[
y = \mu + \sum_a w_{a,\ell(a)} + \varepsilon
\]

where \(\ell(a)\) is the profile's level of attribute \(a\) and \(w\) are part-worth utilities in rating-scale points.

### Estimation

A separate ordinary-least-squares regression is fitted per respondent (`numpy.linalg.lstsq`). A respondent is *estimable* when they rated **strictly more** profiles than the model has parameters \(p = 1 + \sum_a (L_a - 1)\) — a saturated model has zero residual degrees of freedom, fits noise exactly (\(R^2 = 1\)), and yields unstable utilities — **and** their own design matrix has full column rank. Aggregate part-worths are the mean over estimable respondents, and the reported spread is the standard deviation across respondents — a direct heterogeneity signal. A pooled regression with **respondent fixed effects** (within transformation: ratings and design columns are demeaned per respondent) is always fitted as a reference, so differences in rating style between respondents cannot masquerade as attribute effects when respondents saw different profile subsets; its reported fit is the within-respondent \(R^2\). When fewer than 30% of respondents are estimable, the app reports these pooled results only and says so.

### Attribute importance

For each estimable respondent, an attribute's range is \(\max_\ell w_{a,\ell} - \min_\ell w_{a,\ell}\), and its importance is that range divided by the sum of ranges, in percent. The app reports the mean and standard deviation across respondents. Importance is **relative to the levels tested**: an attribute spanning a wider range of levels will look more important.

### Fit

Per-respondent \(R^2\) is reported (and is NaN when a respondent's ratings have no variance). Low individual \(R^2\) means inconsistent ratings or preferences that violate the additive model; such respondents' utilities deserve less weight.

## Missing values

Rows whose rating is not numeric, or whose attribute value is missing or not one of the design's levels, are excluded with a visible count. Effects coding would otherwise silently treat such rows as an 'average' level and bias the part-worths.

## Design health checks

Before estimation the app reports how often each level was shown, warns when a level appears fewer than 5 times or when levels of one attribute differ in exposure by more than 3×, warns when profiles are repeated for the same respondent, and **rejects** designs where the pooled design matrix is rank-deficient — that is, two or more attributes are perfectly confounded and their effects cannot be separated.

## Preference-share simulation

Products are defined as one level per attribute. For each estimable respondent, a product's utility is that respondent's intercept plus the sum of the matching part-worths, so utilities live on the rating scale (a product's mean utility reads as its mean predicted rating). Three classic choice rules are reported (Green & Krieger, 1988):

- **First choice (maximum utility):** each respondent chooses their highest-utility product; exact ties are split equally. Decisive and winner-takes-all — most appropriate for considered, high-involvement purchases.
- **Share of preference:** each respondent splits their choice in proportion to how far each product's predicted rating sits above the study's **lowest observed rating** (products at or below the floor get zero weight; a respondent with no positive weights splits equally). Anchoring at the observed floor makes the rule invariant to shifting the whole rating scale — the naive utility-proportional rule depends on the scale's arbitrary origin. Softer — most appropriate for habitual, low-involvement categories where customers sample around.
- **Logit:** a Bradley–Terry–Luce rule, \(\Pr(j) = e^{u_j} / \sum_k e^{u_k}\), averaged over respondents. Its softness depends on the rating scale, so read it as a sensitivity check, not a calibrated probability.

When the rules disagree strongly, the conclusion is rule-sensitive and should be reported as such. All three are **preference shares among the exact products entered**, from stated preferences — not market-share forecasts.

### Awareness and availability adjustment

A respondent cannot choose a product they have never heard of or cannot find. Given managerial estimates of awareness and availability per product, adjusted shares weight each preference share by awareness × availability and renormalize to 100%. The adjustment is transparent and exactly as good as the estimates behind it.

### Cannibalization

When one of the simulated products is marked as a new entrant, the app compares the remaining products' first-choice shares without and with the entrant. Share the entrant takes from the same firm's other products is cannibalization; whether the incremental gain justifies it is a business judgment, not a model output.

### Highest stated-preference design search

The app can enumerate the full factorial of tested levels and rank every possible design — by first-choice share against a user-defined competitive set, or by mean predicted rating when no competitors are defined (Green & Krieger, 1985). The search is exact, not heuristic, and is bounded so that designs × respondents stays within a responsiveness limit. It is deliberately **not** called an optimal product: it ranks stated preference only, and costs, margins, feasibility, brand fit, and untested levels are outside the search.

### Ideal products

For each estimable respondent, the favorite level of every attribute defines that person's ideal combination; the app counts how often each combination occurs. This is a description of demand heterogeneity, not a launch recommendation. Exporting the per-respondent part-worth matrix (one row per respondent, one column per level) supports proper preference segmentation in a clustering tool.

## Single-concept purchase-intent test

Page 4 answers the other classic pre-launch question: not *which attributes to trade off*, but *would people buy this one described concept?* One row per respondent; the response is the classic five-point purchase-intent scale — *definitely would buy, probably would buy, might or might not buy, probably would not buy, definitely would not buy* — accepted as the standard labels or the numbers 1–5 (5 = definitely; a reversed numeric convention can be declared). Unrecognized responses are excluded with a visible count, and duplicate respondents keep only their first answer, with a warning.

### Shares and uncertainty

The **top-box** share is the fraction answering *definitely would buy*; the **top-two-box** share adds *probably*. Each share \(p = s/n\) is reported with a **Wilson (1927) score interval**:

\[
\frac{p + \frac{z^2}{2n} \pm z \sqrt{\frac{p(1-p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \qquad z = 1.96
\]

chosen over the naive Wald interval because it stays inside \([0, 1]\) and behaves sensibly at small samples and extreme shares.

### From stated intent to an assumed trial rate

Stated intentions systematically overstate purchase (Kalwani & Silk 1982; Jamieson & Bass 1989; Morwitz, Steckel & Gupta 2007). The app therefore never presents raw intent as a trial forecast. Instead it computes a **weighted trial estimate** \(\sum_b w_b \, p_b\) over the five boxes, with user-editable weights defaulting to 0.80 / 0.30 / 0.10 / 0 / 0 — an illustrative starting point in the range practitioners use, **not** a validated constant. The correct weights are category-specific and should be calibrated against past launches. The unadjusted top-two-box share is always carried alongside as the optimistic ceiling, and the export records the weights so the assumption cannot silently detach from the number. The estimate is designed as the **trial** input of an awareness × trial × availability × repeat volume plan (Urban & Hauser 1993); it says nothing about the other factors.

### Rejection reasons and segments

Among **rejecters** — respondents below the top two boxes — an optional reason column is tallied (several reasons per cell may be separated by `;` or `|`; percentages are per rejecter and can sum past 100%). An optional segment column yields per-segment top-box and top-two-box shares with Wilson intervals. The comparison is deliberately descriptive: where intervals overlap heavily the data cannot separate the segments, and no significance test is dressed over that.

### Boundaries of the concept test

- One concept, no trade-offs: it cannot say *why* in attribute terms — that is conjoint's job.
- Intent was asked about a *described* concept; the realized product, price, and packaging shift responses.
- The weighted trial estimate inherits its weights' quality; it is an assumption made explicit, not a measurement.

## Boundaries

- The model is additive; attribute interactions (for example, brand-specific price sensitivity) are not estimated.
- Numeric attributes are treated as discrete levels; the app does not interpolate between tested levels.
- Choice-based conjoint (CBC) with hierarchical Bayes estimation is the modern survey standard for choice data; it requires choice tasks rather than ratings and is out of scope for this release.
- Willingness-to-pay conversion is excluded on purpose: dividing part-worths by a price coefficient assumes a linear, well-estimated price utility and routinely overstates precision.
- Ratings from a single respondent cannot separate that person's scale use from their preferences; comparing part-worths across respondents assumes similar scale use.

## References

- Green, P. E., & Rao, V. R. (1971). Conjoint measurement for quantifying judgmental data. *Journal of Marketing Research*, 8(3), 355–363.
- Green, P. E., & Srinivasan, V. (1978). Conjoint analysis in consumer research: Issues and outlook. *Journal of Consumer Research*, 5(2), 103–123.
- Jamieson, L. F., & Bass, F. M. (1989). Adjusting stated intention measures to predict trial purchase of new products. *Journal of Marketing Research*, 26(3), 336–345.
- Kalwani, M. U., & Silk, A. J. (1982). On the reliability and predictive validity of purchase intention measures. *Marketing Science*, 1(3), 243–286.
- Morwitz, V. G., Steckel, J. H., & Gupta, A. (2007). When do purchase intentions predict sales? *International Journal of Forecasting*, 23(3), 347–364.
- Green, P. E., & Srinivasan, V. (1990). Conjoint analysis in marketing: New developments with implications for research and practice. *Journal of Marketing*, 54(4), 3–19.
- Green, P. E., & Krieger, A. M. (1985). Models and heuristics for product line selection. *Marketing Science*, 4(1), 1–19.
- Green, P. E., & Krieger, A. M. (1988). Choice rules and sensitivity analysis in conjoint simulators. *Journal of the Academy of Marketing Science*, 16(1), 114–127.
- Lilien, G. L., Rangaswamy, A., & De Bruyn, A. (2017). *Principles of Marketing Engineering and Analytics* (3rd ed.). DecisionPro.
- Orme, B. K. (2020). *Getting Started with Conjoint Analysis* (4th ed.). Research Publishers.
- Rao, V. R. (2014). *Applied Conjoint Analysis*. Springer.
- Urban, G. L., & Hauser, J. R. (1993). *Design and Marketing of New Products* (2nd ed.). Prentice Hall.
- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209–212.
