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
    --print-interval N               Default=25 (for print mode only)

Other args are identical to the original script.
"""

import re
import csv
import sys
import time
import json
import argparse
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin

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
    "Accept-Language": "en-US,en;q=0.7",
    "Connection": "close",
}
KEYWORDS = [
    "career", "careers", "job", "jobs", "open role", "open roles", "openings",
    "opportunities", "join us", "work with us", "work at", "we're hiring"
]
ATS_HINTS = [
    "greenhouse.io", "boards.greenhouse.io", "lever.co", "jobs.lever.co",
    "ashbyhq.com", "workable.com", "myworkdayjobs.com", "smartrecruiters.com",
    "icims.com", "eightfold.ai", "oraclecloud.com", "successfactors",
    "recruitee.com", "teamtailor.com", "jobvite.com", "ukg.com", "bamboohr.com"
]
COMMON_CAREER_PATHS = [
    "/careers", "/careers/", "/career", "/jobs", "/jobs/", "/join-us",
    "/join-us/", "/join", "/work-with-us", "/opportunities", "/company/careers",
    "/about/careers", "/global/en/careers", "/en/careers", "/us/en/careers",
    "/careers-home"
]

def normalize_url(u: str) -> str:
    if not isinstance(u, str):
        return ""
    u = u.strip()
    if not u:
        return ""
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return u

def base_from_url(u: str) -> str:
    try:
        p = urlparse(u)
        if not p.netloc:
            return ""
        netloc = re.sub(r"^(www|m)\.", "", p.netloc, flags=re.I)
        scheme = p.scheme or "https"
        return f"{scheme}://{netloc}"
    except Exception:
        return ""

def build_candidates(base: str) -> list:
    candidates = [base + path for path in COMMON_CAREER_PATHS if base]
    # subdomain options
    if base:
        netloc = urlparse(base).netloc
        scheme = "https"
        candidates = [f"{scheme}://careers.{netloc}", f"{scheme}://jobs.{netloc}"] + candidates
    return candidates

def make_session(timeout: int):
    s = requests.Session()
    retries = Retry(
        total=2, connect=2, read=2, backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(HEADERS)
    s.request_timeout = timeout
    return s

def fetch(session: requests.Session, url: str):
    """Return (status_code, reason, final_url, text_snippet, redirects_count)."""
    url = normalize_url(url)
    if not url:
        return None, "invalid-url", "", "", 0
    try:
        # HEAD first
        r = session.head(url, allow_redirects=True, timeout=session.request_timeout)
        status, reason, final = r.status_code, r.reason or "", r.url
        redirects = len(r.history)
        # Some servers don't like HEAD; fallback to GET when ambiguous
        if status in (405, 403) or (status >= 400 and status < 600):
            rg = session.get(url, allow_redirects=True, timeout=session.request_timeout, stream=True)
            status, reason, final = rg.status_code, rg.reason or "", rg.url
            redirects = len(rg.history)
            try:
                text_snippet = rg.text[:5000]
            except Exception:
                text_snippet = ""
        else:
            # do a tiny GET to inspect content
            rg = session.get(final, allow_redirects=True, timeout=session.request_timeout, stream=True)
            status, reason, final = rg.status_code, rg.reason or "", rg.url
            redirects = len(rg.history)
            try:
                text_snippet = rg.text[:5000]
            except Exception:
                text_snippet = ""
        return status, reason, final, text_snippet, redirects
    except requests.exceptions.SSLError:
        return 495, "SSL Error", "", "", 0
    except requests.exceptions.Timeout:
        return 408, "Request Timeout", "", "", 0
    except requests.exceptions.TooManyRedirects:
        return 310, "Too Many Redirects", "", "", 0
    except requests.exceptions.ConnectionError as e:
        return 523, f"Connection Error: {e.__class__.__name__}", "", "", 0
    except Exception as e:
        return 520, f"Unknown Error: {e.__class__.__name__}", "", "", 0

def looks_like_careers(text: str, url: str) -> (bool, list):
    if not text and not url:
        return False, []
    text_l = (text or "").lower()
    found = set(k for k in KEYWORDS if k in text_l)
    # quick ATS domain detection
    u = (url or "").lower()
    if any(h in u for h in ATS_HINTS):
        found.add("ats_link")
    return (len(found) > 0), sorted(found)

def find_replacement(session: requests.Session, input_url: str):
    base = base_from_url(input_url)
    candidates = build_candidates(base)

    # First try homepage and parse anchors for career-like hrefs (requires bs4)
    homepage = base
    if homepage and HAVE_BS4:
        try:
            r = session.get(homepage, allow_redirects=True, timeout=session.request_timeout)
            soup = BeautifulSoup(r.text, "html.parser")
            anchors = soup.find_all("a", href=True)
            for a in anchors:
                href = a["href"]
                text = (a.get_text() or "").strip().lower()
                if any(k in href.lower() for k in ["career", "job"]) or any(k in text for k in ["career", "job"]):
                    candidates.insert(0, urljoin(homepage, href))
        except Exception:
            pass

    # Try candidates in order
    for cand in candidates:
        status, reason, final, text_snippet, redirects = fetch(session, cand)
        ok, keywords = looks_like_careers(text_snippet, final)
        if status and 200 <= int(status) < 400 and ok:
            return {
                "url": cand,
                "status": status,
                "reason": reason,
                "final_url": final,
                "redirects": redirects,
                "method": "homepage_parse" if HAVE_BS4 and cand not in build_candidates(base) else "path_heuristic",
                "keywords_found": ",".join(keywords)
            }
    return None

def process_row(session, company, input_url):
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = {
        "company_name": company,
        "input_url": input_url,
        "input_status_code": "",
        "input_status_text": "",
        "input_final_url": "",
        "input_redirects": "",
        "detected_career_url": "",
        "detected_status_code": "",
        "detected_status_text": "",
        "detected_final_url": "",
        "detected_redirects": "",
        "detection_method": "",
        "page_has_keywords": "",
        "keywords_found": "",
        "last_checked_utc": now_iso
    }

    # Check the input URL
    status, reason, final, text_snippet, redirects = fetch(session, input_url)
    result["input_status_code"] = status
    result["input_status_text"] = reason
    result["input_final_url"] = final
    result["input_redirects"] = redirects
    ok, keywords = looks_like_careers(text_snippet, final)

    if isinstance(status, int) and 200 <= status < 400 and ok:
        # Input link is fine
        result["detected_career_url"] = final or input_url
        result["detected_status_code"] = status
        result["detected_status_text"] = reason
        result["detected_final_url"] = final
        result["detected_redirects"] = redirects
        result["detection_method"] = "original_ok"
        result["page_has_keywords"] = True
        result["keywords_found"] = ",".join(keywords)
        return result

    # If not ok, try to find a replacement
    repl = find_replacement(session, input_url)
    if repl:
        result["detected_career_url"] = repl["url"]
        result["detected_status_code"] = repl["status"]
        result["detected_status_text"] = repl["reason"]
        result["detected_final_url"] = repl["final_url"]
        result["detected_redirects"] = repl["redirects"]
        result["detection_method"] = repl["method"]
        result["page_has_keywords"] = True
        result["keywords_found"] = repl["keywords_found"]
    else:
        # fallback: even if not clearly a "careers" page, record the best final
        result["detected_career_url"] = final or input_url
        result["detected_status_code"] = status
        result["detected_status_text"] = reason
        result["detected_final_url"] = final
        result["detected_redirects"] = redirects
        result["detection_method"] = "unresolved"
        result["page_has_keywords"] = bool(keywords)
        result["keywords_found"] = ",".join(keywords)

    return result

def auto_detect_columns(header):
    company_col = None
    url_col = None
    lower = {c.lower(): c for c in header}
    for key in ["company", "name", "company_name", "org", "organization"]:
        if key in lower:
            company_col = lower[key]
            break
    if company_col is None:
        # First non-URL looking column
        for c in header:
            if not re.search(r"url|link|career|job", c, re.I):
                company_col = c
                break
    for key in ["career_link", "link", "url", "career_url", "careers", "jobs_url"]:
        if key in lower:
            url_col = lower[key]
            break
    if url_col is None:
        for c in header:
            if re.search(r"url|link", c, re.I):
                url_col = c
                break
    if company_col is None:
        company_col = header[0]
    if url_col is None:
        url_col = header[1] if len(header) > 1 else header[0]
    return company_col, url_col

def run(input_path, output_path, company_col, url_col, max_workers=8, timeout=10, sample=0,
        progress_mode="auto", print_interval=25):
    import pandas as pd
    df = pd.read_csv(input_path)
    if not company_col or not url_col:
        company_col, url_col = auto_detect_columns(df.columns.tolist())

    if sample and sample > 0:
        df = df.head(sample)

    total = len(df)

    # Prepare output
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
        "last_checked_utc"
    ]

    session = make_session(timeout=timeout)

    tasks = []
    results = []

    start_time = time.time()
    ok_count = 0
    replaced_count = 0
    unresolved_count = 0
    error_count = 0

    # Decide progress mode
    if progress_mode == "auto":
        if HAVE_TQDM and sys.stderr.isatty():
            mode = "bar"
        else:
            mode = "print"
    elif progress_mode in ("bar", "print", "off"):
        mode = progress_mode
    else:
        mode = "print"

    # Create the bar if needed
    bar = None
    if mode == "bar" and HAVE_TQDM:
        bar = tqdm(total=total, desc="Checking career links", unit="link")

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for _, row in df.iterrows():
            company = str(row.get(company_col, "")).strip()
            url = normalize_url(str(row.get(url_col, "")).strip())
            if not url:
                # if URL is missing, try using company as domain guess
                url = f"https://{company.lower().replace(' ', '')}.com"
            tasks.append(ex.submit(process_row, session, company, url))

        processed = 0
        for fut in as_completed(tasks):
            try:
                res = fut.result()
                results.append(res)
                method = res.get("detection_method", "")
                if method == "original_ok":
                    ok_count += 1
                elif method in ("path_heuristic", "homepage_parse"):
                    replaced_count += 1
                elif method == "unresolved":
                    unresolved_count += 1
                else:
                    # worker_error flows below but just in case
                    pass
            except Exception:
                # Count as error; still advance progress
                res = None
                error_count += 1

            processed += 1

            if bar is not None:
                # update tqdm
                bar.update(1)
                bar.set_postfix_str(f"ok={ok_count} repl={replaced_count} unres={unresolved_count} err={error_count}")
            elif mode == "print":
                if (processed % max(1, int(print_interval)) == 0) or processed == total:
                    elapsed = time.time() - start_time
                    pct = (processed / total) * 100 if total else 100.0
                    rate = processed / elapsed if elapsed > 0 else 0.0
                    remaining = (total - processed) / rate if rate > 0 else 0.0
                    sys.stdout.write(
                        f"\rProgress: {processed}/{total} ({pct:5.1f}%) | "
                        f"ok={ok_count} repl={replaced_count} unres={unresolved_count} err={error_count} | "
                        f"elapsed={elapsed:5.1f}s ETA={remaining:5.1f}s"
                    )
                    sys.stdout.flush()

    if bar is not None:
        bar.close()
    elif mode == "print":
        sys.stdout.write("\n")
        sys.stdout.flush()

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
    parser.add_argument("--sample", type=int, default=0, help="If >0, only process first N rows")
    parser.add_argument("--progress", choices=["auto", "bar", "print", "off"], default="auto", help="Progress/status output mode")
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
