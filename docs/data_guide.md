# Data guide

## The shape ChoiceSignal expects

One row per rated profile, in long format:

| respondent_id | brand   | price | warranty | rating |
| ------------- | ------- | ----- | -------- | ------ |
| R0001         | Brand A | $10   | 1 year   | 7      |
| R0001         | Brand B | $15   | 2 years  | 4      |
| R0002         | Brand A | $15   | 2 years  | 8      |

- **Respondent ID** — any text or number that identifies who gave the rating. Use pseudonymous IDs, never names or emails.
- **Attribute columns** — one column per product feature that was varied. Each needs 2–12 distinct levels, up to 10 attributes. Express numeric features as a few tested levels (`$10`, `$15`, `$20`), not as free numbers.
- **Rating** — a number where higher means better (1–10 works well). Other scales are fine as long as they are consistent.

`examples/ratings_template.csv` is a copyable starting point; the two demo files show complete fictional studies.

## How many ratings does each respondent need?

The model has \(1 + \sum (\text{levels} - 1)\) parameters. Individual preferences can only be estimated for respondents who rated **strictly more profiles than that** (and whose profiles actually vary every attribute) — with exactly as many ratings as parameters the model would fit noise perfectly. For a study with 4 attributes of 3/3/2/3 levels, that is \(1 + 2 + 2 + 1 + 2 = 8\) parameters — so at least 9, and comfortably 12–16, rated profiles per respondent. Respondents below the threshold automatically fall back into a pooled model, with a warning.

## Design tips

- Show every level a similar number of times; the app warns about levels shown rarely or very unevenly.
- Never vary two attributes in lockstep (for example, premium brand always paired with high price) — the app rejects such confounded designs because the effects cannot be separated.
- Randomize which profiles each respondent sees.
- Keep profiles realistic; absurd combinations produce ratings that mean little.

## The shape the concept test expects (page 4)

One row per respondent, answering about a single described concept:

| respondent_id | segment   | purchase_intent        | rejection_reason             |
| ------------- | --------- | ---------------------- | ---------------------------- |
| R0001         | Segment A | Definitely would buy   |                              |
| R0002         | Segment B | Might or might not buy | Too expensive                |
| R0003         | Segment A | Probably would not buy | Too expensive; No need for it |

- **Purchase intent** — the five standard labels (*Definitely would buy*, *Probably would buy*, *Might or might not buy*, *Probably would not buy*, *Definitely would not buy*) or the numbers 1–5 with 5 = definitely would buy. A reversed numeric convention (1 = definitely would buy) can be declared with a checkbox. Anything else is excluded with a visible count.
- **Rejection reason** *(optional)* — free text from respondents below the top two boxes. Several reasons in one cell can be separated with `;` or `|`.
- **Segment** *(optional)* — any grouping label; segments exported from SegmentSignal work directly.

`examples/concept_template.csv` is a copyable starting point, and `examples/demo_concept_test.csv` is a complete fictional study.

## Limits

Files up to 200 MB locally (JSON up to 50 MB), 1 million rows per table, 10 million cells, 500,000 rating rows per analysis. These are responsiveness bounds, not statistical recommendations — most conjoint studies are thousands of rows, not millions.
