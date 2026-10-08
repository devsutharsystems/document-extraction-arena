"""Compare models on the SAME invoices, because n differs between models.

Run runner/score.py first (it writes results/per_invoice.csv). For each level this keeps
the first --per-level invoice ids (sorted) that every model answered without an API error.
"""
import argparse
from pathlib import Path

import pandas as pd


def shared_invoices(df, per_level):
    """Per level, the first per_level sorted ids answered (no API error) by every model that
    answered at least one invoice in that level. Error-only models are skipped, not counted."""
    answered = df[~df.api_error]
    shared_by_level = {}
    for level, g in answered.groupby("level"):
        counts = g.groupby("id").model.nunique()
        shared_by_level[level] = sorted(counts[counts == g.model.nunique()].index)[:per_level]
    return shared_by_level


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=10)
    ap.add_argument("--results", default="results", help="folder holding per_invoice.csv (from score.py --out)")
    ap.add_argument("--models", help="comma-separated model names to compare (default: all models)")
    args = ap.parse_args()

    df = pd.read_csv(Path(args.results) / "per_invoice.csv")
    if args.models:
        wanted = [m.strip() for m in args.models.split(",") if m.strip()]
        unknown = [m for m in wanted if m not in set(df.model)]
        if unknown:
            raise SystemExit(f"unknown model(s) {', '.join(unknown)}; available: {', '.join(sorted(df.model.unique()))}")
        df = df[df.model.isin(wanted)]

    shared_by_level = shared_invoices(df, args.per_level)
    keep = []
    for level, ids in shared_by_level.items():
        models = sorted(df[(df.level == level) & ~df.api_error].model.unique())
        print(f"{level}: {len(ids)} shared invoices, compared models: {', '.join(models)}")
        keep += ids
    if not keep:
        raise SystemExit("No invoice was answered without an API error by every model.")
    same = df[df.id.isin(keep) & ~df.api_error]
    same = same[same.apply(lambda r: r["id"] in shared_by_level.get(r["level"], []), axis=1)]

    summary = same.groupby(["model", "level"]).agg(
        n=("id", "count"),
        accuracy_pct=("accuracy", lambda s: round(s.mean() * 100, 1)),
        exact_invoice_pct=("exact", lambda s: round(s.mean() * 100, 1)),
        avg_seconds=("seconds", lambda s: round(s.mean(), 1)),
        cost_per_invoice_usd=("cost_usd", lambda s: round(s.mean(), 5)),
    ).reset_index()
    summary.to_csv(Path(args.results) / "summary_same_invoices.csv", index=False)
    print("\nn = number of shared invoices scored per model and level; every row in a level uses the same invoices")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
