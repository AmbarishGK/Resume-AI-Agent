#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_career_links_with_progress.py

Adds a live progress/status bar to the original checker.

Usage (basic):
    python check_career_links_with_progress.py --input all_career_links_ranked.csv --output all_career_links_checked.csv

New CLI:
    --progress {auto,bar,print,off}  Default=auto
        auto  -> use tqdm bar if available & TTY, else periodic prints
        bar   -> require tqdm bar (falls back to print if tqdm missing)
        print -> periodic "X/Y (pct%)" prints with OK/REPLACED/UNRESOLVED counts
        off   -> no progress output

    --sample N
        If > 0, only process first N rows (default 10; use 0 for all).

This is intended for batch runs on large company lists; you can keep a cached CSV and rerun periodically.
"""

import argparse
import csv
import sys
import time
import json
import re
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

import requests
from requests.adapters import HTTPAdapter, Retry
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from bs4 import BeautifulSoup
    HAVE_BS4 = True
except Exception:
    HAVE_BS4 = False

try:
    from tqdm import tqdm
    HAVE_TQDM = True
except Exception:
    HAVE_TQDM = False

# ---- Config ----
HEADERS = {
    "User-Agent": "CareerLinkChecker/1.2 (+https://github.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

KEYWORDS = ["career", "careers", "job", "jobs", "open role", "open roles"]

COMMON_CAREER_PATHS = [
    "/careers", "/careers/", "/career", "/jobs", "/jobs/", "/careers/jobs", "/company/careers",
    "/about/careers", "/about-us/careers"
]

ATS_HINTS = {
    "greenhouse": "greenhouse.io",
    "lever": "lever.co",
    "ashby": "ashbyhq.com",
    "workday": "myworkdayjobs.com",
    "smartrecruiters": "smartrecruiters.com",
    "bamboohr": "bamboohr.com",
    "gusto": "gusto.com",
    "adp": "adp.com",
    "ukg": "ukg.com",
    "icims": "icims.com",
}


@dataclass
class LinkResult:
    company_name: str
    input_url: str
    input_status_code: int
    input_status_text: str
    input_final_url: str
    input_redirects: int

    detected_career_url: str
    detected_status_code: int
    detected_status_text: str
    detected_final_url: str
    detected_redirects: int
    detection_method: str
    page_has_keywords: bool
    keywords_found: str
    last_checked_utc: str


def utc_now_iso() -> str:
    import datetime
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def create_session(timeout: int = 10) -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(HEADERS)
    s.request_timeout = timeout  # type: ignore
    return s


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    return url


def fetch_head(session: requests.Session, url: str) -> Tuple[int, str, str, int]:
    status = 0
    status_text = ""
    final_url = url
    redirects = 0
    try:
        resp = session.head(url, allow_redirects=True, timeout=session.request_timeout)
        status = resp.status_code
        status_text = resp.reason or ""
        final_url = resp.url
        redirects = len(resp.history)
    except Exception as e:
        status = 0
        status_text = str(e)
        final_url = url
        redirects = 0
    return status, status_text, final_url, redirects


def fetch_get(session: requests.Session, url: str) -> Tuple[int, str, str, int, str]:
    status = 0
    status_text = ""
    final_url = url
    redirects = 0
    body = ""
    try:
        resp = session.get(url, allow_redirects=True, timeout=session.request_timeout)
        status = resp.status_code
        status_text = resp.reason or ""
        final_url = resp.url
        redirects = len(resp.history)
        body = resp.text or ""
    except Exception as e:
        status = 0
        status_text = str(e)
        final_url = url
        redirects = 0
        body = ""
    return status, status_text, final_url, redirects, body


def detect_keywords(html: str, keywords: List[str]) -> Tuple[bool, List[str]]:
    if not html or not HAVE_BS4:
        return False, []
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True).lower()
    found = []
    for kw in keywords:
        if kw.lower() in text:
            found.append(kw)
    return (len(found) > 0), found


def guess_ats_url(url: str) -> Optional[str]:
    url_lower = url.lower()
    for name, host in ATS_HINTS.items():
        if host in url_lower:
            return url
    return None


def build_candidate_urls(base_url: str) -> List[str]:
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(base_url)
    path = parsed.path or "/"
    candidates = []

    for suffix in COMMON_CAREER_PATHS:
        candidates.append(urlunparse(parsed._replace(path=suffix, query="", fragment="")))

    if path not in ["", "/"]:
        candidates.append(base_url.rstrip("/"))

    seen = set()
    uniq = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def evaluate_company(session: requests.Session, company: str, url: str) -> LinkResult:
    from datetime import datetime

    now = utc_now_iso()

    input_url = url
    input_status_code, input_status_text, input_final_url, input_redirects = fetch_head(session, input_url)

    detected_career_url = input_url
    detected_status_code = input_status_code
    detected_status_text = input_status_text
    detected_final_url = input_final_url
    detected_redirects = input_redirects
    detection_method = "original"
    page_has_keywords = False
    keywords_found = []

    if input_status_code < 200 or input_status_code >= 400:
        s, st, fu, rd, body = fetch_get(session, input_url)
        detected_status_code = s
        detected_status_text = st
        detected_final_url = fu
        detected_redirects = rd
        if s >= 200 and s < 400:
            page_has_keywords, keywords_found = detect_keywords(body, KEYWORDS)
            detection_method = "original_get_ok"
        else:
            ats_url = guess_ats_url(fu)
            if ats_url:
                detected_career_url = ats_url
                detection_method = "ats_hint"
                s2, st2, fu2, rd2, body2 = fetch_get(session, ats_url)
                detected_status_code = s2
                detected_status_text = st2
                detected_final_url = fu2
                detected_redirects = rd2
                page_has_keywords, keywords_found = detect_keywords(body2, KEYWORDS)
            else:
                for cand in build_candidate_urls(input_url):
                    s2, st2, fu2, rd2, body2 = fetch_get(session, cand)
                    if s2 >= 200 and s2 < 400:
                        detected_career_url = cand
                        detected_status_code = s2
                        detected_status_text = st2
                        detected_final_url = fu2
                        detected_redirects = rd2
                        page_has_keywords, keywords_found = detect_keywords(body2, KEYWORDS)
                        detection_method = "heuristic_candidate"
                        break
                else:
                    detection_method = "unresolved"
                    keywords_found = []
    else:
        s, st, fu, rd, body = fetch_get(session, input_url)
        detected_career_url = input_url
        detected_status_code = s
        detected_status_text = st
        detected_final_url = fu
        detected_redirects = rd
        page_has_keywords, keywords_found = detect_keywords(body, KEYWORDS)
        detection_method = "original_ok"

    return LinkResult(
        company_name=company,
        input_url=input_url,
        input_status_code=input_status_code,
        input_status_text=input_status_text,
        input_final_url=input_final_url,
        input_redirects=input_redirects,
        detected_career_url=detected_career_url,
        detected_status_code=detected_status_code,
        detected_status_text=detected_status_text,
        detected_final_url=detected_final_url,
        detected_redirects=detected_redirects,
        detection_method=detection_method,
        page_has_keywords=page_has_keywords,
        keywords_found=",".join(keywords_found),
        last_checked_utc=now,
    )


def auto_detect_columns(cols: List[str]) -> Tuple[str, str]:
    company_col = ""
    url_col = ""
    for c in cols:
        cl = c.lower()
        if not company_col and any(k in cl for k in ["company", "name"]):
            company_col = c
        if not url_col and any(k in cl for k in ["career", "link", "url", "job_page"]):
            url_col = c
    if not company_col:
        company_col = cols[0]
    if not url_col:
        url_col = cols[1] if len(cols) > 1 else cols[0]
    return company_col, url_col


def run(input_path, output_path, company_col, url_col, max_workers=8, timeout=10, sample=10,
        progress_mode="auto", print_interval=25):
    import pandas as pd
    df = pd.read_csv(input_path)
    if not company_col or not url_col:
        company_col, url_col = auto_detect_columns(df.columns.tolist())

    if sample and sample > 0:
        df = df.head(sample)

    total = len(df)

    out_cols = [
        "company_name",
        "input_url",
        "input_status_code",
        "input_status_text",
        "input_final_url",
        "input_redirects",
        "detected_career_url",
        "detected_status_code",
        "detected_status_text",
        "detected_final_url",
        "detected_redirects",
        "detection_method",
        "page_has_keywords",
        "keywords_found",
        "last_checked_utc",
    ]
    results: List[Tuple] = []

    session = create_session(timeout=timeout)

    use_bar = False
    mode = "off"

    if progress_mode == "off":
        mode = "off"
    elif progress_mode == "bar":
        mode = "bar" if HAVE_TQDM and sys.stderr.isatty() else "print"
    elif progress_mode == "print":
        mode = "print"
    elif progress_mode == "auto":
        if HAVE_TQDM and sys.stderr.isatty():
            mode = "bar"
        else:
            mode = "print"
    else:
        mode = "print"

    bar = None
    if mode == "bar" and HAVE_TQDM:
        bar = tqdm(total=total, desc="Checking career links", unit="link")

    ok_count = 0
    replaced_count = 0
    unresolved_count = 0
    error_count = 0

    start_time = time.time()
    last_print = start_time

    def worker(row):
        company = str(row.get(company_col, "")).strip()
        url = normalize_url(str(row.get(url_col, "")).strip())
        if not url:
            res = LinkResult(
                company_name=company,
                input_url="",
                input_status_code=0,
                input_status_text="no input url",
                input_final_url="",
                input_redirects=0,
                detected_career_url="",
                detected_status_code=0,
                detected_status_text="no url",
                detected_final_url="",
                detected_redirects=0,
                detection_method="missing_input",
                page_has_keywords=False,
                keywords_found="",
                last_checked_utc=utc_now_iso(),
            )
            return res

        res = evaluate_company(session, company, url)
        return res

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = []
        for _, row in df.iterrows():
            futures.append(ex.submit(worker, row))

        for i, fut in enumerate(as_completed(futures), start=1):
            try:
                res: LinkResult = fut.result()
            except Exception as e:
                error_count += 1
                continue

            results.append((
                res.company_name,
                res.input_url,
                res.input_status_code,
                res.input_status_text,
                res.input_final_url,
                res.input_redirects,
                res.detected_career_url,
                res.detected_status_code,
                res.detected_status_text,
                res.detected_final_url,
                res.detected_redirects,
                res.detection_method,
                res.page_has_keywords,
                res.keywords_found,
                res.last_checked_utc,
            ))

            if res.detection_method in ("original", "original_ok", "original_get_ok"):
                ok_count += 1
            elif res.detection_method in ("heuristic_candidate", "ats_hint"):
                replaced_count += 1
            elif res.detection_method in ("unresolved", "missing_input"):
                unresolved_count += 1

            if bar is not None:
                bar.update(1)
                bar.set_postfix({
                    "ok": ok_count,
                    "repl": replaced_count,
                    "unres": unresolved_count,
                    "err": error_count
                })
            elif mode == "print":
                now = time.time()
                if i == total or (now - last_print) >= print_interval:
                    last_print = now
                    elapsed = now - start_time
                    rate = elapsed / i if i > 0 else 0
                    remaining = (total - i) * rate if rate > 0 else 0
                    pct = (i / total) * 100 if total > 0 else 0

                    sys.stdout.write(
                        f"\r[{i}/{total} {pct:5.1f}%) | "
                        f"ok={ok_count} repl={replaced_count} unres={unresolved_count} err={error_count} | "
                        f"elapsed={elapsed:5.1f}s ETA={remaining:5.1f}s"
                    )
                    sys.stdout.flush()

    if bar is not None:
        bar.close()
    elif mode == "print":
        sys.stdout.write("\n")
        sys.stdout.flush()

    import pandas as pd
    out_df = pd.DataFrame(results, columns=out_cols)
    out_df.to_csv(output_path, index=False)
    duration = time.time() - start_time
    print(f"Wrote: {output_path}  ({len(out_df)} rows) in {duration:0.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input CSV (e.g., all_career_links_ranked.csv)")
    parser.add_argument("--output", required=True, help="Path to write output CSV")
    parser.add_argument("--company-col", default="", help="Column name for company")
    parser.add_argument("--url-col", default="", help="Column name for career link / url")
    parser.add_argument("--max-workers", type=int, default=8, help="Concurrency")
    parser.add_argument("--timeout", type=int, default=10, help="Per-request timeout seconds")
    parser.add_argument(
        "--sample",
        type=int,
        default=10,
        help="If >0, only process first N rows (default 10; use 0 for all)",
    )
    parser.add_argument("--progress", choices=["auto", "bar", "print", "off"], default="auto",
                        help="Progress/status output mode")
    parser.add_argument("--print-interval", type=int, default=25, help="Update every N items in print mode")
    args = parser.parse_args()

    run(
        input_path=args.input,
        output_path=args.output,
        company_col=args.company_col,
        url_col=args.url_col,
        max_workers=args.max_workers,
        timeout=args.timeout,
        sample=args.sample,
        progress_mode=args.progress,
        print_interval=args.print_interval
    )
