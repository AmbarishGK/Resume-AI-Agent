# Workflow Flow Summary

## ✅ How the Complete Flow Works

### Entry Point: `tools/workflow.py`

The workflow orchestrator runs three sequential steps:

```
python tools/workflow.py
    ↓
[STEP 1] Scrape Jobs
    ↓
[STEP 2] Fetch Job Descriptions  
    ↓
[STEP 3] Ingest into Database
    ↓
Ready for Matching!
```

---

## Step 1: Job Scraping

**Script**: `tools/jobscraper/main.py`  
**Called via**: Subprocess from `workflow.py`

### Process:
1. **Reads config**: `app/config/careers.yaml`
   - Contains company URLs and CSS selectors for scraping
   
2. **Launches Playwright browser** (headless by default)
   - Visits each company's career page
   - Handles cookie/consent banners
   - Supports pagination (scroll/load-more)

3. **Extracts job data**:
   - Role title
   - Posting date
   - Location
   - Job link URL
   - Source company name

4. **Applies filters** (if specified):
   - Include keywords (any match required)
   - Exclude keywords (any match excludes)
   - Location filters

5. **Deduplicates** by link URL

6. **Writes CSV**: `app/data/jobs/jobs.csv`
   ```
   role,date,location,link,source,keywords_matched
   Backend Engineer,2025-12-09,Dublin,https://...,Stripe,
   ```

### Path Resolution:
- BASE_DIR = `tools/jobscraper/main.py` → `parents[2]` = `Resume-AI-Agent/`
- Config: `BASE_DIR/app/config/careers.yaml` ✅
- Output: `BASE_DIR/app/data/jobs/jobs.csv` ✅

---

## Step 2: JD Fetching

**Script**: `tools/make_jds_from_jobs.py`  
**Called via**: Subprocess from `workflow.py`

### Process:
1. **Reads**: `app/data/jobs/jobs.csv`

2. **For each job** (or limited subset):
   - Extracts `link` field
   - Makes HTTP GET request to fetch HTML
   - Parses HTML with BeautifulSoup
   - Extracts main content (finds largest text block >400 chars)
   - Creates filename: `{source}-{role}.txt` (slugified)
   - Saves to: `app/data/jds/{filename}.txt`

