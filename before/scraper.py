"""
ORIGINAL (BROKEN) VERSION — kept unchanged to show the problem.

Worked fine until the shop redesigned its product pages. Now it "succeeds"
but prints "Saved 0 products" and writes an empty CSV. Just renaming the CSS
classes is not enough — it then crashes with:
    AttributeError: 'NoneType' object has no attribute 'text'   (out-of-stock item)
    ValueError: could not convert string to float: '1,299.00'   (thousands separator)
and on Windows the CSV write fails with UnicodeEncodeError on "Café".
"""
import csv
import sys

import requests
from bs4 import BeautifulSoup


def get_html(source):
    if source.startswith("http"):
        return requests.get(source).text
    return open(source).read()


def scrape(source):
    soup = BeautifulSoup(get_html(source), "html.parser")
    products = []
    for card in soup.find_all("div", class_="product-card"):
        name = card.find("h3").text
        price = card.find("span", class_="price").text
        products.append({"name": name, "price": float(price.replace("$", ""))})
    return products


def main():
    products = scrape(sys.argv[1])
    with open("prices.csv", "w") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "price"])
        writer.writeheader()
        writer.writerows(products)
    print(f"Saved {len(products)} products")


if __name__ == "__main__":
    main()
