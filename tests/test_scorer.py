import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))
sys.path.insert(0, str(ROOT / "runner"))

from generate_invoices import make_invoice  # noqa: E402
from score import score_invoice  # noqa: E402

TRUTH, _ = make_invoice("level2_mixed", 1, 42)


def test_perfect_answer_scores_100():
    scores, notes = score_invoice(TRUTH, dict(TRUTH))
    assert all(v == 1.0 for v in scores.values()) and not notes


def test_wrong_total_is_caught_but_other_fields_unaffected():
    scores, _ = score_invoice(TRUTH, dict(TRUTH, total=TRUTH["total"] + 1))
    assert scores["total"] == 0.0 and scores["subtotal"] == 1.0


def test_tiny_rounding_noise_is_tolerated():
    scores, _ = score_invoice(TRUTH, dict(TRUTH, total=TRUTH["total"] + 0.001))
    assert scores["total"] == 1.0


def test_vendor_with_address_is_wrong():
    scores, _ = score_invoice(TRUTH, dict(TRUTH, vendor=TRUTH["vendor"] + ", 12 Main St"))
    assert scores["vendor"] == 0.0


def test_missing_line_item_loses_points():
    pred = dict(TRUTH, line_items=TRUTH["line_items"][:-1])
    scores, _ = score_invoice(TRUTH, pred)
    assert 0.0 < scores["line_items"] < 1.0


def test_unparseable_answer_scores_zero():
    scores, _ = score_invoice(TRUTH, None)
    assert all(v == 0.0 for v in scores.values())