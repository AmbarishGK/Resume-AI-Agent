#!/usr/bin/env python3
import argparse, csv, re, time, sys, os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Iterable, Optional, Tuple
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright

# Default paths relative to project root
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = BASE_DIR / "app" / "config" / "careers.yaml"
DEFAULT_OUTPUT = BASE_DIR / "app" / "data" / "jobs" / "jobs.csv"

# -----------------------------
# Model
# -----------------------------
@dataclass
class JobPosting:
    role: str
    date: str           # YYYY-MM-DD
    location: str
    link: str
    source: str
    keywords_matched: str

# -----------------------------
# Utilities
# -----------------------------
def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()

def parse_relative_date(text: str) -> str:
    s = (text or "").strip().lower()
    if not s:
        return today_iso()
    if "today" in s or "just" in s or "hour" in s:
        return today_iso()
    m = re.search(r"(\d+)\+?\s*(day|days|week|weeks|month|months)", s)
    if not m:
        # Try an absolute like "Aug 24, 2025" or "2025-08-24"
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text.strip(), fmt).date().isoformat()
            except Exception:
                pass
        return today_iso()
    n = int(m.group(1))
    unit = m.group(2)
    mult = 1 if "day" in unit else (7 if "week" in unit else 30)
    return (datetime.now(timezone.utc).date() - timedelta(days=n*mult)).isoformat()

def matches_filters(job: JobPosting,
                    include_keywords: List[str],
                    exclude_keywords: List[str],
                    location_filters: List[str]) -> Tuple[bool, List[str]]:
    hay = f"{job.role} {job.location}".lower()
    matched = []
    if include_keywords:
        ok = False
        for kw in include_keywords:
            if kw.lower() in hay:
                matched.append(kw)
                ok = True
        if not ok:
            return False, []
    for ex in exclude_keywords:
        if ex.lower() in hay:
            return False, []
    if location_filters:
        if not any(loc.lower() in job.location.lower() for loc in location_filters):
            return False, matched
    return True, matched

def write_csv(rows: List[JobPosting], path: str):
    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = ["role", "date", "location", "link", "source", "keywords_matched"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))

