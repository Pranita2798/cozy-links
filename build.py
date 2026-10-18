#!/usr/bin/env python3
"""Build the Cozy Room Edit Finds link-in-bio page.

Reads products.json (newest first), fills template.html and writes index.html.
Everything is rendered at build time, so the published page never fetches data.

Usage (run from anywhere):
  python3 build.py                         rebuild index.html from products.json
  python3 build.py --add "Title" URL       add a new find at the top, then rebuild
  python3 build.py --from-txt FILE         replace products.json with a
                                           "Title | URL" text file, then rebuild

Only the Python standard library is used.
"""

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCTS = HERE / "products.json"
TEMPLATE = HERE / "template.html"
OUTPUT = HERE / "index.html"

REL = "nofollow sponsored noopener"
# Dash characters the brand never uses. Written as code points so this file stays clean.
BANNED_DASHES = {chr(0x2014): ", ", chr(0x2013): ", ", chr(0x2012): ", ", chr(0x2015): ", "}


def clean_text(text):
    """Trim, collapse spaces and swap long dashes for commas."""
    text = str(text)
    for bad, good in BANNED_DASHES.items():
        text = text.replace(" " + bad + " ", good).replace(bad, good)
    return re.sub(r"\s+", " ", text).strip().strip(",").strip()


def display_title(title):
    """Drop a trailing "(Amazon)" because every button already says Amazon."""
    return re.sub(r"\s*\(amazon\)\s*$", "", title, flags=re.IGNORECASE).strip() or title


def validate(products):
    """Return a cleaned, de-duplicated list. Raise ValueError on bad rows."""
    if not isinstance(products, list):
        raise ValueError("products.json must contain a JSON list")
    seen = set()
    cleaned = []
    for i, item in enumerate(products, 1):
        if not isinstance(item, dict):
            raise ValueError("item %d is not an object" % i)
        title = clean_text(item.get("title", ""))
        url = str(item.get("url", "")).strip()
        if not title:
            raise ValueError("item %d has no title" % i)
        if not re.match(r"^https://[^\s\"'<>]+$", url):
            raise ValueError("item %d (%s) needs a full https:// link" % (i, title))
        if url in seen:
            print("Skipping duplicate link: %s" % url, file=sys.stderr)
            continue
        seen.add(url)
        cleaned.append({"title": title, "url": url})
    return cleaned


def parse_txt(path):
    """Read lines like "Title | https://amzn.to/xxxx" (newest first)."""
    products = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            raise ValueError("line has no | separator: %r" % line)
        title, url = line.rsplit("|", 1)
        products.append({"title": title.strip(), "url": url.strip()})
    return products


def load_products():
    return json.loads(PRODUCTS.read_text(encoding="utf-8"))


def save_products(products):
    PRODUCTS.write_text(json.dumps(products, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_items(products):
    rows = []
    for i, p in enumerate(products):
        title = html.escape(display_title(p["title"]))
        url = html.escape(p["url"], quote=True)
        badge = '<span class="badge">New</span>' if i == 0 else ""
        rows.append(
            '      <li><a class="find" href="%s" rel="%s" target="_blank">'
            '<span class="find-title">%s</span>%s'
            '<span class="shop">Amazon<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8"/></svg></span>'
            '<span class="sr-only"> (opens Amazon in a new tab)</span></a></li>'
            % (url, REL, title, badge)
        )
    return "\n".join(rows)


def embed_json(products):
    """JSON that is safe to place inside a <script> tag."""
    data = json.dumps(products, ensure_ascii=False, separators=(",", ":"))
    return data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build(products):
    template = TEMPLATE.read_text(encoding="utf-8")
    page = (
        template.replace("{{PRODUCT_ITEMS}}", render_items(products))
        .replace("{{PRODUCT_COUNT}}", str(len(products)))
        .replace("{{UPDATED}}", date.today().strftime("%b %d, %Y").replace(" 0", " "))
        .replace("{{PRODUCTS_JSON}}", embed_json(products))
    )
    for bad in BANNED_DASHES:
        if bad in page:
            raise ValueError("Output contains a banned dash character, fix the template")
    OUTPUT.write_text(page, encoding="utf-8")
    return page


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the link-in-bio page.")
    ap.add_argument("--add", nargs=2, metavar=("TITLE", "URL"), help="add a new find at the top")
    ap.add_argument("--from-txt", metavar="FILE", help='replace products.json from a "Title | URL" file')
    args = ap.parse_args(argv)

    try:
        if args.from_txt:
            products = validate(parse_txt(args.from_txt))
            save_products(products)
            print("Wrote %d finds to %s" % (len(products), PRODUCTS.name))
        else:
            products = validate(load_products())

        if args.add:
            title, url = args.add
            new = validate([{"title": title, "url": url}])[0]
            products = [new] + [p for p in products if p["url"] != new["url"]]
            save_products(products)
            print("Added: %s" % new["title"])

        build(products)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("Build failed: %s" % exc, file=sys.stderr)
        return 1

    print("Built %s with %d finds" % (OUTPUT.name, len(products)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
