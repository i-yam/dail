#!/usr/bin/env python3
"""
Scrape EUvsDisinfo report pages into a structured CSV.

Why browser automation:
- listing pages are reachable with plain HTTP
- individual report and AJAX endpoints are often Cloudflare-protected
- Playwright browser context handles JS/cookies and can pass challenge
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE = "https://euvsdisinfo.eu"
LISTING = f"{BASE}/disinformation-cases/"


@dataclass
class ReportRow:
    report_url: str
    title: str
    date_of_publication: str
    article_language: str
    outlet_text: str
    countries_regions: str
    tags: str
    summary: str
    response: str
    original_links: str
    archive_links: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/processed/euvsdisinfo_reports.csv")
    parser.add_argument("--per-page", type=int, default=60)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--max-reports", type=int, default=200)
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless (headed is default for easier Cloudflare pass).",
    )
    parser.add_argument(
        "--user-data-dir",
        default=".cache/pw-euvsdisinfo",
        help="Persistent browser profile directory to keep Cloudflare cookies.",
    )
    parser.add_argument(
        "--channel",
        default="chrome",
        choices=["chrome", "chromium", "msedge"],
        help="Browser channel for Playwright persistent context.",
    )
    return parser.parse_args()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _has_cf_clearance_cookie(page) -> bool:
    try:
        cookies = page.context.cookies()
    except Exception:
        return False
    return any(c.get("name") == "cf_clearance" for c in cookies)


def maybe_wait_cloudflare(page) -> None:
    title = page.title().strip().lower()
    content = page.content().lower()
    blocked = (
        "just a moment" in title
        or "enable javascript and cookies" in content
        or "performing security verification" in content
        or "verify you are human" in content
    )
    if not blocked:
        return
    print(
        "Cloudflare challenge detected. Complete it in the opened browser window. "
        "Waiting up to 240 seconds..."
    )
    deadline = time.time() + 240
    while time.time() < deadline:
        time.sleep(2)
        try:
            current_title = page.title().strip().lower()
            current_content = page.content().lower()
        except Exception:
            continue
        if (
            "just a moment" not in current_title
            and "enable javascript and cookies" not in current_content
            and "performing security verification" not in current_content
            and "verify you are human" not in current_content
            and _has_cf_clearance_cookie(page)
        ):
            print("Challenge passed.")
            return
    raise RuntimeError(
        "Cloudflare challenge loop. Try waiting 10-15s after checkbox and "
        "re-run; if it persists, change IP/network and keep same user-data-dir."
    )


def collect_report_links(page, per_page: int, max_pages: int) -> list[str]:
    links: list[str] = []
    seen = set()
    for page_idx in range(max_pages):
        offset = page_idx * per_page
        url = f"{LISTING}?per_page={per_page}&offset={offset}"
        print(f"Listing page {page_idx + 1}/{max_pages}: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        maybe_wait_cloudflare(page)
        page.wait_for_timeout(random.randint(1200, 2200))

        hrefs = page.eval_on_selector_all(
            "a[href*='/report/']",
            "els => els.map(e => e.href)",
        )
        for href in hrefs:
            href = href.split("#")[0].strip()
            if not href.startswith(BASE):
                continue
            if href in seen:
                continue
            seen.add(href)
            links.append(href)

    return links


def extract_with_regex(text: str, label: str) -> str:
    m = re.search(rf"{re.escape(label)}\s*:\s*(.+)", text, flags=re.IGNORECASE)
    return clean_text(m.group(1)) if m else ""


def extract_sections(body_text: str) -> tuple[str, str]:
    summary = ""
    response = ""

    m_summary = re.search(
        r"\bSUMMARY\b\s*(.*?)\s*\bRESPONSE\b",
        body_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m_summary:
        summary = clean_text(m_summary.group(1))

    m_response = re.search(
        r"\bRESPONSE\b\s*(.*)$",
        body_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m_response:
        response = clean_text(m_response.group(1))

    return summary, response


def extract_report(page, report_url: str) -> ReportRow:
    page.goto(report_url, wait_until="domcontentloaded", timeout=120_000)
    maybe_wait_cloudflare(page)
    page.wait_for_timeout(random.randint(1200, 2400))

    title = clean_text(page.locator("h1").first.inner_text(timeout=10_000))
    body_text = page.locator("body").inner_text(timeout=10_000)

    # Sidebar-like fields
    date_of_publication = extract_with_regex(body_text, "Date of publication")
    article_language = extract_with_regex(body_text, "Article language(s)")
    countries_regions = extract_with_regex(body_text, "Countries / regions discussed")

    outlet_text = ""
    outlet_match = re.search(
        r"Outlet\s*:\s*(.+?)\s*(?:Date of publication|Article language\(s\)|Countries / regions discussed)",
        body_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if outlet_match:
        outlet_text = clean_text(outlet_match.group(1))

    # Tags often appear as pills under "TAGS:"
    tags_match = re.search(
        r"\bTAGS\s*:\s*(.+?)\s*(?:SUMMARY|RESPONSE)",
        body_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    tags = clean_text(tags_match.group(1)) if tags_match else ""

    summary, response = extract_sections(body_text)

    link_rows = page.eval_on_selector_all(
        "a[href]",
        """els => els.map(a => ({
            href: a.href,
            text: (a.textContent || '').trim().toLowerCase()
        }))""",
    )
    original_links = []
    archive_links = []
    for row in link_rows:
        href = row.get("href", "")
        text = row.get("text", "")
        if not href.startswith("http"):
            continue
        if "euvsdisinfo.eu" in href:
            continue
        if "archive" in text:
            archive_links.append(href)
        elif "original" in text:
            original_links.append(href)

    return ReportRow(
        report_url=report_url,
        title=title,
        date_of_publication=date_of_publication,
        article_language=article_language,
        outlet_text=outlet_text,
        countries_regions=countries_regions,
        tags=tags,
        summary=summary,
        response=response,
        original_links=" | ".join(sorted(set(original_links))),
        archive_links=" | ".join(sorted(set(archive_links))),
    )


def write_csv(path: Path, rows: Iterable[ReportRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        print("No rows to write.")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    print(f"Wrote {len(rows)} rows to {path}")


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    user_data_dir = Path(args.user_data_dir)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=args.headless,
            channel=args.channel,
            viewport={"width": 1366, "height": 900},
            locale="en-US",
            timezone_id="Europe/Berlin",
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        # Warm-up session first so Cloudflare cookie can be set once.
        page.goto(BASE, wait_until="domcontentloaded", timeout=120_000)
        maybe_wait_cloudflare(page)
        page.wait_for_timeout(1500)

        links = collect_report_links(page, per_page=args.per_page, max_pages=args.max_pages)
        if args.max_reports:
            links = links[: args.max_reports]
        print(f"Collected {len(links)} report URLs.")

        rows: list[ReportRow] = []
        for idx, link in enumerate(links, start=1):
            try:
                print(f"[{idx}/{len(links)}] {link}")
                row = extract_report(page, link)
                rows.append(row)
            except (PlaywrightTimeoutError, RuntimeError) as err:
                print(f"Skip {link}: {err}")
            except Exception as err:
                print(f"Unexpected error for {link}: {err}")

        context.close()

    write_csv(output, rows)


if __name__ == "__main__":
    main()
