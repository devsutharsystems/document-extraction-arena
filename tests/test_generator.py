import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))

from generate_invoices import CURRENCIES, HARD, LEVELS, main, make_invoice, q  # noqa: E402

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
        low, high = (8, 15) if truth["level"] == HARD else (2, 6)
        assert low <= len(truth["line_items"]) <= high, truth["id"]


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
    assert len(files) == len(LEVELS) * 2 * 2  # levels x 2 invoices x (image + json)


# ---- level 4 (hard) ----

def hard_invoices(invoices):
    return [(t, d) for t, d in invoices if t["level"] == HARD]


def test_level4_has_30_invoices_and_8_to_15_lines(invoices):
    hard = hard_invoices(invoices)
    assert len(hard) == 30
    assert all(8 <= len(t["line_items"]) <= 15 for t, _ in hard)


def test_level4_dates_are_numeric_only_and_ambiguous(invoices):
    for truth, disp in hard_invoices(invoices):
        text = disp["date_text"]
        m = re.fullmatch(r"(\d{2})([/.-])(\d{2})\2(\d{4})", text)
        assert m, f"{truth['id']}: not purely numeric: {text!r}"  # no month names
        first, second = int(m.group(1)), int(m.group(3))
        assert first <= 12 and second <= 12, truth["id"]  # day <= 12, so either order parses
        assert first != second, truth["id"]  # equal day and month would not be ambiguous
        d = date.fromisoformat(truth["invoice_date"])
        expected = (d.month, d.day) if CURRENCIES[truth["currency"]]["country"] == "USA" else (d.day, d.month)
        assert (first, second) == expected, truth["id"]
        assert d.day <= 12


def test_level4_mixes_us_and_non_us_vendors(invoices):
    currencies = {t["currency"] for t, _ in hard_invoices(invoices)}
    assert "USD" in currencies and len(currencies - {"USD"}) >= 2


def test_level4_totals_add_up(invoices):
    for truth, disp in hard_invoices(invoices):
        decimals = CURRENCIES[truth["currency"]]["decimals"]
        assert D(truth["subtotal"]) == sum(D(i["amount"]) for i in truth["line_items"]), truth["id"]
        assert D(truth["tax"]) == q(D(truth["subtotal"]) * disp["tax_pct"] / 100, decimals), truth["id"]
        assert D(truth["subtotal"]) + D(truth["tax"]) == D(truth["total"]), truth["id"]


def test_level4_same_seed_gives_same_invoice():
    assert make_invoice(HARD, 7, SEED) == make_invoice(HARD, 7, SEED)
    assert make_invoice(HARD, 7, SEED) != make_invoice(HARD, 7, SEED + 1)


def test_level4_images_are_jpg_and_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    main(out_root=str(a), count=2, seed=7, levels=[HARD])
    main(out_root=str(b), count=2, seed=7, levels=[HARD])
    names = sorted(p.name for p in (a / HARD).iterdir())
    assert names == [f"{HARD}_001.jpg", f"{HARD}_001.json", f"{HARD}_002.jpg", f"{HARD}_002.json"]
    for name in names:
        assert (a / HARD / name).read_bytes() == (b / HARD / name).read_bytes()
