#!/usr/bin/env python3
"""
Automated workflow: Scrape jobs → Fetch JDs → Ingest into marnow database

This script orchestrates the complete pipeline:
1. Scrape job postings from company career pages
2. Fetch job descriptions from the links
3. Ingest job descriptions into marnow database for matching
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
# Add project root to Python path so marnow module can be imported
sys.path.insert(0, str(BASE_DIR))
# Set database path to local marnow.db if not already set
if "MARNOW_DB" not in os.environ:
    os.environ["MARNOW_DB"] = str(BASE_DIR / "marnow.db")

JOBS_CSV = BASE_DIR / "app" / "data" / "jobs" / "jobs.csv"
JDS_DIR = BASE_DIR / "app" / "data" / "jds"
SCRAPER_SCRIPT = BASE_DIR / "tools" / "jobscraper" / "main.py"
FETCH_SCRIPT = BASE_DIR / "tools" / "make_jds_from_jobs.py"


def run_scraper(config_path=None, include="", exclude="", locations="", 
                headless=True, dump_html=False):
    """Step 1: Scrape job postings"""
    print("=" * 60)
    print("STEP 1: Scraping job postings...")
    print("=" * 60)
    
    cmd = [sys.executable, str(SCRAPER_SCRIPT)]
    if config_path:
        cmd.extend(["--config", str(config_path)])
    if include:
        cmd.extend(["--include", include])
    if exclude:
        cmd.extend(["--exclude", exclude])
    if locations:
        cmd.extend(["--locations", locations])
    if not headless:
        cmd.append("--no-headless")
    if dump_html:
        cmd.append("--dump-html")
    
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"[ERROR] Job scraper failed with exit code {result.returncode}")
        return False
    
    if not JOBS_CSV.exists():
        print(f"[ERROR] jobs.csv was not created at {JOBS_CSV}")
        return False
    
    print(f"[OK] Jobs scraped and saved to {JOBS_CSV}")
    return True


def run_fetch_jds(limit=None, fetch_all=False):
    """Step 2: Fetch job descriptions from links"""
    print("\n" + "=" * 60)
    print("STEP 2: Fetching job descriptions...")
    print("=" * 60)
    
    cmd = [sys.executable, str(FETCH_SCRIPT)]
    if fetch_all:
        cmd.append("--all")
    elif limit:
        cmd.extend(["--limit", str(limit)])
    
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"[ERROR] JD fetcher failed with exit code {result.returncode}")
        return False
    
    print(f"[OK] Job descriptions fetched to {JDS_DIR}")
    return True


def run_ingest_jds(limit=None, ingest_all=False):
    """Step 3: Ingest job descriptions into marnow database"""
    print("\n" + "=" * 60)
    print("STEP 3: Ingesting job descriptions into marnow database...")
    print("=" * 60)
    
    # Ensure project root is in Python path before importing
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    # Import here to avoid issues if marnow not available
    from marnow.ingest import ensure_db, ingest_jd
    
    ensure_db()
    
    jd_files = sorted(JDS_DIR.glob("*.txt"))
    if not jd_files:
        print(f"[WARN] No JD files found in {JDS_DIR}")
        return False
    
    if not ingest_all and limit:
        jd_files = jd_files[:limit]
    
    print(f"[info] Found {len(jd_files)} JD file(s) to ingest")
    
    ingested = 0
    skipped = 0
    errors = 0
    
    for i, jd_path in enumerate(jd_files, 1):
        try:
            jid, created = ingest_jd(str(jd_path))
            if created:
                ingested += 1
                print(f"[{i}/{len(jd_files)}] ✓ Ingested: {jd_path.name} (id={jid})")
            else:
                skipped += 1
                print(f"[{i}/{len(jd_files)}] - Skipped (exists): {jd_path.name} (id={jid})")
        except Exception as e:
            errors += 1
            print(f"[{i}/{len(jd_files)}] ✗ Error: {jd_path.name}: {e}")
    
    print(f"\n[OK] Ingested {ingested} new, skipped {skipped} existing, {errors} errors")
    return errors == 0


def main():
    parser = argparse.ArgumentParser(
        description="Automated workflow: Scrape → Fetch JDs → Ingest into marnow"
    )
    parser.add_argument(
        "--config",
        default=str(BASE_DIR / "app" / "config" / "careers.yaml"),
        help="Path to careers.yaml config file"
    )
    parser.add_argument(
        "--include",
        default="",
        help="CSV of include keywords for job filtering"
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="CSV of exclude keywords for job filtering"
    )
    parser.add_argument(
        "--locations",
        default="",
        help="CSV of location filters"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window during scraping"
    )
    parser.add_argument(
        "--dump-html",
        action="store_true",
        help="Save HTML/screenshots for debugging"
    )
    parser.add_argument(
        "--jd-limit",
        type=int,
        default=10,
        help="Limit number of JDs to fetch (default: 10, use --all-jds to fetch all)"
    )
    parser.add_argument(
        "--all-jds",
        action="store_true",
        help="Fetch all job descriptions (ignores --jd-limit)"
    )
    parser.add_argument(
        "--ingest-limit",
        type=int,
        help="Limit number of JDs to ingest (default: same as --jd-limit)"
    )
    parser.add_argument(
        "--all-ingest",
        action="store_true",
        help="Ingest all JD files (ignores --ingest-limit)"
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping step (use existing jobs.csv)"
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip fetching step (use existing JD files)"
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip ingestion step"
    )
    
    args = parser.parse_args()
    
    # Determine ingest limit
    ingest_limit = args.ingest_limit
    if ingest_limit is None and not args.all_ingest:
        ingest_limit = args.jd_limit if not args.all_jds else None
    
    success = True
    
    # Step 1: Scrape
    if not args.skip_scrape:
        success = run_scraper(
            config_path=args.config,
            include=args.include,
            exclude=args.exclude,
            locations=args.locations,
            headless=not args.no_headless,
            dump_html=args.dump_html
        )
        if not success:
            print("\n[ERROR] Workflow stopped at scraping step")
            return 1
    else:
        print("[SKIP] Scraping step skipped (using existing jobs.csv)")
        if not JOBS_CSV.exists():
            print(f"[ERROR] jobs.csv not found at {JOBS_CSV}")
            return 1
    
    # Step 2: Fetch JDs
    if not args.skip_fetch:
        success = run_fetch_jds(
            limit=None if args.all_jds else args.jd_limit,
            fetch_all=args.all_jds
        )
        if not success:
            print("\n[ERROR] Workflow stopped at fetching step")
            return 1
    else:
        print("[SKIP] Fetching step skipped (using existing JD files)")
    
    # Step 3: Ingest
    if not args.skip_ingest:
        success = run_ingest_jds(
            limit=ingest_limit,
            ingest_all=args.all_ingest
        )
        if not success:
            print("\n[ERROR] Workflow stopped at ingestion step")
            return 1
    else:
        print("[SKIP] Ingestion step skipped")
    
    print("\n" + "=" * 60)
    print("✓ Workflow completed successfully!")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"  1. Ingest resumes: python -m marnow.cli ingest-resume <resume.pdf>")
    print(f"  2. Match resume to job: python -m marnow.cli match <resume_id> <job_id>")
    print(f"  3. View match report: python -m marnow.cli report <match_id>")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
