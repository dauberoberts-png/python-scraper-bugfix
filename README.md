# Fixing a price scraper that broke after a site redesign

A demo bug-fix case study: a small Python script that collects product prices into a CSV stopped working after the shop changed its page layout. This repo shows the broken script, the diagnosis, the fix, and tests that prove it works.

> The shop and its pages are a realistic demo (saved HTML in `fixtures/`), so everything here runs offline.

## The problem

The script had run fine for months. After the shop's redesign it still printed a success message, but every run produced an **empty CSV**:

```
$ python before/scraper.py fixtures/new_layout.html
Saved 0 products
```

No error, so nobody noticed until the spreadsheet built on it went blank.

## Diagnosis

| # | Cause | Symptom |
|---|-------|---------|
| 1 | The redesign renamed the HTML: `div.product-card` became `article.product`, and `span.price` became `p.price-current` | The script found 0 products and still reported success |
| 2 | Prices now use thousands separators (`$1,299.00`) and EU format (`€1.149,00`) | `ValueError: could not convert string to float` |
| 3 | Out-of-stock items have no price element at all | `AttributeError: 'NoneType' object has no attribute 'text'` |
| 4 | Names like "Café" and "Kaffeemühle" + no file encoding set | `UnicodeEncodeError` on Windows, garbled text in Excel |
| 5 | No timeout or retries on the web request | Script could hang forever on a slow response |

Simply renaming the CSS classes (the obvious quick fix) would have turned the silent failure into crashes 2–4.

## The fix (`after/scraper.py`)

- **Selectors for both layouts**, newest first, so the script works during a gradual rollout.
- **`parse_price()`**, which handles `$`, `€`, `£`, US and EU number formats, and stores the currency in its own column.
- **Out-of-stock items are kept** with `price` empty and `in_stock = False`, instead of crashing the run.
- **Fails loudly**: if no products are found, it exits with an error and writes no file. That's the safeguard that would have caught the original bug on day one.
- **UTF-8 everywhere**, with the CSV written so Excel shows special characters correctly.
- **Timeout, 3 retries with backoff, and a User-Agent** for live URLs.
- Small command-line interface: `python after/scraper.py <url-or-file> -o prices.csv`

### Result

```
$ python after/scraper.py fixtures/new_layout.html -o prices.csv
INFO: Saved 5 products to prices.csv (1 without a price)
```

| name | price | currency | in_stock | sku |
|------|-------|----------|----------|-----|
| Hand Grinder Classic | 49.9 | USD | True | HG-01 |
| Espresso Machine Pro | 1299.0 | USD | True | EM-PRO |
| Café Cup Set (6 pcs) | 24.9 | EUR | True | CF-SET |
| Pour-Over Kettle | | | False | KT-POUR |
| Kaffeemühle Elektrisch | 1149.0 | EUR | True | GR-ELEC |

## Tests

```
pip install -r requirements.txt
python -m pytest -q
# 14 passed
```

The tests reproduce the original bug (the old script returns nothing on the new layout), then check the fixed version: both layouts, all price formats, out-of-stock items, UTF-8 output, and the "fail loudly on an empty page" safeguard.

## Project layout

```
before/scraper.py   original script, unchanged
after/scraper.py    fixed script
fixtures/           saved pages: old layout and redesigned layout
tests/              pytest suite proving the bug and the fix
```

---

*Have a script that stopped working? Send the error message and what it should do. I'll find the cause and fix it for a fixed price.*
