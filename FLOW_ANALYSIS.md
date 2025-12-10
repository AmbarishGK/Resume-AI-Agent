# Flow Analysis & How It Works

## Complete Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    WORKFLOW.PY (Orchestrator)                   │
│                                                                  │
│  python tools/workflow.py                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────┴─────────────────────┐
        │                                             │
        ▼                                             ▼
┌──────────────────┐                        ┌──────────────────┐
│  STEP 1: SCRAPE  │                        │  STEP 2: FETCH   │
│                  │                        │                  │
│  jobscraper/     │                        │  make_jds_from_  │
│  main.py         │                        │  jobs.py         │
│                  │                        │                  │
│  Input:          │                        │  Input:          │
│  - careers.yaml  │                        │  - jobs.csv      │
│                  │                        │                  │
│  Output:         │                        │  Output:         │
│  - jobs.csv      │                        │  - *.txt files   │
│    (role, date,  │                        │    in jds/       │
│     location,    │                        │                  │
│     link, source)│                        │                  │
└──────────────────┘                        └──────────────────┘
        │                                             │
        │                                             │
        └─────────────────────┬─────────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  STEP 3: INGEST   │
                    │                  │
                    │  marnow/ingest.py│
                    │                  │
                    │  Input:          │
                    │  - *.txt files   │
                    │    in jds/       │
                    │                  │
                    │  Output:         │
                    │  - marnow.db     │
                    │    (SQLite)      │
                    └──────────────────┘
