#!/usr/bin/env python3
"""
Scrape EUvsDisinfo using HTTP + real browser cookies.

Flow:
1) You open euvsdisinfo.eu in your normal Chrome and pass Cloudflare once.
2) Script loads Chrome cookies (including cf_clearance) via browser_cookie3.
3) Script fetches listing/report pages with requests and parses required fields.
"""

from __future__ import annotations

import argparse
import base64
import csv
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import browser_cookie3
import requests
from bs4 import BeautifulSoup

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
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="data/processed/euvsdisinfo_reports.csv")
    p.add_argument("--per-page", type=int, default=60)
    p.add_argument("--max-pages", type=int, default=5)
    p.add_argument("--max-reports", type=int, default=200)
    p.add_argument("--sleep", type=float, default=1.2, help="Delay between report requests.")
    p.add_argument("--timeout", type=float, default=20.0, help="HTTP request timeout in seconds.")
    p.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "requests", "curl_cffi"],
        help="HTTP engine. auto tries curl_cffi first (if installed).",
    )
    p.add_argument(
        "--cookie",
        action="append",
        default=[],
        help="Extra cookie in name=value format. Can repeat.",
    )
    p.add_argument("--debug", action="store_true", help="Print cookie/status diagnostics.")
    return p.parse_args()


def clean_text(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "").strip())


def parse_date_iso(value: str) -> str:
    raw = clean_text(value)
    if not raw:
        return ""
    # Expected format on EUvsDisinfo pages, e.g. "April 13, 2026"
    try:
        return datetime.strptime(raw, "%B %d, %Y").date().isoformat()
    except ValueError:
        return raw


def _create_session(engine: str):
    if engine in ("auto", "curl_cffi"):
        try:
            from curl_cffi import requests as curl_requests

            session = curl_requests.Session(impersonate="chrome124")
            return session, "curl_cffi"
        except Exception:
            if engine == "curl_cffi":
                raise RuntimeError(
                    "Engine curl_cffi requested but package is missing. "
                    "Install with: pip install curl_cffi"
                )
    session = requests.Session()
    return session, "requests"


def build_session(engine: str, extra_cookies: list[str], debug: bool):
    session, selected_engine = _create_session(engine)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": BASE + "/",
        }
    )

    # Load cookies from local Chrome profile (macOS Keychain unlock may prompt).
    jar = browser_cookie3.chrome(domain_name="euvsdisinfo.eu")
    loaded_names = set()
    for c in jar:
        session.cookies.set(c.name, c.value, domain=c.domain, path=c.path)
        loaded_names.add(c.name)

    # Optional manual cookies (e.g. --cookie "cf_clearance=...")
    for item in extra_cookies:
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        session.cookies.set(name, value, domain=".euvsdisinfo.eu", path="/")
        loaded_names.add(name)

    if debug:
        print(f"Engine: {selected_engine}")
        print(f"Loaded cookies: {len(loaded_names)} names")
        print("Cookie names:", ", ".join(sorted(loaded_names)) if loaded_names else "(none)")
        print("cf_clearance present:", "yes" if "cf_clearance" in loaded_names else "no")

    return session


def is_cloudflare_block(html: str) -> bool:
    lower = html.lower()
    return (
        "just a moment" in lower
        or "verify you are human" in lower
        or "performing security verification" in lower
        or "enable javascript and cookies to continue" in lower
    )


def fetch_html(session: requests.Session, url: str, timeout: float) -> str:
    r = session.get(url, timeout=timeout)
    if r.status_code == 403:
        raise RuntimeError(
            "403 Forbidden on this URL. Cloudflare is still blocking the HTTP client. "
            "Try: --engine curl_cffi --debug and ensure cf_clearance cookie exists."
        )
    r.raise_for_status()
    html = r.text
    if is_cloudflare_block(html):
        raise RuntimeError(
            "Cloudflare blocked this request. Open euvsdisinfo.eu in normal Chrome, "
            "pass verification, then rerun."
        )
    return html


def collect_report_links(session: requests.Session, per_page: int, max_pages: int, timeout: float) -> list[str]:
    links: list[str] = []
    seen = set()
    for page_idx in range(max_pages):
        offset = page_idx * per_page
        url = f"{LISTING}?per_page={per_page}&offset={offset}"
        print(f"Listing {page_idx + 1}/{max_pages}: {url}")
        html = fetch_html(session, url, timeout)
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a[href*='/report/']"):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            full = urljoin(BASE, href).split("#")[0]
            if full in seen:
                continue
            seen.add(full)
            links.append(full)
    return links


