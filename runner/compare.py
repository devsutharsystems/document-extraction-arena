"""Compare models on the SAME invoices, because n differs between models.

Run runner/score.py first (it writes results/per_invoice.csv). For each level this keeps
the first --per-level invoice ids (sorted) that every model answered without an API error.
"""
import argparse
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=10)
    ap.add_argument("--results", default="results", help="folder holding per_invoice.csv (from score.py --out)")
    args = ap.parse_args()

    df = pd.read_csv(Path(args.results) / "per_invoice.csv")
    n_models = df.model.nunique()  # count before dropping API errors
    df = df[~df.api_error]

    keep = []
    for level, g in df.groupby("level"):
        counts = g.groupby("id").model.nunique()
        shared = sorted(counts[counts == n_models].index)[: args.per_level]
        keep += shared
        print(f"{level}: {len(shared)} shared invoices")
    if not keep:
        raise SystemExit("No invoice was answered without an API error by every model.")
    same = df[df.id.isin(keep)]

    summary = same.groupby(["model", "level"]).agg(
        n=("id", "count"),
        accuracy_pct=("accuracy", lambda s: round(s.mean() * 100, 1)),
        exact_invoice_pct=("exact", lambda s: round(s.mean() * 100, 1)),
        avg_seconds=("seconds", lambda s: round(s.mean(), 1)),
        cost_per_invoice_usd=("cost_usd", lambda s: round(s.mean(), 5)),
    ).reset_index()
    summary.to_csv(Path(args.results) / "summary_same_invoices.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
