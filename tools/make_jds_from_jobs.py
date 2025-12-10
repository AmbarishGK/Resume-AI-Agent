#!/usr/bin/env python3
import csv
import re
import time
import argparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parents[1]
JOBS_CSV = BASE_DIR / "app" / "data" / "jobs" / "jobs.csv"
JDS_DIR = BASE_DIR / "app" / "data" / "jds"

HEADERS = {
    "User-Agent": "MaRNoW-JD-Fetcher/0.1",
    "Accept-Language": "en-US,en;q=0.9",
}


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "jd"


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    candidates = []
    for selector in ["main", "[role=main]", ".job-description", ".content", "body"]:
        for node in soup.select(selector):
            text = " ".join(node.get_text(separator=" ", strip=True).split())
            if len(text) > 400:
                candidates.append(text)

    if not candidates:
        return " ".join(soup.get_text(separator=" ", strip=True).split())

    candidates.sort(key=len, reverse=True)
    return candidates[0]


def fetch_jd(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    return extract_text_from_html(resp.text)


def main():
    parser = argparse.ArgumentParser(description="Create JD text files from jobs.csv")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Fetch only the first N jobs (default: 10)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ignore limit and fetch all job descriptions",
    )
    args = parser.parse_args()

    print(f"[info] JOBS_CSV = {JOBS_CSV}")
    if not JOBS_CSV.exists():
        print("[error] jobs.csv not found at this path.")
        return

    JDS_DIR.mkdir(parents=True, exist_ok=True)

    with JOBS_CSV.open(newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    total_rows = len(reader)
    if total_rows == 0:
        print("[warn] jobs.csv is empty; nothing to fetch.")
        return

    if args.all:
        rows_to_process = reader
        print(f"[info] Fetching ALL {total_rows} job descriptions...")
    else:
        rows_to_process = reader[: args.limit]
        print(f"[info] Fetching FIRST {args.limit} job descriptions (use --all to fetch all {total_rows}).")

    print(f"[info] Output directory: {JDS_DIR}")

    for i, row in enumerate(rows_to_process, start=1):
        role = row.get("role", "").strip()
        source = row.get("source", "").strip()
        link = row.get("link", "").strip()

        slug = slugify(f"{source}-{role}")
        out_path = JDS_DIR / f"{slug}.txt"

        print(f"[{i}/{len(rows_to_process)}] {role} ({source})")
        if not link:
            print("   [skip] missing link")
            continue

        if out_path.exists():
            print(f"   [skip] {out_path.name} already exists")
            continue

        try:
            print(f"   [fetch] {link}")
            text = fetch_jd(link)
        except Exception as e:
            print(f"   [error] {link}: {e}")
            continue

        out_path.write_text(text, encoding="utf-8")
        print(f"   [ok] wrote {out_path.name} ({len(text)} chars)")
        time.sleep(1.0)

    print("\n[done] JD files created in app/data/jds/")


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
