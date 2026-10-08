import json
import re
from decimal import Decimal
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "my_invoice"
REQUIRED = ["invoice_number", "vendor", "invoice_date", "currency", "line_items", "subtotal", "tax", "total"]


def D(x):
    return Decimal(str(x))


def load():
    return json.loads((EXAMPLE / "my_001.json").read_text())


def test_example_has_required_keys():
    assert set(REQUIRED) <= set(load())


def test_example_date_format():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", load()["invoice_date"])


def test_example_line_amounts():
    for item in load()["line_items"]:
        assert D(item["quantity"]) * D(item["unit_price"]) == D(item["amount"])


def test_example_totals():
    inv = load()
    assert sum(D(i["amount"]) for i in inv["line_items"]) == D(inv["subtotal"])
    assert D(inv["subtotal"]) + D(inv["tax"]) == D(inv["total"])


def test_example_image_exists():
    assert (EXAMPLE / "my_001.png").is_file()
