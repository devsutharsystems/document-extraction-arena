import argparse
import json
import time
from pathlib import Path
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

_client = None


def get_client():
    """Created on first use, so importing this module (tests, --dry-run) needs no API key."""
    global _client
    if _client is None:
        load_dotenv()
        _client = genai.Client(http_options=types.HttpOptions(timeout=90_000))
    return _client

PROMPT = (
    "You are reading an invoice image. Return ONLY a JSON object with these keys: "
    "invoice_number (string), "
    "vendor (the company name that issued the invoice: name only, no address), "
    "invoice_date (YYYY-MM-DD), "
    "currency (ISO 4217 code such as INR, USD, EUR), "
    "line_items (list of objects with description, quantity, unit_price, amount), "
    "subtotal, tax, total. "
    "All money values must be plain numbers: no currency symbols, no thousands separators."
)

MIME = {".png": "image/png", ".jpg": "image/jpeg"}


def extract(model, image_path, no_retry=False):
    data = image_path.read_bytes()
    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0)
    err = None
    for attempt in range(1 if no_retry else 4):
        try:
            start = time.time()
            resp = get_client().models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=data, mime_type=MIME[image_path.suffix]), PROMPT],
                config=config,
            )
            u = resp.usage_metadata
            return {
                "response_text": resp.text,
                "seconds": round(time.time() - start, 2),
                "input_tokens": u.prompt_token_count or 0,
                "output_tokens": u.candidates_token_count or 0,
                "thinking_tokens": u.thoughts_token_count or 0,
                "error": None,
            }
        except Exception as e:  # rate limits and network errors: wait, then retry
            err = str(e)
            if not no_retry:
                time.sleep(2 ** attempt * 2)
    return {"response_text": None, "seconds": None, "input_tokens": 0,
            "output_tokens": 0, "thinking_tokens": 0, "error": err}


def level_names(data_dir):
    return sorted(p.name for p in Path(data_dir).iterdir() if p.is_dir())


def select_invoices(data_dir, levels, per_level):
    """Answer-key paths to run: the given levels in the given order (None = all, sorted)."""
    valid = level_names(data_dir)
    levels = valid if levels is None else levels
    unknown = [lv for lv in levels if lv not in valid]
    if unknown:
        raise ValueError(f"unknown level(s) {', '.join(unknown)}; valid levels: {', '.join(valid)}")
    truths = []
    for level in dict.fromkeys(levels):  # drop repeats, keep order
        truths += sorted((Path(data_dir) / level).glob("*.json"))[:per_level]
    return truths


def status(out_path):
    """'run' (no result yet), 'retry' (saved API error) or 'skip' (finished)."""
    if not out_path.exists():
        return "run"
    return "skip" if json.loads(out_path.read_text()).get("error") is None else "retry"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--per-level", type=int, default=30)
    ap.add_argument("--levels", help="comma-separated level folders, run in this order (default: all)")
    ap.add_argument("--data", default="data/synthetic")
    ap.add_argument("--out", default="results/raw")
    ap.add_argument("--max-consecutive-errors", type=int, default=3)
    ap.add_argument("--no-retry", action="store_true",
                    help="save a failed API call as an error record at once: one request, no retries, no backoff")
    ap.add_argument("--min-interval", type=float, default=0,
                    help="minimum seconds between the starts of two requests (0 = no pacing)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print which invoices would run, retry or be skipped; no API calls, no files written")
    args = ap.parse_args()

    levels = [x.strip() for x in args.levels.split(",") if x.strip()] if args.levels else None
    try:
        truths = select_invoices(args.data, levels, args.per_level)
    except ValueError as e:
        ap.error(str(e))

    out_dir = Path(args.out) / args.model.replace("/", "_")

    if args.dry_run:
        counts = {"run": 0, "retry": 0, "skip": 0}
        for i, truth_path in enumerate(truths, 1):
            st = status(out_dir / f"{truth_path.stem}.json")
            counts[st] += 1
            label = {"run": "WOULD RUN", "retry": "WOULD RETRY (saved error)", "skip": "SKIP (already ok)"}[st]
            print(f"[{i}/{len(truths)}] {truth_path.stem}  {label}")
        print(f"dry run: {counts['run']} to run, {counts['retry']} to retry, {counts['skip']} skipped; no API calls made")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    consecutive_errors = 0
    last_start = None
    for i, truth_path in enumerate(truths, 1):
        inv_id = truth_path.stem
        out_path = out_dir / f"{inv_id}.json"
        if status(out_path) == "skip":  # already done: lets you resume after an interruption
            continue                    # (a saved API failure falls through and is retried)
        image = next(p for p in truth_path.parent.glob(inv_id + ".*") if p.suffix in MIME)
        if last_start is not None and args.min_interval > 0:
            wait = args.min_interval - (time.monotonic() - last_start)
            if wait > 0:
                time.sleep(wait)
        last_start = time.monotonic()
        result = extract(args.model, image, no_retry=args.no_retry)
        result.update({"id": inv_id, "level": truth_path.parent.name, "model": args.model})
        out_path.write_text(json.dumps(result, indent=2))
        tokens = result["input_tokens"] + result["output_tokens"] + result["thinking_tokens"]
        print(f"[{i}/{len(truths)}] {inv_id}  {result['seconds']}s  {tokens} tokens  "
              f"{result['error'] or 'ok'}", flush=True)
        consecutive_errors = consecutive_errors + 1 if result["error"] else 0
        if consecutive_errors >= args.max_consecutive_errors:
            raise SystemExit(f"Stopping: {consecutive_errors} API failures in a row. "
                             f"Last error: {result['error']}")
        time.sleep(1)  # gentle pause so we stay under rate limits


if __name__ == "__main__":
    main()
