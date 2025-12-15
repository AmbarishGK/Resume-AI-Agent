# Mini project report

## Problem
When tailoring a resume to a job description (JD), it’s easy to miss keywords, responsibilities, and domain cues that an ATS or recruiter expects. Doing this manually is slow and inconsistent.

## Goal
Build a reproducible pipeline that:

- collects job postings + full job descriptions
- stores JDs and resumes in a local database
- produces a transparent match score + gap list
- provides an interactive Streamlit "copilot" UI that can analyze/rewrite a resume for a specific JD

## System overview
The repo has three layers:

### 1) Data collection
- **Scraper**: `tools/jobscraper/main.py` (Playwright)
- **JD fetcher**: `tools/make_jds_from_jobs.py` (requests + BeautifulSoup)
- **Orchestrator**: `tools/workflow.py` runs scrape -> fetch -> ingest

### 2) Storage + ingestion
- SQLite DB: `marnow.db` (or `MARNOW_DB`)
- Ingestion utilities: `marnow/ingest.py`
- CLI: `marnow/cli.py`

### 3) Matching + copilot
- **Heuristic matcher**: `marnow/match.py`
  - computes component scores (skills overlap, responsibilities overlap, seniority/domain heuristics)
  - outputs missing skills (top gaps)
- **RAG + Copilot server**: `tools/rag_resume_server.py` (FastAPI + Chroma + Ollama)
- **Streamlit UI**: `tools/rag_resume_app.py`
  - upload resume PDF + paste JD text
  - check score, apply suggested changes, and export LaTeX/PDF

## How to run (recommended demo path)

### A) Pipeline demo (scrape -> fetch -> ingest)

```bash
python tools/workflow.py
```

Expected artifacts:
- `app/data/jobs/jobs.csv`
- `app/data/jds/*.txt`
- `marnow.db`

### B) Matching demo (resume -> match -> report)

```bash
python -m marnow.cli initdb
python -m marnow.cli seed-skills app/data/skills/skills.csv

python -m marnow.cli ingest-resume /path/to/your_resume.pdf
python tools/db_cli.py list-resumes --limit 10
python tools/db_cli.py list-jobs --limit 10
python -m marnow.cli match <resume_id> <job_id>
python -m marnow.cli report <match_id>
```

### C) Streamlit copilot demo (interactive)

See `Streamlit Copilot (RAG)` for the full steps.

## Limitations / notes
- Scraping is config-driven but career sites change often; selectors may need updates.
- The baseline match score is heuristic (intended to be transparent and fast).
- The RAG/copilot features depend on a local Ollama setup and model availability.

## Artifacts
- Code: `tools/`, `marnow/`, `app/config/`
- Data artifacts: `app/data/jobs/jobs.csv`, `app/data/jds/*.txt`
- DB artifact (generated): `marnow.db`
