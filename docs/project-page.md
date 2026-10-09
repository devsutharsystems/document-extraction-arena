# Document Extraction Arena: test how well an AI model reads invoices

You will build a small benchmark that generates fake invoices with known answers, asks a Gemini model to read them, and scores every field with plain Python code.

## Quick facts

| | |
|---|---|
| **Time** | Measured once on the author's laptop: 13 s to install the requirements, 18 s to generate the invoices, 10 s for the tests. Model time depends on rate limits: 974.6 seconds (about 16.2 minutes) for all 120 calls, from `results/per_invoice.csv`. Time spent reading the answer keys, the failures and the docs was not measured, so this page does not give a total for it. |
| **Steps** | 6 |
| **Stack** | Python, Pillow, Faker, google-genai, pytest (plus pandas for scoring, NumPy for the image noise and python-dotenv for the key file; see `requirements.txt`) |
| **Cost** | $0.0008 per invoice on levels 1 and 3, $0.00079 on level 2 and $0.00141 on level 4 for `gemini-3.1-flash-lite` (`results/summary.csv`; pricing source: https://ai.google.dev/gemini-api/docs/pricing). All 120 invoices summed to $0.1144. **These are paid-tier equivalents, calculated with the prices written in `runner/score.py`, which were checked against Google's pricing page on 8 October 2026 (3.1 Flash-Lite $0.25 / $1.50 per 1M tokens; 3.x Flash $0.75 / $3.75 through December 31, 2026, then $1.50 / $7.50). All runs used the free tier, which charged nothing.** |

## Something worth taking away

**A model can get every money field right and still get 12 of 30 invoices (40%) wrong, mostly on a 6 and a date.**

On the hardest level, `gemini-3.1-flash-lite` scores 94.1% accuracy but only 60.0% of invoices are exact (all 8 fields right), according to `results/summary.csv`. The 15 field failures on that level in `results/failures.csv` have two patterns:

- **A 6 read as an 8 in invoice numbers.** All 7 invoice-number errors are this, for example `INV-2026-55529` came back as `INV-2028-55529`. The same misread turns `2026` into `2028` in the year of 2 dates.
- **Day and month swapped.** 4 of the 7 date errors are swaps, for example `2026-03-08` came back as `2026-08-03`. The convention in these images is that US invoices print the month first and other countries print the day first, with the country in the address. The answer keys show all 4 swapped invoices are USD, and in each the model returned the day-first reading. Image review ([`fairness_audit.csv`](fairness_audit.csv)) judged one of them (`014`) as a legible country the model ignored, one (`019`) as borderline because the address is too blurred, and the other 2 have not been checked against their images.
- **Money:** 0 errors in subtotal, tax and total. A single accuracy number hides this; look at which fields fail, not only how many.

**What this can't tell you.** The invoices are synthetic, they all use one layout, and the larger model has only a preliminary run of 16 invoices on level 4, so this says nothing about real documents or about which model is better in general. Level 4 is also not a clean measure: the author checked the images of 5 of the 12 non-exact invoices (2 fair, 1 borderline, 1 unfair because a last digit is ambiguous between 6 and 8, and 1 not yet checked; see [`fairness_audit.csv`](fairness_audit.csv)). The other 7 were never checked against their images, so some of the 7 `6`-to-`8` errors may be legibility problems rather than model mistakes. See step 5.

One hint that the misses are not all unreadable images: on the 16 shared invoices, `gemini-3.6-flash` got `008`, `009`, `014` and `015` exact, so what flash-lite missed on those 4 images was readable by at least one model; this says nothing about invoices `017` to `030`.

## A useful starting point

The finished project, with the data, results and tests, is here: https://github.com/devsutharsystems/document-extraction-arena

```bash
git clone https://github.com/devsutharsystems/document-extraction-arena.git
```

## Six steps

Times marked "measured once on the author's laptop" were taken once on a fresh clone; the others were re-timed later with `time`. Steps that call the model depend on rate limits; for those, the measured model run time from `results/per_invoice.csv` is 974.6 s for all 120 calls (215.6 s for the 30 level 4 calls).

### 1. Generate invoices and read an answer key (measured once on the author's laptop: 13 s install, 18 s generate)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python generator/generate_invoices.py
```

This writes 120 invoices (4 levels x 30) to `data/synthetic/`, each as an image plus a JSON answer key. The generator uses a fixed seed, so you get the same invoices every time. Open one key and compare it with its image:

```bash
cat data/synthetic/level2_mixed/level2_mixed_003.json
```

### 2. Check the dataset with tests (measured once on the author's laptop: 10 s)

```bash
python -m pytest tests -q
```

The tests check the data, not a model: every line amount equals quantity times price, the subtotal is the sum of the lines, tax and total add up, and level 4 dates are numeric with the day at most 12. All tests pass. You do not need a key for this step.

### 3. Run a model (dry run measured with `time`: 0.4 s; a real run depends on rate limits)

Put your key in a file called `.env` (it is listed in `.gitignore`; never commit it):

```bash
echo "GEMINI_API_KEY=your-key" > .env
python runner/run_models.py --model gemini-3.1-flash-lite --per-level 30
```

Preview what would run first, without calling the API:

```bash
python runner/run_models.py --model gemini-3.1-flash-lite --levels level4_hard --per-level 10 --dry-run
```

The runner saves one JSON file per invoice, so you can stop and restart. It skips finished invoices, retries saved API errors, and stops after 3 failures in a row. The repo already contains saved results for `gemini-3.1-flash-lite`, so the first command skips everything unless you delete them.

### 4. Score it (measured with `time`: 0.6 s for `score.py`, 0.3 s for `compare.py`)

```bash
python runner/score.py
python runner/compare.py --models gemini-3.1-flash-lite,gemini-3.6-flash --per-level 20
```

`score.py` prints a table per model and level and writes `results/summary.csv`, `results/failures.csv` (extraction mistakes only) and `results/api_errors.csv` (calls that never returned an answer). `compare.py` compares models on the same invoices; use `--models` to pick two.

### 5. Check what can go wrong (reading; time not measured)

Read [docs/what-can-go-wrong.md](what-can-go-wrong.md). It lists the real failures by id: the `6`-to-`8` invoice numbers, the day/month swaps, and the API errors. It also records a fairness audit of level 4 ([`fairness_audit.csv`](fairness_audit.csv)), and its limits: only 5 of the 12 non-exact invoices were looked at against their images, 1 of those 5 is not yet checked, and the other 7 were never checked. It also records a known defect: with rotation, the description column is offset from the number columns by about one row in the level 4 images the author looked at, which makes line items harder than the answer key implies.

### 6. Make a lens of your own: test your own invoices (a real run depends on rate limits)

Put an image and a matching JSON answer key (same base name, same keys as `data/synthetic/`) in a subfolder of `data/my_invoices/`. This folder is gitignored.

```
data/my_invoices/
  mine/
    my_001.png      # or .jpg
    my_001.json
```

```bash
python runner/run_models.py --model gemini-3.1-flash-lite --data data/my_invoices --out results/raw_mine
python runner/score.py --data data/my_invoices --raw results/raw_mine --out results/mine
```

Your results go to `results/mine/`, so the main results are not touched. Before you run this on real invoices, read the next section.

## Free to learn

You can follow this project on Google's free tier of the Gemini API: create an API key in Google AI Studio, put it in `.env`, and run steps 3 and 6. Free-tier keys have request limits, and they can run out mid-run. In this repo, the free tier allows 20 requests per day each for `gemini-3.6-flash`, `gemini-3.7-flash` and `gemini-3.8-flash`, and 500 per day for `gemini-3.1-flash-lite` (as shown on the owner's Google AI Studio rate-limit page), and failures count against it. `gemini-3.6-flash` answered 16 invoices before a daily-quota (429) error, `gemini-3.8-flash` answered 4, and `gemini-3.7-flash` answered 0, with repeated 503 "high demand" errors from Google along the way (`results/api_errors.csv`).

**Free-tier content may be used by Google.** Google's Gemini API terms (https://ai.google.dev/gemini-api/terms) say that unpaid services may use inputs and outputs to improve Google's products and allow human reviewers, and that paid services do not use prompts or responses to improve products. Read the current terms yourself. So use only the generated, fake invoices on the free tier. Real invoices should only go through a paid tier.

## How it works

**Synthetic data with known answers.** The generator builds each invoice from numbers it chose itself, then draws an image of it. Because the generator knows the right answer, no one has to label anything by hand. There are four levels:

| Level | What changes |
|---|---|
| level1_clean | One currency (INR), ISO dates, clean image |
| level2_mixed | Several currencies, mixed date styles, tax rates and number formats |
| level3_noisy | Same kinds of variation as level 2, plus phone-scan noise, blur and JPEG compression |
| level4_hard | 8-15 line items, smaller text, numeric-only dates, heavier degradation |

**Scoring in plain code, no AI judge.** `runner/score.py` compares each field of the model's JSON with the answer key:

- Money fields (subtotal, tax, total) are equal if they differ by less than 0.005.
- Invoice number and vendor are compared after trimming spaces and ignoring case. A vendor with an address added is wrong.
- Currency must match the ISO code. The date must match `YYYY-MM-DD` exactly.
- Line items are matched by description, and quantity, unit price and amount must all match. Extra invented lines lower the score.
- Accuracy is the mean of 8 field scores per invoice. An invoice is "exact" only if all 8 are right.

You can read the whole scorer in one sitting, and `tests/test_scorer.py` tests it.

**The date convention.** Dates are where the benchmark is hardest. In levels 2 and 3 the generator prints a date in one of several styles (numeric, or with a month name). For numeric dates, US invoices print month first (`MM/DD/YYYY`), Japanese invoices print year first, and the others print day first with `/`, `.` or `-`. The country is printed in the address. In level 4, every date is numeric with the day at most 12 and never equal to the month, so `05/10/2026` could be 5 October or 10 May, and the only clue is the country. The prompt does not tell the model how to resolve this.

## Before you start

**What leaves my computer?** The invoice image and the prompt text are sent to the Gemini API for every call in steps 3 and 6. Your `.env` file stays on your machine. Steps 1, 2, 4 and 5 send no invoice data anywhere.

**Do I need a key?** Only for steps 3 and 6. Scoring and the tests use files already on disk.

**What does it cost?** Paid-tier equivalents, with prices checked against Google's pricing page on 8 October 2026: `gemini-3.1-flash-lite` cost $0.0008 to $0.0014 per invoice, and `gemini-3.6-flash` about $0.0087 per level 4 invoice (n = 16). The free tier charged nothing but has quotas (https://ai.google.dev/gemini-api/docs/pricing).

**Will the results transfer to real invoices?** No. The invoices are fake, every one uses the same template, and the scan noise is added by code, not by a real camera. Real invoices have layouts, stamps, handwriting and languages that this set does not have. The results tell you how one model behaved on this test set. To learn about your own documents, use step 6 with your own data on a paid tier.

**What can't this project tell me?**
- How a model does on real documents.
- How the larger model compares beyond a preliminary run: on 16 level 4 invoices, `gemini-3.6-flash` scored 99.9% vs 96.0% for flash-lite (see below), but nothing is known about the other 14 level 4 invoices or levels 1-3.
- How good a model is from level 4's absolute accuracy. Part of that level was found to be unfair ([`fairness_audit.csv`](fairness_audit.csv)), and 7 of the 12 failing invoices have never been checked against their images.
- Which model is better. Only one comparison exists (n = 16, level 4, preliminary).

## Results for the larger model (preliminary)

`gemini-3.6-flash` was chosen as the large model because it had the most completed invoices under free-tier limits (16), not because of its score. `gemini-3.8-flash` answered 4 invoices (`level4_hard_001` to `_004`) and `gemini-3.7-flash` answered 0; those are partial or failed runs and are not compared. n is small because the free tier allows only 20 requests per day for each of the larger Flash models (500 for flash-lite) and Google returned repeated 503 "high demand" errors over two days. Only `level4_hard` was run; levels 1-3 were run on flash-lite only.

| Model | Level | n | Accuracy | Exact invoice | Avg seconds | Cost / invoice (USD, paid-tier equivalent) |
|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | level4_hard (invoices 001-016 only) | 16 | 96.0% | 68.8% | 6.5 | 0.00145 |
| gemini-3.6-flash | level4_hard (invoices 001-016 only) | 16 | 99.9% | 93.8% | 10.8 | 0.00873 |

Source: `python runner/compare.py --models gemini-3.1-flash-lite,gemini-3.6-flash --per-level 20` (`results/summary_same_invoices.csv`). Both rows use the same 16 invoices, `level4_hard_001` to `level4_hard_016`.

What the numbers show on these 16 invoices: the larger model had 1 non-exact invoice (`level4_hard_011`, line items) and flash-lite had 5 (`008`, `009`, `011`, `014`, `015`). The larger model was slower (10.8 s vs 6.5 s per call) and cost about 6 times more per invoice. Flash-lite has 12 failing invoices across all 30 level 4 invoices; 5 of those 12 fall inside these 16, and the comparison says nothing about the other 7 or about invoices `017` to `030`. With n = 16, one invoice moves exact-invoice % by 6.3 points.

Cost: paid-tier equivalents calculated from token counts with the prices in `runner/score.py` (source: https://ai.google.dev/gemini-api/docs/pricing). The 3.x Flash price ($0.75 in / $3.75 out per 1M tokens) is valid through December 31, 2026 and doubles from January 1, 2027. All runs used the free tier, so nothing was charged.

Plan: after the quota resets, extend the `gemini-3.6-flash` run to 20 (or 30) level 4 invoices and update these numbers.

## Links

- Repo: https://github.com/devsutharsystems/document-extraction-arena
- [README](../README.md)
- [What can go wrong](what-can-go-wrong.md)
- Licence: [Apache 2.0](../LICENSE)
- Google's Gemini API terms: https://ai.google.dev/gemini-api/terms