```

## Detailed Step-by-Step Flow

### Step 1: Job Scraping (`tools/jobscraper/main.py`)

**Path Resolution:**
- Script location: `tools/jobscraper/main.py`
- BASE_DIR: `Path(__file__).resolve().parents[2]` = `Resume-AI-Agent/`
- Config: `BASE_DIR / "app" / "config" / "careers.yaml"`
- Output: `BASE_DIR / "app" / "data" / "jobs" / "jobs.csv"`

**Process:**
1. Reads `app/config/careers.yaml` (company URLs and CSS selectors)
2. Uses Playwright to scrape each company's career page
3. Extracts: role, date, location, link, source
4. Applies filters (include/exclude keywords, locations)
5. Deduplicates by link
6. Writes CSV with columns: `role,date,location,link,source,keywords_matched`

**Example Output (jobs.csv):**
```csv
role,date,location,link,source,keywords_matched
Backend Engineer,2025-12-09,Dublin HQ,https://stripe.com/jobs/...,Stripe,
Software Engineer,2025-12-09,Remote,https://www.tesla.com/...,Tesla,software
```

### Step 2: JD Fetching (`tools/make_jds_from_jobs.py`)

**Path Resolution:**
- Script location: `tools/make_jds_from_jobs.py`
- BASE_DIR: `Path(__file__).resolve().parents[1]` = `Resume-AI-Agent/`
- Input: `BASE_DIR / "app" / "data" / "jobs" / "jobs.csv"`
- Output: `BASE_DIR / "app" / "data" / "jds" /`

**Process:**
1. Reads `app/data/jobs/jobs.csv`
2. For each job row (or limited subset):
   - Extracts `link` field
   - Fetches HTML from the link using `requests`
   - Parses HTML with BeautifulSoup to extract main content
   - Creates filename: `{source}-{role}.txt` (slugified)
   - Saves text to `app/data/jds/{filename}.txt`
3. Skips if file already exists (idempotent)

**Example Output:**
- `app/data/jds/stripe-backend-engineer.txt`
- `app/data/jds/tesla-software-engineer.txt`

### Step 3: JD Ingestion (`marnow/ingest.py`)

**Path Resolution:**
- Called directly from `workflow.py` (not subprocess)
- JD files: `app/data/jds/*.txt`
- Database: `marnow.db` (in project root, or `/app/marnow.db` if MARNOW_DB env set)

**Process:**
1. Ensures database exists (calls `ensure_db()`)
2. Scans `app/data/jds/` for `*.txt` files
3. For each JD file:
   - Reads text content
   - Parses company/role from:
     - Metadata comments: `# company: X` or `# role: Y`
     - Filename: `{company}-{role}.txt` → splits on `-` or `_`
   - Calls `upsert_job(filename, company, role, text, source_url=None)`
   - Stores in `job_posts` table with hash deduplication

**Database Schema (job_posts):**
```sql
CREATE TABLE job_posts(
  id INTEGER PRIMARY KEY,
  filename TEXT,
  company TEXT,
  role TEXT,
  source_url TEXT,
  text TEXT,
  ingested_at TEXT,
  hash TEXT UNIQUE  -- Deduplication by content hash
);
```

## Integration Points

### workflow.py → jobscraper/main.py
- **Method**: Subprocess call
- **Command**: `python tools/jobscraper/main.py --config <path> --out <path> [filters]`
- **Working Directory**: `BASE_DIR` (Resume-AI-Agent/)
- **Validation**: Checks if `jobs.csv` exists after scraping

### workflow.py → make_jds_from_jobs.py
- **Method**: Subprocess call
- **Command**: `python tools/make_jds_from_jobs.py [--limit N | --all]`
- **Working Directory**: `BASE_DIR` (Resume-AI-Agent/)
- **Validation**: Checks exit code (no file existence check needed)

### workflow.py → marnow/ingest.py
- **Method**: Direct Python import
- **Function**: `ingest_jd(path)` for each JD file
- **Error Handling**: Catches exceptions per file, continues with others

## Data Flow

```
careers.yaml (config)
    │
    ▼
[Playwright Scraper]
    │
    ▼
jobs.csv (structured job listings)
    │
    ▼
[HTTP Fetcher]
    │
    ▼
*.txt files (full job descriptions)
    │
    ▼
[Ingestion Parser]
    │
    ▼
marnow.db (SQLite database)
    │
    ▼
[MaRNoW Matching Engine]
    │
    ▼
Match scores & reports
```

## Potential Issues Found

### 1. Database Path Hardcoding
- **Issue**: `marnow/db.py` defaults to `/app/marnow.db` (Docker path)
- **Impact**: Works in Docker, but local dev needs `MARNOW_DB` env var or relative path
- **Fix**: Should default to `./marnow.db` or `BASE_DIR/marnow.db` for local dev

### 2. Missing Error Handling in make_jds_from_jobs.py
- **Issue**: Script returns `None` on error (no exit code)
- **Impact**: `workflow.py` can't detect failures properly
- **Fix**: Should return exit code or raise exceptions

### 3. JD File Naming Consistency
- **Issue**: `make_jds_from_jobs.py` creates `{source}-{role}.txt`
- **Issue**: `ingest.py` parses `{company}-{role}.txt` from filename
- **Impact**: If `source` != `company`, parsing might fail
- **Note**: Usually works because `source` field in CSV is company name

## Testing the Flow

### Manual Testing Steps:

1. **Test Scraper:**
   ```bash
   cd Resume-AI-Agent
   python tools/jobscraper/main.py --config app/config/careers.yaml
   # Check: app/data/jobs/jobs.csv exists
   ```

2. **Test JD Fetcher:**
   ```bash
   python tools/make_jds_from_jobs.py --limit 2
   # Check: app/data/jds/ has .txt files
   ```

3. **Test Ingestion:**
   ```bash
   python -m marnow.cli initdb
   python -c "from marnow.ingest import ingest_jd; ingest_jd('app/data/jds/stripe-backend-engineer.txt')"
   # Check: marnow.db has entries
   ```

4. **Test Full Workflow:**
   ```bash
   python tools/workflow.py --jd-limit 2
   # Should complete all 3 steps
   ```

## Recommendations

1. **Fix database path** to work locally without Docker
2. **Add return codes** to `make_jds_from_jobs.py`
3. **Add validation** that JD files were created before ingestion
4. **Add progress indicators** for long-running steps
5. **Consider adding** metadata to JD files (company/role in comments)
