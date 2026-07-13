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

The model has \(1 + \sum (\text{levels} - 1)\) parameters. Individual preferences can only be estimated for respondents who rated **at least that many profiles** (and whose profiles actually vary every attribute). For a study with 4 attributes of 3/3/2/3 levels, that is 9 parameters — so 12–16 rated profiles per respondent is a comfortable design. Respondents below the threshold automatically fall back into a pooled model, with a warning.

## Design tips

- Show every level a similar number of times; the app warns about levels shown rarely or very unevenly.
- Never vary two attributes in lockstep (for example, premium brand always paired with high price) — the app rejects such confounded designs because the effects cannot be separated.
- Randomize which profiles each respondent sees.
- Keep profiles realistic; absurd combinations produce ratings that mean little.

## Limits

Files up to 200 MB locally (JSON up to 50 MB), 1 million rows per table, 10 million cells, 500,000 rating rows per analysis. These are responsiveness bounds, not statistical recommendations — most conjoint studies are thousands of rows, not millions.
