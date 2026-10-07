# What can go wrong

Everything below comes from the saved runs in `results/raw/`, `results/per_invoice.csv`, `results/failures.csv` and `results/api_errors.csv`. Where a fact comes from an answer-key file or from the repo owner's manual review of images, it says so. Nothing is invented.

## Scope of the evidence

| Model | Invoices answered | API errors |
|---|---|---|
| gemini-3.1-flash-lite | 120 (30 per level, 4 levels) | 0 |
| gemini-3.8-flash | 0 | 2 (of the 2 invoices attempted) |

The large model has no scored answers, so this document says nothing about its extraction mistakes. Every extraction failure below is from `gemini-3.1-flash-lite`.

## Levels 1-3: one error in 90 invoices

`gemini-3.1-flash-lite` made exactly one field error across the 90 invoices of levels 1-3.

- Invoice: `level2_mixed_003` (level 2, USD, US address)
- The image prints `Date: 05/10/2026`. The answer key is `2026-05-10`, which is MM/DD/YYYY.
- The model returned `2026-10-05`, so it read the date as DD/MM/YYYY.
- Every other field on that invoice was correct, so it scored 7 of 8 fields (0.875 accuracy) and is the only non-exact invoice among those 90.

Checked by hand against the image and the answer-key JSON: the key is right and the scorer is right. This is a genuine model error. The invoice carries US cues (USD, a US address) and the model did not use them. The prompt only says `YYYY-MM-DD` for the output and does not say how to resolve day/month order.

## Level 4 (hard): 12 of 30 invoices not exact

Level 4 has 8-15 line items, smaller text, numeric-only dates with day <= 12 (so day/month order is genuinely ambiguous), US and non-US vendors with the country printed in the address, and heavier scan degradation than level 3.

`gemini-3.1-flash-lite`: 94.1% accuracy, 60.0% exact-invoice, so **12 of 30 invoices were not exact**. Field errors (15 in total):

| Field | Invoices with an error |
|---|---|
| invoice_number | 7 |
| invoice_date | 7 |
| line_items | 1 |
| vendor, currency, subtotal, tax, total | 0 |

Three invoices (`011`, `020`, `025`) have both an invoice-number and a date error, which is why 15 field errors fall on 12 invoices.

### Pattern 1: a 6 read as an 8

All 7 invoice-number errors are a `6` read as an `8`:

| id | expected | got |
|---|---|---|
| level4_hard_008 | INV-2026-55529 | INV-2028-55529 |
| level4_hard_009 | INV-2026-36824 | INV-2026-38824 |
| level4_hard_011 | INV-2026-71889 | INV-2028-71889 |
| level4_hard_018 | INV-2026-59066 | INV-2026-59068 |
| level4_hard_020 | INV-2026-24086 | INV-2028-24086 |
| level4_hard_025 | INV-2026-18460 | INV-2026-18480 |
| level4_hard_026 | INV-2026-70686 | INV-2026-70688 |

These patterns are read from the CSV text; of these invoices, only `008` (fair) and `018` (unfair) were checked against their images. The same `6`-to-`8` misread is in the year of two dates: `level4_hard_011` (`2026-08-03` read as `2028-08-03`) and `level4_hard_020` (`2026-11-08` read as `2028-11-06`). The one digit error that goes the other way is the day in `level4_hard_020`, where `08` was read as `06`.

### Pattern 2: day and month swapped

Four of the 7 date errors are pure day/month swaps:

| id | expected | got |
|---|---|---|
| level4_hard_014 | 2026-03-08 | 2026-08-03 |
| level4_hard_019 | 2026-04-01 | 2026-01-04 |
| level4_hard_024 | 2026-04-11 | 2026-11-04 |
| level4_hard_028 | 2026-12-08 | 2026-08-12 |

The convention in these images: US vendors print MM/DD/YYYY, other vendors print DD/MM/YYYY (with `/`, `.` or `-`), and the vendor's country is printed in the address line. Day is always <= 12 and never equal to the month, so both readings are valid dates. Based on the answer keys (the `currency` field in `level4_hard_014.json`, `_019.json`, `_024.json` and `_028.json`), all four swapped invoices are USD; the keys have no country field. In each of the four the model returned the day-first reading. Whether it ignored a legible country is only known for some of them: image review judged `014` as country legible and ignored, `019` as borderline (address too blurred to read the country), and `024` and `028` have not been checked against their images.

The other 3 date errors are not swaps: `011` and `020` (the 2028 years above, plus the day in `020`), and `level4_hard_025`, where `2026-02-08` was read as `2026-05-02` (a swap of the expected date would be `2026-08-02`).

The remaining failure is `level4_hard_015` (line items): `12/13 lines matched, model returned 13`. It has not been looked into.

### Fairness audit (a sample of 5, not the full set)

The repo owner looked at the images of 5 of the 12 non-exact invoices. **This is a sample of 5, not the full set: the other 7 failing invoices were never checked against their images.** Of the 5, 4 were judged and 1 (`level4_hard_015`) is not yet checked.

| id | field | verdict | reason |
|---|---|---|---|
| level4_hard_014 | invoice_date | fair | The country is legible and the model ignored it. |
| level4_hard_008 | invoice_number | fair | The number is clearly legible; the model read the year as 2028. |
| level4_hard_019 | invoice_date | borderline | The address is too blurred to read the country. |
| level4_hard_018 | invoice_number | unfair | The last digit is ambiguous between 6 and 8. |
| level4_hard_015 | line_items | not yet checked | |

So of the 4 judged: 2 fair, 1 borderline, 1 unfair. Because the other 7 failing invoices were never checked against their images, it is not known how many of the 7 `6`-to-`8` invoice-number errors are legibility problems like `018` rather than model mistakes like `008`.

### Known defect: row offset under rotation

In the level 4 images the repo owner looked at, rotation shifts the description column vertically relative to the number columns by about one row, so pairing a description with its quantity and prices depends on row order. This makes line items harder than the answer key implies. How many of the level 4 failures it causes has not been measured.

### Caveat

An item that is unfair for one model (an ambiguous digit, an unreadable country) is unfair for any model reading the same image. This has not been tested on a second model. So compare models on the same images, and do not treat level 4's absolute accuracy as a measure of model quality.

## API failures on the large model (2 of 2 attempts)

- `level1_clean_001`: `503 UNAVAILABLE`, "This model is currently experiencing high demand".
- `level1_clean_002`: `429 RESOURCE_EXHAUSTED`, free-tier quota for `gemini-3.8-flash` (limit 20 requests, retry in about 12 hours). An earlier saved attempt at this same invoice had failed with `504 DEADLINE_EXCEEDED`; that file was overwritten by the later 429.

The run was stopped after these two results instead of looping. These are infrastructure failures, not extraction mistakes. `score.py` excludes them from accuracy and from `results/failures.csv`, and lists them in `results/api_errors.csv` instead.