# -----------------------------
# Consent handling
# -----------------------------
def handle_consent(page):
    # Best-effort to close cookie/consent banners
    selectors = [
        "button:has-text('Reject all')", "button:has-text('Reject All')",
        "button:has-text('Decline')", "button:has-text('I do not accept')",
        "button:has-text('Accept all')", "button:has-text('Accept All')",
        "button:has-text('I accept')", "[aria-label='Close']",
        "button[aria-label*='close']", "div[role='dialog'] button:has-text('Close')"
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible():
                loc.click(timeout=1000)
                page.wait_for_timeout(300)
                break
        except Exception:
            pass

# -----------------------------
# Generic DOM scraper (config-driven)
# -----------------------------
def scrape_company_dom(page, cfg: dict, dump_html: bool=False) -> Iterable[JobPosting]:
    """
    cfg fields (per company):
      name: "CompanyName"
      url: "https://company.com/careers/jobs"
      list_selector: "CSS that selects each job card or row"
      title_selector: "relative CSS inside each card"
      link_selector:  "relative CSS inside each card (anchor)"
      location_selector: "relative CSS inside each card (optional)"
      date_selector: "relative CSS inside each card (optional)"
      date_mode: "relative|absolute" (default: relative)
      pagination:
         type: "load_more" or "scroll" (optional)
         button_selector: "CSS" (for load_more)
         max_clicks: 5
         scroll_steps: 6
         scroll_wait_ms: 700
    """
    url = cfg["url"]
    page.goto(url, wait_until="domcontentloaded")
    handle_consent(page)
    page.wait_for_timeout(1000)

    # Pagination support
    pagination = cfg.get("pagination", {})
    ptype = pagination.get("type", "")
    if ptype == "load_more":
        btn_sel = pagination.get("button_selector", "")
        max_clicks = int(pagination.get("max_clicks", 5))
        for _ in range(max_clicks):
            try:
                if btn_sel and page.locator(btn_sel).first.is_visible():
                    page.locator(btn_sel).first.click()
                    page.wait_for_timeout(int(pagination.get("scroll_wait_ms", 700)))
                else:
                    break
            except Exception:
                break
    elif ptype == "scroll":
        steps = int(pagination.get("scroll_steps", 6))
        wait_ms = int(pagination.get("scroll_wait_ms", 700))
        for _ in range(steps):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(wait_ms)

    # Gather cards
    cards = page.locator(cfg["list_selector"]).element_handles()
    results = 0

    for card in cards:
        try:
            # Check if card itself is a link by trying to get href
            link_selector = cfg.get("link_selector", "a")
            card_href = None
            try:
                card_href = card.get_attribute("href")
            except Exception:
                pass
            
            is_link_card = (card_href is not None) or (link_selector == "&self")
            
            # Get link
            if is_link_card:
                # Card is the link itself
                link = card_href or card.get_attribute("href") or ""
                # Get title from card text or specified selector
                if cfg.get("title_selector") == "&self":
                    role = normalize_space(card.inner_text())
                else:
                    tloc = card.query_selector(cfg["title_selector"]) if cfg.get("title_selector") else None
                    role = normalize_space(tloc.inner_text()) if tloc else normalize_space(card.inner_text())
            else:
                tloc = card.query_selector(cfg["title_selector"])
                role = normalize_space(tloc.inner_text()) if tloc else ""
                aloc = card.query_selector(link_selector)
                link = aloc.get_attribute("href") if aloc else ""
            
            if link and link.startswith("/"):
                # resolve relative to site origin
                from urllib.parse import urljoin
                link = urljoin(url, link)

            # Get location
            location_selector = cfg.get("location_selector", "")
            if location_selector == "&self" and is_link_card:
                # Location might be in the link text, but hard to parse reliably
                # Use "Unspecified" for now - can be enhanced later
                location = "Unspecified"
            elif location_selector:
                lloc = card.query_selector(location_selector)
                location = normalize_space(lloc.inner_text()) if lloc else "Unspecified"
            else:
                location = "Unspecified"

            dloc = card.query_selector(cfg.get("date_selector", "")) if cfg.get("date_selector") else None
            date_raw = normalize_space(dloc.inner_text()) if dloc else ""
            if cfg.get("date_mode", "relative") == "absolute" and date_raw:
                # try common absolute formats
                for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%d %b %Y"):
                    try:
                        date = datetime.strptime(date_raw, fmt).date().isoformat()
                        break
                    except Exception:
                        date = today_iso()
                else:
                    date = today_iso()
            else:
                date = parse_relative_date(date_raw) if date_raw else today_iso()

            if role and link:
                results += 1
                yield JobPosting(
                    role=role, date=date, location=location, link=link,
                    source=cfg["name"], keywords_matched=""
                )
        except Exception:
            continue

    if results == 0 and dump_html:
        debug_dir = BASE_DIR / "debug"
        debug_dir.mkdir(exist_ok=True)
        safe_name = cfg['name'].lower().replace(" ", "_")
        html_path = debug_dir / f"{safe_name}_last_page.html"
        png_path = debug_dir / f"{safe_name}_last_page.png"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        page.screenshot(path=str(png_path), full_page=True)
        print(f"[debug] Saved {html_path} and {png_path} for {cfg['name']}")

# -----------------------------
# Orchestrator
# -----------------------------
def run(config_path: str, include: List[str], exclude: List[str], locations: List[str],
        out_csv: str, headless: bool, dump_html: bool):

    with open(config_path, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)

    all_rows: List[JobPosting] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
        context = browser.new_context(
            locale="en-US",
            timezone_id="America/Los_Angeles",
            viewport={"width": 1366, "height": 860},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36")
        )
        page = context.new_page()

        for site in conf.get("sites", []):
            typ = site.get("type", "dom")
            if typ == "dom":
                for job in scrape_company_dom(page, site, dump_html=dump_html):
                    ok, matched = matches_filters(job, include, exclude, locations)
                    if ok:
                        job.keywords_matched = ",".join(sorted(set(matched)))
                        all_rows.append(job)
            else:
                # Unsupported type placeholder – extend here for workday/ashby/etc.
                print(f"[warn] Unsupported type '{typ}' for {site.get('name')} – skipping.", file=sys.stderr)

        context.close()
        browser.close()

    # Dedupe by link
    dedup: Dict[str, JobPosting] = {}
    for j in all_rows:
        dedup[j.link] = j
    final = list(dedup.values())
    final.sort(key=lambda x: (x.date, x.source, x.role), reverse=True)

    write_csv(final, out_csv)
    print(f"Wrote {len(final)} jobs to {out_csv} (before dedupe: {len(all_rows)})")

def parse_list_arg(val: Optional[str]) -> List[str]:
    if not val:
        return []
    return [normalize_space(x) for x in val.split(",") if normalize_space(x)]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Company careers (Playwright, config-driven) -> CSV")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), 
                    help=f"Path to YAML config defining sites & selectors (default: {DEFAULT_CONFIG})")
    ap.add_argument("--include", default="", help="CSV of include keywords (any match).")
    ap.add_argument("--exclude", default="", help="CSV of exclude keywords.")
    ap.add_argument("--locations", default="", help="CSV of location filters (any match).")
    ap.add_argument("--out", default=str(DEFAULT_OUTPUT), 
                    help=f"Output CSV path (default: {DEFAULT_OUTPUT})")
    ap.add_argument("--no-headless", action="store_true", help="Show the browser window")
    ap.add_argument("--dump-html", action="store_true", help="Save HTML + screenshot when a site yields 0 jobs")
    args = ap.parse_args()

    include = parse_list_arg(args.include)
    exclude = parse_list_arg(args.exclude)
    locations = parse_list_arg(args.locations)

    run(args.config, include, exclude, locations, args.out,
        headless=not args.no_headless, dump_html=args.dump_html)
