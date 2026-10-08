import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

import compare  # noqa: E402


def rows(model, level, ids, error_ids=()):
    return [{"model": model, "level": level, "id": i, "accuracy": 1.0, "exact": True, "seconds": 1.0,
             "cost_usd": 0.001, "api_error": i in error_ids} for i in ids]


@pytest.fixture
def results(tmp_path):
    ids = [f"l4_{n:03d}" for n in range(1, 6)]
    data = (rows("small", "l4", ids)
            + rows("big", "l4", ids[:3] + ids[3:], error_ids=ids[3:])      # answered 001-003 only
            + rows("broken", "l4", ids[:3], error_ids=ids[:3])             # error-only model
            + rows("other", "l4", ids[1:4]))                               # answered 002-004
    pd.DataFrame(data).to_csv(tmp_path / "per_invoice.csv", index=False)
    return tmp_path


def run(monkeypatch, results, *extra):
    monkeypatch.setattr(sys, "argv", ["compare.py", "--results", str(results), *extra])
    compare.main()
    return pd.read_csv(results / "summary_same_invoices.csv")


def test_error_only_model_is_skipped_not_zeroing_the_comparison(monkeypatch, results):
    out = run(monkeypatch, results, "--per-level", "20")
    assert "broken" not in set(out.model)
    assert set(out.model) == {"small", "big", "other"}
    assert set(out.n) == {2}  # shared by small, big and other: 002 and 003


def test_models_option_compares_only_listed_models(monkeypatch, results):
    out = run(monkeypatch, results, "--models", "small,big", "--per-level", "20")
    assert set(out.model) == {"small", "big"} and set(out.n) == {3}


def test_models_option_rejects_unknown_model(monkeypatch, results):
    monkeypatch.setattr(sys, "argv", ["compare.py", "--results", str(results), "--models", "small,nope"])
    with pytest.raises(SystemExit) as e:
        compare.main()
    assert "nope" in str(e.value)


def test_per_level_limit_applies_to_shared_ids(monkeypatch, results):
    out = run(monkeypatch, results, "--models", "small,big", "--per-level", "2")
    assert set(out.n) == {2}
