import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))

from generate_invoices import CURRENCIES, LEVELS, main, make_invoice, q  # noqa: E402

SEED = 42


def D(x):
    return Decimal(str(x))


@pytest.fixture(scope="module")
def invoices():
    return [make_invoice(level, n, SEED) for level in LEVELS for n in range(1, 31)]


def test_required_fields_and_formats(invoices):
    required = {"id", "level", "invoice_number", "vendor", "invoice_date",
                "currency", "line_items", "subtotal", "tax", "total"}
    for truth, _ in invoices:
        assert required <= truth.keys()
        assert truth["currency"] in CURRENCIES
        assert truth["invoice_number"].startswith("INV-2026-")
        date.fromisoformat(truth["invoice_date"])  # raises if not YYYY-MM-DD
        assert 2 <= len(truth["line_items"]) <= 6


def test_line_amounts_equal_quantity_times_price(invoices):
    for truth, _ in invoices:
        decimals = CURRENCIES[truth["currency"]]["decimals"]
        for item in truth["line_items"]:
            assert D(item["amount"]) == q(D(item["unit_price"]) * item["quantity"], decimals), truth["id"]


def test_subtotal_is_sum_of_lines(invoices):
    for truth, _ in invoices:
        assert D(truth["subtotal"]) == sum(D(i["amount"]) for i in truth["line_items"]), truth["id"]


def test_tax_matches_rate_and_total_adds_up(invoices):
    for truth, disp in invoices:
        decimals = CURRENCIES[truth["currency"]]["decimals"]
        expected_tax = q(D(truth["subtotal"]) * disp["tax_pct"] / 100, decimals)
        assert D(truth["tax"]) == expected_tax, truth["id"]
        assert D(truth["subtotal"]) + D(truth["tax"]) == D(truth["total"]), truth["id"]


def test_level1_is_inr_only(invoices):
    assert {t["currency"] for t, _ in invoices if t["level"] == "level1_clean"} == {"INR"}


def test_yen_has_no_decimals(invoices):
    for truth, _ in invoices:
        if truth["currency"] == "JPY":
            assert float(truth["total"]).is_integer(), truth["id"]


def test_same_seed_gives_same_invoice():
    assert make_invoice("level2_mixed", 5, SEED) == make_invoice("level2_mixed", 5, SEED)


def test_files_are_written(tmp_path):
    main(out_root=str(tmp_path), count=2, seed=7)
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(files) == 3 * 2 * 2  # 3 levels x 2 invoices x (image + json)