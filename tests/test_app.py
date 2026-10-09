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
    sample = ROOT / "examples" / "samples" / "sample_01.json"
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


def test_sample_picker_lists_readable_names_with_answer_keys(no_api):
    at = load()
    picker = next(s for s in at.selectbox if s.label == "Use a sample")
    assert picker.options[:3] == ["US software invoice (USD)", "UK print shop (GBP)",
                                  "Indian GST bill, phone photo (INR)"]
    for stem in ("sample_01", "sample_02", "sample_03"):
        assert (ROOT / "examples" / "samples" / f"{stem}.json").exists()
    assert any("never saved" in m.value for m in at.markdown)


def expected_wrong_counts(n=16):
    """Independent recomputation from per_invoice.csv."""
    d = pd.read_csv(ROOT / "results" / "per_invoice.csv")
    ok = d[(d.level == "level4_hard") & ~d.api_error]
    ids = sorted(set(ok[ok.model == "gemini-3.6-flash"].id) & set(ok[ok.model == "gemini-3.1-flash-lite"].id))[:n]
    out = {}
    for model in ("gemini-3.1-flash-lite", "gemini-3.6-flash"):
        sub = ok[(ok.model == model) & ok.id.isin(ids)]
        for col in [c for c in d.columns if c.startswith("f_")]:
            out[(model, col[2:])] = int((sub[col] < 1).sum())
    return ids, out


def test_error_chart_data_matches_per_invoice_csv(no_api):
    sys.path.insert(0, str(ROOT))
    import app
    d = pd.read_csv(ROOT / "results" / "per_invoice.csv")
    ids, expected = expected_wrong_counts()
    assert len(ids) == 16
    counts = app.field_error_counts(d, app.shared_level4_ids(d, 16))
    got = {(r.Model, k): r.Wrong for r in counts.itertuples()
           for k, v in app.FIELD_LABELS.items() if v == r.Field}
    assert got == expected
    assert len(counts) == 16  # 8 fields x 2 models, one row each: grouped, not stacked
    spec = app.error_chart(counts, 16).to_dict()
    assert "stack" not in str(spec["layer"][0]["encoding"]["x"])
    assert spec["layer"][0]["encoding"]["x"]["scale"]["domain"] == [0, int(counts.Wrong.max()) + 1]
    assert spec["layer"][0]["encoding"]["x"]["axis"]["tickMinStep"] == 1
    assert spec["layer"][1]["transform"] == [{"filter": "(datum.Wrong > 0)"}]


def test_results_tab_has_one_same_invoices_caption_and_no_duplicate(no_api):
    at = load()
    assert not at.exception
    assert sum("Same invoices for both models" in c.value for c in at.caption) == 1
    assert not any("Same 16 hard invoices" in c.value for c in at.caption)


def test_inspect_defaults_to_the_known_date_mistake(no_api):
    at = load()
    by_label = {s.label: s for s in at.selectbox}
    assert by_label["Level"].value == "level4_hard"
    assert by_label["Invoice"].value == "level4_hard_014"
    assert [s.value for s in at.selectbox if s.key and s.key.startswith("inspect_model")] == ["gemini-3.1-flash-lite"]


def test_key_field_is_in_the_try_tab_and_there_is_no_sidebar(no_api, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = load()
    assert not at.exception
    field = next(w for w in at.text_input if w.key == "api_key_input")
    assert field.label == "Your Gemini API key (free from Google AI Studio)"
    assert len(at.sidebar.children) == 0
    assert any("never saved" in c.value for c in at.caption)


def test_run_without_a_key_asks_for_one_and_makes_no_call(no_api, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = load()
    at.button[0].click().run()
    assert not at.exception
    assert any("Please add your Gemini API key" in i.value for i in at.info)
    mk, ex = no_api
    mk.assert_not_called()
    ex.assert_not_called()


def test_typed_key_is_used_for_the_call(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sample = ROOT / "examples" / "samples" / "sample_01.json"
    with mock.patch.object(run_models, "make_client", return_value=object()) as mk, \
         mock.patch.object(run_models, "extract", return_value=fake_result(sample.read_text())) as ex:
        at = load()
        next(w for w in at.text_input if w.key == "api_key_input").set_value("typed-key-not-real")
        at.button[0].click().run()
    assert not at.exception
    mk.assert_called_once_with("typed-key-not-real")
    ex.assert_called_once()
