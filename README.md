# Document Extraction Arena

A small benchmark that asks Gemini models to read invoice images and return structured JSON, then scores each answer field by field against a known answer key.

## Status

- Dataset: 120 synthetic invoices (4 levels x 30), generated with a fixed seed.
- `gemini-3.1-flash-lite`: run on all 120 invoices.
- `gemini-3.8-flash`: **not benchmarked yet.** The 2 invoices attempted failed with API errors (503 high demand, then a 429 free-tier daily quota error), so there are 0 scored answers for this model. It needs a rerun after the quota resets.

## Results

Scores come from `python runner/score.py` (`results/summary.csv`). API failures are excluded from accuracy and reported separately.

| Model | Level | n | Accuracy | Exact invoice | Avg seconds | Cost / invoice (USD) |
|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | level1_clean | 30 | 100.0% | 100.0% | 6.9 | 0.00080 |
| gemini-3.1-flash-lite | level2_mixed | 30 | 99.6% | 96.7% | 8.8 | 0.00079 |
| gemini-3.1-flash-lite | level3_noisy | 30 | 100.0% | 100.0% | 9.6 | 0.00080 |
| gemini-3.1-flash-lite | level4_hard | 30 | 94.1% | 60.0% | 7.2 | 0.00141 |
| gemini-3.8-flash | all | 0 | not measured | not measured | not measured | not measured |

- Accuracy is the mean of 8 field scores per invoice (invoice number, vendor, date, currency, subtotal, tax, total, line items). "Exact invoice" means all 8 were right.
- Cost uses the per-million-token prices in `runner/score.py`, counting thinking tokens as output. Those prices have not been re-checked against Google's current pricing page, so verify them before quoting the costs.
- Same-invoice comparison: `python runner/compare.py --per-level 10` compares models on the same invoices. With only one model scored it exits with a message instead of printing a table.
- **Level 4 (hard)** has 8-15 line items, smaller text, numeric-only dates with day <= 12 (so day/month order is genuinely ambiguous), US and non-US vendors, and heavier scan degradation than level 3. On it, flash-lite got 12 of 30 invoices not fully right: 7 invoice numbers, 7 dates, 1 line-item list. In `results/failures.csv`, all 7 invoice-number errors are 6-vs-8 misreads; of the 7 date errors, 4 are day/month swaps (`level4_hard_014`, `019`, `024`, `028`), 2 are digit misreads (`2026` read as `2028`) and 1 (`level4_hard_025`) is neither. This comes from the failure text, not from checking images (see the audit note below).
- Level 2 has one non-exact invoice, `level2_mixed_003`: the model read `05/10/2026` as 5 October instead of 10 May. See [docs/what-can-go-wrong.md](docs/what-can-go-wrong.md), which covers levels 1-3 only.

## Limitations

- **Synthetic data.** Invoices are generated, not real. Real invoices have messier layouts, stamps, handwriting and languages that this set does not cover.
- **One layout.** Every invoice uses the same template, so the results say little about unseen layouts.
- **Near-ceiling on levels 1-3.** Flash-lite scored 100.0%, 99.6% and 100.0% there, so those levels cannot separate strong models; level 4 was added for that. One more failed invoice in a 30-invoice level moves exact-invoice % by 3.3 points (and accuracy by about 0.4).
- **Free-tier rate limits.** The free tier limits requests per day per model. The large model hit its quota after 2 requests, which is why it has no results.
- **Small n for the large model.** Planned at 10 per level (30 total) against 30 per level for flash-lite, and currently 0. Compare models only on the same invoices.
- **Level 4 is only partly audited and has a known defect.** The repo owner looked at the images of 5 of the 12 non-exact level 4 invoices: 2 fair, 1 borderline, 1 unfair (`level4_hard_018`, last digit ambiguous between 6 and 8) and 1 not yet checked (`level4_hard_015`). This is a sample of 5, not the full set: the other 7 failing invoices were never checked against their images. Also, with rotation the description column is offset vertically from the number columns by about one row in the level 4 images looked at, so pairing rows depends on order; this makes line items harder than the answer key implies. Unfair items affect any model reading the same image, so compare models on the same images and do not treat level 4's absolute accuracy as a measure of model quality. Details: [docs/what-can-go-wrong.md](docs/what-can-go-wrong.md).
- **One date convention gap.** The prompt does not say how to read ambiguous numeric dates.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=your-key" > .env      # .env is gitignored; never commit it

python generator/generate_invoices.py       # writes data/synthetic/
python -m pytest tests -q
python runner/run_models.py --model gemini-3.1-flash-lite --per-level 30
python runner/score.py
python runner/compare.py --per-level 10
```

`generate_invoices.py` writes all four levels (120 invoices). `run_models.py` resumes: finished invoices are skipped, and any saved result with an API error is retried. It stops after 3 failures in a row (`--max-consecutive-errors`), each of which has already used 4 attempts.

## Test your own invoices

Put each invoice as an image plus a JSON answer key with the same base name, inside one subfolder of `data/my_invoices/` (the subfolder name is used as the "level"; the whole folder is gitignored):

```
data/my_invoices/
  mine/
    my_001.png      # or .jpg
    my_001.json
```

The JSON uses the same keys as the files in `data/synthetic/`: `invoice_number`, `vendor`, `invoice_date` (YYYY-MM-DD), `currency`, `line_items` (list of `description`, `quantity`, `unit_price`, `amount`), `subtotal`, `tax`, `total`.

Then run the model and score it. Results go to separate folders (both gitignored), so `results/summary.csv` is not touched:

```bash
python runner/run_models.py --model gemini-3.1-flash-lite --data data/my_invoices --out results/raw_mine
python runner/score.py --data data/my_invoices --raw results/raw_mine --out results/mine
```

The summary is printed and saved as `results/mine/summary.csv`, with per-invoice rows in `results/mine/per_invoice.csv` and field-level mistakes in `results/mine/failures.csv`. `python runner/compare.py --results results/mine` compares models on your invoices once you have run more than one.