3. **Skips existing files** (idempotent - won't re-fetch)

### Example Output:
- `app/data/jds/stripe-backend-engineer.txt`
- `app/data/jds/tesla-software-engineer.txt`

### Path Resolution:
- BASE_DIR = `tools/make_jds_from_jobs.py` → `parents[1]` = `Resume-AI-Agent/`
- Input: `BASE_DIR/app/data/jobs/jobs.csv` ✅
- Output: `BASE_DIR/app/data/jds/` ✅

---

## Step 3: JD Ingestion

**Module**: `marnow/ingest.py`  
**Called via**: Direct Python import from `workflow.py`

### Process:
1. **Ensures database exists**:
   - Calls `ensure_db()` → creates `marnow.db` if needed
   - Creates tables: `job_posts`, `resumes`, `skills`, `matches`

2. **Scans JD directory**:
   - Finds all `*.txt` files in `app/data/jds/`
   - Sorts alphabetically

3. **For each JD file**:
   - Reads text content
   - **Parses company/role**:
     - First tries metadata: `# company: X` or `# role: Y` in first 5 lines
     - Falls back to filename: splits `{company}-{role}.txt` on `-` or `_`
   - Calls `upsert_job(filename, company, role, text, source_url=None)`
   - Stores in `job_posts` table
   - **Deduplicates by content hash** (same JD won't be inserted twice)

### Database Schema:
```sql
job_posts (
  id, filename, company, role, source_url, 
  text, ingested_at, hash (UNIQUE)
)
```

### Path Resolution:
- JD files: `app/data/jds/*.txt` ✅
- Database: `marnow.db` (project root) or `/app/marnow.db` (if `MARNOW_DB` env set)

---

## Data Flow Diagram

```
┌─────────────────────┐
│  careers.yaml       │  (Company configs)
│  (app/config/)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  jobscraper/main.py │  (Playwright scraper)
│  [STEP 1]           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  jobs.csv           │  (Structured listings)
│  (app/data/jobs/)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  make_jds_from_     │  (HTTP fetcher)
│  jobs.py [STEP 2]   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  *.txt files        │  (Full job descriptions)
│  (app/data/jds/)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  marnow/ingest.py   │  (Database ingester)
│  [STEP 3]           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  marnow.db          │  (SQLite database)
│  (project root)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  marnow/cli.py      │  (Matching & reporting)
│  [Ready for use!]   │
└─────────────────────┘
```

---

## Integration Details

### workflow.py → jobscraper/main.py
- **Method**: `subprocess.run([sys.executable, script_path, ...args])`
- **Working dir**: `BASE_DIR` (Resume-AI-Agent/)
- **Validation**: Checks if `jobs.csv` exists after completion
- **Error handling**: Returns False if exit code != 0 or file missing

### workflow.py → make_jds_from_jobs.py
- **Method**: `subprocess.run([sys.executable, script_path, ...args])`
- **Working dir**: `BASE_DIR` (Resume-AI-Agent/)
- **Validation**: Checks exit code only
- **Error handling**: Returns False if exit code != 0
- **Note**: Fixed to return exit code (was missing before)

### workflow.py → marnow/ingest.py
- **Method**: Direct Python import `from marnow.ingest import ensure_db, ingest_jd`
- **Error handling**: Try/except per file, continues on errors
- **Returns**: Counts of ingested/skipped/errors

---

## Usage Examples

### Basic Workflow
```bash
# Run all 3 steps with defaults (10 JDs)
python tools/workflow.py
```

### Custom Options
```bash
# Fetch all JDs and ingest all
python tools/workflow.py --all-jds --all-ingest

# Filter jobs by keywords
python tools/workflow.py --include "software,engineer" --exclude "senior"

# Skip steps (if you already have data)
python tools/workflow.py --skip-scrape --skip-fetch  # Only ingest
```

### Manual Steps (if needed)
```bash
# Step 1 only
python tools/jobscraper/main.py

# Step 2 only  
python tools/make_jds_from_jobs.py --limit 10

# Step 3 only
python -m marnow.cli initdb
python -c "from marnow.ingest import ensure_db, ingest_jd; ensure_db(); ingest_jd('app/data/jds/stripe-backend-engineer.txt')"
```

---

## Known Issues & Notes

### ✅ Fixed Issues:
1. **make_jds_from_jobs.py exit code**: Now returns proper exit code
2. **Path resolution**: All paths correctly resolve to project root

### ⚠️ Potential Issues:
1. **Database path**: `marnow/match.py` hardcodes `DB = "/app/marnow.db"` (Docker path)
   - **Workaround**: Set `MARNOW_DB` environment variable
   - **Impact**: Works in Docker, but local dev needs env var
   - **Note**: `marnow/db.py` already handles this correctly

2. **JD filename parsing**: 
   - `make_jds_from_jobs.py` creates: `{source}-{role}.txt`
   - `ingest.py` parses: `{company}-{role}.txt`
   - **Usually works** because `source` field = company name
   - **Better**: Add metadata comments to JD files

3. **Error handling in make_jds_from_jobs.py**:
   - Returns `None` on some errors (empty CSV, missing file)
   - **Fixed**: Now returns exit code 0 or 1

---

## Testing Checklist

- [x] Path resolution works correctly
- [x] Subprocess calls work
- [x] Database path handling
- [x] Exit codes propagate correctly
- [ ] End-to-end test with real data
- [ ] Error handling in all steps
- [ ] JD filename parsing consistency

---

## Next Steps After Workflow

Once jobs are ingested:

1. **Ingest resumes**:
   ```bash
   python -m marnow.cli ingest-resume app/data/resumes/resume.pdf
   ```

2. **Match resume to job**:
   ```bash
   python -m marnow.cli match <resume_id> <job_id>
   ```

3. **View match report**:
   ```bash
   python -m marnow.cli report <match_id>
   ```

The workflow successfully integrates job scraping → JD fetching → database ingestion! 🎉