def extract_with_regex(text: str, label: str) -> str:
    m = re.search(rf"{re.escape(label)}\s*:\s*(.+)", text, flags=re.IGNORECASE)
    return clean_text(m.group(1)) if m else ""


def _decode_seo_href(value: str) -> str:
    if not value:
        return ""
    try:
        pad = "=" * (-len(value) % 4)
        decoded = base64.b64decode(value + pad).decode("utf-8", errors="ignore").strip()
        return decoded
    except Exception:
        return ""


def _resolved_link(a) -> str:
    # EUvsDisinfo often keeps links in data-seo-href and sets href="#".
    encoded = (a.get("data-seo-href") or "").strip()
    if encoded:
        decoded = _decode_seo_href(encoded)
        if decoded:
            return decoded
    href = (a.get("href") or "").strip()
    if not href or href == "#":
        return ""
    if href.startswith("/"):
        return urljoin(BASE, href)
    return href


def _get_detail_value(soup: BeautifulSoup, label: str) -> str:
    for li in soup.select(".b-report li"):
        text = clean_text(li.get_text(" ", strip=True))
        if text.startswith(label):
            span = li.find("span")
            if span:
                return clean_text(span.get_text(" ", strip=True))
            return clean_text(text.replace(label, "", 1).lstrip(": ").strip())
    return ""


def extract_sections(body_text: str) -> tuple[str, str]:
    summary = ""
    response = ""
    m_summary = re.search(r"\bSUMMARY\b\s*(.*?)\s*\bRESPONSE\b", body_text, flags=re.I | re.S)
    if m_summary:
        summary = clean_text(m_summary.group(1))
    m_response = re.search(r"\bRESPONSE\b\s*(.*)$", body_text, flags=re.I | re.S)
    if m_response:
        response = clean_text(m_response.group(1))
    return summary, response


def extract_report(session: requests.Session, report_url: str, timeout: float) -> ReportRow:
    html = fetch_html(session, report_url, timeout)
    soup = BeautifulSoup(html, "lxml")
    title = clean_text(soup.select_one("h1").get_text(" ", strip=True) if soup.select_one("h1") else "")
    body_text = clean_text(soup.get_text("\n", strip=True))

    date_of_publication = parse_date_iso(_get_detail_value(soup, "Date of publication"))
    article_language = _get_detail_value(soup, "Article language(s)")
    countries_regions = _get_detail_value(soup, "Countries / regions discussed")

    outlet_text = ""
    original_links = []
    archive_links = []
    outlet_names = []
    for li in soup.select(".b-report li"):
        li_text = clean_text(li.get_text(" ", strip=True))
        if not li_text.startswith("Outlet:"):
            continue
        for a in li.select("a"):
            text = clean_text(a.get_text(" ", strip=True))
            text_lower = text.lower()
            resolved = _resolved_link(a)
            if not text:
                continue
            if "archive" in text_lower:
                if resolved:
                    archive_links.append(resolved)
                continue
            if "original" in text_lower:
                if resolved:
                    original_links.append(resolved)
                continue
            outlet_names.append(text)
        break
    if outlet_names:
        outlet_text = " | ".join(dict.fromkeys(outlet_names))

    m_tags = re.search(r"\bTAGS\s*:\s*(.+?)\s*(?:SUMMARY|RESPONSE)", body_text, flags=re.I | re.S)
    tags = clean_text(m_tags.group(1)) if m_tags else ""

    summary_node = soup.select_one(".b-report__summary .b-text")
    response_node = soup.select_one(".b-report__response .b-text")
    summary = clean_text(summary_node.get_text(" ", strip=True)) if summary_node else ""
    response = clean_text(response_node.get_text(" ", strip=True)) if response_node else ""
    if not summary or not response:
        # Fallback for unexpected layouts.
        summary_fallback, response_fallback = extract_sections(body_text)
        if not summary:
            summary = summary_fallback
        if not response:
            response = response_fallback

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
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
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
    session = build_session(args.engine, args.cookie, args.debug)

    links = collect_report_links(session, per_page=args.per_page, max_pages=args.max_pages, timeout=args.timeout)
    if args.max_reports:
        links = links[: args.max_reports]
    print(f"Collected {len(links)} report URLs.")

    rows: list[ReportRow] = []
    for idx, link in enumerate(links, 1):
        try:
            print(f"[{idx}/{len(links)}] {link}")
            rows.append(extract_report(session, link, args.timeout))
            time.sleep(args.sleep)
        except Exception as err:
            print(f"Skip {link}: {err}")

    write_csv(Path(args.output), rows)


if __name__ == "__main__":
    main()
