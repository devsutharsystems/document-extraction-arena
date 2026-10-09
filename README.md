# Document Extraction Arena

A small benchmark that asks Gemini models to read invoice images and return structured JSON, then scores each answer field by field against a known answer key.

## Status

- Dataset: 120 synthetic invoices (4 levels x 30), generated with a fixed seed (answer keys are reproducible everywhere; images are byte-identical on macOS, and differ slightly elsewhere because of the font).
- `gemini-3.1-flash-lite`: run on all 120 invoices.
- `gemini-3.6-flash`: **preliminary run, `level4_hard` only.** 16 invoices answered (`level4_hard_001` to `_016`) out of the 20 planned; the run stopped at `level4_hard_017` on the free-tier daily quota (429). It was chosen as the "large model" because it had the most completed invoices under free-tier limits, not because of its score.
- `gemini-3.8-flash`: partial run, 4 invoices answered (`level4_hard_001` to `_004`). `gemini-3.7-flash`: 0 answered. Both were blocked by 503 "high demand" errors and the free tier's 20 requests per day for each of these models (`results/api_errors.csv`). They are not used in the comparison.

## Results

Scores come from `python runner/score.py` (`results/summary.csv`). API failures are excluded from accuracy and reported separately.

| Model | Level | n | Accuracy | Exact invoice | Avg seconds | Cost / invoice (USD) |
|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | level1_clean | 30 | 100.0% | 100.0% | 6.9 | 0.00080 |
| gemini-3.1-flash-lite | level2_mixed | 30 | 99.6% | 96.7% | 8.8 | 0.00079 |
| gemini-3.1-flash-lite | level3_noisy | 30 | 100.0% | 100.0% | 9.6 | 0.00080 |
| gemini-3.1-flash-lite | level4_hard | 30 | 94.1% | 60.0% | 7.2 | 0.00141 |
| gemini-3.6-flash (preliminary) | level4_hard | 16 | 99.9% | 93.8% | 10.8 | 0.00873 |
| gemini-3.8-flash (partial) | level4_hard | 4 | 100.0% | 100.0% | 26.8 | 0.00682 |

- Accuracy is the mean of 8 field scores per invoice (invoice number, vendor, date, currency, subtotal, tax, total, line items). "Exact invoice" means all 8 were right.
- Cost uses the per-million-token prices in `runner/score.py`, counting thinking tokens as output. The prices were checked against Google's pricing page on 8 October 2026 (3.1 Flash-Lite $0.25 / $1.50; 3.x Flash $0.75 / $3.75 per 1M tokens through December 31, 2026, then $1.50 / $7.50). Costs are paid-tier equivalents; all runs used the free tier.
- Same-invoice comparison: `python runner/compare.py --models gemini-3.1-flash-lite,gemini-3.6-flash --per-level 20` compares models on the invoices both answered.
- **Preliminary large-model comparison (n = 16).** Comparison on `level4_hard_001` to `level4_hard_016` (n = 16 shared invoices), `gemini-3.1-flash-lite` vs `gemini-3.6-flash`, from `results/summary_same_invoices.csv`: accuracy 96.0% vs 99.9%, exact-invoice 68.8% vs 93.8%, average 6.5 s vs 10.8 s per call, cost 0.00145 vs 0.00873 USD per invoice (paid-tier equivalent; about 6 times the cost). On these 16 invoices the larger model made fewer mistakes but was slower and costlier. Flash-lite's 12 level-4 failures: 5 of them fall inside these 16 invoices (`008`, `009`, `011`, `014`, `015`); the other 7 are on invoices the large model has not answered. On the 16 invoices the large model had 1 non-exact invoice (`level4_hard_011`, line items: 14 of 15 matched). This says nothing about `level4_hard_017` to `_030`, and levels 1-3 were run on flash-lite only. n is small because the free tier allows 20 requests per day for each larger Flash model (500 for flash-lite) and Google returned repeated 503 "high demand" errors over two days. The plan is to extend the run to 20 (or 30) invoices after the quota resets and update these numbers. Paid-tier equivalent costs use the prices in `runner/score.py` (3.x Flash: $0.75 in / $3.75 out per 1M tokens through December 31, 2026, doubling to $1.50 / $7.50 from January 1, 2027; flash-lite $0.25 / $1.50; source https://ai.google.dev/gemini-api/docs/pricing). All runs used the free tier.
- **Level 4 (hard)** has 8-15 line items, smaller text, numeric-only dates with day <= 12 (so day/month order is genuinely ambiguous), US and non-US vendors, and heavier scan degradation than level 3. On it, flash-lite got 12 of 30 invoices not fully right: 7 invoice numbers, 7 dates, 1 line-item list. In `results/failures.csv`, all 7 invoice-number errors are 6-vs-8 misreads; of the 7 date errors, 4 are day/month swaps (`level4_hard_014`, `019`, `024`, `028`), 2 are digit misreads (`2026` read as `2028`) and 1 (`level4_hard_025`) is neither. This comes from the failure text, not from checking images (see the audit note below and [`docs/fairness_audit.csv`](docs/fairness_audit.csv)).
- Level 2 has one non-exact invoice, `level2_mixed_003`: the model read `05/10/2026` as 5 October instead of 10 May. See [docs/what-can-go-wrong.md](docs/what-can-go-wrong.md), which covers levels 1-4.

