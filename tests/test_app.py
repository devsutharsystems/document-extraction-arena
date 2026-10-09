import sys
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

import run_models  # noqa: E402


@pytest.fixture
def no_api():
    """Any attempt to build a client or call the model during the test fails loudly."""
    with mock.patch.object(run_models, "make_client", side_effect=AssertionError("API client created")) as mk, \
         mock.patch.object(run_models, "extract", side_effect=AssertionError("API call made")) as ex:
        yield mk, ex


def load():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.run()
    return at


def test_app_loads_without_exceptions_and_makes_no_api_call(no_api):
    at = load()
    assert not at.exception
    mk, ex = no_api
    mk.assert_not_called()
    ex.assert_not_called()


def test_results_tab_shows_numbers_computed_from_the_csv(no_api):
    at = load()
    same = pd.read_csv(ROOT / "results" / "summary_same_invoices.csv")
    l4 = same[same.level == "level4_hard"].set_index("model")
    text = " ".join(m.value for m in at.markdown)
    for model in ("gemini-3.6-flash", "gemini-3.1-flash-lite"):
        n = int(l4.loc[model, "n"])
        exact = round(l4.loc[model, "exact_invoice_pct"] / 100 * n)
        assert f"{exact} of {n} fully correct" in text
        assert f"Accuracy {l4.loc[model, 'accuracy_pct']}%" in text
    assert "Preliminary · 16 hard invoices" in text
    assert "15 of 16 fully correct" in text and "11 of 16 fully correct" in text


def fake_result(text=None, error=None):
    return {"response_text": text, "seconds": 1.5, "input_tokens": 1000, "output_tokens": 500,
            "thinking_tokens": 0, "error": error}


def click_run(monkeypatch, result):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    with mock.patch.object(run_models, "make_client", return_value=object()), \
         mock.patch.object(run_models, "extract", return_value=result) as ex:
        at = load()
        at.button[0].click().run()
    return at, ex


def test_run_scores_a_perfect_answer_8_of_8(monkeypatch):
    sample = ROOT / "examples" / "samples" / "level1_clean_001.json"
    at, ex = click_run(monkeypatch, fake_result(sample.read_text()))
    assert not at.exception
    ex.assert_called_once()
    assert ex.call_args.kwargs["no_retry"] is True
    assert any("8 / 8 fields correct" in m.value for m in at.markdown)


@pytest.mark.parametrize("err, words", [("429 RESOURCE_EXHAUSTED", "free quota"), ("503 UNAVAILABLE", "busy")])
def test_friendly_errors(monkeypatch, err, words):
    at, _ = click_run(monkeypatch, fake_result(error=err))
    assert not at.exception
    assert any(words in e.value for e in at.error)
