# Workflow

This doc focuses on the pipeline (scrape -> fetch JDs -> ingest).

## Quick start

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m playwright install chromium

python tools/workflow.py
```

## Run the complete workflow

The automated workflow script handles the entire pipeline:

```bash
# Basic usage - scrape, fetch 10 JDs, and ingest them
python tools/workflow.py

# Fetch all JDs and ingest all
python tools/workflow.py --all-jds --all-ingest

# Custom filtering
python tools/workflow.py --include "software,engineer" --exclude "senior,staff" --locations "remote,sf"

# Skip steps if you already have data
python tools/workflow.py --skip-scrape --skip-fetch  # Only ingest existing JDs
```

## Manual steps (if needed)

#### Scrape Jobs
```bash
python tools/jobscraper/main.py --config app/config/careers.yaml --out app/data/jobs/jobs.csv
```

#### Fetch Job Descriptions
```bash
python tools/make_jds_from_jobs.py --limit 10  # or --all
```

#### Ingest into Database
```bash
python -m marnow.cli initdb
python -m marnow.cli ingest-jd app/data/jds/company-role.txt
```

## Workflow Steps

1. **Scrape Jobs** (`tools/jobscraper/main.py`)
   - Reads company configurations from `app/config/careers.yaml`
   - Scrapes job postings using Playwright
   - Outputs to `app/data/jobs/jobs.csv`

2. **Fetch Job Descriptions** (`tools/make_jds_from_jobs.py`)
   - Reads `app/data/jobs/jobs.csv`
   - Fetches full job descriptions from links
   - Saves as text files in `app/data/jds/`

3. **Ingest into MaRNoW** (`marnow/ingest.py`)
   - Parses JD text files
   - Stores in SQLite database for matching

4. **Match Resumes** (`marnow/cli.py`)
   - Ingest resumes: `python -m marnow.cli ingest-resume resume.pdf`
   - Match: `python -m marnow.cli match <resume_id> <job_id>`
   - Report: `python -m marnow.cli report <match_id>`

## Configuration

Edit `app/config/careers.yaml` to add or modify company career page configurations.

## Directory Structure

```
Resume-AI-Agent/
├── app/
│   ├── config/
│   │   └── careers.yaml          # Company scraping configs
│   └── data/
│       ├── jobs/
│       │   └── jobs.csv          # Scraped job postings
│       ├── jds/                  # Fetched job descriptions
│       ├── resumes/              # Resume PDFs/DOCX
│       └── skills/
│           └── skills.csv        # Skills database
├── tools/
│   ├── jobscraper/
│   │   └── main.py               # Job scraper
│   ├── make_jds_from_jobs.py    # JD fetcher
│   └── workflow.py              # Automated workflow
└── marnow/                       # Matching engine
    ├── cli.py
    ├── db.py
    ├── ingest.py
    └── match.py
```