## Limitations

- **Synthetic data.** Invoices are generated, not real. Real invoices have messier layouts, stamps, handwriting and languages that this set does not cover.
- **One layout.** Every invoice uses the same template, so the results say little about unseen layouts.
- **Near-ceiling on levels 1-3.** Flash-lite scored 100.0%, 99.6% and 100.0% there, so those levels cannot separate strong models; level 4 was added for that. One more failed invoice in a 30-invoice level moves exact-invoice % by 3.3 points (and accuracy by about 0.4).
- **Free-tier rate limits.** The free tier limits requests per day per model: 20 each for `gemini-3.6-flash`, `gemini-3.7-flash` and `gemini-3.8-flash`, 500 for `gemini-3.1-flash-lite` (as shown on the owner's Google AI Studio rate-limit page); failures count. The large model `gemini-3.6-flash` hit that limit after 16 answered invoices plus failed attempts; 503 "high demand" errors from Google also used up requests.
- **Small n for the large model.** 16 invoices on level 4 only (preliminary), against 30 per level for flash-lite. Compare models only on the same invoices; the model comparison says nothing about the 14 uncovered level 4 invoices.
- **Level 4 is only partly audited and has a known defect.** The repo owner looked at the images of 5 of the 12 non-exact level 4 invoices ([`docs/fairness_audit.csv`](docs/fairness_audit.csv)): 2 fair, 1 borderline, 1 unfair (`level4_hard_018`, last digit ambiguous between 6 and 8) and 1 not yet checked (`level4_hard_015`). This is a sample of 5, not the full set: the other 7 failing invoices were never checked against their images. Also, with rotation the description column is offset vertically from the number columns by about one row in the level 4 images looked at, so pairing rows depends on order; this makes line items harder than the answer key implies. Unfair items affect any model reading the same image, so compare models on the same images and do not treat level 4's absolute accuracy as a measure of model quality. Details: [docs/what-can-go-wrong.md](docs/what-can-go-wrong.md).
- **One date convention gap.** The prompt does not say how to read ambiguous numeric dates.
- **Gemini only.** The benchmark and the web app work with Google Gemini models only, using a Google Gemini API key (free from Google AI Studio). Other providers are not supported yet.

## Possible next steps

- Support for other providers (e.g. OpenAI, Anthropic).
- Extend the `gemini-3.6-flash` run to all 20 (or 30) level 4 invoices after the free-tier quota resets.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=your-key" > .env      # .env is gitignored; never commit it

python generator/generate_invoices.py --out data/regenerated   # the 120 invoices are already in data/synthetic/
python -m pytest tests -q
python runner/run_models.py --model gemini-3.1-flash-lite --per-level 30
python runner/score.py
python runner/compare.py --models gemini-3.1-flash-lite,gemini-3.6-flash --per-level 20
```

`generate_invoices.py` writes all four levels (120 invoices); options are `--out` (default `data/synthetic`), `--count` (30) and `--seed` (42). Regenerate into a separate folder, as above, so the images the models were scored on are not overwritten. On macOS the regenerated files are identical to the committed ones. On Windows and Linux a fallback font is used (Arial on Windows, DejaVu Sans otherwise), so the images differ slightly while the answer keys are identical. `run_models.py` resumes: finished invoices are skipped, and any saved result with an API error is retried. It stops after 3 failures in a row (`--max-consecutive-errors`), each of which has already used 4 attempts.

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

A worked example is in [`examples/my_invoice/`](examples/my_invoice/): a fictional invoice image with a correct answer key, to copy as a template for your own. It scored 100% on `gemini-3.1-flash-lite` in my own run, measured once on this single invoice, so it shows the workflow and says little about model quality.

## Web app

A small Streamlit app lets you try an invoice, see the saved results and read how it works, without touching the command line scripts:

```bash
pip install -r requirements.txt
streamlit run app.py
```

It runs locally in your browser. Pick a sample from `examples/samples/` (or upload an image and an optional answer key), choose a model and click **Run**; each click makes one API call with no retries. The key comes from the `GEMINI_API_KEY` environment variable or a password box in the Try tab; the app never shows or saves it, and it does not read `.env`. The Results tab reads `results/*.csv` and `results/raw/`. On the free tier Google may use uploaded content to improve its products ([terms](https://ai.google.dev/gemini-api/terms)), so use the samples, not real invoices with personal or business data.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
