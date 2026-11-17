"""
FIXED VERSION — price scraper for the redesigned shop pages.

What changed and why:
1. Selectors: supports the new layout (article.product / .price-current) and still
   understands the old one, so a partial rollout of the redesign doesn't break it.
2. Price parsing: handles currency symbols, thousands separators and both
   "1,299.00" (US) and "1.149,00" (EU) formats; keeps the currency in its own column.
3. Missing prices: out-of-stock items are kept with price=None and in_stock=False
   instead of crashing the whole run.
4. Silent failures: if zero products are found, the script exits with an error
   instead of writing an empty file (that's how the original bug went unnoticed).
5. Encoding: reads and writes UTF-8 (CSV with BOM so Excel shows "Café" correctly).
6. Network: timeout, retries and a User-Agent for live URLs.

Usage:
    python scraper.py <url-or-html-file> [-o prices.csv]
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("scraper")

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}

# (card selector, name selector, price selector) — newest layout first.
LAYOUTS = [
    ("article.product", ".product-name", ".price-current"),
    ("div.product-card", "h3", "span.price"),
]


@dataclass
class Product:
    name: str
    price: float | None
    currency: str | None
    in_stock: bool
    sku: str | None = None


def parse_price(text: str) -> tuple[float | None, str | None]:
    """Turn '$1,299.00', '€1.149,00' or '€24,90' into (amount, currency)."""
    if not text:
        return None, None
    text = text.strip()
    currency = next((code for sym, code in CURRENCY_SYMBOLS.items() if sym in text), None)
    number = re.sub(r"[^\d.,]", "", text)
    if not number:
        return None, currency

    last_dot, last_comma = number.rfind("."), number.rfind(",")
    if last_comma > last_dot:
        # EU style: '.' groups thousands, ',' is the decimal mark (or only a comma present)
        decimals = len(number) - last_comma - 1
        if last_dot == -1 and decimals == 3:
            number = number.replace(",", "")  # '1,299' -> thousands, not decimals
        else:
            number = number.replace(".", "").replace(",", ".")
    else:
        # US style: ',' groups thousands, '.' is the decimal mark
        number = number.replace(",", "")
    try:
        return float(number), currency
    except ValueError:
        log.warning("Could not parse price %r", text)
        return None, currency


def fetch_html(source: str) -> str:
    if source.startswith(("http://", "https://")):
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))
        session.mount("http://", HTTPAdapter(max_retries=retries))
        resp = session.get(source, timeout=15, headers={"User-Agent": "price-checker/1.0"})
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        return resp.text
    return Path(source).read_text(encoding="utf-8")


def scrape(html: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    for card_sel, name_sel, price_sel in LAYOUTS:
        cards = soup.select(card_sel)
        if not cards:
            continue
        products = []
        for card in cards:
            name_el = card.select_one(name_sel)
            if name_el is None:
                log.warning("Skipping a card without a name")
                continue
            price_el = card.select_one(price_sel)
            price, currency = parse_price(price_el.get_text()) if price_el else (None, None)
            products.append(
                Product(
                    name=name_el.get_text(strip=True),
                    price=price,
                    currency=currency,
                    in_stock=price_el is not None,
                    sku=card.get("data-sku"),
                )
            )
        return products
    return []


def save_csv(products: list[Product], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(products[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(p) for p in products)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape product prices to CSV")
    parser.add_argument("source", help="Page URL or saved HTML file")
    parser.add_argument("-o", "--output", default="prices.csv")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    products = scrape(fetch_html(args.source))
    if not products:
        log.error("No products found — the page layout may have changed again.")
        return 1

    save_csv(products, args.output)
    missing = sum(p.price is None for p in products)
    log.info("Saved %d products to %s (%d without a price)", len(products), args.output, missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
