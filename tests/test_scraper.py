import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"


def load(version):
    spec = importlib.util.spec_from_file_location(f"scraper_{version}", ROOT / version / "scraper.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # needed for dataclasses
    spec.loader.exec_module(module)
    return module


before = load("before")
after = load("after")


# --- The bug, reproduced -------------------------------------------------------

def test_original_works_on_old_layout():
    assert len(before.scrape(str(FIXTURES / "old_layout.html"))) == 3


def test_original_silently_finds_nothing_on_new_layout():
    assert before.scrape(str(FIXTURES / "new_layout.html")) == []


# --- The fix -------------------------------------------------------------------

def html(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_fixed_reads_new_layout():
    products = after.scrape(html("new_layout.html"))
    assert [p.name for p in products] == [
        "Hand Grinder Classic",
        "Espresso Machine Pro",
        "Café Cup Set (6 pcs)",
        "Pour-Over Kettle",
        "Kaffeemühle Elektrisch",
    ]


def test_fixed_still_reads_old_layout():
    assert len(after.scrape(html("old_layout.html"))) == 3


def test_out_of_stock_does_not_crash():
    kettle = next(p for p in after.scrape(html("new_layout.html")) if p.sku == "KT-POUR")
    assert kettle.price is None and kettle.in_stock is False


@pytest.mark.parametrize(
    "text, expected",
    [
        ("$49.90", (49.90, "USD")),
        ("$1,299.00", (1299.00, "USD")),
        ("€24,90", (24.90, "EUR")),
        ("€1.149,00", (1149.00, "EUR")),
        ("£1,299", (1299.0, "GBP")),
        ("", (None, None)),
        ("Call for price", (None, None)),
    ],
)
def test_parse_price(text, expected):
    assert after.parse_price(text) == expected


def test_csv_is_utf8_and_complete(tmp_path):
    out = tmp_path / "prices.csv"
    assert after.main([str(FIXTURES / "new_layout.html"), "-o", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert len(rows) == 5
    assert rows[2]["name"] == "Café Cup Set (6 pcs)"


def test_empty_page_fails_loudly(tmp_path):
    page = tmp_path / "empty.html"
    page.write_text("<html><body>Maintenance</body></html>", encoding="utf-8")
    assert after.main([str(page), "-o", str(tmp_path / "x.csv")]) == 1
    assert not (tmp_path / "x.csv").exists()
