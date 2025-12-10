# Resume-AI-Agent

A complete pipeline for scraping job postings, fetching job descriptions, and matching resumes to jobs using the MaRNoW (Matching Resumes to Jobs Now) system.

## Quick Start

### 1. Setup (UV-based virtual environment)

```bash
# Create venv and install dependencies
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m playwright install chromium

# Or use the quick setup script
./activate.sh
```

### 2. Run the Complete Workflow

```bash
# Activate venv (if not already active)
source .venv/bin/activate

# Run the automated workflow
python tools/workflow.py

# Or with custom options
python tools/workflow.py --all-jds --all-ingest --include "software,engineer"
```

## Features

- **Job Scraping**: Automated scraping of job postings from company career pages using Playwright
- **JD Fetching**: Automatic fetching of full job descriptions from job links
- **Resume Matching**: AI-powered matching of resumes to job descriptions with scoring
- **Workflow Automation**: Single-command workflow to scrape → fetch → ingest → match

## Project Structure

```
Resume-AI-Agent/
├── .venv/                      # UV virtual environment
├── app/
│   ├── config/
│   │   └── careers.yaml        # Company scraping configurations
│   └── data/
│       ├── jobs/
│       │   └── jobs.csv        # Scraped job postings
│       ├── jds/                # Fetched job descriptions
│       ├── resumes/            # Resume PDFs/DOCX
│       └── skills/
│           └── skills.csv       # Skills database
├── tools/
│   ├── jobscraper/
│   │   └── main.py             # Job scraper
│   ├── make_jds_from_jobs.py  # JD fetcher
│   └── workflow.py             # Automated workflow orchestrator
└── marnow/                     # Matching engine
    ├── cli.py                  # CLI interface
    ├── db.py                   # Database operations
    ├── ingest.py               # Data ingestion
    └── match.py                # Matching algorithms
```

## Usage

### Complete Workflow

```bash
python tools/workflow.py
```

This runs:
1. **Scrape Jobs** → `app/data/jobs/jobs.csv`
2. **Fetch JDs** → `app/data/jds/*.txt`
3. **Ingest** → `marnow.db` (SQLite)

### Manual Steps

#### Scrape Jobs
```bash
python tools/jobscraper/main.py --config app/config/careers.yaml
```

#### Fetch Job Descriptions
```bash
python tools/make_jds_from_jobs.py --all
```

#### Ingest into Database
```bash
python -m marnow.cli initdb
python -m marnow.cli ingest-jd app/data/jds/company-role.txt
```

#### Match Resume to Job
```bash
# Ingest resume
python -m marnow.cli ingest-resume app/data/resumes/resume.pdf

# Match resume (id=1) to job (id=2)
python -m marnow.cli match 1 2

# View match report
python -m marnow.cli report <match_id>
```

## Configuration

Edit `app/config/careers.yaml` to add or modify company career page configurations for scraping.

## Dependencies

All dependencies are managed via `requirements.txt`:
- Playwright (for web scraping)
- BeautifulSoup4 (for HTML parsing)
- PyYAML (for configuration)
- Typer (for CLI)
- pypdf, python-docx (for resume parsing)

See `requirements.txt` for complete list.

## Documentation

- **[SETUP.md](SETUP.md)** - Detailed setup instructions
- **[WORKFLOW.md](WORKFLOW.md)** - Workflow documentation
- **[FLOW_SUMMARY.md](FLOW_SUMMARY.md)** - Technical flow analysis

## Virtual Environment

This project uses **UV** for fast Python package management. The virtual environment is located at `.venv/`.

**Activate:**
```bash
source .venv/bin/activate
```

**Deactivate:**
```bash
deactivate
```

## Troubleshooting

### Playwright browser not found
```bash
python -m playwright install chromium
```

### Database path issues
Set environment variable for local development:
```bash
export MARNOW_DB=./marnow.db
```

### Permission errors
Make sure you're in the virtual environment:
```bash
which python  # Should show .venv/bin/python
```
